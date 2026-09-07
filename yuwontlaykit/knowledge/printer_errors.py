"""Printer error knowledge for Yuwon — symptoms, causes, and fix commands.

Commands are written for Windows (CMD / PowerShell) first, since guests
usually print from Windows; CUPS/Linux notes are included when useful.
"""

from __future__ import annotations

from typing import TypedDict


class PrinterError(TypedDict):
    id: str
    title: str
    keywords: tuple[str, ...]
    what_it_means: str
    physical_steps: tuple[str, ...]
    cmd_steps: tuple[tuple[str, str], ...]  # (label, command)
    powershell_steps: tuple[tuple[str, str], ...]
    # Safe-ish auto actions Yuwon may offer to run (PowerShell one-liners)
    auto_fix_label: str
    auto_fix_ps: str


PRINTER_ERRORS: tuple[PrinterError, ...] = (
    {
        "id": "paper_jam",
        "title": "Paper jam",
        "keywords": (
            "paper jam",
            "paper jams",
            "jammed",
            "paper stuck",
            "stuck paper",
            "jam",
        ),
        "what_it_means": (
            "Paper is caught in the path — rollers can't feed cleanly. "
            "Software still helps: clear the stuck job and restart the spooler "
            "after you pull the paper out."
        ),
        "physical_steps": (
            "Power the printer OFF and open every access door / tray.",
            "Gently pull paper in the direction of the path — never force it.",
            "Check for tiny torn scraps near the rollers.",
            "Close covers firmly, power ON, then print a test page.",
        ),
        "cmd_steps": (
            (
                "Restart print spooler (Admin CMD)",
                "net stop spooler && net start spooler",
            ),
            (
                "Wipe stuck spool files after spooler is STOPPED (Admin CMD)",
                r"del /Q %systemroot%\System32\spool\PRINTERS\*.*",
            ),
            (
                "List printers + status",
                "wmic printer get Name,PrinterStatus,PortName",
            ),
        ),
        "powershell_steps": (
            (
                "Restart spooler",
                "Restart-Service -Name Spooler -Force",
            ),
            (
                "Cancel all jobs on a printer (change Name)",
                'Get-PrintJob -PrinterName "PRINTER_NAME" | Remove-PrintJob',
            ),
            (
                "Printer status",
                "Get-Printer | Format-Table Name, PrinterStatus, DriverName -AutoSize",
            ),
        ),
        "auto_fix_label": "restart the Windows print spooler",
        "auto_fix_ps": "Restart-Service -Name Spooler -Force; Get-Service Spooler | Format-List Status,Name",
    },
    {
        "id": "offline",
        "title": "Printer offline / not responding",
        "keywords": (
            "offline",
            "not responding",
            "can't find printer",
            "cannot find printer",
            "printer disconnected",
            "unavailable",
        ),
        "what_it_means": (
            "Windows still has the printer listed, but the port/link is down "
            "(USB unplugged, Wi‑Fi sleepy, or 'Use Printer Offline' toggled)."
        ),
        "physical_steps": (
            "Confirm the printer is powered on and not in sleep/error lights.",
            "Reseat USB, or reconnect the same Wi‑Fi the PC uses.",
            "On Windows: Settings → Bluetooth & devices → Printers → open the printer → clear Use Printer Offline.",
        ),
        "cmd_steps": (
            (
                "See offline flag / status",
                "wmic printer get Name,PrinterStatus,WorkOffline",
            ),
            (
                "Restart spooler (Admin CMD)",
                "net stop spooler && net start spooler",
            ),
            (
                "Ping a network printer (change IP)",
                "ping 192.168.1.50",
            ),
        ),
        "powershell_steps": (
            (
                "Bring a printer online (change Name)",
                'Set-Printer -Name "PRINTER_NAME" -WorkOffline $false',
            ),
            (
                "List printers",
                "Get-Printer | Format-Table Name, PrinterStatus, PortName, DriverName -AutoSize",
            ),
            (
                "Restart spooler",
                "Restart-Service -Name Spooler -Force",
            ),
        ),
        "auto_fix_label": "list printers and clear WorkOffline on all local printers",
        "auto_fix_ps": (
            "Get-Printer | ForEach-Object { "
            "try { Set-Printer -Name $_.Name -WorkOffline $false -ErrorAction SilentlyContinue } catch {} }; "
            "Get-Printer | Format-Table Name, PrinterStatus, PortName -AutoSize | Out-String -Width 200"
        ),
    },
    {
        "id": "spooler",
        "title": "Print spooler / stuck queue",
        "keywords": (
            "spooler",
            "stuck queue",
            "print queue",
            "queued",
            "pending",
            "won't print",
            "wont print",
            "print job stuck",
            "documents stuck",
        ),
        "what_it_means": (
            "Jobs pile up in the Windows spooler. Restarting the service and "
            "clearing PRINTERS folder usually unsticks it."
        ),
        "physical_steps": (
            "Cancel jobs from the printer queue window (double‑click the printer icon).",
            "If the queue won't clear, use the spooler restart commands below.",
        ),
        "cmd_steps": (
            (
                "Stop spooler → delete queue → start spooler (Admin CMD)",
                r"net stop spooler && del /Q %systemroot%\System32\spool\PRINTERS\*.* && net start spooler",
            ),
            (
                "Open printers folder",
                "control printers",
            ),
        ),
        "powershell_steps": (
            (
                "Restart spooler",
                "Restart-Service -Name Spooler -Force",
            ),
            (
                "Remove all jobs from one printer",
                'Get-PrintJob -PrinterName "PRINTER_NAME" | Remove-PrintJob',
            ),
        ),
        "auto_fix_label": "restart the print spooler and show its status",
        "auto_fix_ps": "Restart-Service -Name Spooler -Force; Get-Service Spooler | Format-List Status,Name,StartType",
    },
    {
        "id": "driver",
        "title": "Driver / wrong driver",
        "keywords": (
            "driver",
            "wrong driver",
            "driver error",
            "failed to print",
            "0x00000006",
            "0x00000709",
        ),
        "what_it_means": (
            "Windows is talking to the printer with the wrong or broken driver "
            "(common after Windows updates or when a POS/receipt printer shares a port)."
        ),
        "physical_steps": (
            "Note the exact model on the printer sticker.",
            "Remove the device, reboot, reinstall the vendor driver (not only the Windows default).",
        ),
        "cmd_steps": (
            (
                "List printers + drivers",
                "wmic printer get Name,DriverName,PortName",
            ),
            (
                "Print UI / driver store helpers",
                "printui /s /t2",
            ),
        ),
        "powershell_steps": (
            (
                "List drivers",
                "Get-PrinterDriver | Format-Table Name, Manufacturer, MajorVersion -AutoSize",
            ),
            (
                "List printers with drivers",
                "Get-Printer | Format-Table Name, DriverName, PortName, PrinterStatus -AutoSize",
            ),
        ),
        "auto_fix_label": "list installed printer drivers",
        "auto_fix_ps": (
            "Get-PrinterDriver | Format-Table Name, Manufacturer, MajorVersion -AutoSize | Out-String -Width 200; "
            "Get-Printer | Format-Table Name, DriverName, PortName -AutoSize | Out-String -Width 200"
        ),
    },
    {
        "id": "toner_ink",
        "title": "Toner / ink / quality",
        "keywords": (
            "toner",
            "ink",
            "low ink",
            "out of ink",
            "blank page",
            "faded",
            "streaks",
            "lines on page",
        ),
        "what_it_means": (
            "Supply or print-head issue. CMD can't refill ink, but it can open "
            "maintenance tools and confirm which device Windows is using."
        ),
        "physical_steps": (
            "Check ink/toner levels on the printer screen.",
            "Run the printer's built‑in clean / align nozzles routine.",
            "Confirm you're printing to the real printer, not 'Microsoft Print to PDF' / OneNote.",
        ),
        "cmd_steps": (
            (
                "Open Devices and Printers",
                "control printers",
            ),
            (
                "List default printer",
                "wmic printer where Default=TRUE get Name,DriverName",
            ),
        ),
        "powershell_steps": (
            (
                "Show default printer",
                "Get-Printer | Where-Object {$_.Default -eq $true} | Format-List *",
            ),
            (
                "All printers",
                "Get-Printer | Format-Table Name, PrinterStatus, Default -AutoSize",
            ),
        ),
        "auto_fix_label": "show which printer is default and every printer status",
        "auto_fix_ps": (
            "Get-Printer | Format-Table Name, PrinterStatus, Default, DriverName -AutoSize | Out-String -Width 200"
        ),
    },
    {
        "id": "no_power",
        "title": "No power / no sound / dead",
        "keywords": (
            "no power",
            "no sound",
            "dead",
            "won't turn on",
            "wont turn on",
            "not turning on",
            "no lights",
        ),
        "what_it_means": (
            "If there's no power light, software can't help much until hardware wakes up. "
            "If it powers on but Windows is silent, treat it like offline/spooler next."
        ),
        "physical_steps": (
            "Try another wall outlet / power brick.",
            "Hold power 10+ seconds, wait, power on again.",
            "For USB models: different cable/port (avoid unpowered hubs).",
        ),
        "cmd_steps": (
            (
                "See if Windows still lists it",
                "wmic printer get Name,PrinterStatus,PortName",
            ),
            (
                "Device Manager (look under Printers / Universal Serial Bus)",
                "devmgmt.msc",
            ),
        ),
        "powershell_steps": (
            (
                "PnP devices with 'print' in the name",
                "Get-PnpDevice | Where-Object { $_.FriendlyName -match 'print|USB' } | Format-Table Status, Class, FriendlyName -AutoSize",
            ),
        ),
        "auto_fix_label": "scan PnP devices for printer / USB hints",
        "auto_fix_ps": (
            "Get-PnpDevice | Where-Object { $_.FriendlyName -match 'print|Printer|USB Printing' } | "
            "Format-Table Status, Class, FriendlyName -AutoSize | Out-String -Width 200"
        ),
    },
    {
        "id": "access_denied",
        "title": "Access denied / can't print",
        "keywords": (
            "access denied",
            "permission",
            "can't print",
            "cannot print",
            "error printing",
            "unable to print",
        ),
        "what_it_means": (
            "Permissions, a paused printer, or a crashed spooler often show up as "
            "'unable to print' with little detail."
        ),
        "physical_steps": (
            "Right‑click the printer → see if Pause Printing / Use Printer Offline is on.",
            "Try printing a test page from printer properties.",
        ),
        "cmd_steps": (
            (
                "Restart spooler (Admin CMD)",
                "net stop spooler && net start spooler",
            ),
            (
                "Printers UI",
                "control printers",
            ),
        ),
        "powershell_steps": (
            (
                "Unpause + online (change Name)",
                'Set-Printer -Name "PRINTER_NAME" -WorkOffline $false; Get-Printer -Name "PRINTER_NAME"',
            ),
            (
                "Restart spooler",
                "Restart-Service -Name Spooler -Force",
            ),
        ),
        "auto_fix_label": "restart the spooler and list printer statuses",
        "auto_fix_ps": (
            "Restart-Service -Name Spooler -Force; "
            "Get-Printer | Format-Table Name, PrinterStatus, WorkOffline -AutoSize | Out-String -Width 200"
        ),
    },
)


def find_error(text: str) -> PrinterError | None:
    """Return the best-matching printer error for free-text symptoms."""
    t = text.lower().strip()
    # Prefer longer keyword hits so "paper jam" wins over bare "jam"
    best: PrinterError | None = None
    best_len = 0
    for err in PRINTER_ERRORS:
        for kw in err["keywords"]:
            if kw in t and len(kw) > best_len:
                best = err
                best_len = len(kw)
    return best


def list_symptom_hints() -> str:
    return (
        "paper jam · offline · stuck queue / spooler · driver · "
        "toner/ink · no power · access denied"
    )
