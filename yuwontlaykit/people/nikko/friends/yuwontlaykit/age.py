"""Age calculation and formatting for Yuwontlaykit."""

import calendar
import datetime

from yuwontlaykit.people.nikko.friends.yuwontlaykit.personal_info import BIRTHDAY


def calculate_age(birthday=None, today=None):
    """
    Returns (years, months, days) since birthday, counted against today's date.
    Returns None if today is before the birthday (i.e. she hasn't 'been born' yet).
    """
    birthday = birthday or BIRTHDAY
    today = today or datetime.date.today()

    if today < birthday:
        return None

    years = today.year - birthday.year
    months = today.month - birthday.month
    days = today.day - birthday.day

    if days < 0:
        months -= 1
        prev_month = today.month - 1 or 12
        prev_year = today.year if today.month > 1 else today.year - 1
        days_in_prev_month = calendar.monthrange(prev_year, prev_month)[1]
        days += days_in_prev_month

    if months < 0:
        years -= 1
        months += 12

    return years, months, days


def format_age(birthday=None, today=None) -> str:
    birthday = birthday or BIRTHDAY
    today = today or datetime.date.today()
    age = calculate_age(birthday=birthday, today=today)

    if age is None:
        days_until = (birthday - today).days
        return (
            f"I haven't been 'born' yet! My birthday is "
            f"{birthday.strftime('%B %d, %Y')} — {days_until} day(s) to go."
        )

    years, months, days = age
    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if months:
        parts.append(f"{months} month{'s' if months != 1 else ''}")
    parts.append(f"{days} day{'s' if days != 1 else ''}")

    if years == 0 and months == 0 and days == 0:
        return (
            "Today's my birthday! I was just 'born' today, so I'm 0 days old!"
        )

    return (
        f"I've been around for {', '.join(parts)}, counting from my birthday "
        f"on {birthday.strftime('%B %d, %Y')}."
    )
