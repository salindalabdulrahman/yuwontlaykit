"""Profile helpers and birthday replies for Yuwontlaykit."""

from yuwontlaykit.people.nikko.friends.yuwontlaykit.personal_info import BIRTHDAY

BIRTHDAY_QUERY_PHRASES = (
    "your birthday",
    "when were you born",
    "when's your birthday",
    "when is your birthday",
)

AGE_QUERY_PHRASES = (
    "your age",
    "how old are you",
    "what is your age",
    "what's your age",
)


def format_birthday_reply() -> str:
    return f"My birthday is {BIRTHDAY.strftime('%B %d, %Y')}!"


def matches_birthday_query(text: str) -> bool:
    return any(phrase in text for phrase in BIRTHDAY_QUERY_PHRASES)


def matches_age_query(text: str) -> bool:
    return any(phrase in text for phrase in AGE_QUERY_PHRASES)
