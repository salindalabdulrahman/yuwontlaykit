"""Date and time skills."""

import datetime
import re

_TIME_PATTERN = re.compile(
    r"\b(what time|current time|the time|time is it|system time)\b",
    re.IGNORECASE,
)
_DATE_PATTERN = re.compile(
    r"\b(today'?s date|what date|current date|the date|what is the date)\b",
    re.IGNORECASE,
)


def matches_time(text: str) -> bool:
    t = text.strip().lower()
    return t in {"time", "what's the time", "whats the time"} or bool(_TIME_PATTERN.search(text))


def matches_date(text: str) -> bool:
    t = text.strip().lower()
    return t in {"date", "what's the date", "whats the date"} or bool(_DATE_PATTERN.search(text))


def reply_time(now=None) -> str:
    now = now or datetime.datetime.now()
    current_time = now.strftime("%I:%M %p")
    return f"The current system time is {current_time}."


def reply_date(now=None) -> str:
    now = now or datetime.datetime.now()
    current_date = now.strftime("%A, %B %d, %Y")
    return f"Today's date is {current_date}."
