"""Chat orchestrator: routes user input to skills and profile knowledge."""

from yuwontlaykit.cli import console
from yuwontlaykit.knowledge import entry_modes
from yuwontlaykit.knowledge.session_context import create_session_context
from yuwontlaykit.memory.session_memory import SessionMemory
from yuwontlaykit.people.nikko import profile as nikko_profile
from yuwontlaykit.people.nikko.bedis import BedisTease
from yuwontlaykit.people.nikko.friends.yuwontlaykit import age as friend_age
from yuwontlaykit.people.nikko.friends.yuwontlaykit import identity as friend_identity
from yuwontlaykit.people.nikko.friends.yuwontlaykit import profile as friend_profile
from yuwontlaykit.people.nikko.friends.yuwontlaykit.personal_info import BIRTHDAY
from yuwontlaykit.skills import (
    calculator,
    conversation_start,
    datetime_skill,
    greetings,
    guest_chat,
    help_menu,
    machine_scan,
    memory_skill,
    nikko_play,
    printer_help,
)


class AIEngine:
    def __init__(self, mode: str = entry_modes.GUEST):
        self.mode = mode
        self.context = create_session_context(
            user_name=entry_modes.user_display_name(mode),
            mode=mode,
        )
        self.memories = SessionMemory()
        self.bedis = BedisTease(enabled=entry_modes.is_deep_nikko(mode))
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
        text = user_input.lower().strip()

        # Single if/elif chain (preserves original match priority)
        if self.bedis.matches_serious(text):
            # "Yuwon!" — drop play, get serious
            reply = self.bedis.handle_serious()
            console.set_prompt_label(self.bedis.address_name())

        elif self.bedis.matches_reject(text):
            reply = self.bedis.handle_reject()
            console.set_prompt_label(self.bedis.address_name())

        elif machine_scan.is_awaiting(self.context):
            # yes/no gate before the quiet machine examine
            reply = machine_scan.handle_consent(text, self.context)

        elif printer_help.matches(text, self.context):
            reply = printer_help.handle(user_input, self.context)

        elif conversation_start.matches(text):
            reply = conversation_start.reply()

        elif guest_chat.matches(text, self.mode):
            reply = guest_chat.reply(text, self.context)
            if guest_chat.arms_machine_scan(text):
                machine_scan.set_awaiting(self.context, True)

        elif guest_chat.arms_machine_scan(text):
            # Nikko (and other non-guest) modes can still trigger the examine flow
            machine_scan.set_awaiting(self.context, True)
            reply = guest_chat.SUPPORT_REPLY

        elif greetings.matches(text):
            reply = greetings.reply(mode=self.mode, bedis=self.bedis)

        elif friend_identity.matches_identity_query(text):
            reply = friend_identity.IDENTITY_REPLY

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

        elif nikko_play.matches(text, self.mode, self.bedis):
            reply = nikko_play.reply(text, self.bedis, self.context)
            console.set_prompt_label(self.bedis.address_name())

        else:
            if self.bedis.enabled:
                reply = nikko_play.fallback(self.bedis)
            else:
                reply = guest_chat.fallback(self.mode, user_input, self.context)

        console.print_assistant(reply)
