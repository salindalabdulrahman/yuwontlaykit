"""Diagnostic engine: inspect → analyze → explain → (ask) → remediate → verify."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from yuwontlaykit.diagnostics.analyze import analyze_case
from yuwontlaykit.diagnostics.case import TroubleshootingCase
from yuwontlaykit.diagnostics.explain import explain, technical_details
from yuwontlaykit.diagnostics.history import DiagnosticHistory
from yuwontlaykit.diagnostics.plans import Check, plan_for
from yuwontlaykit.knowledge.topics import get_topic
from yuwontlaykit.tools.base import Confidence, RiskLevel, ToolResult
from yuwontlaykit.tools.registry import ToolRegistry, builtin_registry, run_tool
from yuwontlaykit.tools.validate import is_safe_host


ProgressFn = Callable[[str], None]


class DiagnosticEngine:
    def __init__(self, registry: ToolRegistry | None = None, history: DiagnosticHistory | None = None) -> None:
        self.registry = registry
        self.history = history or DiagnosticHistory()
        self.active: TroubleshootingCase | None = None

    def _run(self, name: str, *, confirmed: bool = False, **kwargs: Any) -> ToolResult:
        if self.registry is not None:
            return self.registry.run(name, confirmed=confirmed, **kwargs)
        return run_tool(name, confirmed=confirmed, **kwargs)

    def start_case(self, problem: str, domain: str, intent: str = "problem") -> TroubleshootingCase:
        case = TroubleshootingCase(
            number=self.history.next_number(),
            problem=problem.strip() or "unspecified problem",
            domain=domain,
            result="inspecting",
        )
        case.extras["intent"] = intent
        self.active = case
        return case

    def inspect(self, case: TroubleshootingCase, progress: ProgressFn | None = None) -> TroubleshootingCase:
        intent = str(case.extras.get("intent") or "problem")
        checks = list(plan_for(case.domain, intent))
        for check in checks:
            self._run_check(case, check, progress)
        # Follow-up: ping printer IP if we discovered one (skip for simple listings)
        if intent != "inventory":
            host = _discovered_printer_host(case)
            if host:
                self._run_check(
                    case,
                    Check(
                        "test_network_connectivity",
                        "Checking whether the printer is reachable",
                        (("host", host),),
                    ),
                    progress,
                )
        case.result = "inspected"
        return case

    def _run_check(self, case: TroubleshootingCase, check: Check, progress: ProgressFn | None) -> None:
        if progress:
            progress(check.label)
        kwargs = dict(check.kwargs)
        result = self._run(check.tool, **kwargs)
        case.diagnostics.append(result)

    def analyze(self, case: TroubleshootingCase) -> TroubleshootingCase:
        analysis = analyze_case(case)
        case.topic_id = analysis.topic_id
        case.diagnosis = analysis.diagnosis
        case.confidence = analysis.confidence
        case.evidence = analysis.evidence
        case.probable_cause = analysis.probable_cause
        case.proposed = analysis.proposed
        case.extras["needs_user"] = analysis.needs_user
        if analysis.extras:
            case.extras.update(analysis.extras)
        if analysis.followup_host and is_safe_host(analysis.followup_host):
            # If we haven't pinged yet, record the candidate; inspect() may already have.
            case.extras["printer_host"] = analysis.followup_host
        case.last_technical = _build_technical(case)
        if case.confidence == Confidence.UNKNOWN and not case.proposed:
            case.result = "needs_user"
        if case not in self.history._cases:
            self.history.add(case)
        return case

    def explain(self, case: TroubleshootingCase) -> str:
        text = explain(case)
        case.last_plain = text
        return text

    def technical(self, case: TroubleshootingCase | None = None) -> str:
        target = case or self.active
        if not target:
            return "I don't have a current troubleshooting case. Describe the problem first."
        return technical_details(target)

    def apply_proposed(self, case: TroubleshootingCase) -> str:
        if not case.proposed:
            return "There's no pending repair step. I won't change anything."
        tool_name = case.proposed.tool
        spec = (self.registry or builtin_registry()).get(tool_name)
        if spec is None:
            return (
                f"I don't have an approved repair named '{tool_name}'. "
                "I will not invent a command."
            )
        if spec.risk == RiskLevel.HIGH_RISK_MODIFICATION:
            return (
                "That change is too risky for me to run automatically "
                "(it could affect your files). I need to stay read-only here."
            )
        result = self._run(tool_name, confirmed=True)
        case.actions_taken.append(
            {
                "tool": tool_name,
                "executed": result.executed,
                "success": result.success,
                "summary": result.summary,
            }
        )
        if not result.executed:
            case.result = "blocked"
            return (
                "I did not make the change. "
                + (result.error or result.summary or "The tool did not run.")
            )
        if not result.success:
            case.result = "blocked"
            return (
                "I tried, but I cannot honestly say it is fixed. "
                + (result.error or result.summary)
            )
        verify_text = self.verify(case)
        return (
            f"I ran the approved repair: {result.summary}\n\n{verify_text}"
        )

    def verify(self, case: TroubleshootingCase) -> str:
        topic = get_topic(case.topic_id) if case.topic_id else None
        names = list((topic or {}).get("verification") or [])
        if not names:
            # Re-run the original plan's first couple of reads
            names = [c.tool for c in plan_for(case.domain)[:3]]
        case.verification = []
        for name in names:
            result = self._run(name)
            case.verification.append(result)
        lines = ["Checking again after the change:"]
        for item in case.verification:
            lines.append(f"  • {item.summary}")
        # Do not claim resolved unless verification tools actually ran successfully
        ran = [v for v in case.verification if v.executed]
        if ran and all(v.success for v in ran):
            case.result = "checked_again"
            lines.append(
                "I re-checked what I can see. Please try the original task "
                "(print / open a site / play sound) to confirm it from your side — "
                "I will not pretend the problem is gone until you say it works."
            )
        else:
            case.result = "unresolved"
            lines.append(
                "I could not fully verify the result from here."
            )
        return "\n".join(lines)

    def cancel_pending(self) -> str:
        if self.active:
            self.active.awaiting = None
            self.active.proposed = None
        return "Okay — I won't change anything. We can keep looking, or you can describe another problem."


def _discovered_printer_host(case: TroubleshootingCase) -> str | None:
    ports = case.results_by_name().get("get_printer_port")
    if not ports or not isinstance(ports.data, dict):
        return None
    from yuwontlaykit.tools.runner import as_list

    for port in as_list(ports.data.get("ports")):
        if not isinstance(port, dict):
            continue
        addr = str(port.get("PrinterHostAddress") or "").strip()
        if addr and is_safe_host(addr):
            return addr
    return None


def _build_technical(case: TroubleshootingCase) -> str:
    lines = [
        f"{case.case_id}",
        f"Problem: {case.problem}",
        f"Domain: {case.domain}",
        "Diagnostics:",
    ]
    for item in case.diagnostics:
        lines.append(f"  - {item.as_evidence_line()}")
    return "\n".join(lines)
