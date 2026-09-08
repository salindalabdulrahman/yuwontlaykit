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
        "it_support_active": False,
        "awaiting_it_diagnostic": False,
        "pending_it_domain": None,
        "pending_it_problem": None,
        "awaiting_remove_printer": False,
        "pending_remove_printer": None,
        "awaiting_clarification": False,
        "pending_clarification": None,
        "active_intent": None,
        "active_domain": None,
        "turn_relation": "unknown",
        "last_lookup": None,
        "last_ip_ok": False,
        "last_application": None,
        "last_file": None,
        "last_folder": None,
        "last_referent": None,
        "search_results": [],
        "awaiting_close_application": False,
        "pending_close_application": None,
        "awaiting_restart_application": False,
        "pending_restart_application": None,
        "awaiting_power_action": False,
        "pending_power_action": None,
        "awaiting_search_choice": False,
        "guest_laugh_count": 0,
        "nikko_play_count": 0,
        "nikko_laugh_count": 0,
        "confusion_guess_index": 0,
        "confusion_unparsed_index": 0,
        "confusion_lost_index": 0,
        "confusion_declined_index": 0,
        "last_confusion_reply": None,
    }
