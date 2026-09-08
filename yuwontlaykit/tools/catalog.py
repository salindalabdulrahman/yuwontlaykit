"""Built-in approved tool catalog."""

from __future__ import annotations

from yuwontlaykit.tools.base import RiskLevel
from yuwontlaykit.tools.registry import ToolRegistry, ToolSpec
from yuwontlaykit.tools import applications, devices, disk, events, files, network, power, printers, remediate, security, services, system


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    specs = (
        ToolSpec("get_system_information", RiskLevel.READ_ONLY, system.get_system_information, "OS, CPU, RAM, uptime"),
        ToolSpec("get_running_processes", RiskLevel.READ_ONLY, system.get_running_processes, "Resource-heavy processes"),
        ToolSpec("get_startup_applications", RiskLevel.READ_ONLY, system.get_startup_applications, "Startup apps"),
        ToolSpec("get_network_information", RiskLevel.READ_ONLY, network.get_network_information, "Adapters, IP, gateway, DNS"),
        ToolSpec("get_wifi_information", RiskLevel.READ_ONLY, network.get_wifi_information, "Wi-Fi adapter and SSID"),
        ToolSpec("test_network_connectivity", RiskLevel.READ_ONLY, network.test_network_connectivity, "Ping a host"),
        ToolSpec("test_dns", RiskLevel.READ_ONLY, network.test_dns, "DNS name lookup"),
        ToolSpec("test_internet", RiskLevel.READ_ONLY, network.test_internet, "Internet vs DNS vs offline"),
        ToolSpec("get_printers", RiskLevel.READ_ONLY, printers.get_printers, "Installed printers"),
        ToolSpec("get_default_printer", RiskLevel.READ_ONLY, printers.get_default_printer, "Default printer"),
        ToolSpec("get_printer_status", RiskLevel.READ_ONLY, printers.get_printer_status, "Printer statuses"),
        ToolSpec("get_printer_port", RiskLevel.READ_ONLY, printers.get_printer_port, "Printer ports / IPs"),
        ToolSpec("get_printer_driver", RiskLevel.READ_ONLY, printers.get_printer_driver, "Printer drivers"),
        ToolSpec("get_print_queue", RiskLevel.READ_ONLY, printers.get_print_queue, "Print queue jobs"),
        ToolSpec("check_print_spooler", RiskLevel.READ_ONLY, printers.check_print_spooler, "Print Spooler service"),
        ToolSpec("get_windows_services", RiskLevel.READ_ONLY, services.get_windows_services, "Key Windows services"),
        ToolSpec("get_device_information", RiskLevel.READ_ONLY, devices.get_device_information, "Device Manager snapshot"),
        ToolSpec("get_audio_information", RiskLevel.READ_ONLY, devices.get_audio_information, "Audio devices and service"),
        ToolSpec("get_display_information", RiskLevel.READ_ONLY, devices.get_display_information, "Displays"),
        ToolSpec("get_usb_devices", RiskLevel.READ_ONLY, devices.get_usb_devices, "USB devices"),
        ToolSpec("get_bluetooth_information", RiskLevel.READ_ONLY, devices.get_bluetooth_information, "Bluetooth"),
        ToolSpec("get_disk_information", RiskLevel.READ_ONLY, disk.get_disk_information, "Disk space"),
        ToolSpec("get_event_logs", RiskLevel.READ_ONLY, events.get_event_logs, "Recent error events"),
        ToolSpec("get_security_overview", RiskLevel.READ_ONLY, security.get_security_overview, "Defender / firewall"),
        ToolSpec("open_application", RiskLevel.LOW_RISK_MODIFICATION, applications.open_application, "Open an allowlisted installed application"),
        ToolSpec("close_application", RiskLevel.LOW_RISK_MODIFICATION, applications.close_application, "Close an allowlisted application"),
        ToolSpec("application_running", RiskLevel.READ_ONLY, applications.application_running, "Check whether an application is running"),
        ToolSpec("list_running_applications", RiskLevel.READ_ONLY, applications.list_running_applications, "List applications with open windows"),
        ToolSpec("search_user_files", RiskLevel.READ_ONLY, files.search_user_files, "Search common user folders"),
        ToolSpec("open_path", RiskLevel.LOW_RISK_MODIFICATION, files.open_path, "Open a file or folder with the default app"),
        ToolSpec("resolve_known_folder", RiskLevel.READ_ONLY, files.resolve_known_folder, "Locate Desktop/Documents/Downloads"),
        ToolSpec("shutdown_computer", RiskLevel.HIGH_RISK_MODIFICATION, power.shutdown_computer, "Shut down the PC"),
        ToolSpec("restart_computer", RiskLevel.HIGH_RISK_MODIFICATION, power.restart_computer, "Restart the PC"),
        ToolSpec("lock_computer", RiskLevel.LOW_RISK_MODIFICATION, power.lock_computer, "Lock the PC"),
        ToolSpec("sleep_computer", RiskLevel.HIGH_RISK_MODIFICATION, power.sleep_computer, "Sleep the PC"),
        ToolSpec("logout_user", RiskLevel.HIGH_RISK_MODIFICATION, power.logout_user, "Sign out the current user"),
        ToolSpec("restart_print_spooler", RiskLevel.LOW_RISK_MODIFICATION, remediate.restart_print_spooler, "Restart Print Spooler"),
        ToolSpec("clear_print_queue", RiskLevel.LOW_RISK_MODIFICATION, remediate.clear_print_queue, "Clear print jobs"),
        ToolSpec("set_printers_online", RiskLevel.LOW_RISK_MODIFICATION, remediate.set_printers_online, "Clear Work Offline"),
        ToolSpec("remove_printer", RiskLevel.LOW_RISK_MODIFICATION, remediate.remove_printer, "Remove an installed printer"),
        ToolSpec("flush_dns", RiskLevel.LOW_RISK_MODIFICATION, remediate.flush_dns, "Flush DNS cache"),
    )
    for spec in specs:
        registry.register(spec)
    return registry
