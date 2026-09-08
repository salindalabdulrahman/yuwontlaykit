"""Load IT troubleshooting topics from JSON — not from hardcoded Python tables."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

TOPICS_DIR = Path(__file__).resolve().parent / "topics"


def _load_file(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or not data.get("id"):
        raise ValueError(f"Invalid topic file: {path}")
    return data


@lru_cache(maxsize=1)
def load_topics() -> dict[str, dict[str, Any]]:
    topics: dict[str, dict[str, Any]] = {}
    if not TOPICS_DIR.is_dir():
        return topics
    for path in sorted(TOPICS_DIR.glob("*.json")):
        topic = _load_file(path)
        topics[str(topic["id"])] = topic
    return topics


def get_topic(topic_id: str) -> dict[str, Any] | None:
    return load_topics().get(topic_id)


def topics_for_domain(domain: str) -> list[dict[str, Any]]:
    return [t for t in load_topics().values() if t.get("domain") == domain]


def reload_topics() -> None:
    load_topics.cache_clear()
