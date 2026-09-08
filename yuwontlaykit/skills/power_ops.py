"""Confirm and carry out computer power actions."""

from __future__ import annotations

from yuwontlaykit.cli import console
from yuwontlaykit.diagnostics.consent import is_no, is_yes
from yuwontlaykit.engine.computer_commands import parse_computer_command
from yuwontlaykit.operations.safety import USER_ACTION_FAILURE, requires_confirmation
from yuwontlaykit.tools.registry import run_tool

_PROMPTS = {
    "shutdown_computer": (
        "I can shut down this PC. Any unsaved work may be lost.\n\n"
        "Do you want me to shut down the computer? (yes/no)"
    ),
    "restart_computer": (
        "I can restart this PC. Any unsaved work may be lost.\n\n"
        "Do you want me to restart the computer? (yes/no)"
    ),
    "lock_computer": "I can lock this PC. Do you want me to lock it? (yes/no)",
    "sleep_computer": (
        "I can put this PC to sleep. Do you want me to do that? (yes/no)"
    ),
    "logout_user": (
        "I can sign you out. Unsaved work may be lost. Do you want to sign out? (yes/no)"
    ),
}

_DONE = {
    "shutdown_computer": "Understood. I'm shutting down the PC now.",
    "restart_computer": "Understood. I'm restarting the PC now.",
    "lock_computer": "Okay. I'm locking the PC now.",
    "sleep_computer": "Okay. I'm putting the PC to sleep now.",
    "logout_user": "Okay. I'm signing you out now.",
}

_CANCELLED = {
    "shutdown_computer": "Okay. I won't shut it down.",
    "restart_computer": "Okay. I won't restart it.",
    "lock_computer": "Okay. I won't lock it.",
    "sleep_computer": "Okay. I won't put it to sleep.",
    "logout_user": "Okay. I won't sign you out.",
}


def matches(text: str, context: dict | None = None) -> bool:
    context = context or {}
    if context.get("awaiting_power_action") and (is_yes(text) or is_no(text)):
        return True
    command = parse_computer_command(text, context)
    return bool(command and command.category == "SYSTEM_POWER")


def handle(text: str, context: dict) -> str:
    if context.get("awaiting_power_action") and (is_yes(text) or is_no(text)):
        return _finish(text, context)
    command = parse_computer_command(text, context)
    if not command or command.category != "SYSTEM_POWER":
        return "What should I do with the PC?"
    intent = command.intent
    if requires_confirmation(intent):
        context["awaiting_power_action"] = True
        context["pending_power_action"] = intent
        return _PROMPTS.get(intent, "Do you want me to continue? (yes/no)")
    return _run(intent, context)


def _finish(text: str, context: dict) -> str:
    intent = str(context.get("pending_power_action") or "")
    context["awaiting_power_action"] = False
    context["pending_power_action"] = None
    if is_no(text):
        return _CANCELLED.get(intent, "Okay. I won't do that.")
    if not intent:
        return "I don't have a pending power action."
    return _run(intent, context)


def _run(intent: str, context: dict) -> str:
    console.print_status("Starting that now…")
    result = run_tool(intent, confirmed=True)
    if result is None or (not result.available and not result.executed):
        return USER_ACTION_FAILURE
    if result.success or result.extras.get("started"):
        return _DONE.get(intent, result.summary or "Done.")
    return USER_ACTION_FAILURE
