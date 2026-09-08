"""Tests for application, file, and power-assistant capabilities."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from yuwontlaykit.diagnostics.engine import DiagnosticEngine
from yuwontlaykit.diagnostics.summary import is_general_pc_check
from yuwontlaykit.engine.computer_commands import parse_computer_command, suggest_computer_command
from yuwontlaykit.engine.intent_resolution import TurnRelation, resolve_turn
from yuwontlaykit.knowledge.session_context import create_session_context
from yuwontlaykit.operations.safety import OperationClass, class_for, requires_confirmation
from yuwontlaykit.skills import it_support
from yuwontlaykit.skills.application_launch import resolve_application
from yuwontlaykit.tools.base import RiskLevel, ToolResult
from yuwontlaykit.tools.registry import ToolRegistry, ToolSpec


def _ok(name: str, **extras) -> ToolResult:
    return ToolResult(
        name=name,
        risk=RiskLevel.LOW_RISK_MODIFICATION,
        executed=True,
        available=True,
        success=True,
        summary="ok",
        extras=extras,
    )


class CommandParseTests(unittest.TestCase):
    def test_open_aliases(self):
        cases = {
            "open vscode": "vscode",
            "open VS Code": "vscode",
            "launch visual studio code": "vscode",
            "open word": "word",
            "open Microsoft Word": "word",
            "launch Excel": "excel",
            "open chrome": "chrome",
            "open Google Chrome": "chrome",
            "open postman": "postman",
            "start Postman": "postman",
            "can you start VS Code?": "vscode",
        }
        for phrase, app_id in cases.items():
            command = parse_computer_command(phrase)
            self.assertIsNotNone(command, phrase)
            self.assertEqual(command.intent, "open_application", phrase)
            self.assertEqual(command.entity, app_id, phrase)
            self.assertEqual(resolve_application(phrase), app_id, phrase)

    def test_close_and_check(self):
        close = parse_computer_command("close chrome")
        self.assertEqual(close.intent, "close_application")
        self.assertEqual(close.entity, "chrome")
        restart = parse_computer_command("restart VS Code")
        self.assertEqual(restart.intent, "restart_application")
        self.assertEqual(restart.entity, "vscode")
        check = parse_computer_command("is chrome running?")
        self.assertEqual(check.intent, "check_application")
        listing = parse_computer_command("what programs are running?")
        self.assertEqual(listing.intent, "list_running_applications")

    def test_close_it_uses_last_application(self):
        context = {"last_application": "vscode", "last_referent": {"application": "vscode"}}
        command = parse_computer_command("close it", context)
        self.assertEqual(command.intent, "close_application")
        self.assertEqual(command.entity, "vscode")
        self.assertEqual(command.relation, "context_continuation")

    def test_power_is_not_a_pc_health_check(self):
        for phrase, intent in (
            ("shutdown my pc", "shutdown_computer"),
            ("shut down the computer", "shutdown_computer"),
            ("restart my PC", "restart_computer"),
            ("lock my PC", "lock_computer"),
        ):
            command = parse_computer_command(phrase)
            self.assertEqual(command.intent, intent, phrase)
            self.assertEqual(command.category, "SYSTEM_POWER", phrase)
            self.assertFalse(is_general_pc_check(phrase), phrase)
            self.assertIsNone(it_support.classify_domain(phrase), phrase)

    def test_file_and_folder_search(self):
        payroll = parse_computer_command("find payroll")
        self.assertEqual(payroll.intent, "search_file")
        self.assertEqual(payroll.query, "payroll")
        project = parse_computer_command("find my project folder")
        self.assertEqual(project.intent, "search_folder")
        self.assertEqual(project.query, "project")
        image = parse_computer_command("look for this image: Plan-A1, and open it")
        self.assertEqual(image.intent, "search_file")
        self.assertEqual(image.kind, "image")
        self.assertEqual(image.query, "plan-a1")
        self.assertTrue(image.open_after)
        downloads = parse_computer_command("open my Downloads folder")
        self.assertEqual(downloads.intent, "open_folder")
        self.assertEqual(downloads.entity, "Downloads")
        for phrase in ("open download folder", "open the download folder"):
            command = parse_computer_command(phrase)
            self.assertEqual(command.intent, "open_folder", phrase)
            self.assertEqual(command.entity, "Downloads", phrase)
        unnamed = parse_computer_command("look for this folder and open it")
        self.assertEqual(unnamed.intent, "search_folder")
        self.assertIsNone(unnamed.query)

    def test_typo_open_downloads_is_suggested(self):
        suggestion = suggest_computer_command("pen my Downloads folder")
        self.assertIsNotNone(suggestion)
        self.assertEqual(suggestion.command.intent, "open_folder")
        self.assertEqual(suggestion.command.entity, "Downloads")
        self.assertIn("Downloads folder", suggestion.prompt)
        self.assertIsNone(parse_computer_command("pen my Downloads folder"))
        self.assertIsNone(suggest_computer_command("open my Downloads folder"))
        self.assertIsNone(suggest_computer_command("hello there"))

    def test_open_it_uses_last_file(self):
        context = {
            "last_referent": {
                "type": "file",
                "path": "/tmp/Payroll_2026.xlsx",
                "display": "Payroll_2026.xlsx",
            }
        }
        command = parse_computer_command("open it", context)
        self.assertEqual(command.intent, "open_file")
        self.assertEqual(command.entity, "/tmp/Payroll_2026.xlsx")


class RoutingTests(unittest.TestCase):
    def test_new_intents(self):
        context = create_session_context()
        expected = {
            "open vscode": "open_application",
            "open word": "open_application",
            "open excel": "open_application",
            "open chrome": "open_application",
            "open postman": "open_application",
            "close chrome": "close_application",
            "restart chrome": "restart_application",
            "is chrome running?": "check_application",
            "find payroll": "search_file",
            "find my project folder": "search_folder",
            "open my Downloads folder": "open_folder",
            "shutdown my PC": "shutdown_computer",
            "restart my PC": "restart_computer",
            "lock my PC": "lock_computer",
            "check my computer": "computer_diagnostic",
            "what is my IP?": "get_ip_address",
            "is my Wi-Fi connected?": "wifi_request",
            "find the image named logo": "search_file",
            "what programs are running?": "list_running_applications",
            "is chrome running?": "check_application",
            "pen my Downloads folder": "clarify_command",
        }
        for phrase, intent in expected.items():
            decision = resolve_turn(phrase, context)
            self.assertEqual(decision.intent, intent, phrase)
            if intent != "computer_diagnostic":
                self.assertNotEqual(decision.intent, "computer_diagnostic", phrase)

    def test_close_it_after_vscode_does_not_require_printer_context(self):
        context = create_session_context()
        context["last_application"] = "vscode"
        context["last_referent"] = {"type": "application", "application": "vscode"}
        decision = resolve_turn("close it", context)
        self.assertEqual(decision.intent, "close_application")
        self.assertEqual(decision.relation, TurnRelation.CONTEXT_CONTINUATION)

    def test_clear_intents_override_app_context(self):
        context = create_session_context()
        context["last_application"] = "vscode"
        context["last_referent"] = {"type": "application", "application": "vscode"}
        ip = resolve_turn("what's my IP?", context)
        self.assertEqual(ip.intent, "get_ip_address")
        self.assertEqual(ip.relation, TurnRelation.NEW_INTENT)
        shutdown = resolve_turn("shutdown my PC", context)
        self.assertEqual(shutdown.intent, "shutdown_computer")


class SafetyPolicyTests(unittest.TestCase):
    def test_central_classes(self):
        self.assertEqual(class_for("get_ip_address"), OperationClass.READ_ONLY)
        self.assertEqual(class_for("open_application"), OperationClass.LOW_RISK)
        self.assertTrue(requires_confirmation("close_application"))
        self.assertTrue(requires_confirmation("shutdown_computer"))
        self.assertFalse(requires_confirmation("search_files"))


class RegistrySafetyTests(unittest.TestCase):
    def test_tool_exception_does_not_escape(self):
        registry = ToolRegistry()

        def boom(**_kwargs):
            raise RuntimeError("printer removal exploded")

        registry.register(ToolSpec("remove_printer", RiskLevel.LOW_RISK_MODIFICATION, boom))
        with self.assertLogs("yuwontlaykit", level="ERROR"):
            result = registry.run("remove_printer", confirmed=True)
        self.assertFalse(result.success)
        self.assertIn("couldn't complete", result.summary.lower())

    def test_tool_name_kwarg_does_not_collide_with_tool_id(self):
        from yuwontlaykit.tools.base import ok

        registry = ToolRegistry()
        captured = {}

        def resolve(name=""):
            captured["name"] = name
            return ok("resolve_known_folder", RiskLevel.READ_ONLY, name)

        registry.register(ToolSpec("resolve_known_folder", RiskLevel.READ_ONLY, resolve))
        result = registry.run("resolve_known_folder", name="Downloads")
        self.assertTrue(result.success)
        self.assertEqual(captured["name"], "Downloads")


class ConversationTests(unittest.TestCase):
    def _engine(self):
        from yuwontlaykit.engine.ai_engine import AIEngine
        from yuwontlaykit.knowledge import entry_modes

        return AIEngine(mode=entry_modes.NIKKO_LIGHT)

    def _chat(self, ai, message, fake_run):
        replies = []
        with patch(
            "yuwontlaykit.cli.console.print_assistant",
            side_effect=lambda text: replies.append(text),
        ), patch(
            "yuwontlaykit.cli.console.print_status",
        ), patch(
            "yuwontlaykit.skills.application_launch.run_tool",
            side_effect=fake_run,
        ), patch(
            "yuwontlaykit.skills.file_ops.run_tool",
            side_effect=fake_run,
        ), patch(
            "yuwontlaykit.skills.power_ops.run_tool",
            side_effect=fake_run,
        ), patch(
            "yuwontlaykit.skills.it_support.run_tool",
            side_effect=fake_run,
        ):
            ai.chat(message)
        return replies

    def test_open_close_it_and_new_apps(self):
        ai = self._engine()
        launched = []

        def fake_run(tool, *, confirmed=False, **kwargs):
            launched.append((tool, confirmed, kwargs))
            if tool == "open_application":
                return _ok(
                    tool,
                    installed=True,
                    started=True,
                    application=kwargs.get("application"),
                )
            if tool == "close_application":
                return _ok(tool, closed=True, running=False)
            return _ok(tool)

        replies = self._chat(ai, "open vscode", fake_run)
        self.assertIn("Visual Studio Code is open. 🟢", replies[-1])
        self.assertEqual(ai.context["last_application"], "vscode")

        replies = self._chat(ai, "close it", fake_run)
        self.assertIn("Visual Studio Code", replies[-1])
        self.assertIn("yes/no", replies[-1].lower())
        self.assertTrue(ai.context["awaiting_close_application"])
        self.assertFalse(any(item[0] == "close_application" for item in launched))

        replies = self._chat(ai, "no", fake_run)
        self.assertIn("leave it open", replies[-1].lower())

        for phrase, app_id, label in (
            ("open word", "word", "Microsoft Word"),
            ("open excel", "excel", "Microsoft Excel"),
            ("open chrome", "chrome", "Google Chrome"),
            ("open postman", "postman", "Postman"),
        ):
            replies = self._chat(ai, phrase, fake_run)
            self.assertEqual(launched[-1][0], "open_application")
            self.assertEqual(launched[-1][2]["application"], app_id)
            self.assertIn(f"{label} is open.", replies[-1])

    def test_file_search_then_open_first(self):
        ai = self._engine()
        opened = []

        def fake_run(tool, *, confirmed=False, **kwargs):
            if tool == "search_user_files":
                return ToolResult(
                    name=tool,
                    risk=RiskLevel.READ_ONLY,
                    executed=True,
                    available=True,
                    success=True,
                    data=[
                        {
                            "name": "MyProject",
                            "path": "/home/nikko/Documents/MyProject",
                            "kind": "folder",
                        },
                        {
                            "name": "project-backup",
                            "path": "/home/nikko/Desktop/project-backup",
                            "kind": "folder",
                        },
                    ],
                    extras={
                        "matches": [
                            {
                                "name": "MyProject",
                                "path": "/home/nikko/Documents/MyProject",
                                "kind": "folder",
                            },
                            {
                                "name": "project-backup",
                                "path": "/home/nikko/Desktop/project-backup",
                                "kind": "folder",
                            },
                        ]
                    },
                )
            if tool == "open_path":
                opened.append(kwargs.get("path"))
                return _ok(tool, opened=True, path=kwargs.get("path"))
            return _ok(tool)

        replies = self._chat(ai, "find my project folder", fake_run)
        self.assertIn("2 folders matching 'project'", replies[-1])
        replies = self._chat(ai, "the first one", fake_run)
        self.assertEqual(opened[-1], "/home/nikko/Documents/MyProject")
        self.assertIn("open", replies[-1].lower())

    def test_open_downloads_folder(self):
        ai = self._engine()
        opened = []

        def fake_run(tool, *, confirmed=False, **kwargs):
            if tool == "resolve_known_folder":
                self.assertEqual(kwargs.get("name"), "Downloads")
                return ToolResult(
                    name=tool,
                    risk=RiskLevel.READ_ONLY,
                    executed=True,
                    available=True,
                    success=True,
                    extras={
                        "path": "/home/nikko/Downloads",
                        "name": "Downloads",
                    },
                )
            if tool == "open_path":
                opened.append(kwargs)
                return _ok(tool, opened=True, path=kwargs.get("path"))
            return _ok(tool)

        for phrase in ("open download folder", "open my Downloads folder"):
            opened.clear()
            replies = self._chat(ai, phrase, fake_run)
            self.assertEqual(opened[-1]["path"], "/home/nikko/Downloads", phrase)
            self.assertIn("Downloads is open.", replies[-1], phrase)

    def test_typo_asks_did_you_mean_then_opens_on_yes(self):
        ai = self._engine()
        opened = []

        def fake_run(tool, *, confirmed=False, **kwargs):
            if tool == "resolve_known_folder":
                return ToolResult(
                    name=tool,
                    risk=RiskLevel.READ_ONLY,
                    executed=True,
                    available=True,
                    success=True,
                    extras={"path": "/home/nikko/Downloads", "name": "Downloads"},
                )
            if tool == "open_path":
                opened.append(kwargs.get("path"))
                return _ok(tool, opened=True, path=kwargs.get("path"))
            return _ok(tool)

        replies = self._chat(ai, "pen my Downloads folder", fake_run)
        self.assertIn("Did you mean", replies[-1])
        self.assertIn("Downloads folder", replies[-1])
        self.assertRegex(
            replies[-1].lower(),
            r"wait|huh|hold on|confused|typo|misspell",
        )
        self.assertIn("yes / no", replies[-1])
        self.assertEqual(opened, [])
        self.assertTrue(ai.context.get("awaiting_clarification"))

        replies = self._chat(ai, "yes", fake_run)
        self.assertEqual(opened[-1], "/home/nikko/Downloads")
        self.assertIn("Downloads is open.", replies[-1])
        self.assertFalse(ai.context.get("awaiting_clarification"))

    def test_uncorrectable_typo_sounds_confused(self):
        ai = self._engine()

        def fake_run(tool, *, confirmed=False, **kwargs):
            return _ok(tool)

        replies = self._chat(ai, "qwrtyzx folder", fake_run)
        self.assertRegex(
            replies[-1].lower(),
            r"confused|typo|didn't quite|didn't come through|misspell|keyboard|scrambled|lost",
        )
        self.assertNotIn("I'm here", replies[-1])
        self.assertNotIn("type 'help'", replies[-1])

    def test_unknown_and_smash_replies_rotate(self):
        ai = self._engine()

        def fake_run(tool, *, confirmed=False, **kwargs):
            return _ok(tool)

        smash = [
            self._chat(ai, "edtgsDFeq", fake_run)[-1],
            self._chat(ai, "fwegWEF", fake_run)[-1],
            self._chat(ai, "qwrtyzx", fake_run)[-1],
        ]
        self.assertEqual(len(set(smash)), 3, smash)
        lost = [
            self._chat(ai, "type", fake_run)[-1],
            self._chat(ai, "whateverthisis", fake_run)[-1],
        ]
        self.assertNotEqual(lost[0], lost[1], lost)
        laugh = self._chat(ai, "HAHAHHA", fake_run)[-1].lower()
        self.assertRegex(laugh, r"laugh|haha|funny|cackling|giggle")
        self.assertNotIn("didn't catch that", laugh)

    def test_typo_did_you_mean_no_cancels(self):
        ai = self._engine()
        opened = []

        def fake_run(tool, *, confirmed=False, **kwargs):
            opened.append(tool)
            return _ok(tool, opened=True)

        self._chat(ai, "pen my Downloads folder", fake_run)
        replies = self._chat(ai, "no", fake_run)
        self.assertRegex(replies[-1].lower(), r"okay|never mind|actually want")
        self.assertNotIn("resolve_known_folder", opened)
        self.assertNotIn("open_path", opened)

    def test_shutdown_asks_and_can_be_cancelled(self):
        ai = self._engine()
        ran = []

        def fake_run(tool, *, confirmed=False, **kwargs):
            ran.append(tool)
            return _ok(tool, started=True)

        replies = self._chat(ai, "shutdown my PC", fake_run)
        self.assertIn("shut down", replies[-1].lower())
        self.assertIn("yes/no", replies[-1].lower())
        self.assertNotIn("shutdown_computer", ran)
        replies = self._chat(ai, "no", fake_run)
        self.assertIn("won't shut", replies[-1].lower())
        self.assertNotIn("shutdown_computer", ran)

    def test_app_context_does_not_steal_ip_or_cpu_question(self):
        from yuwontlaykit.engine.ai_engine import AIEngine
        from yuwontlaykit.knowledge import entry_modes

        ai = AIEngine(mode=entry_modes.NIKKO_LIGHT)
        ai.context["last_application"] = "chrome"
        ai.context["last_referent"] = {
            "type": "application",
            "application": "chrome",
        }
        ip = resolve_turn("what's my IP?", ai.context, ai.diagnostics)
        self.assertEqual(ip.intent, "get_ip_address")
        cpu = resolve_turn("what's using CPU?", ai.context, ai.diagnostics)
        self.assertEqual(cpu.intent, "list_running_applications")
        self.assertNotEqual(cpu.intent, "open_application")

    def test_printer_then_open_vscode_is_new_intent(self):
        context = create_session_context()
        context["it_support_active"] = True
        context["active_domain"] = "printer"
        engine = DiagnosticEngine()
        engine.start_case("printers", "printer", intent="inventory")
        decision = resolve_turn("open vscode", context, engine)
        self.assertEqual(decision.relation, TurnRelation.NEW_INTENT)
        self.assertEqual(decision.intent, "open_application")

    def test_chat_exception_is_user_friendly(self):
        from yuwontlaykit.engine.ai_engine import AIEngine
        from yuwontlaykit.knowledge import entry_modes
        from yuwontlaykit.operations.safety import USER_ACTION_FAILURE

        ai = AIEngine(mode=entry_modes.NIKKO_LIGHT)
        replies = []
        with self.assertLogs("yuwontlaykit", level="ERROR"), patch.object(
            ai, "_chat", side_effect=RuntimeError("boom")
        ), patch(
            "yuwontlaykit.cli.console.print_assistant",
            side_effect=lambda text: replies.append(text),
        ):
            ai.chat("open chrome")
        self.assertEqual(replies[-1], USER_ACTION_FAILURE)


if __name__ == "__main__":
    unittest.main()
