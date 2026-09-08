"""Aggregates and formats Nikko's profile for assistant replies."""

from __future__ import annotations

import re

from yuwontlaykit.people.nikko import background, personal_info

NIKKO_QUERY_PHRASES = (
    "what do you know about nikko",
    "who is nikko",
    "who nikko",
    "tell me about nikko",
    "what do you know about him",
    "tell me about him",
    "who is he",
    "about nikko",
)


def format_bio() -> str:
    """Return the full bio reply about Nikko (preserves existing wording)."""
    return (
        "Here is everything I know about my best friend, Nikko:\n\n"
        f"  • Full Name: {personal_info.FULL_NAME}\n"
        f"  • Birthday: {personal_info.BIRTHDAY}\n"
        f"  • Height: {personal_info.HEIGHT}\n"
        f"  • Favorite Food: {personal_info.FAVORITE_FOOD}\n"
        f"  • Education: {background.EDUCATION}\n"
        f"  • Current Role: {background.CURRENT_ROLE}\n\n"
        "That's my main guy right there!"
    )


def matches_query(text: str) -> bool:
    t = _normalize_who(text)
    if matches_bedis_query(text):
        return False
    return any(phrase in t for phrase in NIKKO_QUERY_PHRASES)


def matches_bedis_query(text: str) -> bool:
    t = _normalize_who(text)
    if not re.search(r"\bbedis\b", t):
        return False
    return bool(re.search(r"\b(?:who|what|whom)\b", t))


def format_bedis_reply() -> str:
    return (
        "Bedis is Nikko. It's his middle name — "
        f"{personal_info.FULL_NAME}.\n\n"
        "I use it when I'm teasing him. He hates it, which is honestly "
        "part of why it's funny.\n"
        "His preferred name is still Nikko."
    )


def _normalize_who(text: str) -> str:
    t = (text or "").lower().replace("’", "'")
    t = re.sub(r"\bwho['’]?s\b", "who is", t)
    t = re.sub(r"\bwhat['’]?s\b", "what is", t)
    t = re.sub(r"[?!.,]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()
