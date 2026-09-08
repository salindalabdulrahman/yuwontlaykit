"""Human-sounding confusion when the user mistypes or mashes keys."""

from __future__ import annotations

GUESS_OPENERS = (
    "Wait — I think that was a typo.",
    "Huh, I'm a little confused.",
    "Hold on, that looked misspelled.",
    "I almost caught that, but it looks off.",
    "That didn't look quite right.",
)

UNPARSED_REPLIES = (
    "Wait, I'm confused. That looked misspelled.\nCan you type it one more time?",
    "Huh? I didn't quite catch that — I think there was a typo.\nSay it again?",
    "Hmm, that didn't come through clearly. Mind typing it again?",
    "I think you mashed the keyboard a bit. What did you want me to do?",
    "That looked like a slip. Try it again in normal words?",
    "Wait wait — I didn't get that. One more time?",
    "Sorry, that scrambled on me. What were you trying to say?",
    "I'm lost. That didn't look like a real request.\nWant to type it again?",
)

LOST_REPLIES = (
    "Hmm, I didn't catch that. What do you want me to do?",
    "I'm a little lost. Say that another way?",
    "Huh? I don't follow. What should I do?",
    "That didn't click. Want to try again?",
    "Wait — what did you want me to do?",
    "I missed that. Open something? Check something?",
    "Sorry, I didn't understand. One more time?",
    "I heard you, but I don't know what that means. Help me out?",
)

LAUGH_REPLIES = (
    "Heh. What's so funny?",
    "Okay, you're laughing. What happened?",
    "Haha — okay. What do you actually need?",
    "You're cackling. Tell me what's going on.",
    "Alright, giggle break's over. What should I do?",
    "Ha. Cute. Now tell me what you wanted.",
)

DECLINED_REPLIES = (
    "Oh — okay, never mind. What did you actually want?",
    "Got it, not that. What did you mean then?",
    "Okay, I'll drop it. Tell me what you need.",
)


def ask_if_meant(prompt: str, typed: str = "", context: dict | None = None) -> str:
    opener = _next(context, "confusion_guess_index", GUESS_OPENERS, typed)
    return f"{opener}\nDid you mean: {prompt}? (yes / no)"


def unparsed(typed: str = "", context: dict | None = None) -> str:
    return _next(context, "confusion_unparsed_index", UNPARSED_REPLIES, typed)


def lost(typed: str = "", context: dict | None = None) -> str:
    return _next(context, "confusion_lost_index", LOST_REPLIES, typed)


def laugh(context: dict | None = None, typed: str = "") -> str:
    return _next(context, "nikko_laugh_count", LAUGH_REPLIES, typed)


def declined(context: dict | None = None) -> str:
    return _next(context, "confusion_declined_index", DECLINED_REPLIES)


def next_reply(
    context: dict | None,
    key: str,
    lines: tuple[str, ...],
    seed: str = "",
) -> str:
    return _next(context, key, lines, seed)


def _next(
    context: dict | None,
    key: str,
    lines: tuple[str, ...],
    seed: str = "",
) -> str:
    if not lines:
        return ""
    ctx = context if context is not None else {}
    last = ctx.get("last_confusion_reply")
    index = int(ctx.get(key, 0))
    chosen = lines[index % len(lines)]
    if chosen == last and len(lines) > 1:
        index += 1
        chosen = lines[index % len(lines)]
    ctx[key] = index + 1
    ctx["last_confusion_reply"] = chosen
    return chosen
