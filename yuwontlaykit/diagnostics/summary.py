"""Format concise diagnostic summaries for the user."""

from __future__ import annotations

import re

from yuwontlaykit.diagnostics.case import TroubleshootingCase
from yuwontlaykit.diagnostics.printer_status import (
    classify_printers,
    rows_and_ports_from_case,
)
from yuwontlaykit.tools.runner import as_list


def is_network_connection_check(problem: str) -> bool:
    text = (problem or "").lower()
    mentions_network = any(
        word in text for word in ("wifi", "wi-fi", "wireless", "internet", "network")
    )
    asks_status = any(
        phrase in text
        for phrase in (
            "connected",
            "connection status",
            "internet access",
            "using wifi",
            "using wi-fi",
            "on wifi",
            "on wi-fi",
            "am i online",
            "is it online",
            "do i have internet",
            "does this pc have internet",
            "does my pc have internet",
        )
    )
    return mentions_network and asks_status


def format_network_connection_summary(case: TroubleshootingCase) -> str:
    """Report Wi-Fi, Ethernet, local network, and internet as separate facts."""
    by_name = case.results_by_name()
    wifi = by_name.get("get_wifi_information")
    network = by_name.get("get_network_information")
    internet = by_name.get("test_internet")

    wifi_data = wifi.data if wifi and isinstance(wifi.data, dict) else {}
    net_data = network.data if network and isinstance(network.data, dict) else {}
    wifi_connected = bool(wifi and wifi.extras.get("connected"))
    ssid = str(
        (wifi.extras.get("ssid") if wifi else None)
        or wifi_data.get("ssid")
        or ""
    ).strip()
    signal = str(
        (wifi.extras.get("signal") if wifi else None)
        or wifi_data.get("signal")
        or ""
    ).strip()
    link_speed = str(
        (wifi.extras.get("link_speed") if wifi else None)
        or wifi_data.get("link_speed")
        or ""
    ).strip()

    adapters = [
        row for row in as_list(net_data.get("adapters")) if isinstance(row, dict)
    ]
    ip_rows = [row for row in as_list(net_data.get("ip")) if isinstance(row, dict)]
    wifi_alias = _wifi_alias(wifi_data, adapters)
    ethernet_alias = _ethernet_alias(adapters)
    ethernet_connected = bool(ethernet_alias)
    internet_state = str(
        (internet.extras.get("state") if internet else None) or ""
    ).lower()
    internet_ok = internet_state == "ok"

    selected_alias = wifi_alias if wifi_connected else ethernet_alias
    selected_ip = _interface_ip(ip_rows, selected_alias)
    local_ip = selected_ip.get("ipv4", "")
    gateway = selected_ip.get("gateway", "")
    local_connected = bool(wifi_connected or ethernet_connected or local_ip or gateway)

    if wifi_connected and internet_ok:
        lines = [
            "Yes — I checked your network connection.",
            "",
            "📶 **Wi-Fi:** 🟢 Connected",
            "🌐 **Internet:** 🟢 Connected",
            f"💻 **Network interface:** {wifi_alias or 'Wi-Fi'}",
            f"📍 **Local IP:** {local_ip or 'Not reported'}",
            f"🚪 **Gateway:** {gateway or 'Not reported'}",
            "",
            "Your PC is currently connected to Wi-Fi and has working internet access.",
            "",
            "If you want, I can also show you **the Wi-Fi network name (SSID), "
            "signal strength, connection speed, and IP address**.",
        ]
        return "\n".join(lines)

    if not wifi_connected and ethernet_connected and internet_ok:
        return "\n".join(
            [
                "Your PC has internet access, but it is **not currently using Wi-Fi**.",
                "",
                "📶 **Wi-Fi:** 🔴 Not connected",
                "🔌 **Ethernet:** 🟢 Connected",
                "🌐 **Internet:** 🟢 Connected",
                "",
                "So your internet is working through the Ethernet cable, not Wi-Fi.",
                "",
                "If you'd like, I can check whether your Wi-Fi adapter is enabled "
                "and show you the available Wi-Fi networks.",
            ]
        )

    if wifi_connected and not internet_ok:
        return "\n".join(
            [
                "Your PC **is connected to Wi-Fi**, but there is a problem reaching the internet.",
                "",
                "📶 **Wi-Fi:** 🟢 Connected",
                f"🏠 **Local network:** {'🟢 Connected' if local_connected else '🟡 Not confirmed'}",
                "🌐 **Internet:** 🔴 Not reachable",
                "",
                "So the Wi-Fi connection itself appears to be working, but the "
                "network doesn't currently have internet access.",
                "",
                "I can investigate the connection further if you'd like.",
            ]
        )

    if not wifi_connected and not ethernet_connected:
        return "\n".join(
            [
                "No — I couldn't confirm an active network connection.",
                "",
                "📶 **Wi-Fi:** 🔴 Not connected",
                "🔌 **Ethernet:** 🔴 Not connected",
                "🌐 **Internet:** 🔴 Not reachable",
                "",
                "Your PC does not currently appear to be connected through Wi-Fi "
                "or Ethernet.",
            ]
        )

    # The adapter state is known, but the internet check was unavailable or unclear.
    interface = wifi_alias if wifi_connected else ethernet_alias
    return "\n".join(
        [
            "I checked the connection, but I couldn't confirm every layer.",
            "",
            f"📶 **Wi-Fi:** {'🟢 Connected' if wifi_connected else '🔴 Not connected'}",
            f"🔌 **Ethernet:** {'🟢 Connected' if ethernet_connected else '🔴 Not connected'}",
            f"🌐 **Internet:** {'🟡 Not confirmed' if not internet_ok else '🟢 Connected'}",
            f"💻 **Network interface:** {interface or 'Not reported'}",
            f"📍 **Local IP:** {local_ip or 'Not reported'}",
            f"🚪 **Gateway:** {gateway or 'Not reported'}",
            "",
            "Tell me if you want me to investigate the uncertain part further.",
        ]
    )


def _wifi_alias(wifi_data: dict, adapters: list[dict]) -> str:
    direct = str(wifi_data.get("interface_name") or "").strip()
    if direct:
        return direct
    for row in as_list(wifi_data.get("adapters")) + adapters:
        if not isinstance(row, dict):
            continue
        name = str(row.get("Name") or row.get("InterfaceAlias") or "").strip()
        desc = str(row.get("InterfaceDescription") or "").lower()
        if any(token in (name + " " + desc).lower() for token in ("wi-fi", "wifi", "wireless", "wlan", "802.11")):
            return name or "Wi-Fi"
    return "Wi-Fi"


def _ethernet_alias(adapters: list[dict]) -> str:
    for row in adapters:
        name = str(row.get("Name") or "").strip()
        desc = str(row.get("InterfaceDescription") or "").lower()
        text = (name + " " + desc).lower()
        if str(row.get("Status") or "").lower() != "up":
            continue
        if any(token in text for token in ("virtual", "vethernet", "hyper-v", "wsl", "vpn")):
            continue
        if "ethernet" in text or "gigabit" in text or "gbe" in text:
            return name or "Ethernet"
    return ""


def _interface_ip(rows: list[dict], alias: str) -> dict[str, str]:
    fallback: dict[str, str] = {}
    for row in rows:
        row_alias = str(row.get("InterfaceAlias") or row.get("Name") or "").strip()
        ipv4 = _first_usable_ipv4(row.get("IPv4") or row.get("IPAddress"))
        gateway = str(row.get("Gateway") or "").split(",")[0].strip()
        candidate = {"ipv4": ipv4, "gateway": gateway}
        if row_alias.lower() == alias.lower():
            return candidate
        if ipv4 and not fallback:
            fallback = candidate
    return fallback


def _first_usable_ipv4(value) -> str:
    for part in str(value or "").split(","):
        address = part.strip()
        if address.count(".") == 3 and not address.startswith(("127.", "169.254.")):
            return address
    return ""


def is_general_pc_check(problem: str) -> bool:
    text = (problem or "").lower()
    if re.search(r"\b(?:shut\s*down|power\s*off|turn\s+off|restart|reboot|lock)\b", text):
        if re.search(r"\b(?:pc|computer|laptop|machine|system)\b", text) and not any(
            phrase in text for phrase in ("check", "health", "working well", "doing")
        ):
            return False
    if any(
        phrase in text
        for phrase in (
            "check my computer",
            "check my pc",
            "check the computer",
            "check the pc",
            "computer health",
            "pc health",
            "health check",
            "examine my computer",
            "examine my pc",
            "scan my computer",
            "scan my pc",
            "look at my computer",
            "look at my pc",
            "general check",
        )
    ):
        return True

    # Natural health questions, not only commands beginning with "check".
    machine = r"(?:my|the|this)\s+(?:pc|computer|laptop|machine)"
    health = (
        r"(?:"
        r"(?:work|works|working|run|runs|running)\s+(?:well|fine|normally|properly)"
        r"|healthy|in\s+good\s+(?:condition|shape)"
        r"|doing\s+(?:well|fine|okay|ok)"
        r"|okay|ok|fine"
        r")"
    )
    return bool(
        re.search(rf"\b(?:is|does)\s+{machine}\s+{health}\b", text)
        or re.search(rf"\bhow\s+is\s+{machine}(?:\s+doing)?\b", text)
        or re.search(rf"\b{machine}\s+health\b", text)
    )


def format_computer_health_summary(
    case: TroubleshootingCase,
    *,
    user_name: str = "Nikko",
) -> str:
    """Summarize a consented general PC check without overstating evidence."""
    by_name = case.results_by_name()
    system = by_name.get("get_system_information")
    disk = by_name.get("get_disk_information")
    processes = by_name.get("get_running_processes")
    startup = by_name.get("get_startup_applications")
    network = by_name.get("get_network_information")
    internet = by_name.get("test_internet")
    printers = by_name.get("get_printers")
    checks = [system, disk, processes, startup, network, internet, printers]

    incomplete = [
        item for item in checks if item is None or not item.available or not item.success
    ]
    low_drives = list((disk.extras.get("low_space") if disk else None) or [])
    internet_state = str((internet.extras.get("state") if internet else "") or "")
    network_problem = bool(internet_state and internet_state != "ok")
    healthy = not incomplete and not low_drives and not network_problem

    if healthy:
        opening = (
            "Overall, your PC looks to be **working normally** "
            "based on the checks I performed. 🟢"
        )
    else:
        opening = (
            "I completed the checks I could, but I can't confirm that everything "
            "is working normally yet. 🟡"
        )

    cpu_load, memory_used = _system_load(system)
    if system and system.success:
        if cpu_load is not None and memory_used is not None:
            system_text = (
                f"CPU load was {cpu_load:.0f}% and memory usage was "
                f"{memory_used:.0f}% during the check."
            )
        else:
            system_text = (
                "I collected the available CPU, memory, operating-system, "
                "and uptime information."
            )
    else:
        system_text = "I couldn't complete the system-performance check."

    if disk and disk.success:
        storage_text = (
            f"Storage is low on: {', '.join(str(x) for x in low_drives)}."
            if low_drives
            else "Your available storage looks sufficient; no drive was below the low-space threshold."
        )
    else:
        storage_text = "I couldn't complete the storage check."

    programs_text = (
        "I reviewed the busiest running programs. "
        + (processes.summary or "The process list was collected.")
        if processes and processes.success
        else "I couldn't complete the running-program check."
    )
    startup_text = (
        "I checked the programs configured to start with Windows. "
        + (startup.summary or "The startup list was collected.")
        if startup and startup.success
        else "I couldn't complete the startup-program check."
    )

    if internet and internet.success:
        network_text = internet.summary or "The connectivity check completed."
    elif network and network.success:
        network_text = (
            "I checked the network interfaces and configuration, "
            "but internet connectivity was not fully confirmed."
        )
    else:
        network_text = "I couldn't complete the network check."

    if printers and printers.success:
        count = len(
            [row for row in as_list(printers.data) if isinstance(row, dict)]
        )
        printers_text = (
            f"I checked the printers installed on this PC; Windows reported {count}."
        )
    else:
        printers_text = "I couldn't complete the installed-printer check."

    if healthy:
        assessment = (
            "🟢 **Your PC appears healthy based on the checks I can perform right now.**\n\n"
            "I didn't find anything that currently looks like a serious software-level problem."
        )
    else:
        issues = []
        if low_drives:
            issues.append("low storage")
        if network_problem:
            issues.append("a network/connectivity issue")
        if incomplete:
            issues.append("one or more incomplete checks")
        assessment = (
            "🟡 **This health check needs attention or more information.**\n\n"
            "I found " + ", ".join(issues or ["an uncertain result"]) + "."
        )

    return "\n".join(
        [
            f"I finished checking your PC, {user_name}.",
            "",
            opening,
            "",
            "Here's what I checked:",
            "",
            "🖥️ **System performance**",
            system_text,
            "",
            "💾 **Storage**",
            storage_text,
            "",
            "⚙️ **Running programs**",
            programs_text,
            "",
            "🚀 **Startup programs**",
            startup_text,
            "",
            "🌐 **Network**",
            network_text,
            "",
            "🖨️ **Printers**",
            printers_text,
            "",
            "### Overall assessment",
            "",
            assessment,
            "",
            "This is a **software-level health check**. It does not prove that every "
            "hardware component is physically healthy.",
            "",
            "If you're experiencing slow performance, Wi-Fi or printer problems, "
            "application errors, or Windows issues, tell me what happened and "
            "I'll investigate that specifically.",
            "",
            "You don't need technical terms—just describe it in your own words.",
        ]
    )


def _system_load(system) -> tuple[float | None, float | None]:
    if not system or not isinstance(system.data, dict):
        return None, None
    cpu = system.data.get("CPU") or {}
    if isinstance(cpu, list):
        cpu = cpu[0] if cpu else {}
    osinfo = system.data.get("OS") or {}
    try:
        cpu_load = float(cpu.get("LoadPercentage"))
    except (AttributeError, TypeError, ValueError):
        cpu_load = None
    try:
        total = float(osinfo.get("TotalVisibleMemorySize"))
        free = float(osinfo.get("FreePhysicalMemory"))
        memory_used = ((total - free) / total) * 100 if total > 0 else None
    except (AttributeError, TypeError, ValueError):
        memory_used = None
    return cpu_load, memory_used


def format_printer_diagnostic_summary(
    case: TroubleshootingCase,
    *,
    reachability: dict[str, bool] | None = None,
) -> str:
    rows, ports = rows_and_ports_from_case(case)
    items = classify_printers(rows, ports, reachability=reachability or {})
    from yuwontlaykit.diagnostics.printer_status import _is_virtual

    desk = [p for p in items if not _is_virtual(p.name)]
    show = desk if desk else items

    spooler = case.results_by_name().get("check_print_spooler")
    queue = case.results_by_name().get("get_print_queue")

    lines = ["Here's what I found:", ""]
    for item in show:
        mark = {"online": "Online", "offline": "Offline", "unknown": "Status unknown"}[item.bucket]
        prefix = {"online": "🟢", "offline": "🔴", "unknown": "🟡"}[item.bucket]
        lines.append(f"{prefix} {item.name} — {mark}")

    lines.append("")
    spooler_line = _spooler_line(spooler)
    queue_line = _queue_line(queue)
    if spooler_line:
        lines.append(spooler_line)
    if queue_line:
        lines.append(queue_line)

    offline = [p for p in show if p.bucket == "offline"]
    unknown = [p for p in show if p.bucket == "unknown"]
    online = [p for p in show if p.bucket == "online"]

    lines.append("")
    if offline:
        focus = offline[0].name
        lines.append(f"The most likely issue is the connection to {focus}.")
        lines.append("")
        lines.append("Want me to investigate that printer further?")
        case.awaiting = "offer_diagnose_offline"
        case.extras["diagnose_targets"] = [p.name for p in offline + unknown]
    elif unknown and not offline:
        lines.append("I couldn't fully confirm every printer's connection yet.")
        lines.append("")
        lines.append("Want me to investigate the uncertain ones further?")
        case.awaiting = "offer_diagnose_offline"
        case.extras["diagnose_targets"] = [p.name for p in unknown]
    elif online:
        names = ", ".join(p.name for p in online)
        lines.append(f"Looks like these are ready: {names}.")
        lines.append("If printing still fails, tell me what happens when you try.")
    else:
        lines.append("I need a bit more detail about what you see when you print.")

    return "\n".join(lines)


def _spooler_line(spooler) -> str:
    if not spooler or not spooler.available:
        return "Print Spooler: 🟡 Could not check"
    if spooler.extras.get("running") is True:
        return "Print Spooler: 🟢 Running"
    if spooler.extras.get("running") is False:
        return "Print Spooler: 🔴 Stopped"
    status = spooler.extras.get("status") or spooler.summary or "Unknown"
    return f"Print Spooler: 🟡 {status}"


def _queue_line(queue) -> str:
    if not queue or not queue.available:
        return "Print Queue: 🟡 Could not check"
    jobs = int(queue.extras.get("job_count") or 0)
    stuck = int(queue.extras.get("stuck_count") or 0)
    if stuck:
        return f"Print Queue: 🔴 {stuck} stuck/failed job(s)"
    if jobs:
        return f"Print Queue: 🟡 {jobs} job(s) waiting"
    return "Print Queue: 🟢 No stuck jobs"
