"""Answer 'what's my IP?' as a lookup — not a troubleshooting case."""

from __future__ import annotations

import platform
from typing import Any

from yuwontlaykit.tools.base import ToolResult
from yuwontlaykit.tools.runner import as_list

_VIRTUAL_HINTS = (
    "vethernet",
    "bluetooth",
    "loopback",
    "hyper-v",
    "wsl",
    "virtualbox",
    "vmware",
    "tailscale",
    "zerotier",
    "docker",
    "vpn",
    "pseudo",
    "teredo",
    "isatap",
)


def hostname_from_sysinfo(sysinfo: ToolResult | None) -> str:
    if sysinfo and isinstance(sysinfo.data, dict):
        osinfo = sysinfo.data.get("OS") or {}
        if isinstance(osinfo, dict) and osinfo.get("CSName"):
            return str(osinfo["CSName"]).strip()
        posix = sysinfo.data.get("posix") or {}
        if isinstance(posix, dict) and posix.get("node"):
            return str(posix["node"]).strip()
    return platform.node() or "this PC"


def _usable_ipv4(value: Any) -> str | None:
    for part in str(value or "").split(","):
        ip = part.strip()
        if ip.count(".") != 3:
            continue
        if ip.startswith("127.") or ip.startswith("169.254."):
            continue
        return ip
    return None


def _is_virtual(name: str) -> bool:
    n = name.lower()
    return any(hint in n for hint in _VIRTUAL_HINTS)


def _interface_label(name: str) -> str:
    n = name.lower()
    if "wi-fi" in n or "wifi" in n or "wireless" in n or "wlan" in n:
        return "Wi-Fi"
    if "ethernet" in n or n.startswith("eth"):
        return "Ethernet"
    return name or "unknown"


def pick_primary_interface(data: dict[str, Any] | None) -> dict[str, str] | None:
    if not isinstance(data, dict):
        return None
    adapters = [a for a in as_list(data.get("adapters")) if isinstance(a, dict)]
    rows = [r for r in as_list(data.get("ip")) if isinstance(r, dict)]
    status_by_name = {
        str(a.get("Name") or ""): str(a.get("Status") or "") for a in adapters
    }

    candidates: list[tuple[int, dict[str, str]]] = []
    for row in rows:
        alias = str(row.get("InterfaceAlias") or row.get("Name") or "")
        ipv4 = _usable_ipv4(row.get("IPv4") or row.get("IPAddress"))
        if not ipv4:
            continue
        status = status_by_name.get(alias, "")
        gateway = str(row.get("Gateway") or "").split(",")[0].strip()
        score = 0
        if status.lower() == "up" or not status:
            score += 10
        if gateway:
            score += 8
        if not _is_virtual(alias):
            score += 5
        label = _interface_label(alias)
        if label == "Ethernet":
            score += 3
        elif label == "Wi-Fi":
            score += 2
        candidates.append(
            (
                score,
                {
                    "ipv4": ipv4,
                    "interface": label,
                    "gateway": gateway,
                    "alias": alias,
                },
            )
        )
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def format_ip_lookup(net: ToolResult, sysinfo: ToolResult | None = None) -> str:
    hostname = hostname_from_sysinfo(sysinfo)
    if not net.available:
        return (
            net.summary
            or "I couldn't read this PC's network addresses from here."
        )
    picked = pick_primary_interface(net.data if isinstance(net.data, dict) else None)
    if not picked:
        return "I couldn't find an active IPv4 address on this PC."
    ipv4 = picked["ipv4"]
    lines = [
        "Your PC's network information:",
        "",
        f"🖥️ Computer: {hostname}",
        f"🌐 IPv4:     {ipv4}",
        f"🔗 Interface: {picked['interface']}",
    ]
    if picked.get("gateway"):
        lines.append(f"🚪 Gateway:   {picked['gateway']}")
    lines += ["", f"Your local IP address is **{ipv4}**."]
    return "\n".join(lines)
