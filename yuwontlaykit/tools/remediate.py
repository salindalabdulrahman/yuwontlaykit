"""Low-risk remediations — never run unless the registry is called with confirmed=True."""

from __future__ import annotations

from yuwontlaykit.tools.base import RiskLevel, ToolResult, failed, ok, skipped, unavailable
from yuwontlaykit.tools.validate import is_safe_printer_name
from yuwontlaykit.tools.windows import powershell_json, windows_tools_available

LOW = RiskLevel.LOW_RISK_MODIFICATION


def _need_windows(name: str) -> ToolResult | None:
    if windows_tools_available():
        return None
    return unavailable(
        name,
        LOW,
        "I wasn't able to make the change because Windows PowerShell is not available here.",
    )


def restart_print_spooler() -> ToolResult:
    blocked = _need_windows("restart_print_spooler")
    if blocked:
        return blocked
    result = powershell_json(
        "restart_print_spooler",
        r"""
try {
  Restart-Service -Name Spooler -Force -ErrorAction Stop
  $svc = Get-Service Spooler | Select-Object Name, Status, StartType
  [pscustomobject]@{ Ok = $true; Service = $svc; Error = $null } | ConvertTo-Json -Depth 3
} catch {
  [pscustomobject]@{ Ok = $false; Service = $null; Error = $_.Exception.Message } | ConvertTo-Json
}
""",
        timeout=40.0,
        risk=LOW,
    )
    data = result.data if isinstance(result.data, dict) else {}
    if data.get("Ok"):
        status = (data.get("Service") or {}).get("Status")
        result.success = True
        result.summary = f"Print Spooler restart finished; status is now {status}."
        return result
    err = data.get("Error") or result.error or "Windows refused the spooler restart."
    return failed(
        "restart_print_spooler",
        LOW,
        f"I wasn't able to restart the printing system: {err} "
        "(this often needs administrator permission).",
        raw=result.raw,
        data=data,
    )


def clear_print_queue() -> ToolResult:
    blocked = _need_windows("clear_print_queue")
    if blocked:
        return blocked
    result = powershell_json(
        "clear_print_queue",
        r"""
try {
  $removed = 0
  Get-Printer | ForEach-Object {
    Get-PrintJob -PrinterName $_.Name -ErrorAction SilentlyContinue | ForEach-Object {
      Remove-PrintJob -InputObject $_ -ErrorAction SilentlyContinue
      $removed++
    }
  }
  [pscustomobject]@{ Ok = $true; Removed = $removed; Error = $null } | ConvertTo-Json
} catch {
  [pscustomobject]@{ Ok = $false; Removed = 0; Error = $_.Exception.Message } | ConvertTo-Json
}
""",
        timeout=40.0,
        risk=LOW,
    )
    data = result.data if isinstance(result.data, dict) else {}
    if data.get("Ok"):
        removed = data.get("Removed") or 0
        result.success = True
        result.summary = f"Cleared {removed} print job(s) from the queue."
        result.extras["removed"] = removed
        return result
    err = data.get("Error") or result.error or "Windows refused to clear the queue."
    return failed(
        "clear_print_queue",
        LOW,
        f"I wasn't able to clear the print queue: {err} "
        "(administrator permission may be required).",
        raw=result.raw,
        data=data,
    )


def set_printers_online() -> ToolResult:
    blocked = _need_windows("set_printers_online")
    if blocked:
        return blocked
    result = powershell_json(
        "set_printers_online",
        r"""
$changed = @()
Get-Printer | ForEach-Object {
  try {
    Set-Printer -Name $_.Name -WorkOffline $false -ErrorAction Stop
    $changed += $_.Name
  } catch {}
}
$printers = Get-Printer | Select-Object Name, PrinterStatus, WorkOffline
[pscustomobject]@{ Changed = @($changed); Printers = @($printers) } | ConvertTo-Json -Depth 4
""",
        timeout=35.0,
        risk=LOW,
    )
    data = result.data if isinstance(result.data, dict) else {}
    changed = data.get("Changed") or []
    if isinstance(changed, str):
        changed = [changed]
    result.summary = (
        "Asked Windows to bring printers online"
        + (f" ({len(changed)} updated)" if changed else "")
        + "."
    )
    result.success = result.executed and result.data is not None
    return result


def flush_dns() -> ToolResult:
    blocked = _need_windows("flush_dns")
    if blocked:
        return blocked
    from yuwontlaykit.tools.windows import powershell_exe
    from yuwontlaykit.tools.runner import run_argv

    exe = powershell_exe()
    code, out, err = run_argv(
        [exe, "-NoProfile", "-NonInteractive", "-Command", "Clear-DnsClientCache; 'flushed'"],
        timeout=20.0,
    )
    if code != 0:
        return failed(
            "flush_dns",
            LOW,
            "I wasn't able to refresh Windows' website-name cache"
            + (f": {err or out}" if (err or out) else ".")
            + " Administrator permission may be required.",
            raw=out or err,
        )
    return ok("flush_dns", LOW, "Refreshed Windows' website-name cache.", raw=out)


def remove_printer(printer_name: str = "") -> ToolResult:
    blocked = _need_windows("remove_printer")
    if blocked:
        return blocked
    printer = (printer_name or "").strip()
    if not is_safe_printer_name(printer):
        return skipped(
            "remove_printer",
            LOW,
            "That printer name isn't safe for me to use, so I didn't remove anything.",
        )
    escaped = printer.replace("'", "''")
    result = powershell_json(
        "remove_printer",
        f"""
$ErrorActionPreference = 'Stop'
try {{
  $target = '{escaped}'
  Remove-Printer -Name $target
  $still = Get-Printer -Name $target -ErrorAction SilentlyContinue
  [pscustomobject]@{{ Ok = -not [bool]$still; Name = $target; Error = $null }} | ConvertTo-Json -Compress
}} catch {{
  [pscustomobject]@{{ Ok = $false; Name = '{escaped}'; Error = $_.Exception.Message }} | ConvertTo-Json -Compress
}}
""",
        timeout=40.0,
        risk=LOW,
    )
    data = result.data if isinstance(result.data, dict) else {}
    if data.get("Ok"):
        result.success = True
        result.summary = f"Removed {printer} from this PC."
        result.extras["name"] = printer
        return result
    err = data.get("Error") or result.error or "Windows refused to remove the printer."
    return failed(
        "remove_printer",
        LOW,
        f"I wasn't able to remove {printer}: {err} "
        "(this often needs administrator permission).",
        raw=result.raw,
        data=data,
    )
