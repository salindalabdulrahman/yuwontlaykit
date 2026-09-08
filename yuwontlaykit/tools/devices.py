"""Device, audio, display, USB, and Bluetooth inspection."""

from __future__ import annotations

from yuwontlaykit.tools.base import RiskLevel, unavailable
from yuwontlaykit.tools.runner import as_list
from yuwontlaykit.tools.windows import powershell_json, windows_tools_available

RISK = RiskLevel.READ_ONLY


def get_device_information(filter_class: str | None = None) -> ToolResult:
    if not windows_tools_available():
        return unavailable(
            "get_device_information",
            RISK,
            "I cannot read Device Manager information without PowerShell.",
        )
    class_filter = ""
    if filter_class:
        safe = "".join(ch for ch in filter_class if ch.isalnum() or ch in " _-")
        class_filter = f" | Where-Object {{ $_.Class -eq '{safe}' -or $_.FriendlyName -match '{safe}' }}"
    result = powershell_json(
        "get_device_information",
        f"""
Get-PnpDevice | Where-Object {{ $_.Present -eq $true }} {class_filter} |
  Select-Object Status, Class, FriendlyName, InstanceId, Problem |
  ConvertTo-Json -Depth 3
""",
        timeout=35.0,
    )
    rows = as_list(result.data)
    result.data = rows
    problem = [
        r for r in rows
        if isinstance(r, dict) and str(r.get("Status") or "").lower() not in ("ok", "unknown", "")
    ]
    result.summary = (
        f"{len(rows)} present device(s)"
        + (f", {len(problem)} not OK" if problem else "")
    )
    result.extras["problem_count"] = len(problem)
    return result


def get_audio_information() -> ToolResult:
    if not windows_tools_available():
        return unavailable(
            "get_audio_information",
            RISK,
            "I cannot inspect Windows audio without PowerShell.",
        )
    result = powershell_json(
        "get_audio_information",
        r"""
$svc = Get-Service Audiosrv, AudioEndpointBuilder -ErrorAction SilentlyContinue |
  Select-Object Name, Status, StartType
$devs = Get-PnpDevice | Where-Object { $_.Class -eq 'MEDIA' -or $_.Class -eq 'AudioEndpoint' -or $_.FriendlyName -match 'audio|speaker|headphone|sound' } |
  Select-Object Status, Class, FriendlyName
[pscustomobject]@{ Services = @($svc); Devices = @($devs) } | ConvertTo-Json -Depth 4
""",
        timeout=30.0,
    )
    data = result.data if isinstance(result.data, dict) else {}
    services = as_list(data.get("Services"))
    devices = as_list(data.get("Devices"))
    result.data = {"services": services, "devices": devices}
    audio_running = any(
        str(s.get("Name")) == "Audiosrv" and str(s.get("Status")).lower() == "running"
        for s in services
        if isinstance(s, dict)
    )
    result.extras["audio_service_running"] = audio_running
    result.summary = (
        ("Windows Audio is running" if audio_running else "Windows Audio is not running")
        + f"; {len(devices)} audio-related device(s)"
    )
    return result


def get_display_information() -> ToolResult:
    if not windows_tools_available():
        return unavailable(
            "get_display_information",
            RISK,
            "I cannot inspect displays without PowerShell.",
        )
    result = powershell_json(
        "get_display_information",
        r"""
$mon = Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorBasicDisplayParams -ErrorAction SilentlyContinue
$vid = Get-PnpDevice | Where-Object { $_.Class -eq 'Monitor' -or $_.Class -eq 'Display' } |
  Select-Object Status, Class, FriendlyName
$res = Get-CimInstance Win32_VideoController | Select-Object Name, CurrentHorizontalResolution, CurrentVerticalResolution, DriverVersion, Status
[pscustomobject]@{ Monitors = @($vid); Video = @($res); Wmi = @($mon) } | ConvertTo-Json -Depth 5
""",
        timeout=30.0,
    )
    data = result.data if isinstance(result.data, dict) else {}
    video = as_list(data.get("Video"))
    result.data = data
    bits = []
    for v in video:
        if not isinstance(v, dict):
            continue
        name = v.get("Name") or "display"
        w = v.get("CurrentHorizontalResolution")
        h = v.get("CurrentVerticalResolution")
        if w and h:
            bits.append(f"{name} {w}x{h}")
        else:
            bits.append(str(name))
    result.summary = "; ".join(bits) if bits else "No display adapters reported."
    return result


def get_usb_devices() -> ToolResult:
    if not windows_tools_available():
        return unavailable("get_usb_devices", RISK, "I cannot list USB devices without PowerShell.")
    result = powershell_json(
        "get_usb_devices",
        r"""
Get-PnpDevice | Where-Object { $_.Class -match 'USB' -or $_.InstanceId -match '^USB' } |
  Select-Object Status, Class, FriendlyName | ConvertTo-Json -Depth 3
""",
        timeout=30.0,
    )
    rows = as_list(result.data)
    result.data = rows
    names = [str(r.get("FriendlyName")) for r in rows if isinstance(r, dict) and r.get("FriendlyName")]
    result.summary = f"{len(names)} USB-related device(s)"
    return result


def get_bluetooth_information() -> ToolResult:
    if not windows_tools_available():
        return unavailable(
            "get_bluetooth_information",
            RISK,
            "I cannot inspect Bluetooth without PowerShell.",
        )
    result = powershell_json(
        "get_bluetooth_information",
        r"""
$svc = Get-Service bthserv, BTAGService, bthhfsrv -ErrorAction SilentlyContinue |
  Select-Object Name, Status, StartType
$devs = Get-PnpDevice | Where-Object { $_.Class -eq 'Bluetooth' -or $_.FriendlyName -match 'Bluetooth' } |
  Select-Object Status, Class, FriendlyName
[pscustomobject]@{ Services = @($svc); Devices = @($devs) } | ConvertTo-Json -Depth 4
""",
        timeout=30.0,
    )
    data = result.data if isinstance(result.data, dict) else {}
    services = as_list(data.get("Services"))
    devices = as_list(data.get("Devices"))
    result.data = {"services": services, "devices": devices}
    running = any(
        str(s.get("Name")) == "bthserv" and str(s.get("Status")).lower() == "running"
        for s in services
        if isinstance(s, dict)
    )
    result.extras["bluetooth_service_running"] = running
    result.summary = (
        ("Bluetooth service is running" if running else "Bluetooth service is not running")
        + f"; {len(devices)} Bluetooth device(s) listed"
    )
    return result
