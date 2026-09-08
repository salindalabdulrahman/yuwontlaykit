"""Persisted troubleshooting history (session + optional user file)."""

from __future__ import annotations

import json
from pathlib import Path

from yuwontlaykit.diagnostics.case import TroubleshootingCase

DEFAULT_PATH = Path.home() / ".yuwontlaykit" / "diagnostic_history.jsonl"


class DiagnosticHistory:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_PATH
        self._cases: list[TroubleshootingCase] = []

    def __len__(self) -> int:
        return len(self._cases)

    def next_number(self) -> int:
        return len(self._cases) + 1

    def add(self, case: TroubleshootingCase) -> None:
        self._cases.append(case)
        self._append_file(case)

    def recent(self, limit: int = 5) -> list[TroubleshootingCase]:
        return self._cases[-limit:]

    def similar(self, domain: str, problem: str) -> TroubleshootingCase | None:
        needle = problem.lower()
        for case in reversed(self._cases):
            if case.domain == domain and case.problem.lower() == needle:
                return case
        return None

    def _append_file(self, case: TroubleshootingCase) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(case.snapshot(), ensure_ascii=False) + "\n")
        except OSError:
            # History file is best-effort; never fail a diagnosis over it.
            pass
