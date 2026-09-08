"""Named-tool registry — the only way diagnostics may touch the OS."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from yuwontlaykit.tools.base import RiskLevel, ToolResult, failed, skipped

_LOG = logging.getLogger("yuwontlaykit")

ToolFn = Callable[..., ToolResult]


class ToolSpec:
    def __init__(self, name: str, risk: RiskLevel, fn: ToolFn, description: str = ""):
        self.name = name
        self.risk = risk
        self.fn = fn
        self.description = description


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def run(self, tool: str, *, confirmed: bool = False, **kwargs: Any) -> ToolResult:
        spec = self._tools.get(tool)
        if spec is None:
            return skipped(
                tool,
                RiskLevel.READ_ONLY,
                f"There is no approved tool named '{tool}'.",
            )
        if spec.risk != RiskLevel.READ_ONLY and not confirmed:
            return skipped(
                tool,
                spec.risk,
                "I need your permission before I change anything on this computer.",
            )
        try:
            result = spec.fn(**kwargs)
        except Exception:
            _LOG.exception("approved tool %s failed", tool)
            return failed(
                tool,
                spec.risk,
                "I couldn't complete that action.",
            )
        # Trust the tool's own name/risk if it returned a ToolResult
        if isinstance(result, ToolResult):
            return result
        return skipped(tool, spec.risk, "Tool returned an unexpected result type.")


_BUILTIN: ToolRegistry | None = None


def builtin_registry() -> ToolRegistry:
    """Lazy singleton so tool modules can import registry without cycles."""
    global _BUILTIN
    if _BUILTIN is None:
        from yuwontlaykit.tools import catalog

        _BUILTIN = catalog.build_registry()
    return _BUILTIN


def run_tool(tool: str, *, confirmed: bool = False, **kwargs: Any) -> ToolResult:
    return builtin_registry().run(tool, confirmed=confirmed, **kwargs)
