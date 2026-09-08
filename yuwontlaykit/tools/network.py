"""Read-only network, Wi-Fi, DNS, and connectivity tools."""

from __future__ import annotations

from yuwontlaykit.tools.base import RiskLevel, ToolResult, ok, skipped, unavailable
from yuwontlaykit.tools.runner import as_list
from yuwontlaykit.tools.validate import is_safe_host, require_safe_host
from yuwontlaykit.tools.windows import powershell_json, run_powershell, windows_tools_available

RISK = RiskLevel.READ_ONLY


def get_network_information() -> ToolResult:
    if not windows_tools_available():
        return unavailable(
            "get_network_information",
            RISK,
            "I cannot read Windows network settings without PowerShell.",
        )
    # Get-NetIPConfiguration is noisy (missing IPv6 routes) and can fail
    # to serialize. Adapter + IPv4 address + default route is enough.
    result = powershell_json(
        "get_network_information",
        r"""
$ErrorActionPreference = 'SilentlyContinue'
$adapters = @(Get-NetAdapter | Select-Object Name, Status, MacAddress, LinkSpeed, InterfaceDescription)
$ip = @(Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias, IPAddress, PrefixLength)
$gw = @(Get-NetRoute -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' | Select-Object InterfaceAlias, NextHop, RouteMetric)
[pscustomobject]@{ Adapters = $adapters; IP = $ip; Gateways = $gw } | ConvertTo-Json -Depth 6 -Compress
""",
        timeout=30.0,
    )
    data = result.data if isinstance(result.data, dict) else {}
    adapters = as_list(data.get("Adapters") or data.get("adapters"))
    ip_rows = as_list(data.get("IP") or data.get("ip"))
    gateways = as_list(data.get("Gateways") or data.get("gateways"))
    gw_by_alias: dict[str, str] = {}
    for row in gateways:
        if not isinstance(row, dict):
            continue
        alias = str(row.get("InterfaceAlias") or "").strip()
        hop = str(row.get("NextHop") or "").strip()
        if alias and hop:
            gw_by_alias[alias] = hop
    ip = []
    for row in ip_rows:
        if not isinstance(row, dict):
            continue
        alias = str(row.get("InterfaceAlias") or row.get("Name") or "").strip()
        ipv4 = row.get("IPv4") or row.get("IPAddress") or ""
        if isinstance(ipv4, list):
            ipv4 = ",".join(str(part) for part in ipv4 if part)
        gw = str(row.get("Gateway") or gw_by_alias.get(alias) or "").strip()
        ip.append(
            {
                "InterfaceAlias": alias,
                "IPv4": str(ipv4).strip(),
                "Gateway": gw,
                "DNS": str(row.get("DNS") or ""),
            }
        )
    result.data = {"adapters": adapters, "ip": ip}
    up = [
        str(a.get("Name"))
        for a in adapters
        if isinstance(a, dict) and str(a.get("Status") or "").lower() == "up"
    ]
    result.summary = (
        f"{len(adapters)} adapter(s), {len(up)} up"
        + (f" ({', '.join(up[:4])})" if up else "")
    )
    return result


def get_wifi_information() -> ToolResult:
    if not windows_tools_available():
        return unavailable(
            "get_wifi_information",
            RISK,
            "I cannot read Wi-Fi details without Windows PowerShell.",
        )
    result = powershell_json(
        "get_wifi_information",
        r"""
$wlan = Get-NetAdapter | Where-Object { $_.InterfaceDescription -match 'Wireless|Wi-?Fi|802\.11' -or $_.Name -match 'Wi-?Fi|Wireless' } |
  Select-Object Name, Status, InterfaceDescription, LinkSpeed, MediaConnectionState
$profiles = @()
try {
  $profiles = Get-NetConnectionProfile | Select-Object Name, InterfaceAlias, NetworkCategory, IPv4Connectivity, IPv6Connectivity
} catch {}
[pscustomobject]@{ WlanAdapters = @($wlan); Profiles = @($profiles) } | ConvertTo-Json -Depth 5
""",
        timeout=25.0,
    )
    data = result.data if isinstance(result.data, dict) else {}
    adapters = as_list(data.get("WlanAdapters"))
    profiles = as_list(data.get("Profiles"))

    ssid = None
    state = None
    signal = None
    receive_rate = None
    transmit_rate = None
    code, out, err = run_powershell("netsh wlan show interfaces", timeout=15.0)
    netsh = out or err
    if code == 0 and netsh:
        for line in netsh.splitlines():
            stripped = line.strip()
            lower = stripped.lower()
            if lower.startswith("ssid") and "bssid" not in lower:
                ssid = stripped.split(":", 1)[-1].strip() or ssid
            if lower.startswith("state"):
                state = stripped.split(":", 1)[-1].strip() or state
            if lower.startswith("signal"):
                signal = stripped.split(":", 1)[-1].strip() or signal
            if lower.startswith("receive rate"):
                receive_rate = stripped.split(":", 1)[-1].strip() or receive_rate
            if lower.startswith("transmit rate"):
                transmit_rate = stripped.split(":", 1)[-1].strip() or transmit_rate

    link_speed = None
    interface_name = None
    for adapter in adapters:
        if not isinstance(adapter, dict):
            continue
        interface_name = str(adapter.get("Name") or "").strip() or interface_name
        link_speed = str(adapter.get("LinkSpeed") or "").strip() or link_speed
        if str(adapter.get("Status") or "").lower() == "up":
            break

    result.data = {
        "adapters": adapters,
        "profiles": profiles,
        "ssid": ssid,
        "wlan_state": state,
        "signal": signal,
        "receive_rate_mbps": receive_rate,
        "transmit_rate_mbps": transmit_rate,
        "link_speed": link_speed,
        "interface_name": interface_name,
        "netsh": netsh[-2000:] if netsh else "",
    }
    connected = bool(ssid) and (state or "").lower() in ("connected", "")
    if adapters and all(str(a.get("Status") or "").lower() != "up" for a in adapters if isinstance(a, dict)):
        result.summary = "Wi-Fi adapter is not connected."
    elif ssid:
        result.summary = f"Wi-Fi network: {ssid}" + (f" ({state})" if state else "")
    elif adapters:
        result.summary = "A Wi-Fi adapter is present, but no network name was reported."
    else:
        result.summary = "No Wi-Fi adapter was reported."
    result.extras["connected"] = connected
    result.extras["ssid"] = ssid
    result.extras["signal"] = signal
    result.extras["link_speed"] = link_speed
    result.extras["interface_name"] = interface_name
    return result


def test_network_connectivity(host: str = "8.8.8.8") -> ToolResult:
    if not is_safe_host(host):
        return skipped("test_network_connectivity", RISK, "That address is not safe to test.")
    target = require_safe_host(host)
    if not windows_tools_available():
        return unavailable(
            "test_network_connectivity",
            RISK,
            "I cannot ping from Windows without PowerShell.",
        )
    result = powershell_json(
        "test_network_connectivity",
        f"""
$ok = $false
try {{
  $ok = Test-Connection -ComputerName '{target}' -Count 1 -Quiet -ErrorAction Stop
}} catch {{
  $ok = $false
}}
[pscustomobject]@{{ Host = '{target}'; Reachable = [bool]$ok }} | ConvertTo-Json
""",
        timeout=20.0,
    )
    data = result.data if isinstance(result.data, dict) else {}
    reachable = bool(data.get("Reachable"))
    result.summary = f"{target} is reachable." if reachable else f"{target} is not reachable."
    result.extras["reachable"] = reachable
    result.extras["host"] = target
    if result.success:
        result.success = True
    return result


def test_dns(hostname: str = "www.microsoft.com") -> ToolResult:
    if not is_safe_host(hostname):
        return skipped("test_dns", RISK, "That name is not safe to look up.")
    target = require_safe_host(hostname)
    if not windows_tools_available():
        return unavailable("test_dns", RISK, "I cannot test Windows DNS without PowerShell.")
    result = powershell_json(
        "test_dns",
        f"""
$records = @()
$ok = $false
$err = $null
try {{
  $records = @(Resolve-DnsName -Name '{target}' -ErrorAction Stop | Select-Object Name, Type, IPAddress, NameHost)
  $ok = $true
}} catch {{
  $err = $_.Exception.Message
}}
[pscustomobject]@{{ Host = '{target}'; Ok = $ok; Error = $err; Records = $records }} | ConvertTo-Json -Depth 5
""",
        timeout=20.0,
    )
    data = result.data if isinstance(result.data, dict) else {}
    ok_flag = bool(data.get("Ok"))
    records = as_list(data.get("Records"))
    ips = [str(r.get("IPAddress")) for r in records if isinstance(r, dict) and r.get("IPAddress")]
    result.extras["resolved"] = ok_flag
    result.extras["addresses"] = ips
    if ok_flag:
        result.summary = f"Resolved {target}" + (f" → {', '.join(ips[:4])}" if ips else "")
        result.success = True
    else:
        err = data.get("Error") or "DNS lookup failed"
        result.summary = f"Could not resolve {target}: {err}"
        result.error = str(err)
        result.success = True  # the check ran; DNS itself failed
        result.extras["resolved"] = False
    return result


def test_internet() -> ToolResult:
    """Distinguish: no network vs DNS vs internet."""
    ip_ping = test_network_connectivity("8.8.8.8")
    dns = test_dns("www.microsoft.com")
    name_ping = test_network_connectivity("www.microsoft.com")
    ip_ok = bool(ip_ping.extras.get("reachable"))
    dns_ok = bool(dns.extras.get("resolved"))
    name_ok = bool(name_ping.extras.get("reachable"))
    if ip_ok and dns_ok:
        summary = "Internet name lookup and a public address both succeeded."
        state = "ok"
    elif ip_ok and not dns_ok:
        summary = "A public address is reachable, but website names are not resolving."
        state = "dns_failed"
    elif not ip_ok and dns_ok:
        summary = "Names resolve, but a public internet address did not respond."
        state = "internet_failed"
    else:
        summary = "Neither a public address nor website names responded."
        state = "offline"
    result = ok(
        "test_internet",
        RISK,
        summary,
        data={
            "ip_ping": ip_ping.data,
            "dns": dns.data,
            "name_ping": name_ping.data,
            "state": state,
        },
    )
    result.extras = {"state": state, "ip_ok": ip_ok, "dns_ok": dns_ok, "name_ok": name_ok}
    return result
