"""Windows service inspection."""

from __future__ import annotations

from yuwontlaykit.tools.base import RiskLevel, ToolResult, unavailable
from yuwontlaykit.tools.runner import as_list
from yuwontlaykit.tools.windows import powershell_json, windows_tools_available

RISK = RiskLevel.READ_ONLY

WATCHED = (
    "Spooler",
    "stisvc",
    "WlanSvc",
    "Dhcp",
    "Dnscache",
    "Audiosrv",
    "AudioEndpointBuilder",
    "bthserv",
    "BTAGService",
    "wuauserv",
    "BITS",
    "WinDefend",
    "mpssvc",
)


def get_windows_services(names: tuple[str, ...] | None = None) -> ToolResult:
    if not windows_tools_available():
        return unavailable(
            "get_windows_services",
            RISK,
            "I cannot inspect Windows services without PowerShell.",
        )
    wanted = names or WATCHED
    quoted = ",".join(f"'{n}'" for n in wanted)
    result = powershell_json(
        "get_windows_services",
        f"""
Get-Service -Name {quoted} -ErrorAction SilentlyContinue |
  Select-Object Name, Status, StartType, DisplayName | ConvertTo-Json -Depth 3
""",
    )
    rows = as_list(result.data)
    result.data = rows
    bits = [
        f"{r.get('Name')}: {r.get('Status')}"
        for r in rows
        if isinstance(r, dict)
    ]
    result.summary = "; ".join(bits) if bits else "No watched Windows services were returned."
    return result
