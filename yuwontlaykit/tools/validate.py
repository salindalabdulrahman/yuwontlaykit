"""Input validation for tools that accept hostnames/IPs — never shell-interpolate raw user text."""

from __future__ import annotations

import ipaddress
import re

_HOSTNAME = re.compile(r"^[A-Za-z0-9._-]{1,253}$")


def is_safe_host(value: str) -> bool:
    text = (value or "").strip()
    if not text or len(text) > 253:
        return False
    try:
        ipaddress.ip_address(text)
        return True
    except ValueError:
        pass
    return bool(_HOSTNAME.fullmatch(text))


_UNSAFE_PRINTER_CHARS = set(";|&`$<>\n\r\"")


def is_safe_printer_name(value: str) -> bool:
    """Printer display names may have spaces/slashes, but never shell metacharacters."""
    text = (value or "").strip()
    if not text or len(text) > 200:
        return False
    if text.startswith("-"):
        return False
    return not any(ch in _UNSAFE_PRINTER_CHARS for ch in text)


def require_safe_host(value: str) -> str:
    text = (value or "").strip()
    if not is_safe_host(text):
        raise ValueError("unsafe host")
    return text
