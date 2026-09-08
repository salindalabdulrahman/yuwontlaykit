"""Chat orchestrator: routes user input to skills and profile knowledge."""

from __future__ import annotations

import logging

from yuwontlaykit.cli import console
from yuwontlaykit.diagnostics.consent import is_explicit_yes, is_no, is_yes
from yuwontlaykit.diagnostics.engine import DiagnosticEngine
from yuwontlaykit.engine.computer_commands import (
    looks_like_misspell,
    suggest_computer_command,
)
from yuwontlaykit.engine.intent_resolution import (
    apply_intent_transition,
    resolve_turn,
)
from yuwontlaykit.knowledge import entry_modes
from yuwontlaykit.knowledge.session_context import create_session_context
from yuwontlaykit.memory.session_memory import SessionMemory
from yuwontlaykit.operations.safety import USER_ACTION_FAILURE
from yuwontlaykit.people.nikko import profile as nikko_profile
from yuwontlaykit.people.nikko.bedis import BedisTease
from yuwontlaykit.people.nikko.friends.yuwontlaykit import age as friend_age
from yuwontlaykit.people.nikko.friends.yuwontlaykit import identity as friend_identity
from yuwontlaykit.people.nikko.friends.yuwontlaykit import profile as friend_profile
from yuwontlaykit.people.nikko.friends.yuwontlaykit.personal_info import BIRTHDAY
from yuwontlaykit.skills import (
    application_launch,
    calculator,
    confusion,
    conversation_start,
    datetime_skill,
    file_ops,
    greetings,
    guest_chat,
    help_menu,
    it_support,
    machine_scan,
    memory_skill,
    nikko_play,
    power_ops,
    printer_help,
    smalltalk,
)

_LOG = logging.getLogger("yuwontlaykit")


class AIEngine:
    def __init__(self, mode: str = entry_modes.GUEST):
        self.mode = mode
        self.context = create_session_context(
            user_name=entry_modes.user_display_name(mode),
            mode=mode,
        )
        self.memories = SessionMemory()
        self.bedis = BedisTease(enabled=entry_modes.is_deep_nikko(mode))
        self.diagnostics = DiagnosticEngine()
        # Preserved for compatibility with prior AIEngine API
        self.birthday = BIRTHDAY

    def address_name(self) -> str:
        if self.bedis.enabled:
            return self.bedis.address_name()
        return entry_modes.user_display_name(self.mode)

    def calculate_age(self):
        return friend_age.calculate_age(birthday=self.birthday)

    def format_age(self):
        return friend_age.format_age(birthday=self.birthday)

    def chat(self, user_input):
        try:
            self._chat(user_input)
        except Exception:
            _LOG.exception("assistant turn failed")
            console.print_assistant(USER_ACTION_FAILURE)

    def _chat(self, user_input):
        text = user_input.lower().strip()
        decision = resolve_turn(user_input, self.context, self.diagnostics)
        apply_intent_transition(decision, self.context, self.diagnostics)

        # Single if/elif chain (preserves original match priority)
        if self.bedis.matches_serious(text):
            # "Yuwon!" — drop play, get serious
            reply = self.bedis.handle_serious()
            console.set_prompt_label(self.bedis.address_name())

        elif self.context.get("awaiting_close_application") and (
            is_yes(text) or is_no(text)
        ):
            reply = application_launch.handle(user_input, self.context)

        elif self.context.get("awaiting_restart_application") and (
            is_yes(text) or is_no(text)
        ):
            reply = application_launch.handle(user_input, self.context)

        elif self.context.get("awaiting_power_action") and (
            is_yes(text) or is_no(text)
        ):
            reply = power_ops.handle(user_input, self.context)

        elif self.context.get("awaiting_search_choice") and file_ops.matches(
            user_input, self.context
        ):
            reply = file_ops.handle(user_input, self.context)

        elif application_launch.matches(user_input, self.context):
            reply = application_launch.handle(user_input, self.context)

        elif file_ops.matches(user_input, self.context):
            reply = file_ops.handle(user_input, self.context)

        elif power_ops.matches(user_input, self.context):
            reply = power_ops.handle(user_input, self.context)

        elif decision.intent == "clarify_command":
            reply = self._offer_command_clarification(user_input)

        elif self.context.get("awaiting_clarification") and (
            is_yes(text) or is_no(text)
        ):
            pending = self.context.get("pending_clarification")
            if isinstance(pending, dict) and pending.get("kind") == "computer_command":
                reply = self._finish_command_clarification(text)
            else:
                reply = it_support.handle(user_input, self.context, self.diagnostics)

        elif (
            self.diagnostics.active
            and self.diagnostics.active.awaiting == "remediate_consent"
            and (is_yes(text) or is_no(text))
        ):
            reply = it_support.handle(user_input, self.context, self.diagnostics)

        elif (
            self.diagnostics.active
            and self.diagnostics.active.awaiting == "offer_diagnose_offline"
            and (is_explicit_yes(text) or is_no(text))
        ):
            reply = it_support.handle(user_input, self.context, self.diagnostics)

        elif self.context.get("awaiting_remove_printer") and (is_yes(text) or is_no(text)):
            reply = it_support.handle(user_input, self.context, self.diagnostics)

        elif self.context.get("awaiting_it_diagnostic") and (is_yes(text) or is_no(text)):
            reply = it_support.handle(user_input, self.context, self.diagnostics)

        elif self.bedis.matches_reject(text):
            reply = self.bedis.handle_reject()
            console.set_prompt_label(self.bedis.address_name())

        elif it_support.matches(text, self.context, self.diagnostics):
            reply = it_support.handle(user_input, self.context, self.diagnostics)

        elif machine_scan.is_awaiting(self.context):
            reply = machine_scan.handle_consent(text, self.context)

        elif printer_help.matches(text, self.context):
            reply = printer_help.handle(
                user_input, self.context, engine=self.diagnostics
            )

        elif conversation_start.matches(text):
            reply = conversation_start.reply()

        elif smalltalk.matches(text):
            reply = smalltalk.reply(
                text, mode=self.mode, bedis=self.bedis, context=self.context
            )

        elif guest_chat.matches(text, self.mode):
            reply = guest_chat.reply(text, self.context)
            if guest_chat.arms_machine_scan(text):
                machine_scan.set_awaiting(self.context, True)

        elif greetings.matches(text):
            reply = greetings.reply(mode=self.mode, bedis=self.bedis)

        elif friend_identity.matches_identity_query(text):
            reply = friend_identity.IDENTITY_REPLY

        elif nikko_profile.matches_bedis_query(text):
            reply = nikko_profile.format_bedis_reply()

        elif nikko_profile.matches_query(text):
            reply = nikko_profile.format_bio()

        elif friend_profile.matches_birthday_query(text):
            reply = friend_profile.format_birthday_reply()

        elif friend_profile.matches_age_query(text):
            reply = self.format_age()

        elif datetime_skill.matches_time(text):
            reply = datetime_skill.reply_time()

        elif datetime_skill.matches_date(text):
            reply = datetime_skill.reply_date()

        elif memory_skill.matches_remember(text):
            reply = memory_skill.reply_remember(user_input, self.memories)

        elif memory_skill.matches_show(text):
            reply = memory_skill.reply_show(self.memories)

        elif help_menu.matches(text):
            reply = help_menu.reply()

        elif calculator.matches(text):
            reply = calculator.reply(text)

        elif guest_chat.matches_laugh(user_input):
            reply = confusion.laugh(self.context, user_input)

        elif nikko_play.matches(text, self.mode, self.bedis):
            reply = nikko_play.reply(text, self.bedis, self.context)
            console.set_prompt_label(self.bedis.address_name())

        else:
            printer_follow = (
                decision.relation.value == "context_continuation"
                and (
                    self.context.get("printer_help_active")
                    or self.context.get("it_support_active")
                )
            )
            if printer_follow:
                reply = guest_chat.fallback(
                    self.mode,
                    user_input,
                    self.context,
                    contextual=True,
                )
            elif looks_like_misspell(user_input, self.context):
                reply = confusion.unparsed(user_input, self.context)
            elif self.mode == entry_modes.GUEST:
                reply = guest_chat.fallback(
                    self.mode,
                    user_input,
                    self.context,
                )
            elif self.bedis.enabled:
                reply = nikko_play.fallback(self.bedis)
            else:
                reply = confusion.lost(user_input, self.context)

        console.print_assistant(reply)

    def _offer_command_clarification(self, user_input: str) -> str:
        suggestion = suggest_computer_command(user_input, self.context)
        if not suggestion:
            return "I'm not sure what you want me to do. Try saying it another way?"
        self.context["awaiting_close_application"] = False
        self.context["awaiting_restart_application"] = False
        self.context["awaiting_power_action"] = False
        self.context["awaiting_search_choice"] = False
        self.context["awaiting_clarification"] = True
        self.context["pending_clarification"] = {
            "kind": "computer_command",
            "corrected_text": suggestion.corrected_text,
        }
        return confusion.ask_if_meant(suggestion.prompt, user_input, self.context)

    def _finish_command_clarification(self, text: str) -> str:
        pending = self.context.get("pending_clarification") or {}
        corrected = str(pending.get("corrected_text") or "")
        self.context["awaiting_clarification"] = False
        self.context["pending_clarification"] = None
        if is_no(text):
            return confusion.declined(self.context)
        if not corrected:
            return "Okay. Please say that again in a few more words."
        decision = resolve_turn(corrected, self.context, self.diagnostics)
        apply_intent_transition(decision, self.context, self.diagnostics)
        if application_launch.matches(corrected, self.context):
            return application_launch.handle(corrected, self.context)
        if file_ops.matches(corrected, self.context):
            return file_ops.handle(corrected, self.context)
        if power_ops.matches(corrected, self.context):
            return power_ops.handle(corrected, self.context)
        return "Okay. Please say that again in a few more words."
