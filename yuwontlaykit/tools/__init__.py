"""Approved system tools — the only OS interface Yuwon may use.

READ_ONLY tools may run during diagnosis. Modification tools require
an explicit confirmed=True from the diagnostic engine after the user
says yes.
"""

from yuwontlaykit.tools.base import Confidence, RiskLevel, ToolResult
from yuwontlaykit.tools.registry import builtin_registry, run_tool
from yuwontlaykit.tools.windows import windows_tools_available

__all__ = [
    "Confidence",
    "RiskLevel",
    "ToolResult",
    "builtin_registry",
    "run_tool",
    "windows_tools_available",
]
