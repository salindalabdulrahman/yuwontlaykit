"""Read-only system information tools."""

from __future__ import annotations

import platform
import shutil

from yuwontlaykit.tools.base import RiskLevel, ToolResult, failed, ok, unavailable
from yuwontlaykit.tools.runner import as_list, run_argv
from yuwontlaykit.tools.windows import powershell_json, windows_tools_available

RISK = RiskLevel.READ_ONLY


def get_system_information() -> ToolResult:
    posix = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "node": platform.node(),
        "uptime_seconds": _posix_uptime(),
    }

    if windows_tools_available():
        result = powershell_json(
            "get_system_information",
            r"""
$os = Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, OSArchitecture, LastBootUpTime, CSName, TotalVisibleMemorySize, FreePhysicalMemory
$cs = Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model, TotalPhysicalMemory, NumberOfLogicalProcessors
$cpu = Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, LoadPercentage
[pscustomobject]@{
  OS = $os
  Computer = $cs
  CPU = $cpu
} | ConvertTo-Json -Depth 5
""",
            timeout=30.0,
        )
        if result.success and isinstance(result.data, dict):
            osinfo = result.data.get("OS") or {}
            cs = result.data.get("Computer") or {}
            cpu = result.data.get("CPU")
            if isinstance(cpu, list):
                cpu0 = cpu[0] if cpu else {}
            else:
                cpu0 = cpu or {}
            boot = osinfo.get("LastBootUpTime")
            result.data["posix"] = posix
            caption = osinfo.get("Caption") or posix["system"]
            build = osinfo.get("BuildNumber") or posix["release"]
            arch = osinfo.get("OSArchitecture") or posix["machine"]
            ram_gb = _bytes_to_gb(cs.get("TotalPhysicalMemory"))
            cpu_name = cpu0.get("Name") or posix["processor"] or "CPU"
            result.summary = (
                f"{caption} (build {build}, {arch}); "
                f"CPU {str(cpu_name).strip()}; RAM {ram_gb}"
            )
            result.extras["boot"] = boot
            return result
        # Fall through to POSIX if Windows query failed

    summary = f"{posix['system']} {posix['release']} ({posix['machine']})"
    if posix["uptime_seconds"] is not None:
        hours = int(posix["uptime_seconds"] // 3600)
        summary += f"; up about {hours} hour(s)"
    return ok("get_system_information", RISK, summary, data={"posix": posix})


def _bytes_to_gb(value) -> str:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return "unknown"
    gb = n / (1024 ** 3)
    return f"{gb:.1f} GB"


def _posix_uptime() -> float | None:
    try:
        with open("/proc/uptime", encoding="utf-8") as fh:
            return float(fh.read().split()[0])
    except (OSError, ValueError, IndexError):
        if shutil.which("uptime"):
            code, out, _ = run_argv(["uptime", "-p"], timeout=5.0)
            if code == 0:
                return None
        return None


def get_running_processes(limit: int = 8) -> ToolResult:
    limit = max(1, min(int(limit), 25))
    if windows_tools_available():
        result = powershell_json(
            "get_running_processes",
            f"""
Get-Process | Sort-Object -Property CPU -Descending |
  Select-Object -First {limit} Name, Id, CPU, WorkingSet, StartTime |
  ConvertTo-Json -Depth 3
""",
            timeout=25.0,
        )
        rows = as_list(result.data)
        if result.executed:
            names = [str(r.get("Name")) for r in rows if isinstance(r, dict) and r.get("Name")]
            result.data = rows
            result.summary = (
                "Top processes: " + ", ".join(names[:limit])
                if names
                else "No process list returned."
            )
            return result

    if shutil.which("ps"):
        code, out, err = run_argv(["ps", "aux", "--sort=-pcpu"], timeout=8.0)
        if code != 0:
            return failed("get_running_processes", RISK, err or "ps failed", raw=out)
        lines = [ln for ln in out.splitlines() if ln.strip()]
        body = lines[: limit + 1]
        return ok(
            "get_running_processes",
            RISK,
            f"Listed {max(0, len(body) - 1)} process row(s).",
            data={"lines": body},
            raw="\n".join(body),
        )
    return unavailable("get_running_processes", RISK, "No process listing tool is available.")


def get_startup_applications() -> ToolResult:
    if not windows_tools_available():
        return unavailable(
            "get_startup_applications",
            RISK,
            "I can only list Windows startup apps when PowerShell is available.",
        )
    result = powershell_json(
        "get_startup_applications",
        r"""
Get-CimInstance Win32_StartupCommand | Select-Object Name, Command, Location, User |
  ConvertTo-Json -Depth 3
""",
        timeout=25.0,
    )
    rows = as_list(result.data)
    result.data = rows
    names = [str(r.get("Name")) for r in rows if isinstance(r, dict) and r.get("Name")]
    result.summary = (
        f"{len(names)} startup item(s): " + ", ".join(names[:8])
        if names
        else "No startup applications were reported."
    )
    return result
