"""Aggregates and formats Nikko's profile for assistant replies."""

from yuwontlaykit.people.nikko import background, personal_info

NIKKO_QUERY_PHRASES = (
    "what do you know about nikko",
    "who is nikko",
    "tell me about nikko",
    "what do you know about him",
    "tell me about him",
    "who is he",
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
    return any(phrase in text for phrase in NIKKO_QUERY_PHRASES)
