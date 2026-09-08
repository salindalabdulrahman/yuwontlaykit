"""Format concise diagnostic summaries for the user."""

from __future__ import annotations

from yuwontlaykit.diagnostics.case import TroubleshootingCase
from yuwontlaykit.diagnostics.printer_status import (
    classify_printers,
    rows_and_ports_from_case,
)
from yuwontlaykit.tools.runner import as_list


def is_general_pc_check(problem: str) -> bool:
    text = (problem or "").lower()
    return any(
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
