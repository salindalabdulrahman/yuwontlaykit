"""Recognize and carry out application management from natural language."""

from __future__ import annotations

from yuwontlaykit.cli import console
from yuwontlaykit.diagnostics.consent import is_no, is_yes
from yuwontlaykit.engine.computer_commands import parse_computer_command
from yuwontlaykit.knowledge.app_catalog import display_name
from yuwontlaykit.operations.safety import USER_ACTION_FAILURE, requires_confirmation
from yuwontlaykit.tools.base import ToolResult
from yuwontlaykit.tools.registry import run_tool
from yuwontlaykit.tools.runner import as_list


def resolve_application(text: str) -> str | None:
    command = parse_computer_command(text, {})
    if command and command.intent == "open_application" and command.entity:
        return command.entity
    return None


def matches(text: str, context: dict | None = None) -> bool:
    command = parse_computer_command(text, context or {})
    return bool(command and command.category == "APPLICATION_MANAGEMENT")


def handle(text: str, context: dict | None = None) -> str:
    context = context if context is not None else {}
    if context.get("awaiting_close_application") and (is_yes(text) or is_no(text)):
        return _finish_close(text, context)
    if context.get("awaiting_restart_application") and (is_yes(text) or is_no(text)):
        return _finish_restart(text, context)

    command = parse_computer_command(text, context)
    if not command or command.category != "APPLICATION_MANAGEMENT":
        return "Which application should I use?"

    if command.intent == "list_running_applications":
        return _list_running(command.extras.get("top_by"))
    if command.intent == "check_application":
        return _check(command.entity, context)
    if command.intent == "close_application":
        return _offer_close(command.entity, context)
    if command.intent == "restart_application":
        return _offer_restart(command.entity, context)
    return _open(command.entity, context)


def _open(app_id: str | None, context: dict) -> str:
    if not app_id:
        return "Which application would you like me to open?"
    label = display_name(app_id)
    console.print_assistant(f"Sure — I'll open {label} for you.")
    console.print_status(f"Checking for {label}…")
    console.print_status(f"Starting {label}…")
    console.print_status("Verifying the application…")
    result = run_tool("open_application", confirmed=True, application=app_id)
    if _tool_failed_hard(result):
        return USER_ACTION_FAILURE
    if result.extras.get("started") and result.success:
        _remember_app(context, app_id)
        return f"{label} is open. 🟢"
    if result.extras.get("installed"):
        return (
            f"I found {label}, but I couldn't start it. "
            "I can investigate why if you'd like."
        )
    return (
        f"I couldn't find {label} installed on this PC.\n\n"
        "If you'd like, I can check whether it's installed in another location "
        "or help you install it."
    )


def _offer_close(app_id: str | None, context: dict) -> str:
    app_id = app_id or context.get("last_application")
    if not app_id:
        return "Which application should I close?"
    label = display_name(app_id)
    if requires_confirmation("close_application"):
        context["awaiting_close_application"] = True
        context["pending_close_application"] = app_id
        _remember_app(context, app_id)
        return (
            f"That would close {label}. Any unsaved work could be lost. "
            "Do you want me to close it? (yes/no)"
        )
    return _close_now(app_id, context)


def _finish_close(text: str, context: dict) -> str:
    app_id = str(context.get("pending_close_application") or "")
    context["awaiting_close_application"] = False
    context["pending_close_application"] = None
    if is_no(text):
        return "Okay. I'll leave it open."
    if not app_id:
        return "Which application should I close?"
    return _close_now(app_id, context)


def _close_now(app_id: str, context: dict) -> str:
    label = display_name(app_id)
    console.print_status(f"Closing {label}…")
    result = run_tool("close_application", confirmed=True, application=app_id)
    if _tool_failed_hard(result):
        return USER_ACTION_FAILURE
    if result.extras.get("closed") or (
        result.success and not result.extras.get("running")
    ):
        _remember_app(context, app_id)
        if "was not running" in (result.summary or "").lower():
            return f"{label} wasn't open."
        return f"{label} is closed."
    return f"I tried to close {label}, but it still appears to be running."


def _offer_restart(app_id: str | None, context: dict) -> str:
    if not app_id:
        return "Which application should I restart?"
    label = display_name(app_id)
    context["awaiting_restart_application"] = True
    context["pending_restart_application"] = app_id
    _remember_app(context, app_id)
    return (
        f"I'll close {label} and open it again. Unsaved work could be lost. "
        "Do you want me to restart it? (yes/no)"
    )


def _finish_restart(text: str, context: dict) -> str:
    app_id = str(context.get("pending_restart_application") or "")
    context["awaiting_restart_application"] = False
    context["pending_restart_application"] = None
    if is_no(text):
        return "Okay. I'll leave it as it is."
    if not app_id:
        return "Which application should I restart?"
    label = display_name(app_id)
    console.print_status(f"Restarting {label}…")
    close_result = run_tool("close_application", confirmed=True, application=app_id)
    if _tool_failed_hard(close_result):
        return USER_ACTION_FAILURE
    return _open(app_id, context)


def _check(app_id: str | None, context: dict) -> str:
    if not app_id:
        return "Which application should I check?"
    label = display_name(app_id)
    result = run_tool("application_running", application=app_id)
    if _tool_failed_hard(result):
        return USER_ACTION_FAILURE
    _remember_app(context, app_id)
    if result.extras.get("running"):
        return f"Yes — {label} is running."
    return f"No — {label} isn't running right now."


def _list_running(top_by: str | None) -> str:
    result = run_tool("list_running_applications")
    if _tool_failed_hard(result):
        return USER_ACTION_FAILURE
    rows = as_list(result.data)
    if not rows:
        return "I don't see any applications with an open window right now."
    if top_by == "cpu":
        rows = sorted(rows, key=lambda row: float(row.get("CPU") or 0), reverse=True)
        top = rows[0]
        name = top.get("MainWindowTitle") or top.get("Name") or "an application"
        return f"{name} is using the most CPU among the open windows I can see."
    if top_by == "memory":
        rows = sorted(
            rows, key=lambda row: float(row.get("WorkingSet") or 0), reverse=True
        )
        top = rows[0]
        name = top.get("MainWindowTitle") or top.get("Name") or "an application"
        return f"{name} is using the most memory among the open windows I can see."
    lines = ["These applications currently have an open window:"]
    for row in rows[:12]:
        title = str(row.get("MainWindowTitle") or "").strip()
        name = str(row.get("Name") or "app").strip()
        lines.append(f"- {title} ({name})" if title and title != name else f"- {name}")
    return "\n".join(lines)


def _remember_app(context: dict, app_id: str) -> None:
    context["last_application"] = app_id
    context["last_referent"] = {
        "type": "application",
        "application": app_id,
        "display": display_name(app_id),
    }


def _tool_failed_hard(result: ToolResult) -> bool:
    if result is None:
        return True
    return bool(result.error and not result.available and not result.executed)
