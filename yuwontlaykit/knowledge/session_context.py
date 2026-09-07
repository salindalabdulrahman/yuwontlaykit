"""Default session context for the assistant."""

import datetime

from yuwontlaykit.knowledge import entry_modes


def create_session_context(
    user_name: str = "You",
    mode: str = entry_modes.GUEST,
) -> dict:
    return {
        "user_name": user_name,
        "mode": mode,
        "session_start": datetime.datetime.now().strftime("%H:%M:%S"),
        "awaiting_machine_scan": False,
        "printer_help_active": False,
        "awaiting_printer_fix": False,
        "pending_printer_error_id": None,
        "guest_laugh_count": 0,
        "nikko_play_count": 0,
    }
