"""Application discovery, launch, close, and process verification."""

from __future__ import annotations

import json
import shutil
import subprocess
import time

from yuwontlaykit.knowledge.app_catalog import display_name, load_catalog, spec_for
from yuwontlaykit.tools.base import RiskLevel, ToolResult, failed, skipped, unavailable
from yuwontlaykit.tools.runner import as_list, run_argv
from yuwontlaykit.tools.windows import powershell_json, windows_tools_available

LOW = RiskLevel.LOW_RISK_MODIFICATION
READ = RiskLevel.READ_ONLY


def open_application(application: str = "") -> ToolResult:
    spec, app_id, missing = _require_spec(application, "open_application", LOW)
    if missing:
        return missing
    if windows_tools_available():
        return _open_windows(app_id, spec)
    return _open_posix(app_id, spec)


def close_application(application: str = "") -> ToolResult:
    spec, app_id, missing = _require_spec(application, "close_application", LOW)
    if missing:
        return missing
    if windows_tools_available():
        return _close_windows(app_id, spec)
    return _close_posix(app_id, spec)


def application_running(application: str = "") -> ToolResult:
    spec, app_id, missing = _require_spec(application, "application_running", READ)
    if missing:
        return missing
    if windows_tools_available():
        return _running_windows(app_id, spec)
    return _running_posix(app_id, spec)


def list_running_applications() -> ToolResult:
    if windows_tools_available():
        result = powershell_json(
            "list_running_applications",
            r"""
$ErrorActionPreference = 'SilentlyContinue'
$apps = @(Get-Process | Where-Object { $_.MainWindowTitle } |
  Select-Object -Property Name, Id, MainWindowTitle,
    @{N='CPU';E={$_.CPU}},
    @{N='WorkingSet';E={$_.WorkingSet64}} |
  Sort-Object WorkingSet -Descending)
if ($apps.Count -eq 0) { '[]' } else { $apps | ConvertTo-Json -Depth 4 -Compress }
""",
            timeout=20.0,
            risk=READ,
        )
        rows = as_list(result.data)
        result.data = rows
        result.extras["count"] = len(rows)
        if result.success:
            result.summary = f"{len(rows)} running application(s) with a window."
        return result
    code, out, err = run_argv(["ps", "-eo", "comm,pid"], timeout=8)
    if code != 0:
        return failed("list_running_applications", READ, err or "Could not list processes.")
    lines = [line.strip() for line in out.splitlines()[1:] if line.strip()]
    return ToolResult(
        name="list_running_applications",
        risk=READ,
        executed=True,
        available=True,
        success=True,
        data=[{"Name": line} for line in lines[:40]],
        summary=f"{min(len(lines), 40)} process name(s).",
        extras={"count": len(lines)},
    )


def _require_spec(
    application: str,
    tool_name: str,
    risk: RiskLevel,
) -> tuple[dict, str, ToolResult | None]:
    app_id = (application or "").strip().lower()
    spec = spec_for(app_id)
    if not spec:
        return {}, app_id, skipped(
            tool_name,
            risk,
            "That application is not on my approved list yet.",
        )
    return spec, app_id, None


def _open_windows(app_id: str, spec: dict) -> ToolResult:
    script = _windows_launch_script(spec)
    result = powershell_json("open_application", script, timeout=25.0, risk=LOW)
    return _interpret_app_result(result, app_id, action="start")


def _close_windows(app_id: str, spec: dict) -> ToolResult:
    script = _windows_close_script(spec)
    result = powershell_json("close_application", script, timeout=20.0, risk=LOW)
    return _interpret_app_result(result, app_id, action="close")


def _running_windows(app_id: str, spec: dict) -> ToolResult:
    names = _ps_json(list(spec.get("process_names") or []))
    script = f"""
$ErrorActionPreference = 'SilentlyContinue'
$names = @(ConvertFrom-Json '{names}') | Where-Object {{ $_ }}
$processes = @()
foreach ($name in $names) {{
  $processes += @(Get-Process -Name $name -ErrorAction SilentlyContinue)
}}
$unique = @($processes | Sort-Object Id -Unique)
[pscustomobject]@{{
  Installed = $true
  Running = [bool]($unique.Count -gt 0)
  ProcessIds = @($unique | ForEach-Object {{ $_.Id }})
}} | ConvertTo-Json -Depth 3 -Compress
"""
    result = powershell_json("application_running", script, timeout=15.0, risk=READ)
    data = result.data if isinstance(result.data, dict) else {}
    running = bool(data.get("Running"))
    result.extras.update(
        {
            "application": app_id,
            "display": display_name(app_id),
            "running": running,
        }
    )
    result.success = bool(result.available and result.executed)
    result.summary = (
        f"{display_name(app_id)} is running."
        if running
        else f"{display_name(app_id)} is not running."
    )
    return result


def _ps_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True).replace("'", "''")


def _windows_launch_script(spec: dict) -> str:
    paths = _ps_json(list(spec.get("windows_paths") or []))
    commands = _ps_json(list(spec.get("windows_commands") or []))
    processes = _ps_json(list(spec.get("process_names") or []))
    return f"""
$ErrorActionPreference = 'SilentlyContinue'
$paths = @((ConvertFrom-Json '{paths}') | ForEach-Object {{ [Environment]::ExpandEnvironmentVariables($_) }})
$commands = @(ConvertFrom-Json '{commands}')
$processNames = @(ConvertFrom-Json '{processes}')
$path = $null
foreach ($commandName in $commands) {{
  $found = Get-Command $commandName -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($found) {{ $path = $found.Source; break }}
}}
if (-not $path) {{
  $path = $paths | Where-Object {{ $_ -and (Test-Path $_) }} | Select-Object -First 1
}}
if (-not $path) {{
  [pscustomobject]@{{
    Installed = $false
    Started = $false
    Running = $false
    Path = $null
    ProcessIds = @()
    Error = $null
  }} | ConvertTo-Json -Depth 3 -Compress
  exit
}}
$launchError = $null
try {{
  Start-Process -FilePath $path -ErrorAction Stop | Out-Null
}} catch {{
  $launchError = $_.Exception.Message
}}
Start-Sleep -Seconds 2
$processes = @()
foreach ($name in $processNames) {{
  $processes += @(Get-Process -Name $name -ErrorAction SilentlyContinue)
}}
$unique = @($processes | Sort-Object Id -Unique)
[pscustomobject]@{{
  Installed = $true
  Started = [bool]($unique.Count -gt 0)
  Running = [bool]($unique.Count -gt 0)
  Path = $path
  ProcessIds = @($unique | ForEach-Object {{ $_.Id }})
  Error = $launchError
}} | ConvertTo-Json -Depth 3 -Compress
"""


def _windows_close_script(spec: dict) -> str:
    processes = _ps_json(list(spec.get("process_names") or []))
    return f"""
$ErrorActionPreference = 'SilentlyContinue'
$processNames = @(ConvertFrom-Json '{processes}')
$before = @()
foreach ($name in $processNames) {{
  $before += @(Get-Process -Name $name -ErrorAction SilentlyContinue)
}}
$uniqueBefore = @($before | Sort-Object Id -Unique)
if ($uniqueBefore.Count -eq 0) {{
  [pscustomobject]@{{
    Installed = $true
    Running = $false
    Closed = $false
    ProcessIds = @()
    Error = $null
  }} | ConvertTo-Json -Depth 3 -Compress
  exit
}}
foreach ($proc in $uniqueBefore) {{
  try {{ $proc.CloseMainWindow() | Out-Null }} catch {{ }}
}}
Start-Sleep -Seconds 1
$still = @()
foreach ($name in $processNames) {{
  $still += @(Get-Process -Name $name -ErrorAction SilentlyContinue)
}}
$uniqueStill = @($still | Sort-Object Id -Unique)
if ($uniqueStill.Count -gt 0) {{
  foreach ($proc in $uniqueStill) {{
    try {{ Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }} catch {{ }}
  }}
  Start-Sleep -Seconds 1
}}
$after = @()
foreach ($name in $processNames) {{
  $after += @(Get-Process -Name $name -ErrorAction SilentlyContinue)
}}
$uniqueAfter = @($after | Sort-Object Id -Unique)
[pscustomobject]@{{
  Installed = $true
  Running = [bool]($uniqueAfter.Count -gt 0)
  Closed = [bool]($uniqueAfter.Count -eq 0)
  ProcessIds = @($uniqueAfter | ForEach-Object {{ $_.Id }})
  Error = $null
}} | ConvertTo-Json -Depth 3 -Compress
"""


def _open_posix(app_id: str, spec: dict) -> ToolResult:
    commands = list(spec.get("posix_commands") or [])
    executable = next((shutil.which(name) for name in commands if shutil.which(name)), None)
    label = display_name(app_id)
    if not executable:
        return unavailable("open_application", LOW, f"{label} was not found on this PC.")
    try:
        subprocess.Popen(  # noqa: S603 - executable came from shutil.which
            [executable],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        return failed(
            "open_application",
            LOW,
            f"{label} is installed, but it could not be started: {exc}",
            data={"Installed": True, "Started": False},
        )
    time.sleep(2)
    running = _posix_running(spec)
    if not running:
        return failed(
            "open_application",
            LOW,
            f"{label} is installed, but its process was not found after launch.",
            data={"Installed": True, "Started": False, "Path": executable},
        )
    return ToolResult(
        name="open_application",
        risk=LOW,
        executed=True,
        available=True,
        success=True,
        data={"Installed": True, "Started": True, "Path": executable},
        summary=f"{label} started and its process was verified.",
        extras={
            "application": app_id,
            "display": label,
            "installed": True,
            "started": True,
        },
    )


def _close_posix(app_id: str, spec: dict) -> ToolResult:
    label = display_name(app_id)
    if not _posix_running(spec):
        return ToolResult(
            name="close_application",
            risk=LOW,
            executed=True,
            available=True,
            success=True,
            data={"Running": False, "Closed": False},
            summary=f"{label} was not running.",
            extras={
                "application": app_id,
                "display": label,
                "running": False,
                "closed": False,
            },
        )
    names = list(spec.get("posix_commands") or spec.get("process_names") or [])
    for name in names:
        run_argv(["pkill", "-x", name], timeout=5)
    time.sleep(1)
    still = _posix_running(spec)
    return ToolResult(
        name="close_application",
        risk=LOW,
        executed=True,
        available=True,
        success=not still,
        data={"Running": still, "Closed": not still},
        summary=(
            f"{label} is closed."
            if not still
            else f"{label} is still running."
        ),
        extras={
            "application": app_id,
            "display": label,
            "running": still,
            "closed": not still,
        },
    )


def _running_posix(app_id: str, spec: dict) -> ToolResult:
    running = _posix_running(spec)
    label = display_name(app_id)
    return ToolResult(
        name="application_running",
        risk=READ,
        executed=True,
        available=True,
        success=True,
        data={"Running": running},
        summary=f"{label} is running." if running else f"{label} is not running.",
        extras={
            "application": app_id,
            "display": label,
            "running": running,
        },
    )


def _posix_running(spec: dict) -> bool:
    names = list(spec.get("posix_commands") or []) + list(spec.get("process_names") or [])
    for name in names:
        if not name:
            continue
        code, out, _ = run_argv(["pgrep", "-x", name], timeout=5)
        if code == 0 and out.strip():
            return True
    return False


def _interpret_app_result(result: ToolResult, app_id: str, action: str) -> ToolResult:
    data = result.data if isinstance(result.data, dict) else {}
    installed = bool(data.get("Installed", True))
    started = bool(data.get("Started"))
    running = bool(data.get("Running", started))
    closed = bool(data.get("Closed"))
    label = display_name(app_id)
    result.extras.update(
        {
            "application": app_id,
            "display": label,
            "installed": installed,
            "started": started,
            "running": running,
            "closed": closed,
        }
    )
    if not result.available or not result.executed:
        return result
    if action == "start":
        if not installed:
            result.success = False
            result.summary = f"{label} was not found on this PC."
            return result
        if not started:
            result.success = False
            detail = data.get("Error")
            result.summary = (
                f"{label} is installed, but it could not be started"
                + (f": {detail}" if detail else ".")
            )
            return result
        result.success = True
        result.summary = f"{label} started and its process was verified."
        return result
    if not running and not closed and action == "close":
        result.success = True
        result.summary = f"{label} was not running."
        return result
    if action == "close":
        result.success = closed
        result.summary = f"{label} is closed." if closed else f"{label} is still running."
    return result


def catalog_ids() -> list[str]:
    return sorted(load_catalog())
