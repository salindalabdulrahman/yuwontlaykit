"""Parse natural-language computer commands into intent + entity.

This is not a per-phrase keyword list. Verbs select the capability;
aliases and conversation context select the entity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from yuwontlaykit.knowledge.app_catalog import display_name, resolve_app_id

_PRONOUNS = {
    "it",
    "that",
    "this",
    "the previous one",
    "the application",
    "the app",
    "the program",
    "the file",
    "the folder",
    "the image",
    "the picture",
}

_MACHINE = r"(?:my|the|this)?\s*(?:pc|computer|laptop|machine|system)\b"
_POLITE = re.compile(
    r"^(?:please[, ]+)?(?:can|could|would|will)\s+you\s+",
    re.IGNORECASE,
)
_TRAILING_POLITE = re.compile(
    r"[\s,]+(?:please|for me|thanks|thank you)\??$",
    re.IGNORECASE,
)
_CHOICE = re.compile(
    r"^(?:the\s+)?(?P<word>first|second|third|fourth|fifth|last|1st|2nd|3rd|4th|5th)"
    r"(?:\s+one)?$|^(?:number\s+)?(?P<num>[1-5])$",
    re.IGNORECASE,
)
_KNOWN_FOLDERS = {
    "downloads": "Downloads",
    "download": "Downloads",
    "documents": "Documents",
    "docs": "Documents",
    "desktop": "Desktop",
    "pictures": "Pictures",
    "photos": "Pictures",
    "videos": "Videos",
    "home": "Home",
    "user folder": "Home",
}
_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff")
_FILE_EXTS = _IMAGE_EXTS + (
    ".pdf",
    ".xlsx",
    ".xls",
    ".docx",
    ".doc",
    ".pptx",
    ".txt",
    ".csv",
)


@dataclass(frozen=True)
class ComputerCommand:
    category: str
    intent: str
    entity: str | None = None
    display: str | None = None
    query: str | None = None
    kind: str | None = None
    open_after: bool = False
    relation: str = "new_intent"
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CommandSuggestion:
    corrected_text: str
    prompt: str
    command: ComputerCommand


_SKIP_FIRST = {
    "a",
    "i",
    "to",
    "of",
    "in",
    "on",
    "at",
    "as",
    "be",
    "we",
    "he",
    "or",
    "if",
    "so",
    "no",
    "ok",
    "hi",
    "hey",
    "yo",
    "um",
    "uh",
    "the",
    "and",
    "for",
    "you",
    "me",
    "it",
    "is",
    "are",
    "was",
    "not",
    "how",
    "what",
    "who",
    "why",
    "when",
    "can",
    "please",
    "just",
    "like",
    "this",
    "that",
    "have",
    "yes",
    "yeah",
    "yep",
}

_COMMAND_VERBS = (
    "open",
    "launch",
    "start",
    "run",
    "show",
    "close",
    "exit",
    "quit",
    "find",
    "search",
    "locate",
    "restart",
    "reboot",
    "lock",
)


def normalize_command_text(text: str) -> str:
    t = (text or "").strip().lower()
    t = _POLITE.sub("", t)
    t = _TRAILING_POLITE.sub("", t)
    t = t.replace("wi-fi", "wifi").replace("wi fi", "wifi")
    t = re.sub(r"[?!.,]+$", "", t).strip()
    t = re.sub(r"\s+", " ", t)
    return t


def choice_index(text: str) -> int | None:
    t = normalize_command_text(text)
    match = _CHOICE.match(t)
    if not match:
        return None
    words = {
        "first": 0,
        "1st": 0,
        "second": 1,
        "2nd": 1,
        "third": 2,
        "3rd": 2,
        "fourth": 3,
        "4th": 3,
        "fifth": 4,
        "5th": 4,
        "last": -1,
    }
    word = (match.group("word") or "").lower()
    if word:
        return words.get(word)
    num = match.group("num")
    if num:
        return int(num) - 1
    return None


def parse_computer_command(text: str, context: dict | None = None) -> ComputerCommand | None:
    """Return a structured command, or None if this is not a computer action."""
    context = context or {}
    t = normalize_command_text(text)
    if not t:
        return None

    pending = _pending_followup(t, context)
    if pending:
        return pending

    power = _parse_power(t)
    if power:
        return power

    listing = _parse_list_running(t)
    if listing:
        return listing

    files = _parse_files(t, context)
    if files:
        return files

    apps = _parse_applications(t, context)
    if apps:
        return apps

    return None


def _pending_followup(text: str, context: dict) -> ComputerCommand | None:
    if context.get("awaiting_search_choice") and choice_index(text) is not None:
        return ComputerCommand(
            category="FILE_MANAGEMENT",
            intent="choose_search_result",
            relation="context_continuation",
            extras={"choice": choice_index(text)},
        )
    return None


def _parse_power(text: str) -> ComputerCommand | None:
    if re.search(rf"\b(?:shut\s*down|power\s*off|turn\s+off)\b.*{_MACHINE}", text) or re.search(
        rf"\b{_MACHINE}.*\b(?:shut\s*down|power\s*off|turn\s+off)\b", text
    ):
        return ComputerCommand("SYSTEM_POWER", "shutdown_computer")
    if re.search(rf"\b(?:restart|reboot)\b.*{_MACHINE}", text) or re.search(
        rf"\b{_MACHINE}.*\b(?:restart|reboot)\b", text
    ):
        return ComputerCommand("SYSTEM_POWER", "restart_computer")
    if re.search(rf"\block\b.*{_MACHINE}", text) or re.search(
        rf"\b{_MACHINE}.*\block\b", text
    ) or text in {"lock", "lock screen"}:
        return ComputerCommand("SYSTEM_POWER", "lock_computer")
    if re.search(rf"\b(?:sleep|suspend|hibernate)\b.*{_MACHINE}", text) or text in {
        "sleep",
        "sleep now",
        "put it to sleep",
    }:
        return ComputerCommand("SYSTEM_POWER", "sleep_computer")
    if re.search(r"\b(?:log\s*out|sign\s*out|log off|sign off)\b", text):
        return ComputerCommand("SYSTEM_POWER", "logout_user")
    return None


def _parse_list_running(text: str) -> ComputerCommand | None:
    if re.search(
        r"\b(?:what|which|show|list)\b.*\b(?:programs?|apps?|applications?)\b.*"
        r"\b(?:running|open)\b"
        r"|\b(?:running|open)\b.*\b(?:programs?|apps?|applications?)\b"
        r"|\bwhat(?:'s| is) running\b"
        r"|\bshow running (?:apps|applications|programs)\b",
        text,
    ):
        return ComputerCommand("APPLICATION_MANAGEMENT", "list_running_applications")
    if re.search(
        r"\b(?:which|what)\b.*\b(?:using|using up|eating|consuming)\b.*"
        r"\b(?:memory|ram|cpu)\b"
        r"|\bmost (?:memory|ram|cpu)\b",
        text,
    ):
        by = "cpu" if "cpu" in text else "memory"
        return ComputerCommand(
            "APPLICATION_MANAGEMENT",
            "list_running_applications",
            extras={"top_by": by},
        )
    return None


def _parse_applications(text: str, context: dict) -> ComputerCommand | None:
    restart_match = re.search(
        r"\b(?:close and reopen|restart|relaunch)\s+(?P<target>.+)$",
        text,
    )
    if restart_match:
        target = restart_match.group("target")
        if _looks_like_machine(target):
            return None
        resolved = _resolve_app_target(target, context)
        if resolved:
            app_id, display, relation = resolved
            return ComputerCommand(
                "APPLICATION_MANAGEMENT",
                "restart_application",
                entity=app_id,
                display=display,
                relation=relation,
            )

    check_match = re.search(
        r"\bis\s+(?P<target>.+?)\s+(?:running|open)\??$",
        text,
    )
    if check_match:
        resolved = _resolve_app_target(check_match.group("target"), context)
        if resolved:
            app_id, display, relation = resolved
            return ComputerCommand(
                "APPLICATION_MANAGEMENT",
                "check_application",
                entity=app_id,
                display=display,
                relation=relation,
            )

    close_match = re.search(
        r"\b(?:close|exit|quit|kill|stop|shut\s*down)\s+(?P<target>.+)$",
        text,
    )
    if close_match:
        target = close_match.group("target")
        if _looks_like_machine(target):
            return None
        resolved = _resolve_app_target(target, context)
        if resolved:
            app_id, display, relation = resolved
            return ComputerCommand(
                "APPLICATION_MANAGEMENT",
                "close_application",
                entity=app_id,
                display=display,
                relation=relation,
            )
        if _is_pronoun(target):
            return ComputerCommand(
                "APPLICATION_MANAGEMENT",
                "close_application",
                relation="context_continuation",
            )

    open_match = re.search(
        r"\b(?:open|launch|start|run)\s+(?P<target>.+)$",
        text,
    )
    if open_match:
        target = open_match.group("target")
        if _looks_like_machine(target) or _looks_like_file_target(target):
            return None
        resolved = _resolve_app_target(target, context)
        if resolved:
            app_id, display, relation = resolved
            return ComputerCommand(
                "APPLICATION_MANAGEMENT",
                "open_application",
                entity=app_id,
                display=display,
                relation=relation,
            )

    return None


def _parse_files(text: str, context: dict) -> ComputerCommand | None:
    open_after = bool(re.search(r"\band open(?:\s+it)?\b", text))
    cleaned = re.sub(r"\s+and open(?:\s+it)?$", "", text).strip()

    known = _known_folder_command(cleaned)
    if known:
        return known

    if cleaned in {"open it", "open that", "open this"}:
        referent = context.get("last_referent") or {}
        kind = referent.get("type")
        path = referent.get("path")
        if kind in {"file", "folder"} and path:
            intent = "open_folder" if kind == "folder" else "open_file"
            category = "FOLDER_MANAGEMENT" if kind == "folder" else "FILE_MANAGEMENT"
            return ComputerCommand(
                category,
                intent,
                entity=path,
                display=referent.get("display"),
                relation="context_continuation",
            )

    image_named = re.search(
        r"\b(?:find|look for|search(?: for)?|locate|open)\b.*?"
        r"\b(?:image|picture|photo|screenshot)\b"
        r"(?:\s*(?:named|called|:)\s*)(?P<name>.+)$",
        cleaned,
    )
    if image_named:
        query = _clean_query(image_named.group("name"))
        if query:
            return ComputerCommand(
                "FILE_MANAGEMENT",
                "search_file",
                query=query,
                kind="image",
                open_after=open_after or cleaned.startswith("open "),
            )

    folder_named = re.search(
        r"\b(?:find|look for|search(?: for)?|locate|open)\b\s+"
        r"(?:my |the |this )?(?P<name>.+?)\s+folder\b",
        cleaned,
    )
    if folder_named:
        query = _clean_query(folder_named.group("name"))
        if query in {"", "this", "that", "the", "my"}:
            return ComputerCommand("FOLDER_MANAGEMENT", "search_folder", query=None, kind="folder")
        return ComputerCommand(
            "FOLDER_MANAGEMENT",
            "search_folder",
            query=query,
            kind="folder",
            open_after=open_after or cleaned.startswith("open "),
        )

    file_named = re.search(
        r"\b(?:find|look for|search(?: for)?|locate)\b\s+"
        r"(?:my |the |this )?(?:file |document )?(?:named |called )?(?P<name>.+)$",
        cleaned,
    )
    if file_named:
        query = _clean_query(file_named.group("name"))
        kind = "any"
        if _looks_like_image_query(cleaned, query):
            kind = "image"
        elif "folder" in cleaned:
            kind = "folder"
        elif any(word in cleaned for word in ("file", "document", "pdf")):
            kind = "file"
        if query in {"", "this", "that", "file", "image", "picture", "photo", "folder"}:
            return ComputerCommand(
                "FILE_MANAGEMENT" if kind != "folder" else "FOLDER_MANAGEMENT",
                "search_file" if kind != "folder" else "search_folder",
                query=None,
                kind=kind,
            )
        if query.endswith(" folder"):
            return ComputerCommand(
                "FOLDER_MANAGEMENT",
                "search_folder",
                query=_clean_query(query[: -len(" folder")]),
                kind="folder",
                open_after=open_after,
            )
        return ComputerCommand(
            "FILE_MANAGEMENT",
            "search_file",
            query=query,
            kind=kind,
            open_after=open_after,
        )

    if re.search(r"\b(?:find|look for|search(?: for)?|locate)\b.+\b(?:image|picture|photo)\b", cleaned):
        return ComputerCommand("FILE_MANAGEMENT", "search_file", query=None, kind="image")

    if re.search(r"\b(?:find|look for|search(?: for)?|locate)\b.+\bfolder\b", cleaned):
        return ComputerCommand("FOLDER_MANAGEMENT", "search_folder", query=None, kind="folder")

    if re.search(r"\b(?:i can't find|i cannot find|can't find|cannot find)\b.+\bfile\b", cleaned):
        return ComputerCommand("FILE_MANAGEMENT", "search_file", query=None, kind="file")

    return None


def _known_folder_command(text: str) -> ComputerCommand | None:
    match = re.search(
        r"\b(?:open|show|go to)\s+(?:me\s+)?(?:my\s+|the\s+)?"
        r"(?P<name>downloads?|documents?|docs|desktop|pictures|photos|videos|home)"
        r"(?:\s+folder)?\b",
        text,
    )
    if not match:
        return None
    key = match.group("name")
    folder = _KNOWN_FOLDERS.get(key)
    if not folder:
        return None
    return ComputerCommand(
        "FOLDER_MANAGEMENT",
        "open_folder",
        entity=folder,
        display=folder,
        kind="known_folder",
    )


def _resolve_app_target(
    target: str,
    context: dict,
) -> tuple[str, str, str] | None:
    cleaned = _clean_query(target)
    if _is_pronoun(cleaned):
        referent = context.get("last_referent") or {}
        app_id = referent.get("application") or context.get("last_application")
        if app_id:
            return str(app_id), display_name(str(app_id)), "context_continuation"
        return None
    app_id = resolve_app_id(cleaned)
    if not app_id:
        return None
    return app_id, display_name(app_id), "new_intent"


def _is_pronoun(text: str) -> bool:
    return _clean_query(text) in _PRONOUNS


def _clean_query(text: str) -> str:
    t = (text or "").strip().lower()
    t = t.strip("\"'`")
    t = re.sub(r"^(?:the|this|that|my|an|a)\s+", "", t)
    t = re.sub(r"\s+(?:file|document|image|picture|photo|folder|application|app|program)$", "", t)
    t = re.sub(r"[.,;:]+$", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _looks_like_machine(text: str) -> bool:
    return bool(re.search(rf"^{_MACHINE}$|\b(?:pc|computer|laptop|machine|system)\b", text))


def _looks_like_file_target(text: str) -> bool:
    t = text.lower()
    if "folder" in t or "directory" in t:
        return True
    if any(t.endswith(ext) or ext in t for ext in _FILE_EXTS):
        return True
    if re.search(r"\b(?:downloads?|documents?|desktop|pictures|videos)\b", t):
        return True
    return False


def _looks_like_image_query(full: str, query: str) -> bool:
    if any(word in full for word in ("image", "picture", "photo", "screenshot")):
        return True
    lowered = query.lower()
    return any(lowered.endswith(ext) for ext in _IMAGE_EXTS)


def suggest_computer_command(
    text: str,
    context: dict | None = None,
) -> CommandSuggestion | None:
    """If this looks like a mistyped computer command, suggest a correction.

    Exact parses return None — only near-misses should ask 'Did you mean?'.
    """
    context = context or {}
    if parse_computer_command(text, context):
        return None
    t = normalize_command_text(text)
    tokens = t.split()
    if len(tokens) < 2:
        return None

    candidates: list[tuple[int, str, ComputerCommand]] = []
    first, rest = tokens[0], tokens[1:]
    if first not in _COMMAND_VERBS and first != "shutdown" and first not in _SKIP_FIRST:
        for verb in _COMMAND_VERBS:
            if len(first) < 3:
                continue
            max_distance = 2 if len(first) >= 4 and len(verb) >= 4 else 1
            if abs(len(first) - len(verb)) > max_distance:
                continue
            distance = _edit_distance(first, verb)
            if distance < 1 or distance > max_distance:
                continue
            candidate_tokens = [verb, *rest]
            fixed = _fuzzy_replace_known_tokens(candidate_tokens) or candidate_tokens
            candidate = " ".join(fixed)
            command = parse_computer_command(candidate, context)
            if command:
                candidates.append((distance, candidate, command))
        shutdown_distance = _edit_distance(first, "shutdown")
        if 1 <= shutdown_distance <= 2 and len(first) >= 5:
            candidate = " ".join(["shutdown", *rest])
            command = parse_computer_command(candidate, context)
            if command:
                candidates.append((shutdown_distance, candidate, command))

    if not candidates:
        entity_fixed = _fuzzy_replace_known_tokens(tokens)
        if entity_fixed and entity_fixed != tokens:
            candidate = " ".join(entity_fixed)
            command = parse_computer_command(candidate, context)
            if command:
                candidates.append((1, candidate, command))

    if not candidates and _looks_like_target_without_verb(t):
        for prefix in ("open ", "find "):
            command = parse_computer_command(prefix + t, context)
            if command:
                candidates.append((2, prefix + t, command))
                break

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], len(item[1])))
    _distance, corrected, command = candidates[0]
    return CommandSuggestion(
        corrected_text=corrected,
        prompt=_suggestion_prompt(command, corrected),
        command=command,
    )


def _fuzzy_replace_known_tokens(tokens: list[str]) -> list[str] | None:
    known = list(_KNOWN_FOLDERS)
    from yuwontlaykit.knowledge.app_catalog import all_aliases

    aliases = [alias for alias, _app_id in all_aliases() if " " not in alias]
    replaced = list(tokens)
    for index, token in enumerate(tokens):
        if len(token) < 4:
            continue
        match = _closest_word(token, known + aliases)
        if match and match != token:
            replaced[index] = match
            return replaced
    return None


def _closest_word(token: str, words: list[str]) -> str | None:
    best: str | None = None
    best_distance = 3
    for word in words:
        max_distance = 2 if len(token) >= 5 and len(word) >= 5 else 1
        if abs(len(token) - len(word)) > max_distance:
            continue
        distance = _edit_distance(token, word)
        if 1 <= distance <= max_distance and distance < best_distance:
            best = word
            best_distance = distance
    return best


def _looks_like_target_without_verb(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:downloads?|documents?|desktop|pictures|videos)\b",
            text,
        )
    )


def looks_like_keyboard_smash(text: str) -> bool:
    """Catch mashed keys like 'edtgsDFeq' that are not a real request."""
    raw = (text or "").strip()
    if not raw:
        return False
    compact = re.sub(r"[^a-z]", "", raw.lower())
    if len(compact) < 4:
        return False
    if compact in _SKIP_FIRST or compact in {
        "hello",
        "thanks",
        "please",
        "help",
        "okay",
        "type",
        "nikko",
        "yuwon",
    }:
        return False
    if re.search(r"[a-z][A-Z]|[A-Z]{2,}[a-z]", raw):
        return True
    vowels = sum(ch in "aeiou" for ch in compact)
    if len(compact) >= 5 and vowels / len(compact) <= 0.25:
        return True
    if re.search(r"[bcdfghjklmnpqrstvwxyz]{5,}", compact):
        return True
    if " " not in raw and len(compact) >= 6:
        return True
    return False


def looks_like_misspell(text: str, context: dict | None = None) -> bool:
    """True when the message looks mistyped, even if we cannot correct it."""
    if suggest_computer_command(text, context):
        return True
    if looks_like_keyboard_smash(text):
        return True
    t = normalize_command_text(text)
    tokens = [tok for tok in t.split() if tok]
    if not tokens:
        return False
    if len(tokens) == 1 and tokens[0] in _SKIP_FIRST:
        return False
    vocab = list(_COMMAND_VERBS) + list(_KNOWN_FOLDERS) + [
        "shutdown",
        "printer",
        "printers",
        "wifi",
        "folder",
        "chrome",
        "excel",
        "word",
        "vscode",
        "postman",
    ]
    from yuwontlaykit.knowledge.app_catalog import all_aliases

    vocab.extend(alias for alias, _app_id in all_aliases() if " " not in alias)
    for token in tokens:
        if token in _SKIP_FIRST:
            continue
        if _closest_word(token, vocab):
            return True
        if len(token) >= 5 and not re.search(r"[aeiou]", token):
            return True
    return False


def _suggestion_prompt(command: ComputerCommand, corrected: str) -> str:
    if command.intent == "open_folder" and command.display:
        return f"open your {command.display} folder"
    if command.intent == "open_application" and command.display:
        return f"open {command.display}"
    if command.intent == "close_application" and command.display:
        return f"close {command.display}"
    if command.intent == "restart_application" and command.display:
        return f"restart {command.display}"
    if command.intent == "search_folder" and command.query:
        return f"find the {command.query} folder"
    if command.intent == "search_file" and command.query:
        return f"find {command.query}"
    if command.intent == "shutdown_computer":
        return "shut down this PC"
    if command.intent == "restart_computer":
        return "restart this PC"
    if command.intent == "lock_computer":
        return "lock this PC"
    return corrected


def _edit_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if abs(len(left) - len(right)) > 2:
        return 99
    previous = list(range(len(right) + 1))
    for i, left_ch in enumerate(left, 1):
        current = [i]
        for j, right_ch in enumerate(right, 1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (left_ch != right_ch),
                )
            )
        previous = current
    return previous[-1]
