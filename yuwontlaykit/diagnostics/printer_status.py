"""Classify installed printers as online, offline, or unconfirmed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from yuwontlaykit.tools.runner import as_list
from yuwontlaykit.tools.validate import is_safe_host

VIRTUAL_HINTS = (
    "microsoft print to pdf",
    "microsoft xps",
    "onenote",
    "fax",
    "send to onenote",
    "anydesk",
    "remote desktop",
    "onenote for windows",
)

CONFIRMED_ONLINE = {
    "normal",
    "idle",
    "printing",
    "warmup",
    "warmingup",
    "warming up",
    "ready",
    "online",
    "busy",
    "processing",
    "waiting",
    "ioactive",
    "i/o active",
    "initialization",
    "powersave",
    "power save",
    "tonerlow",
    "toner low",
}

CONFIRMED_OFFLINE = {
    "offline",
    "error",
    "paused",
    "notavailable",
    "not available",
    "dooropen",
    "door open",
    "paperjam",
    "paper jam",
    "paperout",
    "paper out",
    "no toner",
    "notoner",
    "serverunknown",
    "server unknown",
    "pendingdeletion",
    "pending deletion",
    "userintervention",
    "user intervention",
}

# Win32 / Get-Printer numeric codes that mean ready-ish
ONLINE_CODES = {0, 3, 4, 5, 10, 12, 13, 14, 15, 17}
OFFLINE_CODES = {7, 8, 9, 11}


@dataclass
class PrinterReadiness:
    name: str
    bucket: str  # online | offline | unknown
    reason: str
    connection: str
    host: str | None = None


def classify_printers(
    rows: list[dict],
    ports: list[dict] | None = None,
    reachability: dict[str, bool] | None = None,
) -> list[PrinterReadiness]:
    port_map = _port_address_map(ports or [])
    reachability = reachability or {}
    results: list[PrinterReadiness] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        results.append(_classify_one(row, port_map, reachability))
    return results


def _classify_one(
    row: dict,
    port_map: dict[str, str],
    reachability: dict[str, bool],
) -> PrinterReadiness:
    name = str(row.get("Name") or "Unknown")
    port = str(row.get("PortName") or "")
    host = port_map.get(port) or _host_from_port_name(port)
    connection = _connection_kind(port, name)
    status_raw = row.get("PrinterStatus")
    status = _normalize_status(status_raw)
    work_offline = row.get("WorkOffline") in (True, "True", "true", 1, "1")

    if _is_virtual(name):
        return PrinterReadiness(
            name=name,
            bucket="unknown",
            reason="software/remote printer, not a desk device",
            connection=connection,
            host=host,
        )

    if work_offline or status in CONFIRMED_OFFLINE or _status_code(status_raw) in OFFLINE_CODES:
        return PrinterReadiness(
            name=name,
            bucket="offline",
            reason="Windows reports offline / not ready",
            connection=connection,
            host=host,
        )

    if host and host in reachability:
        if reachability[host] is True:
            return PrinterReadiness(
                name=name,
                bucket="online",
                reason="reachable on the network",
                connection=connection,
                host=host,
            )
        return PrinterReadiness(
            name=name,
            bucket="offline",
            reason="not reachable at its network address",
            connection=connection,
            host=host,
        )

    if status in CONFIRMED_ONLINE or _status_code(status_raw) in ONLINE_CODES:
        # USB / local with a healthy Windows status → treat as confirmed online
        if connection.startswith("USB") or connection.startswith("local"):
            return PrinterReadiness(
                name=name,
                bucket="online",
                reason="Windows status looks ready",
                connection=connection,
                host=host,
            )
        # Network without a successful ping yet → unconfirmed even if Windows says Normal
        if connection.startswith("network"):
            return PrinterReadiness(
                name=name,
                bucket="unknown",
                reason="Windows lists it, but reachability was not confirmed",
                connection=connection,
                host=host,
            )
        return PrinterReadiness(
            name=name,
            bucket="online",
            reason="Windows status looks ready",
            connection=connection,
            host=host,
        )

    return PrinterReadiness(
        name=name,
        bucket="unknown",
        reason="detected, but online status cannot be confirmed",
        connection=connection,
        host=host,
    )


def refresh_reachability(
    rows: list[dict],
    ports: list[dict],
    ping: Callable[[str], bool],
) -> dict[str, bool]:
    """Ping each unique printer host once. ping(host) -> reachable bool."""
    port_map = _port_address_map(ports)
    hosts: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if _is_virtual(str(row.get("Name") or "")):
            continue
        port = str(row.get("PortName") or "")
        host = port_map.get(port) or _host_from_port_name(port)
        if host and is_safe_host(host):
            hosts.add(host)
    result: dict[str, bool] = {}
    for host in sorted(hosts):
        try:
            result[host] = bool(ping(host))
        except Exception:  # noqa: BLE001
            result[host] = False
    return result


def pick_recommended_printer(items: list[PrinterReadiness]) -> PrinterReadiness | None:
    """Choose one desk printer — skip virtual/receipt devices when a real one is online."""
    desk = [p for p in items if not _is_virtual(p.name)]
    pool = [p for p in desk if p.bucket == "online"] or desk or items
    if not pool:
        return None

    def score(p: PrinterReadiness) -> int:
        n = p.name.lower()
        s = 0
        if p.bucket == "online":
            s += 10
        if p.bucket == "offline":
            s -= 6
        if _is_virtual(p.name):
            s -= 20
        if any(token in n for token in ("pos", "receipt", "receift", "bill", "kitchen", "label", "barcode")):
            s -= 8
        if p.connection.startswith("USB"):
            s += 2
        if p.connection.startswith("network"):
            s += 1
        return s

    return max(pool, key=score)


def format_online_answer(items: list[PrinterReadiness], *, detailed: bool = False) -> tuple[str, bool]:
    """Return (reply, offer_diagnose). offer_diagnose means a soft yes/no follow-up is open."""
    online = [p for p in items if p.bucket == "online"]
    offline = [p for p in items if p.bucket == "offline"]
    unknown = [p for p in items if p.bucket == "unknown"]

    if detailed:
        text = _format_detailed(items, online, offline, unknown)
        return text, bool(offline or unknown)
    text = _format_conversational(online, offline, unknown)
    return text, ("Want me to check why" in text or "Want me to diagnose" in text)


def format_online_only_list(items: list[PrinterReadiness]) -> str:
    """List confirmed-online printers only — no diagnose pitch."""
    online = [p for p in items if p.bucket == "online" and not _is_virtual(p.name)]
    if not online:
        online = [p for p in items if p.bucket == "online"]
    if not online:
        return "None of the printers are confirmed online right now."
    lines = [
        "Sure. These are the printers currently confirmed online:",
        "",
    ]
    lines.extend(f"🟢 {p.name}" for p in online)
    n = len(online)
    lines += ["", f"{n} online printer{'s' if n != 1 else ''} found."]
    return "\n".join(lines)


def _format_conversational(
    online: list[PrinterReadiness],
    offline: list[PrinterReadiness],
    unknown: list[PrinterReadiness],
) -> str:
    if len(online) == 1 and not offline and not unknown:
        return f"I checked them. {online[0].name} is confirmed online."

    if online and (offline or unknown):
        names = ", ".join(p.name for p in online)
        if len(online) == 1:
            head = f"I checked them. {names} is confirmed online."
        else:
            head = f"I checked them. Confirmed online: {names}."
        bits = [head]
        others = []
        if offline:
            others.append("appear offline")
        if unknown:
            others.append("I couldn't reliably confirm yet")
        if others:
            bits.append("The others either " + " or ".join(others) + ".")
        pick = pick_recommended_printer(online) or online[0]
        bits.append(
            f"If you're trying to print right now, I'd use {pick.name}. "
            "Want me to check why the others aren't responding?"
        )
        return "\n".join(bits)

    if online:
        names = ", ".join(p.name for p in online)
        return f"I checked them. Confirmed online: {names}."

    if offline and not unknown:
        names = ", ".join(p.name for p in offline)
        return (
            f"I checked them. None are confirmed online right now — "
            f"these look offline: {names}. "
            "Want me to diagnose why?"
        )

    if unknown and not offline:
        names = ", ".join(p.name for p in unknown)
        return (
            f"I found them, but I couldn't reliably confirm which ones are online yet: {names}. "
            "Want me to dig deeper?"
        )

    parts = ["I checked them. None are confirmed online right now."]
    if offline:
        parts.append("Offline: " + ", ".join(p.name for p in offline) + ".")
    if unknown:
        parts.append("Could not confirm: " + ", ".join(p.name for p in unknown) + ".")
    parts.append("Want me to diagnose the ones that aren't responding?")
    return "\n".join(parts)


def _format_detailed(
    items: list[PrinterReadiness],
    online: list[PrinterReadiness],
    offline: list[PrinterReadiness],
    unknown: list[PrinterReadiness],
) -> str:
    total = len(items)
    lines = [
        f"I found {total} installed printer{'s' if total != 1 else ''}. "
        "Let me check which ones are actually reachable.",
        "",
    ]
    if online:
        lines.append("Online")
        lines.extend(f"• {p.name}" for p in online)
        lines.append("")
    if offline:
        lines.append("Offline / Unreachable")
        lines.extend(f"• {p.name}" for p in offline)
        lines.append("")
    if unknown:
        lines.append("Detected, but online status cannot be confirmed")
        lines.extend(f"• {p.name}" for p in unknown)
        lines.append("")
    lines.append(
        "What I checked: Windows printer status, connection type, printer port, "
        "and network/device reachability."
    )
    if offline or unknown:
        lines += [
            "",
            "If you want, I can diagnose the offline/unknown printers further "
            "and tell you exactly what is preventing them from working.",
        ]
    return "\n".join(lines)


def _is_virtual(name: str) -> bool:
    n = name.lower()
    return any(token in n for token in VIRTUAL_HINTS)


def _normalize_status(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    return text.replace("_", " ")


def _status_code(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _connection_kind(port: str, name: str) -> str:
    if _is_virtual(name):
        return "software/remote"
    p = (port or "").upper()
    if p.startswith(("USB", "DOT4", "LPT", "COM")):
        return "USB / local"
    if p.startswith(("WSD", "IP_", "TCP", "HTTP", "HTTPS")) or "IP_" in p:
        return "network"
    if ":" in p and any(ch.isdigit() for ch in p):
        # e.g. 192.168.1.50:9100 style custom ports
        return "network"
    if p.startswith("FILE") or "PDF" in (name or "").upper():
        return "file"
    if port:
        return f"port {port}"
    return "unknown connection"


def _port_address_map(ports: list[dict]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for port in ports:
        if not isinstance(port, dict):
            continue
        name = str(port.get("Name") or "")
        addr = str(port.get("PrinterHostAddress") or "").strip()
        if name and addr and is_safe_host(addr):
            mapping[name] = addr
    return mapping


def _host_from_port_name(port: str) -> str | None:
    p = (port or "").strip()
    upper = p.upper()
    # Local/cable ports are never network hosts
    if upper.startswith(("USB", "DOT4", "LPT", "COM", "FILE", "TS", "SHR", "NU", "PORTPROMPT")):
        return None
    if upper.startswith("IP_"):
        candidate = p[3:]
        if is_safe_host(candidate):
            return candidate
    # host:port
    if ":" in p:
        host = p.split(":", 1)[0].strip()
        if is_safe_host(host) and not host.upper().startswith(("USB", "DOT4")):
            return host
    # Bare IP only — not arbitrary port names like USB001
    try:
        import ipaddress

        ipaddress.ip_address(p)
        return p
    except ValueError:
        return None


def rows_and_ports_from_case(case) -> tuple[list[dict], list[dict]]:
    rows = list(case.extras.get("printer_rows") or [])
    ports: list[dict] = []
    by_name = case.results_by_name() if hasattr(case, "results_by_name") else {}
    if not rows:
        for key in ("get_printer_status", "get_printers"):
            result = by_name.get(key)
            if result and result.data is not None:
                rows = [r for r in as_list(result.data) if isinstance(r, dict)]
                break
    port_result = by_name.get("get_printer_port")
    if port_result and isinstance(port_result.data, dict):
        ports = [p for p in as_list(port_result.data.get("ports")) if isinstance(p, dict)]
    ports = list(case.extras.get("printer_ports") or ports)
    return rows, ports
