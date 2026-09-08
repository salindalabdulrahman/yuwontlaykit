"""Load the application catalog used by launch, close, and discovery."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_CATALOG_PATH = Path(__file__).with_name("applications.json")


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, dict[str, Any]]:
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def all_aliases() -> list[tuple[str, str]]:
    """Return (alias, app_id) pairs, longest alias first."""
    pairs: list[tuple[str, str]] = []
    for app_id, spec in load_catalog().items():
        aliases = list(spec.get("aliases") or [])
        aliases.append(app_id)
        display = str(spec.get("display") or "").strip()
        if display:
            aliases.append(display.lower())
        for alias in aliases:
            cleaned = re.sub(r"\s+", " ", str(alias).strip().lower())
            if cleaned:
                pairs.append((cleaned, app_id))
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    return pairs


def spec_for(app_id: str) -> dict[str, Any] | None:
    return load_catalog().get(app_id)


def display_name(app_id: str) -> str:
    spec = spec_for(app_id)
    if not spec:
        return app_id
    return str(spec.get("display") or app_id)


def resolve_app_id(text: str) -> str | None:
    """Match a catalog alias inside free text using word boundaries."""
    blob = re.sub(r"\s+", " ", (text or "").strip().lower())
    if not blob:
        return None
    for alias, app_id in all_aliases():
        pattern = rf"(?<!\w){re.escape(alias)}(?!\w)"
        if re.search(pattern, blob):
            return app_id
    return None
