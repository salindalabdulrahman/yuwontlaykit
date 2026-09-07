"""Playful banter with Nikko in deep 4782 mode.

Yuwon plays while Bedis teasing is on. The serious-name switch stays
hidden in bedis.py — never tip Nikko off in dialogue.
"""

from __future__ import annotations

import re

from yuwontlaykit.knowledge import entry_modes
from yuwontlaykit.people.nikko.bedis import BedisTease

PLAY_HINTS = (
    "haha",
    "lol",
    "lmao",
    "hehe",
    "joke",
    "kidding",
    "tease",
    "play",
    "boring",
    "shut up",
    "whatever",
    "miss you",
    "what's up",
    "whats up",
    "wyd",
    "you good",
    "you there",
    "annoying",
    "brat",
    "silly",
    "mad",
    "angry",
    "ugh",
    "bro",
    "come on",
    "c'mon",
)

RESUME_HINTS = (
    "just kidding",
    "jk",
    "we can play",
    "keep teasing",
    "you can tease",
    "call me bedis",
    "it's fine",
    "its fine",
    "i'm kidding",
    "im kidding",
    "lighten up",
    "play with me",
)

PLAY_REPLIES = (
    "Heh — got you. Relax, Bedis… I mean Nikko. "
    "I'm just playing. What are we actually doing?",
    "Aww, you're cute when you're mad. "
    "Fine, I'll behave… for like five seconds. What's up?",
    "Play mode: ON. You poked me — of course I'm gonna tease. "
    "What are we on, Bedis?",
    "Okay okay, hands up — no more name games for a minute. "
    "Unless you miss it already. What do you need?",
    "I'm bored and you're my favorite person to bother. "
    "Hit me with a real ask or keep roasting me — your call.",
)

SERIOUS_FALLBACK = (
    "I'm locked in, Nikko. Tell me what you need — "
    "no teasing until you say otherwise."
)

PLAY_FALLBACK = (
    "Heh. I'm listening, Bedis — talk to me."
)

CALM_FALLBACK = (
    "Yeah? I'm here, Nikko. What's on your mind?"
)


def matches_resume(text: str) -> bool:
    t = text.lower().strip()
    return any(h in t for h in RESUME_HINTS)


def matches_play_chat(text: str) -> bool:
    t = text.lower().strip()
    if any(h in t for h in PLAY_HINTS):
        return True
    # Short chatty / emotional lines
    if len(t.split()) <= 10:
        return bool(
            re.search(
                r"\b(you|me|we|why|ugh|bro|dude|please|come on|c'mon|hey)\b",
                t,
            )
        )
    return False


def matches(text: str, mode: str, bedis: BedisTease) -> bool:
    if mode != entry_modes.NIKKO_DEEP or not bedis.enabled:
        return False
    if matches_resume(text):
        return True
    if bedis.serious:
        return False
    return matches_play_chat(text)


def reply(text: str, bedis: BedisTease, context: dict) -> str:
    if matches_resume(text):
        bedis.resume_play()
        context["nikko_play_count"] = 0
        return (
            "Heh — play mode back on. Don't act surprised when I say Bedis again. "
            "Missed me?"
        )

    count = int(context.get("nikko_play_count", 0))
    index = min(count, len(PLAY_REPLIES) - 1)
    context["nikko_play_count"] = count + 1

    if bedis.active:
        return PLAY_REPLIES[index]
    return CALM_FALLBACK


def fallback(bedis: BedisTease) -> str:
    if bedis.serious:
        return SERIOUS_FALLBACK
    if bedis.is_playful():
        return PLAY_FALLBACK
    return CALM_FALLBACK
