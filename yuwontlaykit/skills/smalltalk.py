from __future__ import annotations

import re

from yuwontlaykit.knowledge import entry_modes
from yuwontlaykit.people.nikko.bedis import BedisTease
from yuwontlaykit.skills.confusion import next_reply

# "heyyy", "heey", "hiii", "yo", plain hey/hi/hello
GREETING_PATTERN = re.compile(
    r"^\s*(hey+|hi+|hello+|yo+|sup+|greetings)[!?.]*\s*$",
    re.IGNORECASE,
)

OK_PHRASES = (
    "all good",
    "all goods",
    "im good",
    "i'm good",
    "i am good",
    "doing good",
    "doing fine",
    "im fine",
    "i'm fine",
    "i am fine",
    "im ok",
    "i'm ok",
    "im okay",
    "i'm okay",
    "nothing much",
    "nm",
    "all okay",
    "all ok",
)

HELP_OPENERS = (
    "can you help me",
    "could you help me",
    "can you help",
    "help me please",
    "i need help",
    "need your help",
    "please help",
)

HELP_OPENER_EXACT = {
    "help",
    "help me",
    "help please",
    "please help me",
}

THANKS_EXACT = {
    "thank you",
    "thanks",
    "thx",
    "ty",
    "tysm",
    "thank u",
    "thanks you",
    "thankyou",
    "thanks a lot",
    "thanks so much",
    "thank you so much",
    "thank you very much",
    "appreciate it",
    "much appreciated",
    "ok thanks",
    "okay thanks",
    "ok thank you",
    "okay thank you",
}


def matches_greeting(text: str) -> bool:
    return bool(GREETING_PATTERN.match(text.strip()))


def matches_ok(text: str) -> bool:
    t = text.strip().lower().strip("'\"`")
    return t in OK_PHRASES or any(t == p or t.startswith(p + " ") for p in OK_PHRASES)


def _help_opener_text(text: str) -> str:
    t = text.strip().lower().strip("'\"`")
    t = re.sub(r"[!?.,]+$", "", t).strip()
    t = re.sub(r"[\s0-9]+$", "", t).strip()  # "i need help0" / "i need help 0"
    t = re.sub(r"\s+", " ", t)
    return t


def matches_help_opener(text: str) -> bool:
    """Vague help with no named problem (printer/wifi/etc.)."""
    t = _help_opener_text(text)
    asks_for_help = (
        t in HELP_OPENER_EXACT
        or any(t == phrase for phrase in HELP_OPENERS)
        or bool(
            re.search(
                r"\b(?:i\s+)?need\s+(?:your\s+|some\s+)?help\b"
                r"|\b(?:can|could|would|will)\s+you\s+(?:please\s+)?help(?:\s+me)?\b"
                r"|\bplease\s+help(?:\s+me)?\b",
                t,
            )
        )
    )
    if not asks_for_help:
        return False

    # If they already named a domain, IT support should handle it instead.
    problemish = (
        "printer",
        "print",
        "wifi",
        "wi-fi",
        "internet",
        "computer",
        "laptop",
        "sound",
        "audio",
        "bluetooth",
        "slow",
        "disk",
        "storage",
    )
    return not any(word in t for word in problemish)


def matches_thanks(text: str) -> bool:
    t = text.strip().lower().strip("'\"`")
    t = re.sub(r"[!?.,]+$", "", t).strip()
    compact = t.replace(" ", "")
    if t in THANKS_EXACT or compact in {"thankyou", "thanks", "thx", "ty", "tysm"}:
        return True
    if t.startswith(("thank you", "thanks ", "thanks")) and len(t.split()) <= 6:
        problemish = ("printer", "wifi", "internet", "ip", "broken", "not working")
        return not any(word in t for word in problemish)
    return False


REACT_PATTERN = re.compile(
    r"^\s*(?:wow+|woah+|whoa+|ooh+|oh+|nice|no way|for real|whoa)\s*[!?.]*\s*$",
    re.IGNORECASE,
)

REACT_REPLIES_NIKKO = (
    "Heh. Yeah?",
    "I know, right?",
    "Ha. Glad that landed.",
    "Mhm. What's next?",
    "Right? What else do you need?",
    "Yeah — pretty cool. What now?",
)

REACT_REPLIES_GUEST = (
    "Heh. Okay… still, who sent you?",
    "Wow from a stranger. Cute. Who told you about me?",
    "Okay. Now tell me how you found me.",
)

ACK_EXACT = {
    "ok",
    "okay",
    "k",
    "kk",
    "alright",
    "all right",
    "got it",
    "cool",
    "noted",
}


def matches_react(text: str) -> bool:
    t = text.strip().lower().strip("'\"`")
    t = re.sub(r"[!?.,]+$", "", t).strip()
    return bool(REACT_PATTERN.match(t)) or t in {"wow", "woah", "whoa", "nice", "oh"}


def matches_ack(text: str) -> bool:
    t = text.strip().lower().strip("'\"`")
    t = re.sub(r"[!?.,]+$", "", t).strip()
    return t in ACK_EXACT


def matches(text: str) -> bool:
    return (
        matches_greeting(text)
        or matches_ok(text)
        or matches_help_opener(text)
        or matches_thanks(text)
        or matches_ack(text)
        or matches_react(text)
    )


def reply(
    text: str,
    mode: str = entry_modes.GUEST,
    bedis: BedisTease | None = None,
    context: dict | None = None,
) -> str:
    name = "Nikko"
    if bedis and entry_modes.is_deep_nikko(mode):
        name = bedis.address_name()
    elif mode == entry_modes.GUEST:
        name = "there"

    if matches_react(text):
        lines = REACT_REPLIES_GUEST if mode == entry_modes.GUEST else REACT_REPLIES_NIKKO
        return next_reply(context, "smalltalk_react_index", lines, text)

    if matches_ok(text):
        if mode == entry_modes.GUEST:
            return "Okay… glad you're good. Still — who sent you?"
        return "Good to hear. What's on your mind?"

    if matches_thanks(text):
        if mode == entry_modes.GUEST:
            return "You're welcome."
        return "You're welcome. Anytime."

    if matches_ack(text):
        if mode == entry_modes.GUEST:
            return "Okay."
        return "Okay. What else do you need?"

    if matches_help_opener(text):
        if mode == entry_modes.GUEST:
            return (
                "I can try. Tell me what's wrong — "
                "or say Nikko sent you if that's how you found me."
            )
        return "Of course. What's going on?"

    # greeting
    if mode == entry_modes.GUEST:
        return "Uh… hi? Still weird that you know me. Who sent you?"
    if mode == entry_modes.NIKKO_LIGHT:
        return f"Heeey, {name}. What's up?"
    if bedis and bedis.serious:
        return f"Hey {name}. I'm in serious mode — what do you need?"
    if bedis and bedis.is_playful():
        return f"Heeey {name}~ What's good?"
    return f"Heeey, {name}. What's up?"
