"""Windows access helpers (PowerShell via powershell.exe, including from WSL)."""

from __future__ import annotations

import shutil
from functools import lru_cache

from yuwontlaykit.tools.base import RiskLevel, ToolResult, failed, unavailable
from yuwontlaykit.tools.runner import parse_json, run_argv


@lru_cache(maxsize=1)
def powershell_exe() -> str | None:
    return shutil.which("powershell.exe") or shutil.which("pwsh")


def windows_tools_available() -> bool:
    return powershell_exe() is not None


def run_powershell(
    script: str,
    timeout: float = 25.0,
) -> tuple[int, str, str]:
    exe = powershell_exe()
    if not exe:
        return 127, "", "PowerShell not found"
    argv = [
        exe,
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        script,
    ]
    return run_argv(argv, timeout=timeout)


def powershell_json(
    name: str,
    script: str,
    timeout: float = 25.0,
    risk: RiskLevel = RiskLevel.READ_ONLY,
) -> ToolResult:
    """Run a PowerShell script expected to print JSON."""
    if not powershell_exe():
        return unavailable(
            name,
            risk,
            "PowerShell is not available, so I cannot inspect Windows from here.",
        )
    code, out, err = run_powershell(script, timeout=timeout)
    if code == 127:
        return unavailable(name, risk, "PowerShell is not available on this machine.")
    if code == 124:
        return failed(name, risk, "That Windows check timed out.", raw=err or out)
    payload = parse_json(out)
    if code != 0 and payload is None:
        detail = err or out or f"exit {code}"
        return failed(name, risk, detail, raw=out or err)
    return ToolResult(
        name=name,
        risk=risk,
        executed=True,
        available=True,
        success=code == 0 or payload is not None,
        data=payload,
        raw=out,
        error=err or None,
        summary="Windows data collected" if payload is not None else (out[:200] or "no JSON"),
    )
