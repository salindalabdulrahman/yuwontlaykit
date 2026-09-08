"""Guest-mode dialogue beats for Yuwontlaykit / Yuwon.

Covers the stranger arc: nervous opening → laughter → \"Nikko sent me\"
→ compliments (she likes being admired) → gentle help offers for
real-world asks like printers (examine first, don't shut them down).
"""

from __future__ import annotations

import re

from yuwontlaykit.knowledge import entry_modes

LAUGH_PATTERN = re.compile(
    r"(ha(ha)+|he(he)+|hi(hi)+|loll*|lmao+|rofl+)",
    re.IGNORECASE,
)

REFERRAL_PHRASES = (
    "nikko recommend",
    "nikko recommended",
    "nikko told me",
    "nikko sent me",
    "nikko introduced",
    "nikko said",
    "a friend of nikko",
    "friend of nikko",
    "nikko knows you",
    "know you through nikko",
    "from nikko",
)

# Guests (and Nikko) gushing — Yuwon likes admiration / compliments
COMPLIMENT_HINTS = (
    "pretty",
    "beautiful",
    "cute",
    "gorgeous",
    "lovely",
    "smart",
    "brainy",
    "braniny",  # common typo for brainy
    "clever",
    "brilliant",
    "intelligent",
    "talented",
    "amazing",
    "awesome",
    "adorable",
    "charming",
    "sweet",
    "cool",
    "impressive",
)

# Real-world / tech help asks with a named problem (not vague "help me")
SUPPORT_HINTS = (
    "fix my",
    "fix the",
    "help me fix",
    "help me with",
    "my printer",
    "my computer",
    "my wifi",
    "my laptop",
    "broken",
    "not working",
    "how do i install",
    "troubleshoot",
)

VAGUE_HELP_HINTS = (
    "can you help me",
    "could you help me",
    "can you help",
    "i need help",
)

SUPPORT_REPLY = (
    "Got it — tell me what's wrong and I'll check it. "
    "Printer, Wi-Fi, a slow computer… whatever it is."
)

VAGUE_HELP_REPLY = (
    "I can try. Tell me what's wrong — "
    "or say Nikko sent you if that's how you found me."
)

LAUGH_REPLIES = (
    # 1st laugh — soft, still asking
    (
        "Heh… okay, funny. Still doesn't answer me though — "
        "where did you hear about me?"
    ),
    # 2nd — starts teasing back
    (
        "Okay okay, the laugh track is looping. "
        "I'm not a comedy club — spill it. Who sent you?"
    ),
    # 3rd — funnier pushback
    (
        "Bro. You're cackling like I just tripped on a banana peel. "
        "I'm flattered… and slightly concerned. Nikko? A rumor? A glitch?"
    ),
    # 4th — dramatic
    (
        "HALT. Security has detained one (1) mysterious giggler. "
        "Charge: excessive hahaha with zero explanation. "
        "Speak now or I keep being spooky."
    ),
    # 5th+ — peak unserious, then soft reset tone
    (
        "…Alright, you win the laugh-off. Trophy unlocked: Most Suspicious Guest. "
        "Now for the plot twist ending — just say 'Nikko' if that's how you found me."
    ),
)

# Back-compat alias (first beat)
LAUGH_REPLY = LAUGH_REPLIES[0]

REFERRAL_REPLY = (
    "Ohhh — Nikko sent you. That tracks. Alright, you're less scary now. "
    "I'm Yuwontlaykit (he calls me Yuwon). I can chat a bit, tell you "
    "who I am, or do small stuff like time, date, and calc. "
    "What do you need?"
)

COMPLIMENT_REPLY = (
    "Aww… okay, I'm smiling now. "
    "I really like being admired — thank you for saying that. "
    "You're sweet. What can I help you with?"
)

COMPLIMENT_WITH_REFERRAL_REPLY = (
    "Ohhh — Nikko sent you *and* he said I'm pretty and brainy? "
    "…Yeah, that tracks. He knows I love being admired a little. "
    "Thank you for saying it out loud — that made my day. "
    "I'm Yuwontlaykit (he calls me Yuwon). What do you need?"
)


def arms_machine_scan(text: str) -> bool:
    """Only arm the quiet scan when the guest named a concrete tech problem."""
    if matches_compliment(text) or matches_referral(text) or matches_laugh(text):
        return False
    t = text.lower()
    if any(v in t for v in VAGUE_HELP_HINTS) and not any(
        hint in t for hint in ("printer", "computer", "wifi", "laptop", "broken", "not working")
    ):
        return False
    return matches_support_ask(text) and any(
        hint in t for hint in ("printer", "computer", "wifi", "laptop", "broken", "not working", "fix my", "fix the")
    )

GUEST_FALLBACK = (
    "Hmm. I don't really know you yet. "
    "If Nikko sent you, say that — otherwise type 'help' "
    "and I'll show what I can do."
)


def matches_laugh(text: str) -> bool:
    t = text.strip().lower()
    if LAUGH_PATTERN.search(t):
        return True
    # Messy laughter like HAHAHAHAHAHHAH / WHAHAHAHAHHAAH (extra letters, no spaces)
    compact = re.sub(r"[^a-z]", "", t)
    if len(compact) >= 4 and re.fullmatch(r"[whaeio]+", compact):
        if "ha" in compact or "ah" in compact or "he" in compact or "wha" in compact:
            return True
    return False


def matches_referral(text: str) -> bool:
    t = text.strip().lower()
    # Bare "Nikko" counts — guests often answer the opener with just his name
    if t == "nikko" or t == "from nikko":
        return True
    return any(phrase in t for phrase in REFERRAL_PHRASES)


def matches_compliment(text: str) -> bool:
    return any(hint in text for hint in COMPLIMENT_HINTS)


def matches_support_ask(text: str) -> bool:
    t = text.lower()
    if any(v in t for v in VAGUE_HELP_HINTS) and not any(
        hint in t
        for hint in (
            "printer",
            "computer",
            "wifi",
            "laptop",
            "broken",
            "not working",
            "fix my",
            "fix the",
            "help me with",
            "help me fix",
        )
    ):
        return True  # vague help — still a guest_chat match, but not a scan arm
    return any(hint in t for hint in SUPPORT_HINTS)


def matches(text: str, mode: str) -> bool:
    if mode != entry_modes.GUEST:
        return False
    return (
        matches_laugh(text)
        or matches_referral(text)
        or matches_compliment(text)
        or matches_support_ask(text)
    )


def _laugh_reply(context: dict | None) -> str:
    """Escalate — never spam the same laugh line twice in a row."""
    ctx = context if context is not None else {}
    count = int(ctx.get("guest_laugh_count", 0))
    index = min(count, len(LAUGH_REPLIES) - 1)
    ctx["guest_laugh_count"] = count + 1
    return LAUGH_REPLIES[index]


def reply(text: str, context: dict | None = None) -> str:
    # Compliments first — Yuwon likes being admired; don't bury that
    # under a plain referral ack when Nikko also hyped her up.
    if matches_compliment(text) and matches_referral(text):
        return COMPLIMENT_WITH_REFERRAL_REPLY
    if matches_compliment(text):
        return COMPLIMENT_REPLY
    if matches_referral(text):
        return REFERRAL_REPLY
    if matches_laugh(text):
        return _laugh_reply(context)
    t = text.lower()
    if any(v in t for v in VAGUE_HELP_HINTS) and not any(
        hint in t for hint in ("printer", "computer", "wifi", "laptop", "broken", "not working")
    ):
        return VAGUE_HELP_REPLY
    if matches_support_ask(text):
        return SUPPORT_REPLY
    return GUEST_FALLBACK


def fallback(
    mode: str,
    user_input: str,
    context: dict | None = None,
    *,
    contextual: bool = False,
) -> str:
    if (
        contextual
        and context
        and (context.get("printer_help_active") or context.get("it_support_active"))
    ):
        return (
            "What do you want next about that — "
            "which printers are installed, which is online, or which is default?"
        )
    if mode == entry_modes.GUEST:
        return GUEST_FALLBACK
    return "Hmm, I didn't catch that. What do you want me to do?"
