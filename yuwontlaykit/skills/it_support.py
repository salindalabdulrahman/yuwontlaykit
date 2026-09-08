"""IT support skill — classify a problem, run diagnostics, speak plainly.

This is the user-facing entry for printer / Wi-Fi / computer / software /
hardware help. Personality stays in the wording; the thinking lives in
``diagnostics``.
"""

from __future__ import annotations

import re

from yuwontlaykit.cli import console
from yuwontlaykit.diagnostics.capabilities import format_inventory
from yuwontlaykit.diagnostics.consent import is_explicit_yes, is_no, is_yes, normalize
from yuwontlaykit.diagnostics.engine import DiagnosticEngine
from yuwontlaykit.diagnostics.explain import (
    explain_default_followup,
    explain_offline_followup,
    explain_online_followup,
    explain_pick_followup,
)
from yuwontlaykit.diagnostics.intent import (
    clarification_suggestion,
    classify_intent,
    is_ip_followup,
    is_ip_lookup,
    is_printer_followup,
    is_remove_printer,
    is_why_followup,
)
from yuwontlaykit.diagnostics.ip_lookup import format_ip_lookup
from yuwontlaykit.diagnostics.printer_status import refresh_reachability, rows_and_ports_from_case
from yuwontlaykit.diagnostics.summary import (
    format_computer_health_summary,
    format_network_connection_summary,
    format_printer_diagnostic_summary,
    is_general_pc_check,
    is_network_connection_check,
)
from yuwontlaykit.knowledge.printer_errors import find_error
from yuwontlaykit.skills import (
    computer_help,
    hardware_help,
    network_help,
    printer_domain,
    security_help,
    software_help,
    storage_help,
    windows_help,
)
from yuwontlaykit.tools.base import ToolResult
from yuwontlaykit.tools.registry import run_tool
from yuwontlaykit.tools.runner import as_list
from yuwontlaykit.tools.validate import is_safe_printer_name

# Order matters: more specific domains first.
_DOMAIN_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (printer_domain.DOMAIN, printer_domain.HINTS),
    (network_help.WIFI_DOMAIN, network_help.WIFI_HINTS),
    (hardware_help.AUDIO_DOMAIN, hardware_help.AUDIO_HINTS),
    (hardware_help.BLUETOOTH_DOMAIN, hardware_help.BLUETOOTH_HINTS),
    (storage_help.DOMAIN, storage_help.HINTS),
    (security_help.DOMAIN, security_help.HINTS),
    (software_help.DOMAIN, software_help.HINTS),
    (network_help.NETWORK_DOMAIN, network_help.NETWORK_HINTS),
    (hardware_help.HARDWARE_DOMAIN, hardware_help.HARDWARE_HINTS),
    (windows_help.DOMAIN, windows_help.HINTS),
    (computer_help.DOMAIN, computer_help.HINTS),
)

CAPABILITY_PHRASES = (
    "what can you check",
    "what can you inspect",
    "your capabilities",
    "can you really",
)

TECHNICAL_PHRASES = (
    "technical details",
    "tech details",
    "show evidence",
    "technical detail",
)

HISTORY_PHRASES = (
    "troubleshooting history",
    "past cases",
    "previous cases",
    "case history",
)

DIAGNOSTIC_OFFERS = {
    "printer": (
        "Got it. I can check that for you.\n"
        "I'll first inspect the printer, connection, queue,\n"
        "and Windows Print Spooler without changing anything.\n\n"
        "Want me to run a quick diagnostic? (yes / no)"
    ),
    "wifi": (
        "Got it. I can check your Wi-Fi for you.\n"
        "I'll inspect the adapter, connection, and internet path without changing anything.\n\n"
        "Want me to run a quick diagnostic? (yes / no)"
    ),
    "network": (
        "Got it. I can check the network/internet for you.\n"
        "I'll inspect connectivity and name lookup without changing anything.\n\n"
        "Want me to run a quick diagnostic? (yes / no)"
    ),
    "computer": (
        "Sure — let me check it for you.\n"
        "I'll look at system load, storage, and busy programs without changing anything.\n\n"
        "Want me to run a quick diagnostic? (yes / no)"
    ),
}


def classify_domain(text: str) -> str | None:
    t = text.lower()
    if is_ip_lookup(text):
        return "network"
    if is_printer_followup(text) or is_remove_printer(text):
        return "printer"
    for domain, needles in _DOMAIN_PATTERNS:
        for needle in needles:
            if needle in t:
                return domain
    if re.search(r"\b(broken|not working|isn't working|isnt working|won't work)\b", t):
        if "print" in t:
            return "printer"
        if any(w in t for w in ("wifi", "wi-fi", "internet", "network")):
            return "network"
        if any(w in t for w in ("computer", "laptop", "pc")):
            return "computer"
    return None


def matches(text: str, context: dict, engine: DiagnosticEngine | None = None) -> bool:
    t = normalize(text)
    command = None
    try:
        from yuwontlaykit.engine.computer_commands import parse_computer_command

        command = parse_computer_command(text, context)
    except Exception:
        command = None
    if command and command.category in {
        "APPLICATION_MANAGEMENT",
        "FILE_MANAGEMENT",
        "FOLDER_MANAGEMENT",
        "SYSTEM_POWER",
    }:
        return False
    try:
        from yuwontlaykit.engine.computer_commands import suggest_computer_command

        if suggest_computer_command(text, context):
            return False
    except Exception:
        pass
    if is_general_pc_check(text):
        return True
    if context.get("awaiting_clarification") and (is_yes(text) or is_no(text)):
        return True
    if clarification_suggestion(text):
        return True
    if any(p in t for p in TECHNICAL_PHRASES + CAPABILITY_PHRASES + HISTORY_PHRASES):
        return True
    if context.get("awaiting_remove_printer") and (is_yes(text) or is_no(text)):
        return True
    if is_remove_printer(text):
        return True
    if context.get("awaiting_it_diagnostic") and (is_yes(text) or is_no(text)):
        return True
    if engine and engine.active and engine.active.awaiting in (
        "remediate_consent",
        "offer_diagnose_offline",
    ):
        if engine.active.awaiting == "offer_diagnose_offline":
            if is_explicit_yes(text) or is_no(text):
                return True
        elif is_yes(text) or is_no(text):
            return True
        return classify_domain(text) is not None or is_printer_followup(text)
    if engine and engine.active and is_printer_followup(text):
        return True
    if context.get("it_support_active") and is_printer_followup(text):
        return True
    if context.get("it_support_active") and t in {"status", "what's wrong", "whats wrong"}:
        return True
    if is_ip_lookup(text):
        return True
    if context.get("last_lookup") == "ip" and is_ip_followup(text):
        return True
    return classify_domain(text) is not None


def handle(text: str, context: dict, engine: DiagnosticEngine) -> str:
    t = normalize(text)
    if context.get("awaiting_clarification"):
        suggestion = context.get("pending_clarification")
        if is_yes(text):
            context["awaiting_clarification"] = False
            context["pending_clarification"] = None
            if suggestion == "printer_inventory":
                text = "list installed printers on this PC"
                t = normalize(text)
        elif is_no(text):
            context["awaiting_clarification"] = False
            context["pending_clarification"] = None
            return "Okay. Tell me what you want me to display, and I'll check that instead."

    suggestion = clarification_suggestion(text)
    if suggestion:
        context["awaiting_clarification"] = True
        context["pending_clarification"] = suggestion
        return (
            "Wait — I'm a bit confused by that.\n"
            "Did you mean: list the printers installed on this PC? (yes / no)"
        )

    # A general health check is read-only, so it can run immediately. Keep
    # consent prompts for actual repairs and changes.
    if is_general_pc_check(text):
        context["awaiting_it_diagnostic"] = False
        context["pending_it_domain"] = None
        context["pending_it_problem"] = None
        if engine.active:
            engine.active.awaiting = None
        console.print_status("I'll check it for you.")
        case = engine.start_case(text.strip(), "computer", intent="problem")
        return _run_problem_case(
            case,
            engine,
            consented=True,
            user_name=str(context.get("user_name") or "Nikko"),
        )

    if is_ip_lookup(text) or (
        context.get("last_lookup") == "ip" and is_ip_followup(text)
    ):
        context["awaiting_it_diagnostic"] = False
        context["pending_it_domain"] = None
        context["pending_it_problem"] = None
        retry = bool(context.get("last_lookup") == "ip" and is_ip_followup(text))
        return _show_ip_address(
            engine,
            context,
            retry=retry,
            explain=is_why_followup(text),
        )

    if context.get("awaiting_remove_printer"):
        if is_yes(text):
            name = str(context.get("pending_remove_printer") or "")
            context["awaiting_remove_printer"] = False
            context["pending_remove_printer"] = None
            return _remove_printer_now(engine, name)
        if is_no(text):
            context["awaiting_remove_printer"] = False
            context["pending_remove_printer"] = None
            return "Okay — I won't remove it."

    context["it_support_active"] = True

    if is_remove_printer(text):
        if engine.active:
            engine.active.awaiting = None
        return _offer_remove_printer(text, context, engine)

    if any(p in t for p in CAPABILITY_PHRASES):
        return format_inventory()

    if any(p in t for p in TECHNICAL_PHRASES):
        return engine.technical()

    if any(p in t for p in HISTORY_PHRASES):
        return _format_history(engine)

    active = engine.active
    if active and active.awaiting == "remediate_consent":
        if is_yes(text):
            active.awaiting = None
            return engine.apply_proposed(active)
        if is_no(text):
            return engine.cancel_pending()
        return "Say yes and I'll make that change, or no to skip."

    if active and active.awaiting == "offer_diagnose_offline":
        if is_explicit_yes(text):
            active.awaiting = None
            targets = active.extras.get("diagnose_targets") or []
            focus = targets[0] if targets else "the offline printers"
            case = engine.start_case(
                f"diagnose why {focus} is not responding",
                "printer",
                intent="problem",
            )
            return _run_problem_case(
                case,
                engine,
                consented=True,
                user_name=str(context.get("user_name") or "Nikko"),
            )
        if is_no(text):
            active.awaiting = None
            return "Okay."

    # Consent gate for a pending diagnostic
    if context.get("awaiting_it_diagnostic"):
        if is_yes(text):
            domain = context.get("pending_it_domain") or "printer"
            problem = context.get("pending_it_problem") or text
            context["awaiting_it_diagnostic"] = False
            context["pending_it_domain"] = None
            context["pending_it_problem"] = None
            case = engine.start_case(str(problem), str(domain), intent="problem")
            console.print_status("Alright. Running a read-only check...")
            return _run_problem_case(
                case,
                engine,
                consented=True,
                user_name=str(context.get("user_name") or "Nikko"),
            )
        if is_no(text):
            context["awaiting_it_diagnostic"] = False
            context["pending_it_domain"] = None
            context["pending_it_problem"] = None
            return "Okay — I won't run a check. Tell me whenever you're ready."
        # New problem statement while waiting — restart offer
        domain = classify_domain(text)
        if domain:
            return _offer_diagnostic(text, domain, context)

    intent = classify_intent(text)
    if intent.startswith("followup_"):
        if active:
            active.awaiting = None
        if active and active.domain == "printer" and (
            active.extras.get("printer_rows") or active.extras.get("printer_lines")
        ):
            return _answer_followup(intent, active)
        case = engine.start_case(text.strip(), "printer", intent="inventory")
        engine.inspect(case, progress=lambda label: console.print_status(label + "…"))
        engine.analyze(case)
        return _answer_followup(intent, case)

    domain = classify_domain(text)
    if domain is None and active:
        domain = active.domain
    if domain is None:
        return (
            "I can help with printers, Wi-Fi, internet, a slow computer, sound, "
            "Bluetooth, storage, apps, or a general check. Tell me what's going wrong."
        )

    # Inventory questions still answer immediately
    if intent == "inventory":
        case = engine.start_case(text.strip(), domain, intent=intent)
        engine.inspect(case, progress=lambda label: console.print_status(label + "…"))
        engine.analyze(case)
        return engine.explain(case)

    # Read-only diagnostics run immediately. Consent is still required later
    # if a proposed action would change the computer.
    context["awaiting_it_diagnostic"] = False
    context["pending_it_domain"] = None
    context["pending_it_problem"] = None
    console.print_status("I'll check it for you.")
    case = engine.start_case(text.strip(), domain, intent="problem")
    return _run_problem_case(
        case,
        engine,
        consented=True,
        user_name=str(context.get("user_name") or "Nikko"),
    )


def _show_ip_address(
    engine: DiagnosticEngine,
    context: dict | None = None,
    *,
    retry: bool = False,
    explain: bool = False,
) -> str:
    if retry:
        console.print_status("Checking the network interfaces again.")
    else:
        console.print_status("Sure — let me check the network interfaces.")
    net = engine._run("get_network_information")
    sysinfo = engine._run("get_system_information")
    reply = format_ip_lookup(net, sysinfo)
    ok = "local IP address is" in reply
    if context is not None:
        context["last_lookup"] = "ip"
        context["last_ip_ok"] = ok
    if explain and not ok:
        extra = _explain_ip_miss(net)
        if extra and extra not in reply:
            reply = reply + "\n\n" + extra
    return reply


def _explain_ip_miss(net: ToolResult) -> str:
    if not net.available:
        return (
            "I need Windows PowerShell to read this PC's adapters, "
            "and that wasn't available from here."
        )
    data = net.data if isinstance(net.data, dict) else {}
    adapters = [a for a in as_list(data.get("adapters")) if isinstance(a, dict)]
    ips = [r for r in as_list(data.get("ip")) if isinstance(r, dict)]
    parts = []
    if adapters:
        names = [str(a.get("Name") or "unnamed") for a in adapters]
        parts.append("I can see adapter(s): " + ", ".join(names[:6]) + ".")
    else:
        parts.append("Windows didn't return any network adapters.")
    usable = any(
        str(r.get("IPv4") or r.get("IPAddress") or "").strip()
        and not str(r.get("IPv4") or r.get("IPAddress") or "").startswith(("127.", "169.254."))
        for r in ips
    )
    if ips and not usable:
        parts.append("The addresses I saw were loopback or unused, so I didn't treat them as your PC IP.")
    elif not ips:
        parts.append("No IPv4 addresses came back on those adapters.")
    parts.append("That's why I couldn't show you an address. Say retry and I'll check again.")
    return " ".join(parts)


_STATUS_TAIL = re.compile(
    r"\s*[—\-]\s*(Online|Offline|Status unknown)\s*$",
    re.IGNORECASE,
)
_EMOJI_MARK = re.compile(r"[🟢🔴🟡]")


def _known_printer_names(engine: DiagnosticEngine) -> list[str]:
    names: list[str] = []
    active = engine.active
    if active:
        for row in active.extras.get("printer_rows") or []:
            if isinstance(row, dict) and row.get("Name"):
                names.append(str(row["Name"]))
        for item in active.extras.get("readiness") or []:
            if isinstance(item, dict) and item.get("name"):
                names.append(str(item["name"]))
        rec = active.extras.get("recommended_printer")
        if rec:
            names.append(str(rec))
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def _extract_printer_name(text: str, known: list[str]) -> str | None:
    cleaned = _EMOJI_MARK.sub("", text)
    cleaned = _STATUS_TAIL.sub("", cleaned)
    lower = cleaned.lower()
    for name in sorted(known, key=len, reverse=True):
        if name.lower() in lower:
            return name
    return None


def _offer_remove_printer(text: str, context: dict, engine: DiagnosticEngine) -> str:
    known = _known_printer_names(engine)
    if not known:
        printers = engine._run("get_printers")
        if printers.success and printers.data is not None:
            known = [
                str(row.get("Name"))
                for row in as_list(printers.data)
                if isinstance(row, dict) and row.get("Name")
            ]
            if engine.active is None:
                engine.start_case(text.strip(), "printer", intent="inventory")
            if engine.active is not None:
                engine.active.extras["printer_rows"] = [
                    r for r in as_list(printers.data) if isinstance(r, dict)
                ]
    name = _extract_printer_name(text, known)
    if not name:
        if known:
            listed = ", ".join(known[:8])
            return (
                "Which printer should I remove? Tell me the exact name.\n"
                f"Installed: {listed}."
            )
        return "Which printer should I remove? Tell me the exact name."
    if not is_safe_printer_name(name):
        return "That printer name isn't something I can safely remove."
    context["awaiting_remove_printer"] = True
    context["pending_remove_printer"] = name
    context["awaiting_it_diagnostic"] = False
    return (
        f"I can remove {name} from this PC.\n"
        "That deletes it from Windows — it won't print from here until it's added again.\n\n"
        "Want me to remove it? (yes / no)"
    )


def _remove_printer_now(engine: DiagnosticEngine, name: str) -> str:
    if not name or not is_safe_printer_name(name):
        return "I don't have a safe printer name to remove."
    console.print_status(f"Removing {name}…")
    result = engine._run("remove_printer", confirmed=True, printer_name=name)
    if result.success and result.executed:
        if engine.active:
            rows = [
                r
                for r in (engine.active.extras.get("printer_rows") or [])
                if isinstance(r, dict) and str(r.get("Name")) != name
            ]
            engine.active.extras["printer_rows"] = rows
        return f"Done. {name} is no longer installed on this PC."
    return result.summary or result.error or f"I wasn't able to remove {name}."


def _offer_diagnostic(text: str, domain: str, context: dict) -> str:
    context["awaiting_it_diagnostic"] = True
    context["pending_it_domain"] = domain
    context["pending_it_problem"] = text.strip()
    return DIAGNOSTIC_OFFERS.get(
        domain,
        (
            "Got it. I can check that for you without changing anything.\n\n"
            "Want me to run a quick diagnostic? (yes / no)"
        ),
    )


def _run_problem_case(
    case,
    engine: DiagnosticEngine,
    *,
    consented: bool,
    user_name: str = "Nikko",
) -> str:
    def progress(label: str) -> None:
        console.print_status(label + "…")

    engine.inspect(case, progress=progress)
    reach = {}
    if case.domain == "printer":
        # Prefer the engine registry (tests/mocks) when present
        def ping(host: str) -> bool:
            result = engine._run("test_network_connectivity", host=host)
            return bool(result.extras.get("reachable"))

        reach = _refresh_reachability_only(case, ping=ping)
        # Copy printer rows into extras for summary/follow-ups
        by_name = case.results_by_name()
        printers = by_name.get("get_printers") or by_name.get("get_printer_status")
        if printers and printers.data is not None:
            case.extras["printer_rows"] = [
                r for r in as_list(printers.data) if isinstance(r, dict)
            ]
        ports = by_name.get("get_printer_port")
        if ports and isinstance(ports.data, dict):
            case.extras["printer_ports"] = [
                p for p in as_list(ports.data.get("ports")) if isinstance(p, dict)
            ]
    engine.analyze(case)

    if case.domain == "printer":
        return format_printer_diagnostic_summary(case, reachability=reach)

    if case.domain == "computer" and is_general_pc_check(case.problem):
        return format_computer_health_summary(case, user_name=user_name)

    if case.domain in ("wifi", "network") and is_network_connection_check(
        case.problem
    ):
        return format_network_connection_summary(case)

    body = engine.explain(case)
    extra = _physical_printer_tips(case.problem, case.domain, "problem")
    if extra:
        body = body + "\n\n" + extra
    return body


def _answer_followup(intent: str, case) -> str:
    if intent == "followup_online":
        return _answer_online_status(case, detailed=False)
    if intent == "followup_online_list":
        return _answer_online_status(case, detailed=False, list_only=True)
    if intent == "followup_offline":
        reach = _refresh_printer_snapshot(case)
        return explain_offline_followup(case, reachability=reach)
    if intent == "followup_default":
        _refresh_printer_snapshot(case)
        return explain_default_followup(case)
    if intent == "followup_pick":
        reach = _refresh_reachability_only(case)
        return explain_pick_followup(case, reachability=reach)
    return "Ask me which printers are installed, which is online, or which is default."


def _answer_online_status(case, *, detailed: bool, list_only: bool = False) -> str:
    console.print_status("Checking which printers are actually reachable…")
    reach = _refresh_printer_snapshot(case)
    return explain_online_followup(
        case,
        reachability=reach,
        detailed=detailed,
        list_only=list_only,
    )


def _refresh_printer_snapshot(case) -> dict[str, bool]:
    printers = run_tool("get_printers")
    ports = run_tool("get_printer_port")
    if printers.success and printers.data is not None:
        rows = [r for r in as_list(printers.data) if isinstance(r, dict)]
        case.extras["printer_rows"] = rows
        case.diagnostics.append(printers)
    if ports.success and isinstance(ports.data, dict):
        port_rows = [p for p in as_list(ports.data.get("ports")) if isinstance(p, dict)]
        case.extras["printer_ports"] = port_rows
        case.diagnostics.append(ports)
    return _refresh_reachability_only(case)


def _refresh_reachability_only(case, ping=None) -> dict[str, bool]:
    rows, port_rows = rows_and_ports_from_case(case)
    if not port_rows:
        ports = run_tool("get_printer_port")
        if ports.success and isinstance(ports.data, dict):
            port_rows = [p for p in as_list(ports.data.get("ports")) if isinstance(p, dict)]
            case.extras["printer_ports"] = port_rows
            case.diagnostics.append(ports)
            rows, port_rows = rows_and_ports_from_case(case)

    if ping is None:
        def ping(host: str) -> bool:
            result = run_tool("test_network_connectivity", host=host)
            return bool(result.extras.get("reachable"))

    return refresh_reachability(rows, port_rows, ping)


def _physical_printer_tips(text: str, domain: str, intent: str = "problem") -> str:
    if domain != "printer" or intent == "inventory" or intent.startswith("followup_"):
        return ""
    err = find_error(text)
    if not err:
        return ""
    steps = "\n".join(f"  {i}. {step}" for i, step in enumerate(err["physical_steps"], 1))
    return f"Hands-on (I cannot do these for you) — {err['title']}:\n{steps}"


def _format_history(engine: DiagnosticEngine) -> str:
    rows = engine.history.recent(8)
    if not rows:
        return "I don't have any troubleshooting cases stored yet in this session."
    lines = ["Recent troubleshooting cases:"]
    for case in rows:
        lines.append(
            f"  • {case.case_id} ({case.created_at[:10] if case.created_at else ''}) "
            f"{case.problem} → {case.diagnosis or 'in progress'} "
            f"[{case.result or 'open'}]"
        )
    return "\n".join(lines)
