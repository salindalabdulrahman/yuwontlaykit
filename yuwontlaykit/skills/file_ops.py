"""Search and open files or folders from natural language."""

from __future__ import annotations

from yuwontlaykit.cli import console
from yuwontlaykit.engine.computer_commands import choice_index, parse_computer_command
from yuwontlaykit.operations.safety import USER_ACTION_FAILURE
from yuwontlaykit.tools.base import ToolResult
from yuwontlaykit.tools.registry import run_tool
from yuwontlaykit.tools.runner import as_list


def matches(text: str, context: dict | None = None) -> bool:
    context = context or {}
    if context.get("awaiting_search_choice") and choice_index(text) is not None:
        return True
    command = parse_computer_command(text, context)
    return bool(
        command
        and command.category in {"FILE_MANAGEMENT", "FOLDER_MANAGEMENT"}
    )


def handle(text: str, context: dict) -> str:
    if context.get("awaiting_search_choice") and choice_index(text) is not None:
        return _choose(text, context)

    command = parse_computer_command(text, context)
    if not command:
        return "What file or folder should I look for?"

    if command.intent in {"open_file", "open_folder"} and command.kind == "known_folder":
        return _open_known_folder(str(command.entity or ""), context)
    if command.intent in {"open_file", "open_folder"} and command.entity:
        return _open_path(str(command.entity), context, command.display)
    if command.intent in {"search_file", "search_folder"}:
        return _search(command, context)
    return "What file or folder should I look for?"


def _search(command, context: dict) -> str:
    query = (command.query or "").strip()
    kind = command.kind or "file"
    if not query:
        if kind == "image":
            return (
                "I can look for an image file by name, or you can share the image "
                "if you want me to look at it. What is the image named?"
            )
        if kind == "folder":
            return "Which folder should I look for?"
        return "What file should I look for?"

    console.print_status("I'll search your common folders for it.")
    result = run_tool("search_user_files", query=query, kind=kind)
    if _tool_failed_hard(result):
        return USER_ACTION_FAILURE
    matches = as_list(result.extras.get("matches") or result.data)
    if not matches:
        label = "folders" if kind == "folder" else "files"
        return f"I didn't find any {label} matching '{query}' in your usual folders."

    context["search_results"] = matches
    if len(matches) == 1:
        item = matches[0]
        _remember_item(context, item)
        context["awaiting_search_choice"] = False
        if command.open_after or command.intent.startswith("open"):
            return _open_path(item["path"], context, item.get("name"))
        noun = "folder" if item.get("kind") == "folder" else "file"
        return f"I found {item.get('name')}."

    lines = [
        f"I found {len(matches)} {('folders' if kind == 'folder' else 'files')} matching '{query}':"
    ]
    for index, item in enumerate(matches, start=1):
        lines.append(f"{index}. {item.get('name')}")
    lines.append("Which one should I open?")
    context["awaiting_search_choice"] = True
    return "\n".join(lines)


def _choose(text: str, context: dict) -> str:
    results = list(context.get("search_results") or [])
    index = choice_index(text)
    if index is None or not results:
        context["awaiting_search_choice"] = False
        return "Tell me which file or folder you want."
    if index == -1:
        index = len(results) - 1
    if index < 0 or index >= len(results):
        return "I only have the matches I just listed. Which number should I open?"
    item = results[index]
    context["awaiting_search_choice"] = False
    console.print_assistant("Opening it.")
    return _open_path(item.get("path", ""), context, item.get("name"))


def _open_known_folder(name: str, context: dict) -> str:
    located = run_tool("resolve_known_folder", name=name)
    if _tool_failed_hard(located) or not located.success:
        return f"I couldn't find your {name} folder."
    path = str(located.extras.get("path") or "")
    return _open_path(path, context, name)


def _open_path(path: str, context: dict, display: str | None) -> str:
    if not path:
        return "I don't have a file or folder to open yet."
    label = display or path
    console.print_status(f"Opening {label}…")
    result = run_tool("open_path", confirmed=True, path=path)
    if _tool_failed_hard(result):
        return USER_ACTION_FAILURE
    kind = "folder" if _looks_like_folder(path, display) else "file"
    _remember_item(context, {"name": label, "path": path, "kind": kind})
    if result.success or result.extras.get("opened"):
        return f"{label} is open."
    return f"I found {label}, but I couldn't open it."


def _remember_item(context: dict, item: dict) -> None:
    kind = item.get("kind") or "file"
    path = item.get("path")
    if kind == "folder":
        context["last_folder"] = path
    else:
        context["last_file"] = path
    context["last_referent"] = {
        "type": kind,
        "path": path,
        "display": item.get("name") or path,
    }


def _looks_like_folder(path: str, display: str | None) -> bool:
    if display in {"Downloads", "Documents", "Desktop", "Pictures", "Videos", "Home"}:
        return True
    return not bool(display and "." in str(display) and not str(display).startswith("."))


def _tool_failed_hard(result: ToolResult) -> bool:
    return bool(result is None or (not result.available and not result.executed))
