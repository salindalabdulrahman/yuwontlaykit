"""Date and time skills."""

import datetime


def matches_time(text: str) -> bool:
    return "time" in text


def matches_date(text: str) -> bool:
    return "date" in text


def reply_time(now=None) -> str:
    now = now or datetime.datetime.now()
    current_time = now.strftime("%I:%M %p")
    return f"The current system time is {current_time}."


def reply_date(now=None) -> str:
    now = now or datetime.datetime.now()
    current_date = now.strftime("%A, %B %d, %Y")
    return f"Today's date is {current_date}."
