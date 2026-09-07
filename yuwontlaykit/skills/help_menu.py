"""Help / capabilities menu skill."""

import re

# Whole-word / phrase matches — avoids "help me fix my printer" → help menu
HELP_PATTERNS = (
    re.compile(r"^help$"),
    re.compile(r"^help\s+please$"),
    re.compile(r"^show\s+help$"),
    re.compile(r"^what can you do\??$"),
    re.compile(r"^commands$"),
    re.compile(r"^list\s+commands$"),
    re.compile(r"^\/help$"),
)

HELP_REPLY = (
    "Here is what I can do natively:\n"
    "  - Launch with 'yuwontlaykit' (guest), '4782' (Nikko deep), or 'yuwon' (Nikko light).\n"
    "  - I'm Yuwontlaykit — Nikko also calls me Yuwon.\n"
    "  - Ask me 'what time is it?' or 'what is today's date?'\n"
    "  - Ask me 'how old are you?' or 'when's your birthday?'\n"
    "  - Tell me 'calc [math]' (e.g., calc 45 * 12)\n"
    "  - Say 'remember [something]' to save a temporary note.\n"
    "  - Say 'show memories' to view saved notes.\n"
    "  - Ask to fix/check a printer — I'll examine, then walk errors with CMD/PowerShell fixes.\n"
    "  - Type 'exit' or 'quit' to close."
)


def matches(text: str) -> bool:
    return any(pattern.search(text) for pattern in HELP_PATTERNS)


def reply() -> str:
    return HELP_REPLY
