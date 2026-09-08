"""Power actions: shutdown, restart, lock, sleep, and sign out."""

from __future__ import annotations

from yuwontlaykit.tools.base import RiskLevel, ToolResult, failed, unavailable
from yuwontlaykit.tools.windows import powershell_json, windows_tools_available

HIGH = RiskLevel.HIGH_RISK_MODIFICATION
LOW = RiskLevel.LOW_RISK_MODIFICATION


def shutdown_computer() -> ToolResult:
    return _run_power(
        "shutdown_computer",
        HIGH,
        "Stop-Computer -Force",
        "I'm shutting down the PC now.",
    )


def restart_computer() -> ToolResult:
    return _run_power(
        "restart_computer",
        HIGH,
        "Restart-Computer -Force",
        "I'm restarting the PC now.",
    )


def lock_computer() -> ToolResult:
    return _run_power(
        "lock_computer",
        LOW,
        "rundll32.exe user32.dll,LockWorkStation",
        "The PC is locked.",
        expect_json=False,
    )


def sleep_computer() -> ToolResult:
    return _run_power(
        "sleep_computer",
        HIGH,
        "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
        "The PC is going to sleep.",
        expect_json=False,
    )


def logout_user() -> ToolResult:
    return _run_power(
        "logout_user",
        HIGH,
        "shutdown.exe /l",
        "Signing out now.",
        expect_json=False,
    )


def _run_power(
    name: str,
    risk: RiskLevel,
    command: str,
    success_summary: str,
    *,
    expect_json: bool = True,
) -> ToolResult:
    if not windows_tools_available():
        return unavailable(
            name,
            risk,
            "I can only do that from a Windows session I can reach.",
        )
    if expect_json:
        result = powershell_json(
            name,
            f"""
$ErrorActionPreference = 'Stop'
try {{
  {command}
  [pscustomobject]@{{ Started = $true; Error = $null }} | ConvertTo-Json -Compress
}} catch {{
  [pscustomobject]@{{ Started = $false; Error = $_.Exception.Message }} | ConvertTo-Json -Compress
}}
""",
            timeout=20.0,
            risk=risk,
        )
        data = result.data if isinstance(result.data, dict) else {}
        started = bool(data.get("Started"))
        result.extras["started"] = started
        if started:
            result.success = True
            result.summary = success_summary
        else:
            result.success = False
            result.summary = str(data.get("Error") or "I could not start that power action.")
        return result

    result = powershell_json(
        name,
        f"""
$ErrorActionPreference = 'Stop'
try {{
  {command} | Out-Null
  [pscustomobject]@{{ Started = $true; Error = $null }} | ConvertTo-Json -Compress
}} catch {{
  [pscustomobject]@{{ Started = $false; Error = $_.Exception.Message }} | ConvertTo-Json -Compress
}}
""",
        timeout=20.0,
        risk=risk,
    )
    if not result.available:
        return result
    data = result.data if isinstance(result.data, dict) else {}
    # Lock/sleep may succeed even if JSON is empty because the session is leaving.
    started = bool(data.get("Started")) or (result.executed and not data.get("Error"))
    if not started and result.error:
        return failed(name, risk, result.error)
    result.success = True
    result.summary = success_summary
    result.extras["started"] = True
    return result
