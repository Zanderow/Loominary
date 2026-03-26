from __future__ import annotations

import logging
import re
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path

from loominary.meeting.errors import RecorderError

logger = logging.getLogger(__name__)


def get_ffmpeg_exe() -> str:
    """Return the path to the ffmpeg executable, or raise RecorderError."""
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RecorderError(
            "ffmpeg not found on PATH. Please install ffmpeg:\n"
            "  winget install ffmpeg\n"
            "Then restart your terminal and try again."
        )
    logger.debug("ffmpeg found at: %s", exe)
    return exe


def _slugify(text: str) -> str:
    """Convert a meeting name to a filesystem-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = slug.strip("-")
    return slug or "meeting"


def build_output_dir(base_dir: Path, meeting_name: str, start_time: datetime) -> Path:
    """Create and return the output directory for this meeting's recordings."""
    date_str = start_time.strftime("%Y-%m-%d")
    slug = _slugify(meeting_name)
    output_dir = base_dir / f"{date_str}_{slug}"
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Output directory: %s", output_dir)
    return output_dir


def record(
    output_dir: Path,
    duration_seconds: int,
    loopback_device: str,
    ffmpeg_exe: str,
) -> Path:
    """
    Record screen + system audio for duration_seconds using ffmpeg.
    Returns the path to the output MP4 file.
    """
    output_file = output_dir / "recording.mp4"
    log_file_path = output_dir / "ffmpeg.log"

    cmd = [
        ffmpeg_exe,
        "-loglevel", "warning",
        "-f", "gdigrab",
        "-framerate", "15",
        "-draw_mouse", "1",
        "-i", "desktop",
        "-f", "dshow",
        "-i", f"audio={loopback_device}",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-c:a", "aac",
        "-b:a", "128k",
        "-async", "1",
        "-vsync", "1",
        "-movflags", "+faststart",
        str(output_file),
    ]

    logger.info("Starting recording: %s", " ".join(cmd))
    print(
        f"Recording started. Duration: {duration_seconds // 60}m {duration_seconds % 60}s",
        flush=True,
    )

    stop_event = threading.Event()

    with open(log_file_path, "wb") as log_fh:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=log_fh,
        )

        def _stop_recording():
            if proc.poll() is None:
                logger.info("Sending stop signal to ffmpeg...")
                try:
                    proc.stdin.write(b"q\n")
                    proc.stdin.flush()
                except (OSError, BrokenPipeError):
                    proc.terminate()
            stop_event.set()

        timer = threading.Timer(duration_seconds, _stop_recording)
        timer.daemon = True
        timer.start()

        try:
            proc.wait(timeout=duration_seconds + 30)
        except subprocess.TimeoutExpired:
            logger.warning("ffmpeg did not exit within grace period; terminating.")
            proc.terminate()
            proc.wait()
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received — stopping recording early.")
            print("\nStopping recording early...", flush=True)
            timer.cancel()
            _stop_recording()
            stop_event.wait(timeout=15)
            if proc.poll() is None:
                proc.terminate()
            proc.wait()

        timer.cancel()

    if not output_file.exists() or output_file.stat().st_size == 0:
        raise RecorderError(
            f"Recording failed: output file is missing or empty.\n"
            f"Check ffmpeg log for details: {log_file_path}"
        )

    size_mb = output_file.stat().st_size / (1024 * 1024)
    logger.info("Recording saved: %s (%.1f MB)", output_file, size_mb)
    print(f"Recording saved: {output_file} ({size_mb:.1f} MB)", flush=True)
    return output_file


def record_indefinite(
    output_dir: Path,
    loopback_device: str,
    ffmpeg_exe: str,
    stop_event: threading.Event,
) -> Path:
    """
    Record screen + system audio indefinitely until stop_event is set.
    Returns the path to the output MP4 file.
    """
    output_file = output_dir / "recording.mp4"
    log_file_path = output_dir / "ffmpeg.log"

    cmd = [
        ffmpeg_exe,
        "-loglevel", "warning",
        "-f", "gdigrab",
        "-framerate", "15",
        "-draw_mouse", "1",
        "-i", "desktop",
        "-f", "dshow",
        "-i", f"audio={loopback_device}",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-c:a", "aac",
        "-b:a", "128k",
        "-async", "1",
        "-vsync", "1",
        "-movflags", "+faststart",
        str(output_file),
    ]

    logger.info("Starting indefinite recording: %s", " ".join(cmd))

    with open(log_file_path, "wb") as log_fh:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=log_fh,
        )

        def _stop():
            if proc.poll() is None:
                logger.info("Sending stop signal to ffmpeg...")
                try:
                    proc.stdin.write(b"q\n")
                    proc.stdin.flush()
                except (OSError, BrokenPipeError):
                    proc.terminate()

        try:
            while not stop_event.is_set():
                try:
                    proc.wait(timeout=1.0)
                    break
                except subprocess.TimeoutExpired:
                    continue
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received — stopping recording early.")
            print("\nStopping recording early...", flush=True)

        _stop()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            logger.warning("ffmpeg did not exit within grace period; terminating.")
            proc.terminate()
            proc.wait()

    if not output_file.exists() or output_file.stat().st_size == 0:
        raise RecorderError(
            f"Recording failed: output file is missing or empty.\n"
            f"Check ffmpeg log for details: {log_file_path}"
        )

    size_mb = output_file.stat().st_size / (1024 * 1024)
    logger.info("Recording saved: %s (%.1f MB)", output_file, size_mb)
    print(f"Recording saved: {output_file} ({size_mb:.1f} MB)", flush=True)
    return output_file
