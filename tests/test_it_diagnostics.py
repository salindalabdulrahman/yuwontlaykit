"""Tests for Yuwontlaykit IT diagnostics, tools, and existing personality."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from yuwontlaykit.diagnostics.analyze import analyze_case
from yuwontlaykit.diagnostics.case import ProposedAction, TroubleshootingCase
from yuwontlaykit.diagnostics.engine import DiagnosticEngine
from yuwontlaykit.diagnostics.history import DiagnosticHistory
from yuwontlaykit.knowledge.session_context import create_session_context
from yuwontlaykit.knowledge.topics import get_topic, load_topics
from yuwontlaykit.skills import datetime_skill, guest_chat, greetings, help_menu, it_support
from yuwontlaykit.skills.calculator import matches as calc_matches
from yuwontlaykit.tools.base import Confidence, RiskLevel, ToolResult, ok
from yuwontlaykit.tools.registry import ToolRegistry, ToolSpec
from yuwontlaykit.tools.runner import parse_json
from yuwontlaykit.tools.validate import is_safe_host


def _result(
    name: str,
    summary: str,
    data=None,
    extras=None,
    success: bool = True,
    available: bool = True,
    executed: bool = True,
    risk: RiskLevel = RiskLevel.READ_ONLY,
    error: str | None = None,
) -> ToolResult:
    return ToolResult(
        name=name,
        risk=risk,
        executed=executed,
        available=available,
        success=success,
        data=data,
        summary=summary,
        error=error,
        extras=extras or {},
    )


class KnowledgeTests(unittest.TestCase):
    def test_topics_load_from_json(self):
        topics = load_topics()
        self.assertIn("printer_offline", topics)
        self.assertIn("dns_failure", topics)
        self.assertIn("computer_slow", topics)
        topic = get_topic("printer_spooler")
        self.assertIsNotNone(topic)
        self.assertEqual(topic["remediation"]["tool"], "restart_print_spooler")
        self.assertIn("plain_language", topic)

    def test_knowledge_is_not_only_python(self):
        path = Path(__file__).resolve().parents[1] / "yuwontlaykit" / "knowledge" / "topics"
        json_files = list(path.glob("*.json"))
        self.assertGreaterEqual(len(json_files), 10)


class ParseJsonTests(unittest.TestCase):
    def test_object_with_nested_array_is_not_sliced_at_first_bracket(self):
        blob = """{
    "Adapters":  [
                     {
                         "Name":  "Ethernet",
                         "Status":  "Up"
                     }
                 ],
    "IP":  [
               {
                   "InterfaceAlias":  "Ethernet",
                   "IPv4":  "172.16.86.37",
                   "Gateway":  "172.16.86.1"
               }
           ]
}"""
        payload = parse_json(blob)
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["IP"][0]["IPv4"], "172.16.86.37")
        self.assertEqual(payload["Adapters"][0]["Name"], "Ethernet")

    def test_array_payload_still_parses(self):
        self.assertEqual(parse_json("[1, 2]"), [1, 2])


class ValidateTests(unittest.TestCase):
    def test_safe_hosts(self):
        self.assertTrue(is_safe_host("8.8.8.8"))
        self.assertTrue(is_safe_host("www.microsoft.com"))
        self.assertFalse(is_safe_host("8.8.8.8; calc"))
        self.assertFalse(is_safe_host("$(whoami)"))
        self.assertFalse(is_safe_host(""))
        from yuwontlaykit.tools.validate import is_safe_printer_name

        self.assertTrue(is_safe_printer_name("POSPrinter POS58_bill/receift"))
        self.assertFalse(is_safe_printer_name("foo; Remove-Item C:\\"))


class RegistryPermissionTests(unittest.TestCase):
    def test_unknown_tool_does_not_execute(self):
        registry = ToolRegistry()
        result = registry.run("rm_rf")
        self.assertFalse(result.executed)
        self.assertIn("no approved tool", result.error.lower())

    def test_modification_requires_confirmation(self):
        calls = {"n": 0}

        def boom():
            calls["n"] += 1
            return ok("restart_print_spooler", RiskLevel.LOW_RISK_MODIFICATION, "restarted")

        registry = ToolRegistry()
        registry.register(
            ToolSpec("restart_print_spooler", RiskLevel.LOW_RISK_MODIFICATION, boom)
        )
        blocked = registry.run("restart_print_spooler")
        self.assertFalse(blocked.executed)
        self.assertEqual(calls["n"], 0)
        allowed = registry.run("restart_print_spooler", confirmed=True)
        self.assertTrue(allowed.executed)
        self.assertEqual(calls["n"], 1)

    def test_read_only_runs_without_confirmation(self):
        registry = ToolRegistry()
        registry.register(
            ToolSpec(
                "get_printers",
                RiskLevel.READ_ONLY,
                lambda: ok("get_printers", RiskLevel.READ_ONLY, "none", data=[]),
            )
        )
        result = registry.run("get_printers")
        self.assertTrue(result.executed)
        self.assertTrue(result.success)


class PrinterReasoningTests(unittest.TestCase):
    def test_no_printers(self):
        case = TroubleshootingCase(1, "printer isn't working", "printer")
        case.diagnostics = [
            _result("get_printers", "no printers", data=[]),
            _result("check_print_spooler", "Print Spooler is Running", extras={"running": True}),
            _result("get_print_queue", "0 queued", extras={"job_count": 0, "stuck_count": 0}),
        ]
        analysis = analyze_case(case)
        self.assertEqual(analysis.topic_id, "printer_not_found")
        self.assertEqual(analysis.confidence, Confidence.CONFIRMED)

    def test_spooler_stopped(self):
        case = TroubleshootingCase(1, "can't print", "printer")
        case.diagnostics = [
            _result(
                "get_printers",
                "1 printer",
                data=[{"Name": "HP Laser", "PrinterStatus": "Normal", "Default": True, "WorkOffline": False}],
            ),
            _result("check_print_spooler", "Print Spooler is Stopped", extras={"running": False, "status": "Stopped"}),
        ]
        analysis = analyze_case(case)
        self.assertEqual(analysis.topic_id, "printer_spooler")
        self.assertEqual(analysis.confidence, Confidence.CONFIRMED)
        self.assertIsNotNone(analysis.proposed)
        self.assertEqual(analysis.proposed.tool, "restart_print_spooler")

    def test_stuck_queue(self):
        case = TroubleshootingCase(1, "won't print", "printer")
        case.diagnostics = [
            _result(
                "get_printers",
                "1 printer",
                data=[{"Name": "Office", "PrinterStatus": "Normal", "WorkOffline": False}],
            ),
            _result("check_print_spooler", "running", extras={"running": True}),
            _result("get_print_queue", "3 jobs, 3 stuck", extras={"job_count": 3, "stuck_count": 3}),
        ]
        analysis = analyze_case(case)
        self.assertEqual(analysis.topic_id, "printer_queue_stuck")
        self.assertEqual(analysis.proposed.tool, "clear_print_queue")

    def test_offline_printer(self):
        case = TroubleshootingCase(1, "printer offline", "printer")
        case.diagnostics = [
            _result(
                "get_printers",
                "offline",
                data=[{"Name": "Office", "PrinterStatus": "Offline", "WorkOffline": True, "PortName": "USB001"}],
            ),
            _result("check_print_spooler", "running", extras={"running": True}),
            _result("get_print_queue", "0", extras={"job_count": 0, "stuck_count": 0}),
        ]
        analysis = analyze_case(case)
        self.assertEqual(analysis.topic_id, "printer_usb")
        self.assertEqual(analysis.confidence, Confidence.CONFIRMED)

    def test_default_printer_detection_via_rows(self):
        case = TroubleshootingCase(1, "nothing comes out", "printer")
        case.diagnostics = [
            _result(
                "get_printers",
                "2 printers",
                data=[
                    {"Name": "Microsoft Print to PDF", "PrinterStatus": "Normal", "Default": False},
                    {"Name": "Brother", "PrinterStatus": "Normal", "WorkOffline": False},
                ],
            ),
            _result(
                "get_default_printer",
                "Default printer is Microsoft Print to PDF.",
                data={"Name": "Microsoft Print to PDF", "Default": True},
            ),
            _result("check_print_spooler", "running", extras={"running": True}),
            _result("get_print_queue", "0", extras={"job_count": 0, "stuck_count": 0}),
        ]
        analysis = analyze_case(case)
        self.assertEqual(analysis.topic_id, "printer_wrong_default")


class NetworkReasoningTests(unittest.TestCase):
    def test_wifi_disconnected(self):
        case = TroubleshootingCase(1, "wifi not connecting", "wifi")
        case.diagnostics = [
            _result("get_wifi_information", "not connected", extras={"connected": False, "ssid": None}),
            _result("get_network_information", "0 up", data={"adapters": [{"Name": "Wi-Fi", "Status": "Disconnected"}]}),
            _result("test_internet", "offline", extras={"state": "offline"}),
        ]
        analysis = analyze_case(case)
        self.assertEqual(analysis.topic_id, "wifi_disconnected")
        self.assertIn("not connected", analysis.probable_cause.lower() + analysis.diagnosis.lower())

    def test_dns_vs_internet(self):
        case = TroubleshootingCase(1, "internet isn't working", "network")
        case.diagnostics = [
            _result("get_wifi_information", "HomeNet", extras={"connected": True, "ssid": "HomeNet"}),
            _result(
                "get_network_information",
                "1 up",
                data={"adapters": [{"Name": "Wi-Fi", "Status": "Up"}]},
            ),
            _result("test_internet", "dns failed", extras={"state": "dns_failed", "ip_ok": True, "dns_ok": False}),
        ]
        analysis = analyze_case(case)
        self.assertEqual(analysis.topic_id, "dns_failure")
        self.assertEqual(analysis.confidence, Confidence.CONFIRMED)

        case2 = TroubleshootingCase(2, "internet isn't working", "network")
        case2.diagnostics = [
            _result("get_wifi_information", "HomeNet", extras={"connected": True, "ssid": "HomeNet"}),
            _result(
                "get_network_information",
                "1 up",
                data={"adapters": [{"Name": "Wi-Fi", "Status": "Up"}]},
            ),
            _result("test_internet", "offline beyond router", extras={"state": "internet_failed"}),
        ]
        analysis2 = analyze_case(case2)
        self.assertEqual(analysis2.topic_id, "internet_unavailable")


class ComputerReasoningTests(unittest.TestCase):
    def test_low_disk_not_just_restart(self):
        case = TroubleshootingCase(1, "my computer is very slow", "computer")
        case.diagnostics = [
            _result("get_system_information", "Windows 11"),
            _result("get_disk_information", "C: 2 GB free (3%)", extras={"low_space": ["C:"]}),
            _result("get_running_processes", "chrome, teams"),
        ]
        analysis = analyze_case(case)
        self.assertEqual(analysis.topic_id, "disk_full")
        self.assertNotIn("restart your computer", (analysis.probable_cause or "").lower())

    def test_general_pc_check_uses_health_summary_when_checks_are_healthy(self):
        from yuwontlaykit.diagnostics.summary import (
            format_computer_health_summary,
            is_general_pc_check,
        )

        self.assertTrue(is_general_pc_check("check my PC"))
        self.assertFalse(is_general_pc_check("my computer is frozen"))
        case = TroubleshootingCase(1, "check my PC", "computer")
        case.diagnostics = [
            _result(
                "get_system_information",
                "Windows 11",
                data={
                    "CPU": {"LoadPercentage": 24},
                    "OS": {
                        "TotalVisibleMemorySize": 16_000_000,
                        "FreePhysicalMemory": 8_000_000,
                    },
                },
            ),
            _result(
                "get_disk_information",
                "C: 200 GB free",
                extras={"low_space": []},
            ),
            _result("get_running_processes", "Top processes: app1, app2"),
            _result("get_startup_applications", "4 startup items"),
            _result("get_network_information", "Ethernet is up"),
            _result(
                "test_internet",
                "Internet name lookup and public address succeeded.",
                extras={"state": "ok"},
            ),
            _result(
                "get_printers",
                "2 printers",
                data=[{"Name": "EPSON"}, {"Name": "PDF"}],
            ),
        ]

        text = format_computer_health_summary(case, user_name="Nikko")
        self.assertIn("I finished checking your PC, Nikko.", text)
        self.assertIn("working normally", text)
        self.assertIn("System performance", text)
        self.assertIn("Storage", text)
        self.assertIn("Running programs", text)
        self.assertIn("Startup programs", text)
        self.assertIn("Network", text)
        self.assertIn("Printers", text)
        self.assertIn("software-level health check", text)
        self.assertIn("CPU load was 24%", text)
        self.assertIn("memory usage was 50%", text)

    def test_pc_health_summary_does_not_claim_healthy_when_incomplete(self):
        from yuwontlaykit.diagnostics.summary import format_computer_health_summary

        case = TroubleshootingCase(1, "check my PC", "computer")
        case.diagnostics = [
            _result("get_system_information", "Windows 11"),
            _result(
                "get_disk_information",
                "C: low",
                extras={"low_space": ["C:"]},
            ),
        ]
        text = format_computer_health_summary(case, user_name="Nikko")
        self.assertNotIn("looks to be **working normally**", text)
        self.assertIn("needs attention", text)
        self.assertIn("low storage", text)
        self.assertIn("incomplete checks", text)


class EngineFlowTests(unittest.TestCase):
    def _engine(self, results: dict[str, ToolResult]) -> DiagnosticEngine:
        registry = ToolRegistry()

        def make_fn(res: ToolResult):
            def _fn(**kwargs):
                return res

            return _fn

        for name, res in results.items():
            risk = res.risk
            registry.register(ToolSpec(name, risk, make_fn(res)))
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()
        return DiagnosticEngine(registry=registry, history=DiagnosticHistory(path=Path(tmp.name)))

    def test_inspect_analyze_does_not_claim_fix(self):
        engine = self._engine(
            {
                "get_printers": _result("get_printers", "none", data=[]),
                "get_default_printer": _result("get_default_printer", "none", data=None),
                "get_printer_status": _result("get_printer_status", "none", data=[]),
                "get_printer_port": _result("get_printer_port", "none", data={"ports": [], "printers": []}),
                "get_printer_driver": _result("get_printer_driver", "none", data={"drivers": [], "printers": []}),
                "get_print_queue": _result("get_print_queue", "0", extras={"job_count": 0, "stuck_count": 0}),
                "check_print_spooler": _result("check_print_spooler", "running", extras={"running": True}),
            }
        )
        case = engine.start_case("My printer isn't working.", "printer")
        engine.inspect(case)
        engine.analyze(case)
        text = engine.explain(case)
        self.assertNotIn("I fixed", text.lower())
        self.assertIn("not found", text.lower() + (case.diagnosis or "").lower())

    def test_remediation_blocked_without_permission_and_honesty(self):
        ran = {"spooler": False}

        def restart():
            ran["spooler"] = True
            return ok("restart_print_spooler", RiskLevel.LOW_RISK_MODIFICATION, "restarted")

        registry = ToolRegistry()
        registry.register(
            ToolSpec("restart_print_spooler", RiskLevel.LOW_RISK_MODIFICATION, restart)
        )
        engine = DiagnosticEngine(registry=registry, history=DiagnosticHistory(path=Path(tempfile.mkstemp()[1])))
        case = engine.start_case("spooler", "printer")
        case.proposed = ProposedAction("restart_print_spooler", "restart printing", "needs admin")
        # Direct apply is what handle() does after yes — without going through registry confirmed
        # First: registry itself must not run without confirmed
        blocked = registry.run("restart_print_spooler")
        self.assertFalse(blocked.executed)
        self.assertFalse(ran["spooler"])
        reply = engine.apply_proposed(case)
        self.assertTrue(ran["spooler"])
        self.assertNotIn("I fixed your printer", reply)

    def test_missing_windows_is_honest(self):
        case = TroubleshootingCase(1, "printer", "printer")
        case.diagnostics = [
            _result(
                "get_printers",
                "PowerShell missing",
                available=False,
                executed=False,
                success=False,
                error="PowerShell is not available",
            )
        ]
        analysis = analyze_case(case)
        self.assertIn("cannot inspect", analysis.diagnosis.lower())
        self.assertFalse(analysis.proposed)


class IntentTests(unittest.TestCase):
    def test_example_phrases(self):
        self.assertEqual(it_support.classify_domain("My printer isn't working."), "printer")
        self.assertEqual(it_support.classify_domain("My Wi-Fi is not connecting."), "wifi")
        self.assertEqual(it_support.classify_domain("My computer is very slow."), "computer")
        self.assertEqual(it_support.classify_domain("I can't hear anything."), "audio")
        self.assertEqual(it_support.classify_domain("My application won't open."), "software")
        self.assertEqual(it_support.classify_domain("The internet isn't working."), "network")
        self.assertEqual(it_support.classify_domain("My computer can't find the printer."), "printer")
        self.assertEqual(it_support.classify_domain("Can you check my computer?"), "computer")

    def test_datetime_does_not_steal_update(self):
        self.assertFalse(datetime_skill.matches_date("windows update is broken"))
        self.assertTrue(datetime_skill.matches_date("what is today's date?"))
        self.assertTrue(datetime_skill.matches_time("what time is it?"))

    def test_list_printers_is_inventory_not_a_fault(self):
        from yuwontlaykit.diagnostics.intent import (
            clarification_suggestion,
            classify_intent,
        )

        phrase = "can you check what printer that installed to this Pc?"
        self.assertEqual(it_support.classify_domain(phrase), "printer")
        self.assertEqual(classify_intent(phrase), "inventory")
        for variant in (
            "list the install printer here",
            "list the installed printers on this PC",
            "show printers installed here",
            "display available printer in my computer",
            "which printer is installed?",
        ):
            self.assertEqual(
                classify_intent(variant),
                "inventory",
                msg=variant,
            )
        self.assertEqual(classify_intent("My printer isn't working."), "problem")
        self.assertEqual(
            clarification_suggestion("display available pc in this pc"),
            "printer_inventory",
        )
        self.assertIsNone(
            clarification_suggestion("display available apps in this pc")
        )


class PrinterInventoryTests(unittest.TestCase):
    def test_lists_printers_even_if_spooler_is_stopped(self):
        from yuwontlaykit.diagnostics.explain import explain

        case = TroubleshootingCase(1, "what printers are installed", "printer")
        case.extras["intent"] = "inventory"
        case.diagnostics = [
            _result(
                "get_printers",
                "2 printers",
                data=[
                    {
                        "Name": "HP LaserJet",
                        "PrinterStatus": "Normal",
                        "Default": True,
                        "PortName": "USB001",
                    },
                    {
                        "Name": "Microsoft Print to PDF",
                        "PrinterStatus": "Normal",
                        "Default": False,
                        "PortName": "PORTPROMPT:",
                    },
                ],
            ),
            _result(
                "get_default_printer",
                "HP LaserJet",
                data={"Name": "HP LaserJet", "Default": True},
            ),
            _result(
                "check_print_spooler",
                "Stopped",
                extras={"running": False, "status": "Stopped"},
            ),
        ]
        analysis = analyze_case(case)
        self.assertEqual(analysis.diagnosis, "Printer inventory")
        self.assertTrue(analysis.extras.get("printer_lines"))
        self.assertIn("HP LaserJet", analysis.extras["printer_lines"][0])
        self.assertIsNone(analysis.proposed)
        case.extras.update(analysis.extras)
        case.proposed = analysis.proposed
        case.diagnosis = analysis.diagnosis
        text = explain(case)
        self.assertIn("HP LaserJet", text)
        self.assertNotIn("Case #", text)
        self.assertNotIn("paper jam", text.lower())
        self.assertNotIn("Side note", text)
        self.assertNotIn("Would you like me", text)
        self.assertNotIn("I haven't changed", text)
        self.assertNotIn("technical details", text.lower())

    def test_empty_list_with_spooler_down_is_still_just_a_list_answer(self):
        from yuwontlaykit.diagnostics.explain import explain

        case = TroubleshootingCase(1, "check what printer is installed", "printer")
        case.extras["intent"] = "inventory"
        case.diagnostics = [
            _result("get_printers", "none", data=[]),
            _result(
                "check_print_spooler",
                "Stopped",
                extras={"running": False, "status": "Stopped"},
            ),
        ]
        analysis = analyze_case(case)
        self.assertEqual(analysis.diagnosis, "No printers listed")
        self.assertIsNone(analysis.proposed)
        case.extras.update(analysis.extras)
        case.proposed = analysis.proposed
        case.diagnosis = analysis.diagnosis
        case.probable_cause = analysis.probable_cause
        text = explain(case)
        self.assertIn("did not report any printers", text.lower())
        self.assertNotIn("paper jam", text.lower())
        self.assertNotIn("Would you like me", text)
        self.assertNotIn("What I think is going on", text)

    def test_which_one_is_online_followup(self):
        from yuwontlaykit.diagnostics.explain import explain_online_followup
        from yuwontlaykit.diagnostics.intent import classify_intent

        self.assertEqual(classify_intent("which one is online?"), "followup_online")
        case = TroubleshootingCase(1, "printers installed", "printer")
        case.extras["printer_rows"] = [
            {"Name": "EPSON L6460 - Unit 2", "PrinterStatus": "Normal", "WorkOffline": False, "PortName": "USB001"},
            {"Name": "EPSON L6460 - Unit 1", "PrinterStatus": "Offline", "WorkOffline": True, "PortName": "USB002"},
            {"Name": "AnyDesk Printer", "PrinterStatus": "Normal", "WorkOffline": False, "PortName": "TS001"},
            {"Name": "EPSON L565 Series", "PrinterStatus": "", "WorkOffline": False, "PortName": "WSD-abc"},
        ]
        text = explain_online_followup(case)
        self.assertIn("EPSON L6460 - Unit 2", text)
        self.assertIn("confirmed online", text.lower())
        self.assertNotIn("None look online", text)
        self.assertNotIn("Would you like me to restart", text.lower())

    def test_pick_one_prefers_desk_printer_over_pos(self):
        from yuwontlaykit.diagnostics.explain import explain_pick_followup
        from yuwontlaykit.diagnostics.intent import classify_intent

        self.assertEqual(classify_intent("pick one"), "followup_pick")
        self.assertEqual(classify_intent("pick obne"), "followup_pick")
        case = TroubleshootingCase(1, "printers", "printer")
        case.extras["printer_rows"] = [
            {
                "Name": "POSPrinter POS58_bill/receift",
                "PrinterStatus": "Normal",
                "PortName": "USB001",
                "WorkOffline": False,
            },
            {
                "Name": "EPSON L3110 Series",
                "PrinterStatus": "Normal",
                "PortName": "USB002",
                "WorkOffline": False,
            },
            {
                "Name": "Microsoft Print to PDF",
                "PrinterStatus": "Normal",
                "PortName": "PORTPROMPT:",
                "WorkOffline": False,
            },
        ]
        text = explain_pick_followup(case)
        self.assertIn("EPSON L3110 Series", text)
        self.assertNotIn("POSPrinter", text)
        self.assertNotIn("What do you want next", text)

    def test_display_only_online_lists_without_diagnostic(self):
        from yuwontlaykit.diagnostics.explain import explain_online_followup
        from yuwontlaykit.diagnostics.intent import classify_intent

        phrases = (
            "display only the online",
            "again list the reachable printer in this pc",
            "show reachable printers",
            "list online printer again",
            "display connected printers",
            "give me the ready printers",
            "list the reachble printer",
        )
        for phrase in phrases:
            self.assertEqual(
                classify_intent(phrase),
                "followup_online_list",
                msg=phrase,
            )
            self.assertEqual(it_support.classify_domain(phrase), "printer")
            self.assertNotEqual(it_support.classify_domain(phrase), "hardware")
        self.assertEqual(
            classify_intent("this printer is not reachable"),
            "problem",
        )

        case = TroubleshootingCase(1, "printers", "printer")
        case.extras["printer_rows"] = [
            {
                "Name": "EPSON L6460 - Unit 2",
                "PrinterStatus": "Normal",
                "PortName": "USB001",
                "WorkOffline": False,
            },
            {
                "Name": "EPSON L565 Series",
                "PrinterStatus": "Normal",
                "PortName": "USB002",
                "WorkOffline": False,
            },
            {
                "Name": "Microsoft Print to PDF",
                "PrinterStatus": "Normal",
                "PortName": "PORTPROMPT:",
                "WorkOffline": False,
            },
        ]
        text = explain_online_followup(case, list_only=True)
        self.assertIn("Sure. These are the printers currently confirmed online:", text)
        self.assertIn("🟢 EPSON L6460 - Unit 2", text)
        self.assertIn("🟢 EPSON L565 Series", text)
        self.assertIn("2 online printers found.", text)
        self.assertNotIn("Microsoft Print to PDF", text)
        self.assertNotIn("quick diagnostic", text.lower())
        self.assertNotIn("Want me to", text)
        self.assertIsNone(case.awaiting)

    def test_online_status_buckets_with_reachability(self):
        from yuwontlaykit.diagnostics.explain import explain_online_followup

        case = TroubleshootingCase(1, "printers", "printer")
        case.extras["printer_rows"] = [
            {"Name": "EPSON L6460 - Unit 2", "PrinterStatus": "Normal", "PortName": "IP_192.168.1.20", "WorkOffline": False},
            {"Name": "EPSON L6460 - Unit 1", "PrinterStatus": "Normal", "PortName": "IP_192.168.1.21", "WorkOffline": False},
            {"Name": "POSPrinter POS58", "PrinterStatus": "Unknown", "PortName": "USB001", "WorkOffline": False},
            {"Name": "AnyDesk Printer", "PrinterStatus": "Normal", "PortName": "TS001", "WorkOffline": False},
        ]
        case.extras["printer_ports"] = [
            {"Name": "IP_192.168.1.20", "PrinterHostAddress": "192.168.1.20"},
            {"Name": "IP_192.168.1.21", "PrinterHostAddress": "192.168.1.21"},
        ]
        text = explain_online_followup(
            case,
            reachability={"192.168.1.20": True, "192.168.1.21": False},
            detailed=True,
        )
        self.assertIn("EPSON L6460 - Unit 2", text)
        self.assertIn("Online", text)
        self.assertIn("Offline / Unreachable", text)
        self.assertIn("EPSON L6460 - Unit 1", text)
        self.assertIn("cannot be confirmed", text)
        self.assertIn("AnyDesk Printer", text)
        self.assertIn("What I checked", text)

    def test_usb_port_is_not_pinged_as_host(self):
        from yuwontlaykit.diagnostics.printer_status import classify_printers

        items = classify_printers(
            [{"Name": "EPSON L3110 Series", "PrinterStatus": "", "PortName": "USB001", "WorkOffline": False}],
            ports=[],
            reachability={},
        )
        self.assertEqual(items[0].bucket, "unknown")

        items2 = classify_printers(
            [{"Name": "EPSON Unit 2", "PrinterStatus": "Normal", "PortName": "IP_192.168.1.20", "WorkOffline": False}],
            ports=[{"Name": "IP_192.168.1.20", "PrinterHostAddress": "192.168.1.20"}],
            reachability={"192.168.1.20": True},
        )
        self.assertEqual(items2[0].bucket, "online")


class PersonalityRegressionTests(unittest.TestCase):
    def test_guest_laugh_and_help_still_work(self):
        from yuwontlaykit.knowledge import entry_modes

        self.assertTrue(guest_chat.matches("hahaha", entry_modes.GUEST))
        self.assertTrue(help_menu.matches("help"))
        self.assertIn("printer", help_menu.reply().lower())
        self.assertTrue(calc_matches("calc 2+2"))

    def test_smalltalk_for_nikko(self):
        from yuwontlaykit.knowledge import entry_modes
        from yuwontlaykit.skills import smalltalk

        self.assertTrue(smalltalk.matches("all goods"))
        self.assertTrue(smalltalk.matches("heyyy"))
        self.assertTrue(smalltalk.matches("can you help me?"))
        self.assertTrue(smalltalk.matches("i need your help"))
        self.assertTrue(smalltalk.matches("I need some help!"))
        self.assertTrue(smalltalk.matches("could you please help me"))
        self.assertTrue(smalltalk.matches("i need help0"))
        self.assertEqual(
            smalltalk.reply("i need help0", entry_modes.NIKKO_LIGHT),
            "Of course. What's going on?",
        )
        self.assertEqual(
            smalltalk.reply("i need your help", entry_modes.NIKKO_LIGHT),
            "Of course. What's going on?",
        )
        self.assertIn("Good to hear", smalltalk.reply("all goods", entry_modes.NIKKO_LIGHT))
        self.assertIn("What's up", smalltalk.reply("heyyy", entry_modes.NIKKO_LIGHT))
        self.assertEqual(
            smalltalk.reply("can you help me?", entry_modes.NIKKO_LIGHT),
            "Of course. What's going on?",
        )
        self.assertTrue(smalltalk.matches("thank you"))
        self.assertTrue(smalltalk.matches("thanks"))
        self.assertEqual(
            smalltalk.reply("thank you", entry_modes.NIKKO_LIGHT),
            "You're welcome. Anytime.",
        )
        self.assertTrue(smalltalk.matches("okay"))
        self.assertEqual(
            smalltalk.reply("okay", entry_modes.NIKKO_LIGHT),
            "Okay. What else do you need?",
        )

    def test_vague_help_does_not_arm_printer_scan(self):
        self.assertFalse(guest_chat.arms_machine_scan("can you help me?"))
        self.assertTrue(guest_chat.arms_machine_scan("my printer is not working"))

    def test_it_support_does_not_eat_hello(self):
        ctx = create_session_context()
        engine = DiagnosticEngine(registry=ToolRegistry())
        self.assertFalse(it_support.matches("hello", ctx, engine))
        self.assertFalse(it_support.matches("who are you", ctx, engine))
        self.assertFalse(it_support.matches("all goods", ctx, engine))
        self.assertFalse(it_support.matches("can you help me?", ctx, engine))

    def test_pending_repair_does_not_swallow_identity(self):
        ctx = create_session_context()
        engine = DiagnosticEngine(registry=ToolRegistry())
        case = engine.start_case("printer", "printer")
        case.awaiting = "remediate_consent"
        engine.active = case
        self.assertFalse(it_support.matches("who are you", ctx, engine))
        self.assertTrue(it_support.matches("yes", ctx, engine))
        self.assertTrue(it_support.matches("no", ctx, engine))

    def test_ip_lookup_is_not_a_computer_diagnostic(self):
        from yuwontlaykit.diagnostics.intent import classify_intent, is_ip_lookup
        from yuwontlaykit.diagnostics.ip_lookup import format_ip_lookup
        from yuwontlaykit.knowledge import entry_modes
        from yuwontlaykit.engine.ai_engine import AIEngine

        phrases = (
            "can you show what ip address does this machine?",
            "show me the ip adress of my pc",
            "show me the IP address of my PC",
        )
        for phrase in phrases:
            self.assertTrue(is_ip_lookup(phrase), phrase)
            self.assertEqual(classify_intent(phrase), "inventory")
            self.assertEqual(it_support.classify_domain(phrase), "network")
            self.assertTrue(it_support.matches(phrase, create_session_context(), DiagnosticEngine()))

        net = _result(
            "get_network_information",
            "2 adapters",
            data={
                "adapters": [
                    {"Name": "Ethernet", "Status": "Up"},
                    {"Name": "Wi-Fi", "Status": "Up"},
                    {"Name": "vEthernet (WSL)", "Status": "Up"},
                ],
                "ip": [
                    {
                        "InterfaceAlias": "vEthernet (WSL)",
                        "IPv4": "172.20.80.1",
                        "Gateway": "",
                    },
                    {
                        "InterfaceAlias": "Ethernet",
                        "IPv4": "192.168.1.105",
                        "Gateway": "192.168.1.1",
                    },
                    {
                        "InterfaceAlias": "Wi-Fi",
                        "IPv4": "192.168.1.200",
                        "Gateway": "192.168.1.1",
                    },
                ],
            },
        )
        sysinfo = _result(
            "get_system_information",
            "Windows",
            data={"OS": {"CSName": "ICO-NIKKO"}},
        )
        card = format_ip_lookup(net, sysinfo)
        self.assertIn("ICO-NIKKO", card)
        self.assertIn("192.168.1.105", card)
        self.assertIn("Ethernet", card)
        self.assertIn("192.168.1.1", card)
        self.assertIn("Your local IP address is **192.168.1.105**.", card)
        self.assertNotIn("Case #", card)
        self.assertNotIn("172.20.80.1", card)

        captured = []
        statuses = []

        def fake_run(name: str, *, confirmed: bool = False, **kwargs):
            if name == "get_network_information":
                return net
            if name == "get_system_information":
                return sysinfo
            return _result(name, "unused")

        with patch(
            "yuwontlaykit.engine.ai_engine.console.print_assistant",
            side_effect=lambda m: captured.append(m),
        ), patch(
            "yuwontlaykit.skills.it_support.console.print_status",
            side_effect=lambda m: statuses.append(m),
        ):
            ai = AIEngine(mode=entry_modes.NIKKO_LIGHT)
            ai.diagnostics._run = fake_run
            ai.chat("can you show what ip address does this machine?")
            first = captured[-1]
            ai.chat("show me the ip adress of my pc")
            second = captured[-1]

        for reply in (first, second):
            self.assertIn("192.168.1.105", reply)
            self.assertIn("ICO-NIKKO", reply)
            self.assertNotIn("Case #", reply)
            self.assertNotIn("quick diagnostic", reply.lower())
            self.assertNotIn("Computer snapshot", reply)
        self.assertFalse(ai.context.get("awaiting_it_diagnostic"))
        self.assertFalse(ai.context.get("it_support_active"))
        self.assertEqual(ai.context.get("last_lookup"), "ip")
        self.assertTrue(any("network interfaces" in s.lower() for s in statuses))

    def test_ip_followups_retry_instead_of_falling_through(self):
        from yuwontlaykit.knowledge import entry_modes
        from yuwontlaykit.engine.ai_engine import AIEngine

        net = _result(
            "get_network_information",
            "1 adapter",
            data={
                "adapters": [{"Name": "Ethernet", "Status": "Up"}],
                "ip": [
                    {
                        "InterfaceAlias": "Ethernet",
                        "IPv4": "172.16.86.37",
                        "Gateway": "172.16.86.1",
                    }
                ],
            },
        )
        sysinfo = _result(
            "get_system_information",
            "Windows",
            data={"OS": {"CSName": "ICO-NIKKO"}},
        )
        captured = []

        def fake_run(name: str, *, confirmed: bool = False, **kwargs):
            if name == "get_network_information":
                return net
            if name == "get_system_information":
                return sysinfo
            return _result(name, "unused")

        with patch(
            "yuwontlaykit.engine.ai_engine.console.print_assistant",
            side_effect=lambda m: captured.append(m),
        ), patch(
            "yuwontlaykit.skills.it_support.console.print_status",
        ):
            ai = AIEngine(mode=entry_modes.NIKKO_LIGHT)
            ai.diagnostics._run = fake_run
            ai.chat("i need to know my pc ip address")
            ai.chat("why?")
            self.assertIn("172.16.86.37", captured[-1])
            self.assertNotIn("I'm here", captured[-1])
            ai.chat("please badly need it to know")
            self.assertIn("172.16.86.37", captured[-1])
            ai.chat("re try it")
            self.assertIn("172.16.86.37", captured[-1])
            self.assertIn("ICO-NIKKO", captured[-1])

    def test_printer_problem_asks_consent_first(self):
        from yuwontlaykit.knowledge import entry_modes
        from yuwontlaykit.engine.ai_engine import AIEngine
        from unittest.mock import patch

        captured = []
        with patch(
            "yuwontlaykit.engine.ai_engine.console.print_assistant",
            side_effect=lambda m: captured.append(m),
        ):
            ai = AIEngine(mode=entry_modes.NIKKO_LIGHT)
            ai.chat("my printer isn't working")
        self.assertTrue(ai.context.get("awaiting_it_diagnostic"))
        self.assertIn("quick diagnostic", captured[-1].lower())
        self.assertIn("yes / no", captured[-1].lower())
        self.assertNotIn("Here's what I found", captured[-1])

    def test_natural_printer_list_request_answers_immediately(self):
        from yuwontlaykit.engine.ai_engine import AIEngine
        from yuwontlaykit.knowledge import entry_modes

        printer_rows = [
            {
                "Name": "EPSON L3110 Series",
                "PrinterStatus": "Normal",
                "Default": True,
                "PortName": "USB001",
                "WorkOffline": False,
            }
        ]

        def fake_run(name: str, *, confirmed: bool = False, **kwargs):
            if name in {"get_printers", "get_printer_status"}:
                return _result(name, "1 printer", data=printer_rows)
            if name == "get_default_printer":
                return _result(
                    name,
                    "Default printer is EPSON L3110 Series",
                    data={"Name": "EPSON L3110 Series", "Default": True},
                )
            if name == "get_printer_port":
                return _result(name, "1 port", data={"ports": [], "printers": []})
            if name == "check_print_spooler":
                return _result(name, "Running", extras={"running": True})
            return _result(name, "unused")

        captured = []
        with patch(
            "yuwontlaykit.engine.ai_engine.console.print_assistant",
            side_effect=lambda message: captured.append(message),
        ), patch("yuwontlaykit.skills.it_support.console.print_status"):
            ai = AIEngine(mode=entry_modes.NIKKO_LIGHT)
            ai.diagnostics._run = fake_run
            ai.chat("list the install printer here")

        self.assertIn("Installed printers:", captured[-1])
        self.assertIn("EPSON L3110 Series", captured[-1])
        self.assertNotIn("quick diagnostic", captured[-1].lower())
        self.assertFalse(ai.context.get("awaiting_it_diagnostic"))

    def test_confusing_inventory_request_asks_did_you_mean(self):
        from yuwontlaykit.engine.ai_engine import AIEngine
        from yuwontlaykit.knowledge import entry_modes

        printer_rows = [
            {
                "Name": "EPSON L3110 Series",
                "PrinterStatus": "Normal",
                "Default": False,
                "PortName": "USB001",
                "WorkOffline": False,
            }
        ]

        def fake_run(name: str, *, confirmed: bool = False, **kwargs):
            if name in {"get_printers", "get_printer_status"}:
                return _result(name, "1 printer", data=printer_rows)
            if name == "get_default_printer":
                return _result(name, "No default", data=None)
            if name == "get_printer_port":
                return _result(name, "1 port", data={"ports": [], "printers": []})
            if name == "check_print_spooler":
                return _result(name, "Running", extras={"running": True})
            return _result(name, "unused")

        captured = []
        with patch(
            "yuwontlaykit.engine.ai_engine.console.print_assistant",
            side_effect=lambda message: captured.append(message),
        ), patch("yuwontlaykit.skills.it_support.console.print_status"):
            ai = AIEngine(mode=entry_modes.NIKKO_LIGHT)
            ai.diagnostics._run = fake_run
            ai.chat("display available pc in this pc")

            self.assertIn("Did you mean", captured[-1])
            self.assertIn("printers installed on this PC", captured[-1])
            self.assertTrue(ai.context.get("awaiting_clarification"))

            ai.chat("yes")

        self.assertIn("Installed printers:", captured[-1])
        self.assertIn("EPSON L3110 Series", captured[-1])
        self.assertFalse(ai.context.get("awaiting_clarification"))
        self.assertNotIn("quick diagnostic", captured[-1].lower())


    def test_okay_does_not_launch_printer_diagnostic(self):
        from yuwontlaykit.knowledge import entry_modes
        from yuwontlaykit.engine.ai_engine import AIEngine

        captured = []
        with patch(
            "yuwontlaykit.engine.ai_engine.console.print_assistant",
            side_effect=lambda m: captured.append(m),
        ), patch(
            "yuwontlaykit.skills.it_support.console.print_status",
        ):
            ai = AIEngine(mode=entry_modes.NIKKO_LIGHT)
            case = ai.diagnostics.start_case("printers", "printer")
            case.awaiting = "offer_diagnose_offline"
            case.extras["diagnose_targets"] = ["EPSON L565 Series"]
            ai.context["it_support_active"] = True
            ai.chat("okay")
        self.assertTrue(captured)
        self.assertNotIn("Here's what I found", captured[-1])
        self.assertNotIn("Print Spooler", captured[-1])
        self.assertIn("Okay", captured[-1])

    def test_remove_printer_asks_consent_not_diagnostic(self):
        ctx = create_session_context()
        engine = DiagnosticEngine(registry=ToolRegistry())
        case = engine.start_case("list printers", "printer", intent="inventory")
        case.extras["printer_rows"] = [
            {"Name": "POSPrinter POS58_bill/receift", "PrinterStatus": "Normal", "PortName": "USB001"}
        ]
        engine.active = case
        reply = it_support.handle(
            "can you remove this printer to this machine? 🟢 POSPrinter POS58_bill/receift — Online",
            ctx,
            engine,
        )
        self.assertIn("remove it", reply.lower())
        self.assertIn("POSPrinter POS58_bill/receift", reply)
        self.assertNotIn("quick diagnostic", reply.lower())
        self.assertTrue(ctx.get("awaiting_remove_printer"))
        self.assertEqual(ctx.get("pending_remove_printer"), "POSPrinter POS58_bill/receift")

        removed = []

        def fake_run(tool: str, *, confirmed: bool = False, **kwargs):
            removed.append((tool, confirmed, kwargs))
            return _result(
                "remove_printer",
                f"Removed {kwargs.get('printer_name')}",
                extras={"name": kwargs.get("printer_name")},
            )

        engine._run = fake_run
        done = it_support.handle("yes", ctx, engine)
        self.assertIn("no longer installed", done)
        self.assertEqual(removed[0][0], "remove_printer")
        self.assertTrue(removed[0][1])
        self.assertEqual(removed[0][2].get("printer_name"), "POSPrinter POS58_bill/receift")
        self.assertNotIn("name", removed[0][2])


class ServiceAndSystemToolShapeTests(unittest.TestCase):
    def test_builtin_catalog_contains_required_tools(self):
        from yuwontlaykit.tools.catalog import build_registry

        names = set(build_registry().names())
        required = {
            "get_system_information",
            "get_network_information",
            "get_wifi_information",
            "get_default_printer",
            "get_printers",
            "get_printer_status",
            "get_printer_port",
            "get_printer_driver",
            "get_print_queue",
            "check_print_spooler",
            "test_network_connectivity",
            "test_dns",
            "get_windows_services",
            "get_device_information",
            "get_disk_information",
            "get_running_processes",
            "get_event_logs",
        }
        self.assertTrue(required.issubset(names), msg=sorted(required - names))

    @patch("yuwontlaykit.tools.windows.powershell_exe", return_value=None)
    def test_windows_tools_unavailable_without_powershell(self, _mock):
        from yuwontlaykit.tools import printers

        result = printers.get_printers()
        self.assertFalse(result.executed)
        self.assertFalse(result.available)
        self.assertIn("PowerShell", result.summary)


if __name__ == "__main__":
    unittest.main()
