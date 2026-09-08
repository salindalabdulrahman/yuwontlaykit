"""Diagnostic check plans per domain — named tools only."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Check:
    tool: str
    label: str
    kwargs: tuple[tuple[str, object], ...] = ()


DOMAIN_PLANS: dict[str, tuple[Check, ...]] = {
    "printer": (
        Check("get_printers", "Checking printers"),
        Check("get_default_printer", "Checking the default printer"),
        Check("get_printer_status", "Checking printer status"),
        Check("get_printer_port", "Checking printer connection"),
        Check("get_printer_driver", "Checking printer software"),
        Check("get_print_queue", "Checking the print queue"),
        Check("check_print_spooler", "Checking the printing system"),
    ),
    "wifi": (
        Check("get_wifi_information", "Checking Wi-Fi"),
        Check("get_network_information", "Checking network addresses"),
        Check("get_windows_services", "Checking wireless services"),
        Check("test_internet", "Checking internet and website names"),
    ),
    "network": (
        Check("get_wifi_information", "Checking Wi-Fi"),
        Check("get_network_information", "Checking network addresses"),
        Check("test_internet", "Checking internet and website names"),
        Check("get_windows_services", "Checking network services"),
    ),
    "computer": (
        Check("get_system_information", "Checking the computer"),
        Check("get_disk_information", "Checking storage space"),
        Check("get_running_processes", "Checking busy programs"),
        Check("get_startup_applications", "Checking startup programs"),
        Check("get_network_information", "Checking network"),
        Check("test_internet", "Checking internet connectivity"),
        Check("get_printers", "Checking installed printers"),
    ),
    "software": (
        Check("get_running_processes", "Checking running programs"),
        Check("get_event_logs", "Checking recent error reports"),
    ),
    "audio": (
        Check("get_audio_information", "Checking sound"),
        Check("get_windows_services", "Checking sound services"),
    ),
    "bluetooth": (
        Check("get_bluetooth_information", "Checking Bluetooth"),
        Check("get_windows_services", "Checking Bluetooth services"),
    ),
    "storage": (
        Check("get_disk_information", "Checking storage space"),
    ),
    "hardware": (
        Check("get_device_information", "Checking devices"),
        Check("get_usb_devices", "Checking USB"),
        Check("get_display_information", "Checking screens"),
    ),
    "security": (
        Check("get_security_overview", "Checking protection status"),
        Check("get_startup_applications", "Checking startup programs"),
        Check("get_running_processes", "Checking running programs"),
    ),
    "windows": (
        Check("get_system_information", "Checking Windows"),
        Check("get_windows_services", "Checking important services"),
        Check("get_event_logs", "Checking recent errors"),
    ),
}


# Shorter read-only plans when the user asked what's installed, not to fix a fault
INVENTORY_PLANS: dict[str, tuple[Check, ...]] = {
    "printer": (
        Check("get_printers", "Looking up installed printers"),
        Check("get_default_printer", "Checking which one Windows uses by default"),
        Check("get_printer_status", "Checking Windows printer status"),
        Check("get_printer_port", "Checking printer ports"),
        Check("check_print_spooler", "Checking whether Windows can talk to printers"),
    ),
}


def plan_for(domain: str, intent: str = "problem") -> tuple[Check, ...]:
    if intent == "inventory":
        return INVENTORY_PLANS.get(domain, DOMAIN_PLANS.get(domain, DOMAIN_PLANS["computer"]))
    return DOMAIN_PLANS.get(domain, DOMAIN_PLANS["computer"])
