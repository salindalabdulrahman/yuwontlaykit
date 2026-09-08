"""Machine / printer examine skill for Yuwon.

After the guest agrees (yes/no), runs a small allowlisted set of
read-only diagnostic commands *quietly* (not shown to the user) and
plays a short terminal animation while gathering results.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from typing import Callable

from colorama import Fore, Style

AWAITING_KEY = "awaiting_machine_scan"

YES_WORDS = (
    "yes",
    "y",
    "yeah",
    "yep",
    "yup",
    "sure",
    "ok",
    "okay",
    "go",
    "go ahead",
    "proceed",
    "do it",
    "please",
    "check",
    "examine",
    "scan",
)

NO_WORDS = (
    "no",
    "n",
    "nope",
    "nah",
    "cancel",
    "stop",
    "nevermind",
    "never mind",
    "not now",
)


def _norm(text: str) -> str:
    """Strip whitespace and wrapping quotes so `'yes` still counts."""
    return text.strip().lower().strip("'\"`")

CANCEL_REPLY = (
    "Alright — I won't peek. If it acts up again, just ask and "
    "say yes when I'm ready to examine."
)

PROMPT_AGAIN = (
    "I need a clear yes or no before I check your machine. "
    "Type yes to examine, or no to skip."
)

# (animation label, callable that returns a short human summary line)
CheckFn = Callable[[], str]


def is_awaiting(context: dict) -> bool:
    return bool(context.get(AWAITING_KEY))


def set_awaiting(context: dict, value: bool) -> None:
    context[AWAITING_KEY] = value


def matches_yes(text: str) -> bool:
    t = _norm(text)
    return t in YES_WORDS or t.startswith("yes ")


def matches_no(text: str) -> bool:
    t = _norm(text)
    return t in NO_WORDS or t.startswith("no ")


def _run_hidden(cmd: list[str], timeout: float = 8.0) -> tuple[int, str, str]:
    """Run a command without echoing it to the user."""
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return completed.returncode, (completed.stdout or "").strip(), (completed.stderr or "").strip()
    except FileNotFoundError:
        return 127, "", "not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timed out"
    except OSError as exc:
        return 1, "", str(exc)


def _first_lines(text: str, limit: int = 6) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return "(no output)"
    clipped = lines[:limit]
    more = f" … (+{len(lines) - limit} more)" if len(lines) > limit else ""
    return " | ".join(clipped) + more


def _check_os() -> str:
    from yuwontlaykit.tools.registry import run_tool

    result = run_tool("get_system_information")
    return result.summary or _first_lines(result.raw or result.error or "unavailable")


def _check_printer_spool() -> str:
    from yuwontlaykit.tools.registry import run_tool

    printers = run_tool("get_printers")
    spooler = run_tool("check_print_spooler")
    bits = [printers.summary, spooler.summary]
    return " | ".join(b for b in bits if b) or "Printer check unavailable."


def _check_usb_printers() -> str:
    from yuwontlaykit.tools.registry import run_tool

    usb = run_tool("get_usb_devices")
    if usb.available and usb.success:
        return usb.summary
    if shutil.which("lsusb"):
        code, out, _ = _run_hidden(["lsusb"])
        if code != 0 or not out:
            return "Could not list USB devices."
        printerish = [
            line
            for line in out.splitlines()
            if any(token in line.lower() for token in ("print", "hp", "canon", "epson", "brother", "lexmark"))
        ]
        if printerish:
            return _first_lines("\n".join(printerish), 5)
        return "USB devices visible; none obviously labeled as a printer."
    return usb.summary or "USB printer check unavailable."


def _check_disk() -> str:
    from yuwontlaykit.tools.registry import run_tool

    result = run_tool("get_disk_information")
    return result.summary or "Disk check unavailable."


def _check_memory() -> str:
    from yuwontlaykit.tools.registry import run_tool

    result = run_tool("get_system_information")
    if result.success and result.summary:
        return result.summary
    if shutil.which("free"):
        code, out, _ = _run_hidden(["free", "-h"])
        if code == 0 and out:
            for line in out.splitlines():
                if line.lower().startswith("mem:"):
                    return " ".join(line.split())
            return _first_lines(out, 2)
    return "Memory check unavailable."


def _check_cups_service() -> str:
    from yuwontlaykit.tools.registry import run_tool

    spooler = run_tool("check_print_spooler")
    if spooler.available:
        return spooler.summary
    if shutil.which("systemctl"):
        code, out, _ = _run_hidden(["systemctl", "is-active", "cups"])
        if out:
            return f"cups service: {out}"
        return f"cups service check exit={code}"
    if shutil.which("service"):
        code, out, err = _run_hidden(["service", "cups", "status"])
        blob = out or err
        if blob:
            return _first_lines(blob, 3)
    return "Print service status not queryable here."


CHECKS: list[tuple[str, CheckFn]] = [
    ("Reading machine identity", _check_os),
    ("Looking for print services", _check_cups_service),
    ("Scanning printer queue / drivers", _check_printer_spool),
    ("Checking USB for printers", _check_usb_printers),
    ("Checking free disk space", _check_disk),
    ("Checking memory headroom", _check_memory),
]


def _animate_step(label: str, frames: str = "|/-\\", spins: int = 6) -> None:
    for i in range(spins):
        frame = frames[i % len(frames)]
        sys.stdout.write(
            f"\r{Fore.MAGENTA}  {frame}{Style.RESET_ALL} "
            f"{Fore.CYAN}{label}…{Style.RESET_ALL}   "
        )
        sys.stdout.flush()
        time.sleep(0.09)
    sys.stdout.write(
        f"\r{Fore.GREEN}  ✓{Style.RESET_ALL} {label}{' ' * 12}\n"
    )
    sys.stdout.flush()


def run_scan_with_animation() -> str:
    """Play animation, run hidden checks, return Yuwon's spoken summary."""
    print()
    print(
        f"{Fore.CYAN}Yuwontlaykit >{Style.RESET_ALL} "
        f"Okay… slipping in quietly. One sec while I examine things.\n"
    )

    findings: list[str] = []
    for label, fn in CHECKS:
        _animate_step(label)
        try:
            findings.append(f"• {label}: {fn()}")
        except Exception as exc:  # noqa: BLE001 — keep scan resilient
            findings.append(f"• {label}: skipped ({exc})")

    print()
    body = "\n".join(findings)
    return (
        "Done peeking — here's what I found inside your machine:\n"
        f"{body}\n\n"
        "Tell me what the printer does (paper jam, offline, stuck queue, "
        "driver, toner/ink, no power, access denied…) and I'll inspect "
        "the machine, then explain what I found in plain language."
    )


def handle_consent(text: str, context: dict) -> str:
    if matches_yes(text):
        set_awaiting(context, False)
        # Hand off to printer symptom matching after the scan summary
        from yuwontlaykit.skills import printer_help

        summary = run_scan_with_animation()
        printer_help.activate(context)
        return summary
    if matches_no(text):
        set_awaiting(context, False)
        return CANCEL_REPLY
    return PROMPT_AGAIN
