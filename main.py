"""Yuwontlaykit CLI entrypoint.

Yuwontlaykit and Yuwon are the same assistant. The console script only
changes the *user* / bond depth:

- ``yuwontlaykit`` → guest
- ``4782``         → Nikko (deep; Bedis teasing)
- ``yuwon``        → Nikko (shallower than 4782)
"""

import logging

from yuwontlaykit.cli import console
from yuwontlaykit.engine.ai_engine import AIEngine
from yuwontlaykit.knowledge import entry_modes
from yuwontlaykit.operations.safety import USER_ACTION_FAILURE

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


def main():
    mode = entry_modes.resolve_mode()
    ai = AIEngine(mode=mode)

    console.set_prompt_label(entry_modes.prompt_label(mode))
    console.print_banner("Yuwontlaykit is online. (Type 'exit' to quit)")
    console.print_assistant(entry_modes.opening_reply(mode))

    while True:
        try:
            user_input = console.prompt_user()
            if user_input.lower().strip() in ["exit", "quit"]:
                console.print_goodbye(ai.address_name())
                break
            if user_input.strip() == "":
                continue
            if console.is_clear_screen(user_input):
                console.clear_screen()
                console.print_banner("Yuwontlaykit is online. (Type 'exit' to quit)")
                continue

            ai.chat(user_input)

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception:
            logging.getLogger("yuwontlaykit").exception("CLI turn failed")
            console.print_assistant(USER_ACTION_FAILURE)


if __name__ == "__main__":
    main()
