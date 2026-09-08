"""Evidence → diagnosis. Rule-based; never invents a cause without checks."""

from __future__ import annotations

from dataclasses import dataclass, field

from yuwontlaykit.diagnostics.case import ProposedAction, TroubleshootingCase
from yuwontlaykit.knowledge.topics import get_topic
from yuwontlaykit.tools.base import Confidence, ToolResult
from yuwontlaykit.tools.runner import as_list
from yuwontlaykit.tools.validate import is_safe_host


VIRTUAL_PRINTERS = (
    "microsoft print to pdf",
    "microsoft xps",
    "onenote",
    "fax",
    "send to onenote",
    "anydesk",
)


@dataclass
class Analysis:
    topic_id: str | None
    diagnosis: str
    confidence: Confidence
    evidence: list[str]
    probable_cause: str
    proposed: ProposedAction | None = None
    followup_host: str | None = None
    needs_user: str | None = None
    extras: dict = field(default_factory=dict)


def analyze_case(case: TroubleshootingCase) -> Analysis:
    by_name = case.results_by_name()
    domain = case.domain
    if domain == "printer":
        return _analyze_printer(case, by_name)
    if domain in ("wifi", "network"):
        return _analyze_network(case, by_name)
    if domain == "computer":
        return _analyze_computer(case, by_name)
    if domain == "audio":
        return _analyze_audio(case, by_name)
    if domain == "bluetooth":
        return _analyze_bluetooth(case, by_name)
    if domain == "storage":
        return _analyze_storage(case, by_name)
    if domain == "security":
        return _analyze_security(case, by_name)
    if domain == "software":
        return _analyze_software(case, by_name)
    if domain == "hardware":
        return _analyze_hardware(case, by_name)
    return _unknown("I ran the checks I have, but I don't have a specific playbook for this yet.")


def _topic_action(topic_id: str) -> ProposedAction | None:
    topic = get_topic(topic_id) or {}
    rem = topic.get("remediation")
    if not rem or not rem.get("tool"):
        return None
    return ProposedAction(
        tool=str(rem["tool"]),
        label=str(rem.get("label") or rem["tool"]),
        user_impact=str(rem.get("user_impact") or ""),
        topic_id=topic_id,
    )


def _unknown(reason: str) -> Analysis:
    return Analysis(
        topic_id=None,
        diagnosis="Not enough information",
        confidence=Confidence.UNKNOWN,
        evidence=[reason],
        probable_cause=reason,
        needs_user="Tell me what you see on the screen, or what happens when you try again.",
    )


def _printer_rows(by_name: dict[str, ToolResult]) -> list[dict]:
    result = by_name.get("get_printers") or by_name.get("get_printer_status")
    if not result or not result.success:
        return []
    return [r for r in as_list(result.data) if isinstance(r, dict)]


def _is_virtual(name: str) -> bool:
    n = (name or "").lower()
    return any(token in n for token in VIRTUAL_PRINTERS)


def _analyze_printer(case: TroubleshootingCase, by_name: dict[str, ToolResult]) -> Analysis:
    if str(case.extras.get("intent") or "") == "inventory":
        return _analyze_printer_inventory(case, by_name)

    printers = by_name.get("get_printers")
    if printers and not printers.available:
        return Analysis(
            topic_id=None,
            diagnosis="Cannot inspect Windows printers",
            confidence=Confidence.CONFIRMED,
            evidence=[printers.as_evidence_line()],
            probable_cause=printers.summary,
            needs_user="I need Windows PowerShell to inspect printers on this PC.",
        )

    rows = _printer_rows(by_name)
    physical = [r for r in rows if not _is_virtual(str(r.get("Name") or ""))]
    spooler = by_name.get("check_print_spooler")
    queue = by_name.get("get_print_queue")
    ports = by_name.get("get_printer_port")
    default = by_name.get("get_default_printer")

    evidence: list[str] = []
    if printers:
        evidence.append(printers.as_evidence_line())
    if spooler:
        evidence.append(spooler.as_evidence_line())
    if queue:
        evidence.append(queue.as_evidence_line())
    if default:
        evidence.append(default.as_evidence_line())

    if spooler and spooler.available and spooler.success and _spooler_down(by_name):
        return Analysis(
            topic_id="printer_spooler",
            diagnosis="Print Spooler problem",
            confidence=Confidence.CONFIRMED,
            evidence=evidence,
            probable_cause="Windows' printing system is not running.",
            proposed=_topic_action("printer_spooler"),
        )

    if not physical:
        return Analysis(
            topic_id="printer_not_found",
            diagnosis="Printer not found",
            confidence=Confidence.CONFIRMED if printers and printers.success else Confidence.LIKELY,
            evidence=evidence or ["No physical printers were listed."],
            probable_cause="Windows does not currently list a real printer.",
            needs_user="Please check the printer is powered on and connected, then tell me.",
        )

    stuck = int((queue.extras.get("stuck_count") if queue else 0) or 0)
    jobs = int((queue.extras.get("job_count") if queue else 0) or 0)
    if queue and queue.success and (stuck or jobs >= 3):
        return Analysis(
            topic_id="printer_queue_stuck",
            diagnosis="Print queue stuck",
            confidence=Confidence.LIKELY if stuck else Confidence.POSSIBLE,
            evidence=evidence,
            probable_cause=f"{jobs} document(s) in the queue"
            + (f", {stuck} look failed or stuck" if stuck else "")
            + ".",
            proposed=_topic_action("printer_queue_stuck"),
        )

    offline = []
    for row in physical:
        status = str(row.get("PrinterStatus") or "").lower()
        work_off = row.get("WorkOffline") in (True, "True", "true")
        if work_off or "offline" in status or "error" in status:
            offline.append(row)
    if offline:
        host = _printer_ip(ports)
        if host:
            return Analysis(
                topic_id="printer_network",
                diagnosis="Printer offline (network)",
                confidence=Confidence.LIKELY,
                evidence=evidence + [f"Candidate printer address: {host}"],
                probable_cause="The printer is marked offline and appears to use a network address.",
                followup_host=host,
                proposed=_topic_action("printer_offline"),
            )
        usbish = any(
            str(r.get("PortName") or "").upper().startswith(("USB", "DOT4", "LPT", "FILE"))
            for r in offline
        )
        topic = "printer_usb" if usbish else "printer_offline"
        return Analysis(
            topic_id=topic,
            diagnosis="Printer offline",
            confidence=Confidence.CONFIRMED,
            evidence=evidence,
            probable_cause="Windows reports the printer as offline or in error.",
            proposed=_topic_action("printer_offline"),
            needs_user="Please confirm the printer is powered on and its cable/Wi-Fi light looks normal.",
        )

    if default and isinstance(default.data, dict):
        name = str(default.data.get("Name") or "")
        if _is_virtual(name) and physical:
            return Analysis(
                topic_id="printer_wrong_default",
                diagnosis="Wrong default printer",
                confidence=Confidence.LIKELY,
                evidence=evidence,
                probable_cause=f"The selected printer is '{name}', which saves a file instead of printing on paper.",
            )

    # Driver mismatch: printer names a driver that isn't in the driver list
    drivers = by_name.get("get_printer_driver")
    if drivers and isinstance(drivers.data, dict):
        installed = {
            str(d.get("Name")).lower()
            for d in as_list(drivers.data.get("drivers"))
            if isinstance(d, dict) and d.get("Name")
        }
        missing = []
        for row in physical:
            drv = str(row.get("DriverName") or "")
            if drv and installed and drv.lower() not in installed:
                missing.append(drv)
        if missing:
            return Analysis(
                topic_id="printer_driver",
                diagnosis="Driver problem",
                confidence=Confidence.POSSIBLE,
                evidence=evidence + [f"Missing driver name(s): {', '.join(missing)}"],
                probable_cause="A printer is using a driver Windows did not list as installed.",
            )

    return Analysis(
        topic_id=None,
        diagnosis="Printers look present",
        confidence=Confidence.POSSIBLE,
        evidence=evidence,
        probable_cause="I see at least one printer, but I have not confirmed a single failing part yet.",
        needs_user="What exactly happens when you print — error message, blank pages, or nothing at all?",
    )


def _spooler_down(by_name: dict[str, ToolResult]) -> bool:
    spooler = by_name.get("check_print_spooler")
    if not spooler or not spooler.available or not spooler.success:
        return False
    status = str(spooler.extras.get("status") or "").lower()
    if status in ("stopped", "stoppending", "paused"):
        return True
    return spooler.extras.get("running") is False and status not in ("", "unknown")


def _connection_kind(port: str, name: str) -> str:
    if _is_virtual(name):
        return "saves a file (not a desk printer)"
    p = (port or "").upper()
    if p.startswith(("USB", "DOT4", "LPT")):
        return "USB / cable"
    if p.startswith(("WSD", "IP_", "TCP", "HTTP")) or "IP_" in p:
        return "network"
    if p.startswith("FILE") or "PDF" in (name or "").upper():
        return "file"
    if port:
        return f"port {port}"
    return "connection unknown"


def format_printer_lines(rows: list[dict], default_name: str | None = None) -> list[str]:
    lines: list[str] = []
    for row in rows:
        name = str(row.get("Name") or "Unknown")
        status = str(row.get("PrinterStatus") or "unknown")
        port = str(row.get("PortName") or "")
        kind = _connection_kind(port, name)
        tags: list[str] = []
        is_default = row.get("Default") in (True, "True", "true") or (
            default_name is not None and name == default_name
        )
        if is_default:
            tags.append("default")
        if _is_virtual(name):
            tags.append("not a physical printer")
        extra = f" ({', '.join(tags)})" if tags else ""
        lines.append(f"{name}{extra} — {kind}; status: {status}")
    return lines


def _analyze_printer_inventory(case: TroubleshootingCase, by_name: dict[str, ToolResult]) -> Analysis:
    printers = by_name.get("get_printers")
    default = by_name.get("get_default_printer")
    spooler = by_name.get("check_print_spooler")
    evidence = [r.as_evidence_line() for r in (printers, default, spooler) if r]

    if printers and not printers.available:
        return Analysis(
            topic_id=None,
            diagnosis="Could not list printers",
            confidence=Confidence.CONFIRMED,
            evidence=evidence,
            probable_cause=printers.summary,
            needs_user="I need Windows PowerShell to see printers on this PC.",
            extras={"mode": "inventory", "printer_lines": []},
        )

    rows = _printer_rows(by_name)
    default_name = None
    if default and isinstance(default.data, dict):
        default_name = default.data.get("Name")
    ports_result = by_name.get("get_printer_port")
    port_rows: list[dict] = []
    if ports_result and isinstance(ports_result.data, dict):
        port_rows = [
            p for p in as_list(ports_result.data.get("ports")) if isinstance(p, dict)
        ]
    lines = format_printer_lines(rows, str(default_name) if default_name else None)
    extras = {
        "mode": "inventory",
        "intent": "inventory",
        "printer_lines": lines,
        "printer_rows": rows,
        "printer_ports": port_rows,
        "default_printer": str(default_name) if default_name else None,
        "spooler_down": _spooler_down(by_name),
    }

    if lines:
        return Analysis(
            topic_id=None,
            diagnosis="Printer inventory",
            confidence=Confidence.CONFIRMED,
            evidence=evidence,
            probable_cause="Listed installed printers.",
            proposed=None,
            extras=extras,
        )

    if extras["spooler_down"]:
        return Analysis(
            topic_id=None,
            diagnosis="No printers listed",
            confidence=Confidence.LIKELY,
            evidence=evidence,
            probable_cause="Windows did not report any printers on this PC.",
            proposed=None,
            extras=extras,
        )

    return Analysis(
        topic_id=None,
        diagnosis="No printers listed",
        confidence=Confidence.LIKELY,
        evidence=evidence or ["No printers were listed."],
        probable_cause="Windows did not report any printers on this PC.",
        extras=extras,
    )


def _printer_ip(ports: ToolResult | None) -> str | None:
    if not ports or not isinstance(ports.data, dict):
        return None
    for port in as_list(ports.data.get("ports")):
        if not isinstance(port, dict):
            continue
        addr = str(port.get("PrinterHostAddress") or "").strip()
        if addr and is_safe_host(addr):
            return addr
    return None


def _analyze_network(case: TroubleshootingCase, by_name: dict[str, ToolResult]) -> Analysis:
    wifi = by_name.get("get_wifi_information")
    net = by_name.get("get_network_information")
    internet = by_name.get("test_internet")
    evidence = [r.as_evidence_line() for r in (wifi, net, internet) if r]

    ssid = wifi.extras.get("ssid") if wifi else None
    wifi_connected = bool(wifi.extras.get("connected")) if wifi else False
    adapters_up = False
    if net and isinstance(net.data, dict):
        adapters_up = any(
            str(a.get("Status") or "").lower() == "up"
            for a in as_list(net.data.get("adapters"))
            if isinstance(a, dict)
        )

    if wifi and wifi.available and not ssid and not wifi_connected and not adapters_up:
        return Analysis(
            topic_id="wifi_disconnected",
            diagnosis="Not connected to Wi-Fi",
            confidence=Confidence.CONFIRMED if wifi.success else Confidence.LIKELY,
            evidence=evidence,
            probable_cause="The computer is not joined to a Wi-Fi network.",
        )

    state = (internet.extras.get("state") if internet else None) or ""
    if state == "dns_failed":
        return Analysis(
            topic_id="dns_failure",
            diagnosis="DNS problem",
            confidence=Confidence.CONFIRMED,
            evidence=evidence,
            probable_cause="The network is up, but website names are not translating.",
            proposed=_topic_action("dns_failure"),
        )
    if state == "internet_failed" or state == "offline":
        if ssid or adapters_up or wifi_connected:
            return Analysis(
                topic_id="internet_unavailable",
                diagnosis="Internet unavailable",
                confidence=Confidence.LIKELY,
                evidence=evidence,
                probable_cause="The computer is on a local network, but the internet beyond it did not respond.",
                needs_user="A router restart often helps. I cannot press the router's power button.",
            )
        return Analysis(
            topic_id="wifi_disconnected",
            diagnosis="Not connected to Wi-Fi",
            confidence=Confidence.LIKELY,
            evidence=evidence,
            probable_cause="No working network path to the internet was found.",
        )
    if state == "ok":
        return Analysis(
            topic_id=None,
            diagnosis="Internet looks available",
            confidence=Confidence.LIKELY,
            evidence=evidence,
            probable_cause="A public address and website names both responded from here.",
            needs_user="If one website still fails, it may be that site — tell me which.",
        )

    if not internet or not internet.available:
        return Analysis(
            topic_id=None,
            diagnosis="Cannot finish the internet test",
            confidence=Confidence.UNKNOWN,
            evidence=evidence,
            probable_cause="Windows network tools were not available or did not complete.",
        )
    return _unknown("Network checks completed without a clear single cause.")


def _analyze_computer(case: TroubleshootingCase, by_name: dict[str, ToolResult]) -> Analysis:
    disk = by_name.get("get_disk_information")
    procs = by_name.get("get_running_processes")
    sysinfo = by_name.get("get_system_information")
    startup = by_name.get("get_startup_applications")
    evidence = [r.as_evidence_line() for r in (sysinfo, disk, procs, startup) if r]

    low = list((disk.extras.get("low_space") if disk else None) or [])
    if low:
        return Analysis(
            topic_id="disk_full",
            diagnosis="Storage is almost full",
            confidence=Confidence.LIKELY,
            evidence=evidence,
            probable_cause=f"Drive(s) {', '.join(str(x) for x in low)} have very little free space.",
        )

    # Slow computer with no disk issue: report top processes honestly, don't say reboot.
    if "slow" in case.problem.lower() or case.domain == "computer":
        return Analysis(
            topic_id="computer_slow" if "slow" in case.problem.lower() else "general_inspect",
            diagnosis="Computer snapshot",
            confidence=Confidence.POSSIBLE,
            evidence=evidence,
            probable_cause=procs.summary if procs and procs.summary else "I collected a health snapshot.",
            needs_user=None,
        )
    return _unknown("I collected system information but need a more specific symptom.")


def _analyze_audio(case: TroubleshootingCase, by_name: dict[str, ToolResult]) -> Analysis:
    audio = by_name.get("get_audio_information")
    evidence = [audio.as_evidence_line()] if audio else []
    if audio and audio.available and audio.extras.get("audio_service_running") is False:
        return Analysis(
            topic_id="audio_no_sound",
            diagnosis="Sound system is stopped",
            confidence=Confidence.CONFIRMED,
            evidence=evidence,
            probable_cause="Windows Audio is not running.",
            needs_user="I can describe this, but starting the service often needs administrator permission — say if you want guided steps.",
        )
    return Analysis(
        topic_id="audio_no_sound",
        diagnosis="Sound check finished",
        confidence=Confidence.POSSIBLE,
        evidence=evidence,
        probable_cause=audio.summary if audio else "Could not inspect audio.",
        needs_user="Please check the volume icon and mute key. I cannot see if headphones are unplugged unless Windows reports it.",
    )


def _analyze_bluetooth(case: TroubleshootingCase, by_name: dict[str, ToolResult]) -> Analysis:
    bt = by_name.get("get_bluetooth_information")
    evidence = [bt.as_evidence_line()] if bt else []
    running = bt.extras.get("bluetooth_service_running") if bt else None
    conf = Confidence.CONFIRMED if running is False else Confidence.POSSIBLE
    return Analysis(
        topic_id="bluetooth_problem",
        diagnosis="Bluetooth check finished",
        confidence=conf,
        evidence=evidence,
        probable_cause=bt.summary if bt else "Could not inspect Bluetooth.",
        needs_user="Turn Bluetooth on from the settings icon if you can. I cannot press that icon.",
    )


def _analyze_storage(case: TroubleshootingCase, by_name: dict[str, ToolResult]) -> Analysis:
    disk = by_name.get("get_disk_information")
    evidence = [disk.as_evidence_line()] if disk else []
    low = list((disk.extras.get("low_space") if disk else None) or [])
    if low:
        return Analysis(
            topic_id="disk_full",
            diagnosis="Storage is almost full",
            confidence=Confidence.CONFIRMED,
            evidence=evidence,
            probable_cause=f"Drive(s) {', '.join(str(x) for x in low)} are low on space.",
        )
    return Analysis(
        topic_id="disk_full",
        diagnosis="Storage check finished",
        confidence=Confidence.LIKELY if disk and disk.success else Confidence.UNKNOWN,
        evidence=evidence,
        probable_cause=disk.summary if disk else "Could not read disk space.",
    )


def _analyze_security(case: TroubleshootingCase, by_name: dict[str, ToolResult]) -> Analysis:
    sec = by_name.get("get_security_overview")
    startup = by_name.get("get_startup_applications")
    evidence = [r.as_evidence_line() for r in (sec, startup) if r]
    return Analysis(
        topic_id="security_warning",
        diagnosis="Security overview",
        confidence=Confidence.POSSIBLE,
        evidence=evidence,
        probable_cause=sec.summary if sec else "Limited security information.",
        needs_user="This is not a full virus scan. Use Windows Security if you still worry.",
    )


def _analyze_software(case: TroubleshootingCase, by_name: dict[str, ToolResult]) -> Analysis:
    procs = by_name.get("get_running_processes")
    events = by_name.get("get_event_logs")
    evidence = [r.as_evidence_line() for r in (procs, events) if r]
    return Analysis(
        topic_id="app_wont_start",
        diagnosis="Application check",
        confidence=Confidence.UNKNOWN,
        evidence=evidence,
        probable_cause="I need the program's name to match it against running processes and error reports.",
        needs_user="Which program won't open? Exact name helps.",
    )


def _analyze_hardware(case: TroubleshootingCase, by_name: dict[str, ToolResult]) -> Analysis:
    devs = by_name.get("get_device_information")
    usb = by_name.get("get_usb_devices")
    display = by_name.get("get_display_information")
    evidence = [r.as_evidence_line() for r in (devs, usb, display) if r]
    problems = int((devs.extras.get("problem_count") if devs else 0) or 0)
    conf = Confidence.LIKELY if problems else Confidence.POSSIBLE
    return Analysis(
        topic_id=None,
        diagnosis="Hardware device check",
        confidence=conf,
        evidence=evidence,
        probable_cause=(
            f"{problems} device(s) are not reporting OK."
            if problems
            else (display.summary if display else "Device list collected.")
        ),
        needs_user="I cannot see loose cables. If a keyboard/mouse is wireless, check its battery/dongle.",
    )
