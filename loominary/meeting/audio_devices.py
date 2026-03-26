from __future__ import annotations

import re
import subprocess
import logging

from loominary.meeting.errors import AudioDeviceError

logger = logging.getLogger(__name__)

_cached_loopback_device: str | None = None


def list_dshow_audio_devices(ffmpeg_exe: str) -> list[str]:
    """Return dshow audio device names by parsing ffmpeg -list_devices output."""
    result = subprocess.run(
        [ffmpeg_exe, "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = result.stderr
    devices: list[str] = []
    in_audio_section = False
    for line in output.splitlines():
        if "(audio)" in line.lower() or "DirectShow audio" in line:
            in_audio_section = True
        if "(video)" in line.lower() or "DirectShow video" in line:
            in_audio_section = False
        if in_audio_section:
            match = re.search(r'"([^"]+)"', line)
            if match:
                name = match.group(1)
                if name not in devices:
                    devices.append(name)
    logger.debug("dshow audio devices found: %s", devices)
    return devices


def _get_render_device_names() -> list[str]:
    """Enumerate render (output) audio endpoints via PowerShell."""
    ps_cmd = (
        "Get-PnpDevice -Class AudioEndpoint -Status OK "
        "| Where-Object { $_.InstanceId -like '*0.0.0.*' } "
        "| Select-Object -ExpandProperty FriendlyName"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    logger.debug("PowerShell render devices: %s", names)
    return names


def _probe_loopback_device(ffmpeg_exe: str, device_name: str) -> bool:
    """Test whether a loopback device name is valid with a 1-second capture probe."""
    result = subprocess.run(
        [
            ffmpeg_exe,
            "-f", "dshow",
            "-i", f"audio={device_name}",
            "-t", "1",
            "-f", "null",
            "-",
        ],
        capture_output=True,
    )
    success = result.returncode == 0
    logger.debug("Probe '%s': %s", device_name, "OK" if success else "FAIL")
    return success


def find_loopback_device(ffmpeg_exe: str) -> str:
    """
    Detect the WASAPI loopback audio device name for use with ffmpeg dshow.

    Strategy:
    1. Check dshow audio device list for any name containing '(loopback)'.
    2. Check dshow list for 'Stereo Mix'.
    3. Enumerate render devices via PowerShell, probe '<name> (loopback)'.
    4. Raise AudioDeviceError with instructions if nothing works.
    """
    global _cached_loopback_device
    if _cached_loopback_device is not None:
        return _cached_loopback_device

    dshow_devices = list_dshow_audio_devices(ffmpeg_exe)
    for name in dshow_devices:
        if "loopback" in name.lower():
            logger.info("Found loopback device in dshow list: '%s'", name)
            _cached_loopback_device = name
            return name

    for name in dshow_devices:
        if "stereo mix" in name.lower():
            if _probe_loopback_device(ffmpeg_exe, name):
                logger.info("Found Stereo Mix device: '%s'", name)
                _cached_loopback_device = name
                return name

    render_devices = _get_render_device_names()
    if not render_devices:
        render_devices = [d for d in dshow_devices if "loopback" not in d.lower()]

    tried: list[str] = []
    for render_name in render_devices:
        candidate = f"{render_name} (loopback)"
        tried.append(candidate)
        if _probe_loopback_device(ffmpeg_exe, candidate):
            logger.info("Validated loopback device: '%s'", candidate)
            _cached_loopback_device = candidate
            return candidate

    raise AudioDeviceError(
        "Could not find a WASAPI loopback audio device.\n"
        f"Tried: {tried}\n"
        "To fix this:\n"
        "  1. Right-click the speaker icon in the taskbar → Sounds\n"
        "  2. Go to the Recording tab\n"
        "  3. Right-click in the device list → Show Disabled Devices\n"
        "  4. Enable 'Stereo Mix' if available, then retry.\n"
        "Alternatively, install a virtual audio cable (e.g. VB-Audio VoiceMeeter)."
    )
