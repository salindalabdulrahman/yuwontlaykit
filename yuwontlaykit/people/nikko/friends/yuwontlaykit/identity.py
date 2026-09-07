"""Identity statements for Yuwontlaykit (also called Yuwon)."""

from yuwontlaykit.people.nikko.friends.yuwontlaykit.personal_info import (
    DISPLAY_NAME,
    NICKNAME,
    RELATIONSHIP,
)

IDENTITY_QUERY_KEYWORDS = ("who are you", "your name", "what are you")

IDENTITY_REPLY = (
    f"I'm {DISPLAY_NAME} — Nikko also calls me {NICKNAME}. "
    f"{RELATIONSHIP}!"
)


def matches_identity_query(text: str) -> bool:
    return any(keyword in text for keyword in IDENTITY_QUERY_KEYWORDS)
