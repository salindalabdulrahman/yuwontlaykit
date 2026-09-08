"""Classify each turn before conversational context is applied."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from yuwontlaykit.diagnostics.intent import (
    clarification_suggestion,
    is_ip_followup,
    is_ip_lookup,
    is_printer_followup,
    is_printer_inventory_lookup,
    is_remove_printer,
)
from yuwontlaykit.diagnostics.summary import is_general_pc_check
from yuwontlaykit.engine.computer_commands import (
    parse_computer_command,
    suggest_computer_command,
)
from yuwontlaykit.skills.application_launch import resolve_application


class TurnRelation(str, Enum):
    NEW_INTENT = "new_intent"
    CONTEXT_CONTINUATION = "context_continuation"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class IntentDecision:
    relation: TurnRelation
    intent: str | None = None
    domain: str | None = None


def resolve_turn(text: str, context: dict, diagnostics: Any = None) -> IntentDecision:
    """Prefer a clear standalone request; use context only for true follow-ups."""
    command = parse_computer_command(text, context)
    if command:
        relation = (
            TurnRelation.CONTEXT_CONTINUATION
            if command.relation == "context_continuation"
            else TurnRelation.NEW_INTENT
        )
        return IntentDecision(relation, command.intent, _command_domain(command))
    if resolve_application(text):
        return IntentDecision(TurnRelation.NEW_INTENT, "open_application", "application")
    if is_ip_lookup(text):
        return IntentDecision(TurnRelation.NEW_INTENT, "get_ip_address", "network")
    if is_general_pc_check(text):
        return IntentDecision(
            TurnRelation.NEW_INTENT, "computer_diagnostic", "computer"
        )
    if is_remove_printer(text):
        return IntentDecision(TurnRelation.NEW_INTENT, "remove_printer", "printer")
    if is_printer_inventory_lookup(text):
        return IntentDecision(TurnRelation.NEW_INTENT, "list_printers", "printer")
    suggestion = suggest_computer_command(text, context)
    if suggestion:
        return IntentDecision(
            TurnRelation.AMBIGUOUS,
            "clarify_command",
            _command_domain(suggestion.command),
        )
    if clarification_suggestion(text):
        return IntentDecision(TurnRelation.AMBIGUOUS, "clarify")

    if is_printer_followup(text):
        return IntentDecision(
            TurnRelation.CONTEXT_CONTINUATION, "printer_followup", "printer"
        )
    if context.get("last_lookup") == "ip" and is_ip_followup(text):
        return IntentDecision(
            TurnRelation.CONTEXT_CONTINUATION, "ip_followup", "network"
        )
    if _looks_like_reference(text):
        active_domain = getattr(getattr(diagnostics, "active", None), "domain", None)
        return IntentDecision(
            TurnRelation.CONTEXT_CONTINUATION,
            "entity_followup",
            active_domain or context.get("active_domain"),
        )

    # Import locally to avoid a module-import cycle with the IT skill.
    from yuwontlaykit.skills.it_support import classify_domain

    domain = classify_domain(text)
    if domain:
        return IntentDecision(
            TurnRelation.NEW_INTENT, f"{domain}_request", domain
        )
    return IntentDecision(TurnRelation.UNKNOWN)


def apply_intent_transition(
    decision: IntentDecision,
    context: dict,
    diagnostics: Any = None,
) -> None:
    """Clear stale task state only when the user clearly starts another task."""
    context["turn_relation"] = decision.relation.value
    if decision.relation != TurnRelation.NEW_INTENT:
        return

    context["active_intent"] = decision.intent
    context["active_domain"] = decision.domain
    context["it_support_active"] = False
    context["printer_help_active"] = False
    context["awaiting_machine_scan"] = False
    context["awaiting_printer_fix"] = False
    context["pending_printer_error_id"] = None
    context["awaiting_it_diagnostic"] = False
    context["pending_it_domain"] = None
    context["pending_it_problem"] = None
    context["awaiting_remove_printer"] = False
    context["pending_remove_printer"] = None
    context["awaiting_clarification"] = False
    context["pending_clarification"] = None
    context["awaiting_close_application"] = False
    context["pending_close_application"] = None
    context["awaiting_restart_application"] = False
    context["pending_restart_application"] = None
    context["awaiting_power_action"] = False
    context["pending_power_action"] = None
    context["awaiting_search_choice"] = False
    if decision.intent != "get_ip_address":
        context["last_lookup"] = None
        context["last_ip_ok"] = False

    active = getattr(diagnostics, "active", None)
    if active is not None:
        active.awaiting = None


def _looks_like_reference(text: str) -> bool:
    t = text.lower().strip()
    return bool(
        re.search(
            r"^(?:what|how)\s+about\b"
            r"|^(?:that|this|the)\s+one\b"
            r"|\bunit\s*\d+\b"
            r"|^(?:it|that|this)\??$",
            t,
        )
    )


def _command_domain(command: Any) -> str:
    mapping = {
        "APPLICATION_MANAGEMENT": "application",
        "FILE_MANAGEMENT": "file",
        "FOLDER_MANAGEMENT": "folder",
        "SYSTEM_POWER": "power",
    }
    return mapping.get(command.category, command.category.lower())
