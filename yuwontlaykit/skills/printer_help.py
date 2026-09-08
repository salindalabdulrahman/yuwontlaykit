"""Printer troubleshooting skill — diagnose symptoms and run allowlisted fixes.

After a machine scan (or when the guest describes a printer symptom),
Yuwon explains the error, shows Windows CMD / PowerShell commands, and
can optionally execute a safe PowerShell fix when the user says yes.
"""

from __future__ import annotations

import shutil
import subprocess

from yuwontlaykit.knowledge.printer_errors import (
    PrinterError,
    find_error,
    list_symptom_hints,
)

ACTIVE_KEY = "printer_help_active"
AWAITING_FIX_KEY = "awaiting_printer_fix"
PENDING_ERROR_KEY = "pending_printer_error_id"

YES_WORDS = {
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
    "run it",
    "try it",
    "fix it",
}

NO_WORDS = {
    "no",
    "n",
    "nope",
    "nah",
    "cancel",
    "stop",
    "nevermind",
    "never mind",
    "not now",
    "skip",
}


def _norm(text: str) -> str:
    return text.strip().lower().strip("'\"`")


def activate(context: dict) -> None:
    context[ACTIVE_KEY] = True


def is_active(context: dict) -> bool:
    return bool(context.get(ACTIVE_KEY))


def is_awaiting_fix(context: dict) -> bool:
    return bool(context.get(AWAITING_FIX_KEY))


def matches_symptom(text: str) -> bool:
    return find_error(text) is not None


def matches(text: str, context: dict) -> bool:
    if is_awaiting_fix(context):
        return True
    return matches_symptom(text)


def _format_guide(err: PrinterError) -> str:
    physical = "\n".join(f"  {i}. {step}" for i, step in enumerate(err["physical_steps"], 1))
    cmd_lines = "\n".join(
        f"  • {label}\n    CMD> {cmd}" for label, cmd in err["cmd_steps"]
    )
    ps_lines = "\n".join(
        f"  • {label}\n    PS> {cmd}" for label, cmd in err["powershell_steps"]
    )
    return (
        f"Got it — that sounds like {err['title']}.\n\n"
        f"{err['what_it_means']}\n\n"
        f"Hands-on first:\n{physical}\n\n"
        f"Windows CMD powers I know for this:\n{cmd_lines}\n\n"
        f"PowerShell versions:\n{ps_lines}\n\n"
        f"Want me to try to {err['auto_fix_label']} from here? (yes / no)"
    )


def _run_powershell(command: str, timeout: float = 45.0) -> str:
    exe = shutil.which("powershell.exe") or shutil.which("pwsh")
    if not exe:
        return (
            "I couldn't find PowerShell on this machine (WSL-only?). "
            "Copy the CMD/PowerShell lines above into an Admin Windows terminal."
        )
    try:
        completed = subprocess.run(
            [
                exe,
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "That fix timed out — try the Admin CMD lines yourself."
    except OSError as exc:
        return f"Couldn't launch PowerShell: {exc}"

    out = (completed.stdout or "").strip()
    err = (completed.stderr or "").strip()
    if completed.returncode != 0:
        detail = err or out or f"exit {completed.returncode}"
        return (
            "I tried, but Windows pushed back "
            f"(often needs Admin):\n{detail}\n\n"
            "Run the Admin CMD lines I listed — that usually clears it."
        )
    if not out:
        return "Done — PowerShell finished with no extra output. Try printing again."
    # Keep the reply readable
    lines = [ln for ln in out.splitlines() if ln.strip()]
    clipped = "\n".join(lines[:20])
    if len(lines) > 20:
        clipped += f"\n… (+{len(lines) - 20} more lines)"
    return f"I ran the fix. Here's what Windows said:\n{clipped}\n\nTry printing again."


def _pending_error(context: dict) -> PrinterError | None:
    err_id = context.get(PENDING_ERROR_KEY)
    if not err_id:
        return None
    from yuwontlaykit.knowledge.printer_errors import PRINTER_ERRORS

    for err in PRINTER_ERRORS:
        if err["id"] == err_id:
            return err
    return None


def handle(text: str, context: dict, engine=None) -> str:
    t = _norm(text)

    # Consent to run the auto-fix for the last matched error (legacy path)
    if is_awaiting_fix(context):
        err = _pending_error(context)
        context[AWAITING_FIX_KEY] = False
        if t in YES_WORDS or t.startswith("yes"):
            if not err:
                return "I lost the error context — tell me the symptom again (paper jam, offline, …)."
            result = _run_powershell(err["auto_fix_ps"])
            return (
                f"Okay — attempting to {err['auto_fix_label']}…\n\n{result}"
            )
        if t in NO_WORDS or t.startswith("no"):
            return (
                "No problem — I won't touch the spooler. "
                "Use the CMD lines above when you're ready, "
                f"or describe another symptom ({list_symptom_hints()})."
            )
        # Still waiting for a clear answer
        context[AWAITING_FIX_KEY] = True
        return "Say yes and I'll run the fix, or no to skip."

    # Preferred path: inspect the machine, then speak from evidence
    if engine is not None:
        from yuwontlaykit.skills import it_support

        problem = text if it_support.classify_domain(text) else f"printer problem: {text}"
        return it_support.handle(problem, context, engine)

    err = find_error(text)
    if not err:
        activate(context)
        return (
            "I'm in printer-help mode. Tell me the symptom — "
            f"{list_symptom_hints()}."
        )

    activate(context)
    context[PENDING_ERROR_KEY] = err["id"]
    context[AWAITING_FIX_KEY] = True
    return _format_guide(err)
