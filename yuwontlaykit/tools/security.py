"""Defensive security inspection — never offensive."""

from __future__ import annotations

from yuwontlaykit.tools.base import RiskLevel, unavailable
from yuwontlaykit.tools.runner import as_list
from yuwontlaykit.tools.windows import powershell_json, windows_tools_available

RISK = RiskLevel.READ_ONLY


def get_security_overview() -> ToolResult:
    if not windows_tools_available():
        return unavailable(
            "get_security_overview",
            RISK,
            "I cannot read Windows security status without PowerShell.",
        )
    result = powershell_json(
        "get_security_overview",
        r"""
$defender = $null
try {
  $defender = Get-MpComputerStatus | Select-Object AMServiceEnabled, AntispywareEnabled, RealTimeProtectionEnabled,
    NISEnabled, FullScanAge, QuickScanAge, AntivirusEnabled
} catch { $defender = @{ Error = $_.Exception.Message } }
$fw = $null
try {
  $fw = Get-NetFirewallProfile | Select-Object Name, Enabled
} catch { $fw = @() }
[pscustomobject]@{ Defender = $defender; Firewall = @($fw) } | ConvertTo-Json -Depth 5
""",
        timeout=30.0,
    )
    data = result.data if isinstance(result.data, dict) else {}
    defender = data.get("Defender") or {}
    firewall = as_list(data.get("Firewall"))
    result.data = {"defender": defender, "firewall": firewall}
    if isinstance(defender, dict) and defender.get("Error"):
        result.summary = "Could not read Microsoft Defender status (permission or feature missing)."
        return result
    rtp = defender.get("RealTimeProtectionEnabled")
    av = defender.get("AntivirusEnabled")
    fw_off = [
        str(p.get("Name"))
        for p in firewall
        if isinstance(p, dict) and p.get("Enabled") in (False, "False", "false")
    ]
    bits = []
    if av is True or str(av).lower() == "true":
        bits.append("antivirus on")
    elif av is False:
        bits.append("antivirus off")
    if rtp is True or str(rtp).lower() == "true":
        bits.append("real-time protection on")
    elif rtp is False:
        bits.append("real-time protection off")
    if fw_off:
        bits.append("firewall off for: " + ", ".join(fw_off))
    result.summary = "; ".join(bits) if bits else "Security status collected."
    result.extras["realtime_off"] = rtp in (False, "False", "false")
    result.extras["firewall_off"] = fw_off
    return result
