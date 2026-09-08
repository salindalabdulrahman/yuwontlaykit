"""Event log inspection — last errors only, read-only."""

from __future__ import annotations

from yuwontlaykit.tools.base import RiskLevel, unavailable
from yuwontlaykit.tools.runner import as_list
from yuwontlaykit.tools.windows import powershell_json, windows_tools_available

RISK = RiskLevel.READ_ONLY


def get_event_logs(log_name: str = "System", newest: int = 8) -> ToolResult:
    if not windows_tools_available():
        return unavailable(
            "get_event_logs",
            RISK,
            "I cannot read Windows event logs without PowerShell.",
        )
    newest = max(1, min(int(newest), 20))
    safe_log = "System" if log_name not in ("System", "Application", "Microsoft-Windows-PrintService/Admin") else log_name
    result = powershell_json(
        "get_event_logs",
        f"""
try {{
  Get-WinEvent -FilterHashtable @{{ LogName = '{safe_log}'; Level = 2 }} -MaxEvents {newest} -ErrorAction Stop |
    Select-Object TimeCreated, Id, ProviderName, LevelDisplayName,
      @{{n='Message';e={{ $_.Message.Substring(0, [Math]::Min(180, $_.Message.Length)) }}}} |
    ConvertTo-Json -Depth 3
}} catch {{
  [pscustomobject]@{{ Error = $_.Exception.Message; Events = @() }} | ConvertTo-Json
}}
""",
        timeout=35.0,
    )
    if isinstance(result.data, dict) and "Error" in result.data and "Events" in result.data:
        result.summary = f"Could not read {safe_log}: {result.data.get('Error')}"
        result.success = False
        result.error = str(result.data.get("Error"))
        return result
    rows = as_list(result.data)
    result.data = rows
    result.summary = f"{len(rows)} recent error event(s) from {safe_log}"
    return result
