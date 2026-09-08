"""Approved-tool result types and risk levels.

Yuwon may only talk to the OS through named tools. Risk is explicit so
the diagnostic engine can auto-run reads and must ask before changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RiskLevel(str, Enum):
    READ_ONLY = "READ_ONLY"
    LOW_RISK_MODIFICATION = "LOW_RISK_MODIFICATION"
    HIGH_RISK_MODIFICATION = "HIGH_RISK_MODIFICATION"


class Confidence(str, Enum):
    CONFIRMED = "confirmed"
    LIKELY = "likely"
    POSSIBLE = "possible"
    UNKNOWN = "unknown"


@dataclass
class ToolResult:
    """Honest report of a single approved-tool attempt."""

    name: str
    risk: RiskLevel
    executed: bool
    available: bool
    success: bool
    data: Any = None
    raw: str = ""
    error: str | None = None
    summary: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    def as_evidence_line(self) -> str:
        if not self.available:
            return f"{self.name}: unavailable ({self.error or 'not available on this machine'})"
        if not self.executed:
            return f"{self.name}: not run ({self.error or 'skipped'})"
        if not self.success:
            return f"{self.name}: failed ({self.error or 'unknown error'})"
        return f"{self.name}: {self.summary or 'ok'}"


def unavailable(name: str, risk: RiskLevel, reason: str) -> ToolResult:
    return ToolResult(
        name=name,
        risk=risk,
        executed=False,
        available=False,
        success=False,
        error=reason,
        summary=reason,
    )


def skipped(name: str, risk: RiskLevel, reason: str) -> ToolResult:
    return ToolResult(
        name=name,
        risk=risk,
        executed=False,
        available=True,
        success=False,
        error=reason,
        summary=reason,
    )


def ok(name: str, risk: RiskLevel, summary: str, data: Any = None, raw: str = "") -> ToolResult:
    return ToolResult(
        name=name,
        risk=risk,
        executed=True,
        available=True,
        success=True,
        data=data,
        raw=raw,
        summary=summary,
    )


def failed(name: str, risk: RiskLevel, reason: str, raw: str = "", data: Any = None) -> ToolResult:
    return ToolResult(
        name=name,
        risk=risk,
        executed=True,
        available=True,
        success=False,
        data=data,
        raw=raw,
        error=reason,
        summary=reason,
    )
