"""Yes/no consent helpers shared by IT support flows."""

from __future__ import annotations

YES_WORDS = {
    "yes",
    "y",
    "yeah",
    "yep",
    "yup",
    "sure",
    "ok",
    "okay",
    "go",
    "go ahead",
    "proceed",
    "do it",
    "please",
    "run it",
    "try it",
    "fix it",
}

# Soft "Want me to check why?" prompts — not a yes/no gate. "okay" is just an ack.
EXPLICIT_YES_WORDS = {
    "yes",
    "y",
    "yeah",
    "yep",
    "yup",
    "sure",
    "go",
    "go ahead",
    "proceed",
    "do it",
    "run it",
    "try it",
    "fix it",
}

NO_WORDS = {
    "no",
    "n",
    "nope",
    "nah",
    "cancel",
    "stop",
    "nevermind",
    "never mind",
    "not now",
    "skip",
}


def normalize(text: str) -> str:
    return text.strip().lower().strip("'\"`")


def is_yes(text: str) -> bool:
    t = normalize(text)
    return t in YES_WORDS or t.startswith("yes ")


def is_explicit_yes(text: str) -> bool:
    t = normalize(text)
    return t in EXPLICIT_YES_WORDS or t.startswith("yes ")


def is_no(text: str) -> bool:
    t = normalize(text)
    return t in NO_WORDS or t.startswith("no ")
