from __future__ import annotations

import logging
import subprocess
from datetime import datetime
from pathlib import Path

from loominary.meeting.errors import TranscriptionError

logger = logging.getLogger(__name__)


def extract_audio(mp4_path: Path, wav_path: Path, ffmpeg_exe: str) -> None:
    """Extract 16kHz mono PCM WAV from an MP4 file (Whisper's preferred format)."""
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i", str(mp4_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(wav_path),
    ]
    logger.info("Extracting audio: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise TranscriptionError(
            f"Audio extraction failed (exit {result.returncode}):\n"
            + result.stderr.decode("utf-8", errors="replace")
        )
    logger.info("Audio extracted: %s", wav_path)


def _fmt_time_txt(seconds: float) -> str:
    """Format seconds as HH:MM:SS for the plain-text transcript."""
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _fmt_time_srt(seconds: float) -> str:
    """Format seconds as HH:MM:SS,mmm for SRT subtitles."""
    total_ms = int(seconds * 1000)
    h = total_ms // 3_600_000
    m = (total_ms % 3_600_000) // 60_000
    s = (total_ms % 60_000) // 1_000
    ms = total_ms % 1_000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def save_transcript(
    segments: list,
    output_path: Path,
    meeting_name: str,
    start_time: datetime,
) -> None:
    """
    Write two transcript files:
    - output_path        → plain text with timestamps
    - output_path.with_suffix('.srt') → SRT subtitle format
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"Meeting: {meeting_name}\n")
        f.write(f"Date: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Segments: {len(segments)}\n")
        f.write("-" * 60 + "\n")
        for seg in segments:
            start = _fmt_time_txt(seg.start)
            end = _fmt_time_txt(seg.end)
            f.write(f"[{start} --> {end}] {seg.text.strip()}\n")

    srt_path = output_path.with_suffix(".srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, start=1):
            f.write(f"{i}\n")
            f.write(f"{_fmt_time_srt(seg.start)} --> {_fmt_time_srt(seg.end)}\n")
            f.write(f"{seg.text.strip()}\n\n")

    logger.info("Transcript saved: %s", output_path)
    logger.info("SRT saved: %s", srt_path)
    print(f"Transcript saved: {output_path}", flush=True)
