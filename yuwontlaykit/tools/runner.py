"""Safe subprocess runner for allowlisted diagnostics.

This module never accepts an arbitrary user-supplied command string as
something to execute. Callers pass an argv list that an approved tool
already constructed.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any


DEFAULT_TIMEOUT = 20.0


def run_argv(
    argv: list[str],
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[int, str, str]:
    """Run a concrete argv list. Returns (returncode, stdout, stderr)."""
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return (
            completed.returncode,
            (completed.stdout or "").strip(),
            (completed.stderr or "").strip(),
        )
    except FileNotFoundError:
        return 127, "", "not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timed out"
    except OSError as exc:
        return 1, "", str(exc)


def parse_json(text: str) -> Any:
    """Parse PowerShell/JSON output; PowerShell emits one object or a list."""
    blob = (text or "").strip().lstrip("\ufeff")
    if not blob:
        return None
    # Strip BOM / CLIXML noise before the first JSON token.
    # Use whichever of '{' or '[' appears first — preferring '[' would
    # slice into the first array inside an object and break the parse.
    starts = [i for i in (blob.find("{"), blob.find("[")) if i != -1]
    if starts:
        blob = blob[min(starts) :]
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return None


def as_list(payload: Any) -> list[Any]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    return [payload]
