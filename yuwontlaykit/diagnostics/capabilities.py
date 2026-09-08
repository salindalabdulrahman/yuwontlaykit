"""What Yuwon can and cannot actually do from this machine."""

from __future__ import annotations

from yuwontlaykit.tools.windows import windows_tools_available


def inventory() -> list[dict[str, str]]:
    win = windows_tools_available()
    win_status = "Available" if win else "Unavailable"
    win_note = (
        "Windows PowerShell is reachable."
        if win
        else "PowerShell is not available from this environment."
    )
    return [
        {
            "capability": "Printer list / status / queue / spooler",
            "status": win_status,
            "note": win_note,
        },
        {
            "capability": "Printer IP detection",
            "status": win_status,
            "note": "Only if Windows reports a PrinterHostAddress on the port.",
        },
        {
            "capability": "Physical printer inspection",
            "status": "Unavailable",
            "note": "I cannot see paper, lights, cables, or jam paths.",
        },
        {
            "capability": "Wi-Fi / network / DNS / internet tests",
            "status": win_status,
            "note": win_note,
        },
        {
            "capability": "Computer performance (CPU, RAM, disk, processes)",
            "status": "Available" if win else "Partial",
            "note": "Windows details need PowerShell; basic OS info always works.",
        },
        {
            "capability": "Audio / Bluetooth / USB / display devices",
            "status": win_status,
            "note": win_note,
        },
        {
            "capability": "Defensive security overview",
            "status": win_status,
            "note": "Not a full antivirus scan.",
        },
        {
            "capability": "Deleting user files",
            "status": "Unavailable",
            "note": "I will not automatically delete documents, photos, or downloads.",
        },
        {
            "capability": "Arbitrary command execution",
            "status": "Unavailable",
            "note": "I only run named approved tools.",
        },
    ]


def format_inventory() -> str:
    lines = ["Here's what I can actually check from here:"]
    for item in inventory():
        lines.append(f"  • {item['capability']}: {item['status']} — {item['note']}")
    return "\n".join(lines)
