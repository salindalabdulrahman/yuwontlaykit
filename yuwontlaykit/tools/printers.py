"""Read-only printer tools."""

from __future__ import annotations

from yuwontlaykit.tools.base import RiskLevel, ToolResult, ok, unavailable
from yuwontlaykit.tools.runner import as_list
from yuwontlaykit.tools.windows import powershell_json, windows_tools_available

RISK = RiskLevel.READ_ONLY


def get_printers() -> ToolResult:
    if not windows_tools_available():
        return unavailable(
            "get_printers",
            RISK,
            "I cannot list Windows printers from here (PowerShell is missing).",
        )
    result = powershell_json(
        "get_printers",
        r"""
Get-Printer | Select-Object Name, DriverName, PortName, PrinterStatus, Type,
  Published, Shared, WorkOffline, Default, Location, Comment, DeviceType |
  ConvertTo-Json -Depth 3
""",
    )
    rows = as_list(result.data)
    result.data = rows
    if not rows:
        result.summary = "Windows did not report any installed printers."
        return result
    names = [str(r.get("Name")) for r in rows if isinstance(r, dict)]
    result.summary = f"{len(names)} printer(s): " + ", ".join(names[:8])
    return result


def get_default_printer() -> ToolResult:
    if not windows_tools_available():
        return unavailable(
            "get_default_printer",
            RISK,
            "I cannot read the default printer without Windows PowerShell.",
        )
    result = powershell_json(
        "get_default_printer",
        r"""
$ErrorActionPreference = 'SilentlyContinue'
$cim = @(Get-CimInstance Win32_Printer | Where-Object { $_.Default -eq $true } | Select-Object Name)
$gp = @(Get-Printer | Where-Object { $_.Default -eq $true } | Select-Object Name)
[pscustomobject]@{ Cim = @($cim); GetPrinter = @($gp) } | ConvertTo-Json -Depth 4 -Compress
""",
    )
    data = result.data if isinstance(result.data, dict) else {}
    names = []
    for key in ("Cim", "GetPrinter"):
        for row in as_list(data.get(key)):
            if isinstance(row, dict) and row.get("Name"):
                names.append(str(row.get("Name")))
    if not names:
        printers = get_printers()
        if printers.success:
            for row in printers.data or []:
                if isinstance(row, dict) and (row.get("Default") is True or str(row.get("Default")).lower() == "true"):
                    names.append(str(row.get("Name")))
                    break
    if not names:
        return ok(
            "get_default_printer",
            RISK,
            "Windows didn't report a default printer.",
            data=None,
            raw=result.raw,
        )
    name = names[0]
    return ok(
        "get_default_printer",
        RISK,
        f"Default printer is {name}.",
        data={"Name": name, "Default": True},
        raw=result.raw,
    )


def get_printer_status() -> ToolResult:
    printers = get_printers()
    printers.name = "get_printer_status"
    if printers.success and printers.data:
        bits = []
        for row in printers.data:
            if not isinstance(row, dict):
                continue
            name = row.get("Name") or "?"
            status = row.get("PrinterStatus") or "unknown"
            offline = row.get("WorkOffline")
            extra = " (set offline in Windows)" if offline in (True, "True", "true") else ""
            bits.append(f"{name}: {status}{extra}")
        printers.summary = "; ".join(bits) if bits else printers.summary
    return printers


def get_printer_port() -> ToolResult:
    if not windows_tools_available():
        return unavailable(
            "get_printer_port",
            RISK,
            "I cannot read printer ports without Windows PowerShell.",
        )
    result = powershell_json(
        "get_printer_port",
        r"""
$ports = Get-PrinterPort | Select-Object Name, Description, PrinterHostAddress, PortNumber
$printers = Get-Printer | Select-Object Name, PortName
[pscustomobject]@{ Ports = @($ports); Printers = @($printers) } | ConvertTo-Json -Depth 5
""",
    )
    data = result.data if isinstance(result.data, dict) else {}
    ports = as_list(data.get("Ports"))
    printers = as_list(data.get("Printers"))
    result.data = {"ports": ports, "printers": printers}
    addresses = [
        str(p.get("PrinterHostAddress"))
        for p in ports
        if isinstance(p, dict) and p.get("PrinterHostAddress")
    ]
    result.summary = (
        f"{len(ports)} port(s)"
        + ("; IPs: " + ", ".join(addresses[:6]) if addresses else "; no printer IP addresses reported")
    )
    return result


def get_printer_driver() -> ToolResult:
    if not windows_tools_available():
        return unavailable(
            "get_printer_driver",
            RISK,
            "I cannot list printer drivers without Windows PowerShell.",
        )
    result = powershell_json(
        "get_printer_driver",
        r"""
$drivers = Get-PrinterDriver | Select-Object Name, Manufacturer, MajorVersion, PrinterEnvironment
$printers = Get-Printer | Select-Object Name, DriverName
[pscustomobject]@{ Drivers = @($drivers); Printers = @($printers) } | ConvertTo-Json -Depth 5
""",
    )
    data = result.data if isinstance(result.data, dict) else {}
    drivers = as_list(data.get("Drivers"))
    printers = as_list(data.get("Printers"))
    result.data = {"drivers": drivers, "printers": printers}
    names = [str(d.get("Name")) for d in drivers if isinstance(d, dict) and d.get("Name")]
    result.summary = f"{len(names)} driver(s): " + ", ".join(names[:6]) if names else "No printer drivers reported."
    return result


def get_print_queue() -> ToolResult:
    if not windows_tools_available():
        return unavailable(
            "get_print_queue",
            RISK,
            "I cannot read the Windows print queue without PowerShell.",
        )
    result = powershell_json(
        "get_print_queue",
        r"""
Get-Printer | ForEach-Object {
  $jobs = @()
  try { $jobs = @(Get-PrintJob -PrinterName $_.Name -ErrorAction Stop) } catch { $jobs = @() }
  [pscustomobject]@{
    Printer = $_.Name
    JobCount = $jobs.Count
    Jobs = @($jobs | Select-Object Id, JobStatus, DocumentName, UserName, Size, SubmittedTime)
  }
} | ConvertTo-Json -Depth 6
""",
        timeout=30.0,
    )
    rows = as_list(result.data)
    result.data = rows
    total = 0
    stuck = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        total += int(row.get("JobCount") or 0)
        for job in as_list(row.get("Jobs")):
            if not isinstance(job, dict):
                continue
            status = str(job.get("JobStatus") or "").lower()
            if any(token in status for token in ("error", "stuck", "paused", "deleting", "blocked")):
                stuck += 1
    result.summary = f"{total} queued job(s)" + (f", {stuck} look stuck/failed" if stuck else "")
    result.extras["job_count"] = total
    result.extras["stuck_count"] = stuck
    return result


def check_print_spooler() -> ToolResult:
    if not windows_tools_available():
        return unavailable(
            "check_print_spooler",
            RISK,
            "I cannot check the Windows Print Spooler without PowerShell.",
        )
    result = powershell_json(
        "check_print_spooler",
        r"""
Get-Service Spooler | Select-Object Name, Status, StartType, DisplayName | ConvertTo-Json
""",
    )
    data = result.data if isinstance(result.data, dict) else {}
    status = str(data.get("Status") or "unknown")
    result.summary = f"Print Spooler is {status}"
    result.extras["status"] = status
    result.extras["running"] = status.lower() == "running"
    return result
