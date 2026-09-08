"""Troubleshooting case — one user problem, one diagnostic session."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from yuwontlaykit.tools.base import Confidence, ToolResult


@dataclass
class ProposedAction:
    tool: str
    label: str
    user_impact: str
    topic_id: str | None = None


@dataclass
class TroubleshootingCase:
    number: int
    problem: str
    domain: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    topic_id: str | None = None
    awaiting: str | None = None  # inspect_consent | remediate_consent | followup | technical
    diagnostics: list[ToolResult] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    diagnosis: str | None = None
    confidence: Confidence = Confidence.UNKNOWN
    probable_cause: str | None = None
    proposed: ProposedAction | None = None
    actions_taken: list[dict[str, Any]] = field(default_factory=list)
    verification: list[ToolResult] = field(default_factory=list)
    result: str | None = None  # resolved | unresolved | blocked | needs_user | inspecting
    last_technical: str = ""
    last_plain: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def case_id(self) -> str:
        return f"Case #{self.number:04d}"

    def results_by_name(self) -> dict[str, ToolResult]:
        return {item.name: item for item in self.diagnostics}

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.case_id,
            "date": self.created_at,
            "problem": self.problem,
            "domain": self.domain,
            "topic_id": self.topic_id,
            "diagnosis": self.diagnosis,
            "confidence": self.confidence.value,
            "evidence": list(self.evidence),
            "actions": list(self.actions_taken),
            "result": self.result,
            "resolution": self.last_plain,
        }
