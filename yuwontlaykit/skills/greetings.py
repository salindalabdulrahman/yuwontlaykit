"""Greeting skill — tone depends on who launched the CLI.

Yuwon / Yuwontlaykit is always the speaker; the user is Guest or Nikko.
"""

from __future__ import annotations

import re

from yuwontlaykit.knowledge import entry_modes
from yuwontlaykit.people.nikko.bedis import BedisTease

# Whole-word greetings only — avoids matching "hi" inside "this" / "which"
GREETING_PATTERN = re.compile(
    r"\b(hi|hello|hey|greetings|yo|sup)\b",
    re.IGNORECASE,
)


def matches(text: str) -> bool:
    return bool(GREETING_PATTERN.search(text))


def reply(mode: str = entry_modes.GUEST, bedis: BedisTease | None = None) -> str:
    if mode == entry_modes.GUEST:
        return "Uh… hi? Still weird that you know me. Who sent you?"

    if mode == entry_modes.NIKKO_LIGHT:
        return "Hey Nikko! Good to hear from you. What are we on?"

    if bedis and bedis.serious:
        return "Hey Nikko. I'm in serious mode — what do you need?"

    # Deep Nikko (4782) — use Bedis only while teasing is active
    name = bedis.address_name() if bedis else "Nikko"
    if bedis and bedis.is_playful():
        return f"Heeey {name}~ What's good? I'm in a teasing mood."
    return f"Hey {name}! Great to hear from you. What are we working on today?"
