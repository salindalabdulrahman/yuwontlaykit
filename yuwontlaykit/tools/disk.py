"""Disk and storage inspection. Never deletes files."""

from __future__ import annotations

import shutil

from yuwontlaykit.tools.base import RiskLevel, ok, unavailable
from yuwontlaykit.tools.runner import as_list, run_argv
from yuwontlaykit.tools.windows import powershell_json, windows_tools_available

RISK = RiskLevel.READ_ONLY


def get_disk_information() -> ToolResult:
    if windows_tools_available():
        result = powershell_json(
            "get_disk_information",
            r"""
Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DriveType -eq 3 } |
  Select-Object DeviceID, VolumeName, FileSystem,
    @{n='SizeGB';e={[math]::Round($_.Size/1GB,1)}},
    @{n='FreeGB';e={[math]::Round($_.FreeSpace/1GB,1)}},
    @{n='PercentFree';e={ if ($_.Size) { [math]::Round(($_.FreeSpace/$_.Size)*100,1) } else { $null } }} |
  ConvertTo-Json -Depth 3
""",
            timeout=25.0,
        )
        rows = as_list(result.data)
        result.data = rows
        bits = []
        low = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            letter = row.get("DeviceID") or "?"
            free = row.get("PercentFree")
            bits.append(f"{letter} {row.get('FreeGB')} GB free ({free}%)")
            try:
                if float(free) < 10:
                    low.append(letter)
            except (TypeError, ValueError):
                pass
        result.summary = "; ".join(bits) if bits else "No local disks reported."
        result.extras["low_space"] = low
        return result

    if shutil.which("df"):
        code, out, err = run_argv(["df", "-h"], timeout=8.0)
        if code == 0:
            return ok(
                "get_disk_information",
                RISK,
                "Disk space from this environment (not necessarily Windows).",
                data={"lines": out.splitlines()},
                raw=out,
            )
        return unavailable("get_disk_information", RISK, err or "df failed")
    return unavailable("get_disk_information", RISK, "No disk tools are available.")
