"""Distinguish inventory vs problem vs short follow-ups on the active case."""

from __future__ import annotations

import re

PROBLEM_HINTS = (
    "not working",
    "isn't working",
    "isnt working",
    "won't print",
    "wont print",
    "can't print",
    "cannot print",
    "broken",
    "paper jam",
    "jammed",
    "error",
    "stuck",
    "won't open",
    "wont open",
    "slow",
    "no sound",
    "can't hear",
    "no internet",
)

IP_LOOKUP_HINTS = (
    "ip address",
    "ip adress",
    "ipv4",
    "ipv6",
    "my ip",
    "the ip",
    "what ip",
    "which ip",
    "show ip",
    "show me the ip",
    "show me ip",
    "ip of my",
    "ip of this",
    "ip of the",
)


WHY_FOLLOWUPS = {
    "why",
    "why?",
    "why not",
    "why not?",
    "how come",
    "how come?",
    "what happened",
    "what happened?",
}

RETRY_HINTS = (
    "retry",
    "re try",
    "try again",
    "try it again",
    "check again",
    "do it again",
    "please badly",
    "badly need",
    "need it to know",
    "still need",
)


def is_ip_lookup(text: str) -> bool:
    t = text.lower().strip()
    if any(hint in t for hint in IP_LOOKUP_HINTS):
        return True
    compact = t.replace(" ", "")
    if "ipaddress" in compact or "ipadress" in compact:
        return True
    tokens = set(t.replace("?", " ").replace("'", " ").split())
    if "ip" in tokens and tokens & {"address", "adress", "machine", "pc", "computer"}:
        return True
    return False


def is_ip_followup(text: str) -> bool:
    """Short follow-ups after an IP lookup ('why?', 'retry', 'please badly need it')."""
    t = text.lower().strip()
    if t in WHY_FOLLOWUPS or t.rstrip("?.!") in {"why", "why not", "how come", "what happened"}:
        return True
    if any(hint in t for hint in RETRY_HINTS):
        return True
    if t in {"again", "again please", "please", "please do"}:
        return True
    return False


def is_why_followup(text: str) -> bool:
    t = text.lower().strip()
    return t in WHY_FOLLOWUPS or t.rstrip("?.!") in {"why", "why not", "how come", "what happened"}


INVENTORY_HINTS = (
    "what printer",
    "which printer",
    "what printers",
    "which printers",
    "printers installed",
    "printer installed",
    "installed printer",
    "installed to this",
    "installed on this",
    "installed in this",
    "list printer",
    "list the printer",
    "show printer",
    "show the printer",
    "show me the printer",
    "check what printer",
    "check which printer",
    "see what printer",
    "see which printer",
    "what is installed",
    "what's installed",
    "whats installed",
)


def is_printer_inventory_lookup(text: str) -> bool:
    """Recognize natural variants of requests to list installed printers."""
    t = text.lower().replace("’", "'")
    t = re.sub(r"[^a-z0-9']+", " ", t).strip()
    tokens = set(t.split())
    mentions_printer = bool(tokens & {"printer", "printers", "printing"})
    if not mentions_printer:
        return False

    # A fault remains troubleshooting even if words like "check" or "printer" occur.
    if any(hint in t for hint in PROBLEM_HINTS):
        return False

    list_action = bool(
        tokens
        & {
            "list",
            "show",
            "display",
            "tell",
            "check",
            "find",
            "see",
            "what",
            "which",
        }
    )
    installed_word = bool(
        tokens
        & {
            "install",
            "installed",
            "installs",
            "installation",
            "available",
            "added",
        }
    )
    return list_action and installed_word


def clarification_suggestion(text: str) -> str | None:
    """Suggest a likely intent when an inventory request contradicts itself."""
    t = text.lower().replace("’", "'")
    t = re.sub(r"[^a-z0-9']+", " ", t).strip()
    tokens = t.split()
    token_set = set(tokens)
    list_action = bool(token_set & {"list", "show", "display", "tell", "check"})
    inventory_word = bool(
        token_set & {"install", "installed", "available", "added"}
    )
    machine_words = {"pc", "computer", "machine"}

    # Example: "display available pc in this pc". Repeating the machine as
    # both the requested item and location usually means the item was mistyped.
    machine_mentions = sum(token in machine_words for token in tokens)
    named_item = bool(
        token_set
        & {
            "printer",
            "printers",
            "app",
            "apps",
            "application",
            "applications",
            "software",
            "device",
            "devices",
            "drive",
            "drives",
        }
    )
    if list_action and inventory_word and machine_mentions >= 2 and not named_item:
        return "printer_inventory"
    return None


# Answers that only make sense after a recent printer look-up
FOLLOWUP_ONLINE = (
    "which one is online",
    "which is online",
    "who's online",
    "who is online",
    "which are online",
    "which ones are online",
    "which printers are online",
    "which printer is online",
    "any online",
    "is online",
    "online ones",
    "online printer",
    "actually reachable",
    "which are reachable",
)

# List-only: no diagnose pitch — just the online names
FOLLOWUP_ONLINE_LIST = (
    "display only the online",
    "display only online",
    "show only the online",
    "show only online",
    "list only the online",
    "list only online",
    "only the online",
    "only online printers",
    "online only",
    "show online printers",
    "list online printers",
    "display online printers",
    "show the online",
    "list the online",
    "display the online",
)


def is_online_printer_list(text: str) -> bool:
    """Recognize flexible requests to list only reachable/online printers."""
    t = text.lower().replace("’", "'")
    t = re.sub(r"[^a-z0-9']+", " ", t).strip()
    tokens = set(t.split())
    mentions_printer = bool(tokens & {"printer", "printers", "printing"})
    asks_for_list = bool(
        tokens
        & {
            "list",
            "show",
            "display",
            "tell",
            "find",
            "check",
            "give",
        }
    )
    asks_for_online = bool(
        tokens
        & {
            "online",
            "reachable",
            "reachble",
            "connected",
            "ready",
        }
    )
    fault_language = any(
        hint in t
        for hint in (
            "not reachable",
            "not online",
            "not connected",
            "isn't reachable",
            "isnt reachable",
            "cannot reach",
            "can't reach",
        )
    )
    return mentions_printer and asks_for_list and asks_for_online and not fault_language


FOLLOWUP_DEFAULT = (
    "which one is default",
    "which is default",
    "what's the default",
    "whats the default",
    "default printer",
    "which is the default",
)

FOLLOWUP_OFFLINE = (
    "which one is offline",
    "which is offline",
    "which are offline",
    "offline ones",
)

FOLLOWUP_PICK = (
    "pick one",
    "pick obne",  # common typo
    "pick 1",
    "choose one",
    "pick one of them",
    "choose one of them",
    "just pick",
    "you pick",
    "which should i use",
    "which one should i use",
    "which one do i use",
    "which printer should i use",
)

REMOVE_PRINTER_HINTS = (
    "remove this printer",
    "remove the printer",
    "remove printer",
    "uninstall this printer",
    "uninstall the printer",
    "uninstall printer",
    "delete this printer",
    "delete the printer",
    "delete printer",
    "remove it from this",
    "remove it from my",
)


def classify_intent(text: str) -> str:
    """Return inventory | problem | followup_* ."""
    t = text.lower().strip()
    # Follow-ups before problem hints so "offline" in a short question stays a follow-up
    if is_online_printer_list(text) or any(
        hint in t for hint in FOLLOWUP_ONLINE_LIST
    ):
        return "followup_online_list"
    if any(hint in t for hint in FOLLOWUP_ONLINE) or t in {"online?", "online"}:
        return "followup_online"
    if any(hint in t for hint in FOLLOWUP_DEFAULT) or t in {"default?", "default"}:
        return "followup_default"
    if any(hint in t for hint in FOLLOWUP_OFFLINE) or t in {"offline?", "offline"}:
        return "followup_offline"
    if _is_pick_followup(t):
        return "followup_pick"
    if is_remove_printer(text):
        return "remove_printer"
    if is_ip_lookup(text):
        return "inventory"
    if any(hint in t for hint in PROBLEM_HINTS):
        # "printer offline" as a problem statement still counts as problem
        if "printer" in t or "print" in t or len(t.split()) > 3:
            return "problem"
        return "problem"
    if is_printer_inventory_lookup(text) or any(hint in t for hint in INVENTORY_HINTS):
        return "inventory"
    return "problem"


def _is_pick_followup(t: str) -> bool:
    compact = t.rstrip("?.!")
    if compact in {"pick", "choose"}:
        return True
    if any(hint in t for hint in FOLLOWUP_PICK):
        return True
    if compact.startswith("pick ") and len(compact.split()) <= 3:
        return True
    return False


def is_remove_printer(text: str) -> bool:
    t = text.lower()
    if any(hint in t for hint in REMOVE_PRINTER_HINTS):
        return True
    if "printer" in t and any(w in t for w in ("remove", "uninstall", "delete")):
        return True
    return False


def is_printer_followup(text: str) -> bool:
    return classify_intent(text) in (
        "followup_online",
        "followup_online_list",
        "followup_default",
        "followup_offline",
        "followup_pick",
    )
