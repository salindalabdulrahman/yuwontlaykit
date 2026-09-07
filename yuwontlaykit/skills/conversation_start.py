"""Conversation start / session unlock skill."""

START_CODE = "4782"

START_REPLY = (
    "Access confirmed — deep Nikko bond unlocked. "
    "I'm locked in and ready. What do you need?"
)


def matches(text: str) -> bool:
    return text.strip() == START_CODE


def reply() -> str:
    return START_REPLY
