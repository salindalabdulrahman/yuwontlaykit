"""Central safety classification for every named computer operation."""

from __future__ import annotations

from enum import Enum


class OperationClass(str, Enum):
    READ_ONLY = "read_only"
    LOW_RISK = "low_risk"
    CONFIRMATION_REQUIRED = "confirmation_required"
    DESTRUCTIVE = "destructive"


# Named operations — skills must consult this instead of inventing local rules.
OPERATIONS: dict[str, OperationClass] = {
    "get_ip_address": OperationClass.READ_ONLY,
    "list_printers": OperationClass.READ_ONLY,
    "check_printer_status": OperationClass.READ_ONLY,
    "check_wifi": OperationClass.READ_ONLY,
    "check_disk": OperationClass.READ_ONLY,
    "list_running_applications": OperationClass.READ_ONLY,
    "check_application": OperationClass.READ_ONLY,
    "search_files": OperationClass.READ_ONLY,
    "search_folders": OperationClass.READ_ONLY,
    "get_system_information": OperationClass.READ_ONLY,
    "computer_diagnostic": OperationClass.READ_ONLY,
    "open_application": OperationClass.LOW_RISK,
    "open_file": OperationClass.LOW_RISK,
    "open_folder": OperationClass.LOW_RISK,
    "restart_application": OperationClass.CONFIRMATION_REQUIRED,
    "close_application": OperationClass.CONFIRMATION_REQUIRED,
    "remove_printer": OperationClass.CONFIRMATION_REQUIRED,
    "restart_print_spooler": OperationClass.CONFIRMATION_REQUIRED,
    "lock_computer": OperationClass.CONFIRMATION_REQUIRED,
    "sleep_computer": OperationClass.CONFIRMATION_REQUIRED,
    "logout_user": OperationClass.CONFIRMATION_REQUIRED,
    "restart_computer": OperationClass.DESTRUCTIVE,
    "shutdown_computer": OperationClass.DESTRUCTIVE,
    "delete_file": OperationClass.DESTRUCTIVE,
    "uninstall_application": OperationClass.DESTRUCTIVE,
}


def class_for(operation: str) -> OperationClass:
    return OPERATIONS.get(operation, OperationClass.CONFIRMATION_REQUIRED)


def requires_confirmation(operation: str) -> bool:
    return class_for(operation) in (
        OperationClass.CONFIRMATION_REQUIRED,
        OperationClass.DESTRUCTIVE,
    )


def is_read_only(operation: str) -> bool:
    return class_for(operation) == OperationClass.READ_ONLY


USER_ACTION_FAILURE = (
    "I couldn't complete that action.\n\n"
    "Nothing else was changed.\n\n"
    "I can investigate the problem if you'd like."
)
