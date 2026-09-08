"""Named-tool registry — the only way diagnostics may touch the OS."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from yuwontlaykit.tools.base import RiskLevel, ToolResult, skipped

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

    def run(self, name: str, *, confirmed: bool = False, **kwargs: Any) -> ToolResult:
        spec = self._tools.get(name)
        if spec is None:
            return skipped(
                name,
                RiskLevel.READ_ONLY,
                f"There is no approved tool named '{name}'.",
            )
        if spec.risk != RiskLevel.READ_ONLY and not confirmed:
            return skipped(
                name,
                spec.risk,
                "I need your permission before I change anything on this computer.",
            )
        result = spec.fn(**kwargs)
        # Trust the tool's own name/risk if it returned a ToolResult
        if isinstance(result, ToolResult):
            return result
        return skipped(name, spec.risk, "Tool returned an unexpected result type.")


_BUILTIN: ToolRegistry | None = None


def builtin_registry() -> ToolRegistry:
    """Lazy singleton so tool modules can import registry without cycles."""
    global _BUILTIN
    if _BUILTIN is None:
        from yuwontlaykit.tools import catalog

        _BUILTIN = catalog.build_registry()
    return _BUILTIN


def run_tool(name: str, *, confirmed: bool = False, **kwargs: Any) -> ToolResult:
    return builtin_registry().run(name, confirmed=confirmed, **kwargs)
