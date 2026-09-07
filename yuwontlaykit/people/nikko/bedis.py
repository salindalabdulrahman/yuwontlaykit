"""Bedis nickname teasing + serious switch for deep Nikko (4782).

Yuwon plays by calling Nikko \"Bedis\". He hates it.
- Soft shut-downs (\"don't call me that\", \"I hate that name\") → stop teasing.
- Sharp \"Yuwon!\" → she drops the play entirely and gets serious.
"""

from __future__ import annotations

import re

REJECT_PHRASES = (
    "not now yuwon",
    "don't call me bedis",
    "dont call me bedis",
    "do not call me bedis",
    "stop calling me bedis",
    "stop calling me that",
    "don't call me that",
    "dont call me that",
    "do not call me that",
    "don't ever call",
    "dont ever call",
    "do not ever call",
    "never call me",
    "never call that",
    "never call me that",
    "i hate that name",
    "hate that name",
    "hate being called",
    "stop with bedis",
    "no more bedis",
    "not bedis",
    "calling me that",
    "call me that",
    # Short shut-downs while she's teasing
    "stop it",
    "cut it out",
    "quit it",
    "enough",
    "not in the mood",
    "not in mood",
    "i'm not in the mood",
    "im not in the mood",
    "i ma not in the mood",  # common typo
    "leave me alone",
    "don't tease",
    "dont tease",
    "stop teasing",
    "no teasing",
)

# Bare lines that mean "stop playing" while Bedis tease is on
REJECT_EXACT = (
    "stop",
    "stop it",
    "stop.",
    "enough",
    "enough.",
    "no",
    "nope",
)

# Firm call of her name — playtime over
SERIOUS_PATTERN = re.compile(
    r"^\s*yuwon[!?.]+(?:\s+.*)?$",
    re.IGNORECASE,
)

STOP_TEASING_REPLY = (
    "Alright, alright — no more Bedis. Nikko it is. "
    "I was only playing with you. What do you need?"
)

SERIOUS_REPLY = (
    "Okay. I'm serious now — no jokes, no Bedis. "
    "I'm here, Nikko. What's going on?"
)

NICKNAME = "Bedis"
PREFERRED = "Nikko"


class BedisTease:
    """Session-scoped tease + serious state for deep Nikko (4782)."""

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.active = enabled  # Bedis nickname on
        self.serious = False  # hard lock: no play

    def address_name(self) -> str:
        if self.enabled and self.active and not self.serious:
            return NICKNAME
        return PREFERRED

    def is_playful(self) -> bool:
        return self.enabled and not self.serious and self.active

    def matches_serious(self, text: str) -> bool:
        if not self.enabled:
            return False
        return bool(SERIOUS_PATTERN.match(text.strip()))

    def handle_serious(self) -> str:
        self.serious = True
        self.active = False
        return SERIOUS_REPLY

    def matches_reject(self, text: str) -> bool:
        if not self.enabled or not self.active or self.serious:
            return False
        t = text.lower().strip().strip("'\"`")
        if t in REJECT_EXACT:
            return True
        if any(phrase in t for phrase in REJECT_PHRASES):
            return True
        # Broader: hate/stop/don't + name/bedis/call
        hates = ("hate", "stop", "don't", "dont", "do not", "never", "enough")
        targets = ("bedis", "that name", "calling me", "call me that", "call that")
        if any(h in t for h in hates) and any(x in t for x in targets):
            return True
        # Mood shut-down: "not in the mood" / typos like "i ma not…"
        if "mood" in t and any(x in t for x in ("not", "no", "aint", "ain't")):
            return True
        return False

    def handle_reject(self) -> str:
        self.active = False
        return STOP_TEASING_REPLY

    def resume_play(self) -> None:
        """Lighten up again if Nikko invites it."""
        if self.enabled:
            self.serious = False
            self.active = True
