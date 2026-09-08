"""Answer only what was asked — no extra repair pitches or disclaimer chatter."""

from __future__ import annotations

from yuwontlaykit.diagnostics.case import TroubleshootingCase
from yuwontlaykit.diagnostics.printer_status import (
    VIRTUAL_HINTS,
    classify_printers,
    format_online_answer,
    format_online_only_list,
    pick_recommended_printer,
    rows_and_ports_from_case,
)
from yuwontlaykit.knowledge.topics import get_topic
from yuwontlaykit.tools.base import Confidence
from yuwontlaykit.tools.runner import as_list

CONFIDENCE_LABEL = {
    Confidence.CONFIRMED: "High (confirmed by what I measured)",
    Confidence.LIKELY: "Medium-high (likely)",
    Confidence.POSSIBLE: "Medium (possible)",
    Confidence.UNKNOWN: "Low (not enough information yet)",
}


def explain(case: TroubleshootingCase) -> str:
    if str(case.extras.get("mode") or case.extras.get("intent") or "") == "inventory":
        return explain_inventory(case)

    topic = get_topic(case.topic_id) if case.topic_id else None
    plain = ""
    if topic:
        plain = str((topic.get("plain_language") or {}).get("problem") or "")
        solution = str((topic.get("plain_language") or {}).get("solution") or "")
    else:
        solution = ""

    problem = (case.problem or "").rstrip(" .")
    lines = [
        f"I looked at this as {case.case_id} — {problem}.",
        "",
        f"What I think is going on: {case.diagnosis or 'still investigating'}.",
        f"How sure I am: {CONFIDENCE_LABEL.get(case.confidence, case.confidence)}.",
    ]
    if plain:
        lines += ["", plain]
    elif case.probable_cause:
        lines += ["", case.probable_cause]
    if case.proposed:
        if solution:
            lines += ["", solution]
        else:
            lines += ["", f"I can {case.proposed.label}."]
        if case.proposed.user_impact:
            lines += [case.proposed.user_impact]
        lines += ["Would you like me to do that? (yes / no)"]
        case.awaiting = "remediate_consent"
    else:
        if solution:
            lines += ["", solution]
        if case.extras.get("needs_user"):
            lines += ["", str(case.extras["needs_user"])]
    return "\n".join(lines)


def explain_inventory(case: TroubleshootingCase) -> str:
    """Answer an inventory question with the list only."""
    lines_found = list(case.extras.get("printer_lines") or [])
    if lines_found:
        parts = ["Installed printers:"]
        parts.extend(f"  • {item}" for item in lines_found)
        return "\n".join(parts)
    if case.extras.get("needs_user"):
        return str(case.extras["needs_user"])
    return case.probable_cause or "Windows did not report any printers on this PC."


def explain_online_followup(
    case: TroubleshootingCase,
    *,
    reachability: dict[str, bool] | None = None,
    detailed: bool = False,
    list_only: bool = False,
) -> str:
    rows, ports = rows_and_ports_from_case(case)
    if not rows:
        return "I don't have a printer list yet. Ask me which printers are installed first."
    items = classify_printers(rows, ports, reachability=reachability or {})
    case.extras["readiness"] = [
        {"name": p.name, "bucket": p.bucket, "reason": p.reason} for p in items
    ]
    picked = pick_recommended_printer(items)
    if picked:
        case.extras["recommended_printer"] = picked.name
    if list_only:
        case.awaiting = None
        return format_online_only_list(items)
    text, offer = format_online_answer(items, detailed=detailed)
    if offer:
        case.awaiting = "offer_diagnose_offline"
        case.extras["diagnose_targets"] = [
            p.name for p in items if p.bucket in ("offline", "unknown")
        ]
    return text


def explain_offline_followup(
    case: TroubleshootingCase,
    *,
    reachability: dict[str, bool] | None = None,
) -> str:
    rows, ports = rows_and_ports_from_case(case)
    if not rows:
        return "I don't have a printer list yet. Ask me which printers are installed first."
    items = classify_printers(rows, ports, reachability=reachability or {})
    offline = [p for p in items if p.bucket == "offline"]
    if offline:
        names = ", ".join(p.name for p in offline)
        return f"Offline / unreachable: {names}."
    return "None look offline from what I can confirm right now."


def explain_default_followup(case: TroubleshootingCase) -> str:
    default = case.extras.get("default_printer")
    if default:
        return f"Default printer: {default}."
    rows, _ports = rows_and_ports_from_case(case)
    for row in rows:
        if row.get("Default") in (True, "True", "true"):
            return f"Default printer: {row.get('Name')}."
    return "Windows didn't report a default printer. You can say 'pick one' and I'll recommend which to use."


def explain_pick_followup(
    case: TroubleshootingCase,
    *,
    reachability: dict[str, bool] | None = None,
) -> str:
    rows, ports = rows_and_ports_from_case(case)
    if not rows:
        return "I don't have a printer list yet. Ask me which printers are installed first."
    items = classify_printers(rows, ports, reachability=reachability or {})
    picked = pick_recommended_printer(items)
    if not picked:
        return "I couldn't pick one from what Windows reported."
    extra = ""
    n = picked.name.lower()
    if any(token in n for token in ("pos", "receipt", "receift", "bill")):
        extra = " It's the only confirmed device I can recommend right now."
    elif picked.bucket == "online":
        extra = " It's online and looks like a regular printer."
    elif picked.bucket == "unknown":
        extra = " I couldn't fully confirm it's reachable, but it's the best desk printer on the list."
    return f"I'd use {picked.name}.{extra}"


def technical_details(case: TroubleshootingCase) -> str:
    if case.last_technical:
        return case.last_technical
    lines = [
        f"{case.case_id} technical details",
        f"Domain: {case.domain}",
        f"Diagnosis: {case.diagnosis} ({case.confidence.value})",
        "Evidence:",
    ]
    for line in case.evidence:
        lines.append(f"  • {line}")
    if not case.evidence:
        lines.append("  • (none recorded)")
    lines.append("Checks run:")
    for item in case.diagnostics:
        ran = "ran" if item.executed else "did not run"
        lines.append(f"  • {item.name} [{item.risk.value}] {ran}: {item.summary}")
    if case.actions_taken:
        lines.append("Actions:")
        for action in case.actions_taken:
            lines.append(f"  • {action}")
    return "\n".join(lines)


def _is_virtual_name(name: str) -> bool:
    n = (name or "").lower()
    return any(token in n for token in VIRTUAL_HINTS)
