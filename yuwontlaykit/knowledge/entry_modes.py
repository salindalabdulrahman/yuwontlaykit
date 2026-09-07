"""CLI entry-point identity modes.

Yuwontlaykit and Yuwon are the same character (the assistant).
Which console script was used only changes who the *user* is and how deep
the bond is:

- ``yuwontlaykit`` → guest (stranger)
- ``4782``         → Nikko, deep bond (Bedis teasing allowed)
- ``yuwon``        → Nikko, same access as 4782 but shallower (no Bedis tease)
"""

from __future__ import annotations

import os
import sys

GUEST = "guest"
NIKKO_DEEP = "nikko_deep"
NIKKO_LIGHT = "nikko_light"

# basename of the installed console script → mode
_COMMAND_TO_MODE = {
    "yuwontlaykit": GUEST,
    "4782": NIKKO_DEEP,
    "yuwon": NIKKO_LIGHT,
}

OPENING_REPLIES = {
    GUEST: "Where did you know me? Scary huh",
    NIKKO_DEEP: "Whatsup Bedis?",
    NIKKO_LIGHT: "Hey Nikko — what's up?",
}

PROMPT_LABELS = {
    GUEST: "Guest",
    NIKKO_DEEP: "Nikko",
    NIKKO_LIGHT: "Nikko",
}

USER_DISPLAY_NAMES = {
    GUEST: "Guest",
    NIKKO_DEEP: "Nikko",
    NIKKO_LIGHT: "Nikko",
}


def _command_basename(argv0: str | None = None) -> str:
    raw = argv0 if argv0 is not None else (sys.argv[0] if sys.argv else "")
    return os.path.basename(raw).lower().removesuffix(".exe")


def resolve_mode(argv0: str | None = None) -> str:
    """Map the invoking console script name to an identity mode."""
    return _COMMAND_TO_MODE.get(_command_basename(argv0), GUEST)


def opening_reply(mode: str) -> str:
    return OPENING_REPLIES.get(mode, OPENING_REPLIES[GUEST])


def prompt_label(mode: str) -> str:
    return PROMPT_LABELS.get(mode, PROMPT_LABELS[GUEST])


def user_display_name(mode: str) -> str:
    return USER_DISPLAY_NAMES.get(mode, USER_DISPLAY_NAMES[GUEST])


def is_nikko(mode: str) -> bool:
    """True when the user is Nikko (either depth)."""
    return mode in (NIKKO_DEEP, NIKKO_LIGHT)


def is_deep_nikko(mode: str) -> bool:
    """True only for the deep 4782 bond (Bedis teasing)."""
    return mode == NIKKO_DEEP
