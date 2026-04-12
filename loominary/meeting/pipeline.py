"""Meeting recording pipeline — automatic (scheduled) and manual (record-now) modes."""
from __future__ import annotations

import logging
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import questionary
from rich.table import Table

from loominary import config as loom_config
from loominary.utils.progress import console
from loominary.meeting.errors import MeetingError

logger = logging.getLogger(__name__)

_MEETINGS_DIR = Path("./meetings")
_RECORDINGS_DIR = Path("./data/recordings")


def run(conn) -> None:
    """Entry point for the meeting pipeline. Prompts for automatic or manual mode."""
    console.print("\n[bold cyan]Meeting Recorder[/bold cyan]")

    mode = questionary.select(
        "Select recording mode:",
        choices=["Automatic (scheduled from YAML config)", "Manual (start now, stop on command)"],
    ).ask()

    if mode is None:
        return

    try:
        if mode.startswith("Automatic"):
            _run_automatic(conn)
        else:
            _run_manual(conn)
    except MeetingError as e:
        console.print(f"[red]Meeting recorder error:[/red] {e}")
    except KeyboardInterrupt:
        console.print("\n[dim]Meeting recording aborted.[/dim]")


def _run_automatic(conn) -> None:
    """Automatic mode: load a YAML config from meetings/, record at scheduled time."""
    from loominary.meeting.config import load_config
    from loominary.meeting.recorder import get_ffmpeg_exe, build_output_dir, record
    from loominary.meeting.audio_devices import find_loopback_device
    from loominary.meeting.scheduler import wait_until_premeet, open_meeting_url, wait_until_start
    from loominary.meeting.transcriber import extract_audio, save_transcript
    from loominary.meeting.shutdown import post_meeting_wait, shutdown_computer

    # Discover YAML configs in meetings/ folder
    yaml_files = _discover_meeting_configs()
    if not yaml_files:
        console.print(
            f"[red]No YAML config files found in '{_MEETINGS_DIR}'.[/red]\n"
            "[dim]Create a YAML file there with: name, url, platform, start_time, duration_minutes[/dim]"
        )
        return

    choices = [f.name for f in yaml_files] + ["Cancel"]
    selected_name = questionary.select("Select a meeting config:", choices=choices).ask()
    if not selected_name or selected_name == "Cancel":
        return

    config_path = yaml_files[choices.index(selected_name)]

    console.print(f"[cyan]Loading config: {config_path}[/cyan]")
    cfg = load_config(config_path)
    console.print(
        f"Meeting: [bold]{cfg.name}[/bold] | Platform: {cfg.platform} | "
        f"Start: {cfg.start_time.strftime('%Y-%m-%d %H:%M:%S')} | "
        f"Duration: {cfg.duration_minutes}m"
    )

    # Pre-flight checks
    ffmpeg_exe = get_ffmpeg_exe()
    console.print("[cyan]Detecting audio loopback device...[/cyan]")
    loopback_device = find_loopback_device(ffmpeg_exe)
    console.print(f"[green]Audio device:[/green] {loopback_device}")

    # Prepare output directory
    _RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    output_dir = build_output_dir(_RECORDINGS_DIR, cfg.name, cfg.start_time)
    _setup_file_logging(output_dir)

    # Wait, open browser, wait for start
    wait_until_premeet(cfg.start_time)
    open_meeting_url(cfg.url, cfg.platform)
    wait_until_start(cfg.start_time)

    # Record
    duration_seconds = cfg.duration_minutes * 60
    mp4_path = record(output_dir, duration_seconds, loopback_device, ffmpeg_exe)

    # Extract audio + transcribe
    wav_path = output_dir / "audio.wav"
    console.print("[cyan]Extracting audio...[/cyan]")
    extract_audio(mp4_path, wav_path, ffmpeg_exe)

    engine = _get_transcription_engine()
    console.print("[cyan]Transcribing... this may take a few minutes.[/cyan]")
    transcribe_start = time.time()
    result = engine.transcribe(str(wav_path))
    elapsed = time.time() - transcribe_start

    # Build transcript filename and save
    loom_config.LOOMINARY_TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    transcript_filename = _build_meeting_filename(cfg.name, cfg.start_time)
    transcript_path = loom_config.LOOMINARY_TRANSCRIPTS_DIR / transcript_filename

    # Use segment objects if available (faster-whisper), else build minimal stubs
    segments = _extract_segments(result)
    save_transcript(segments, transcript_path, cfg.name, cfg.start_time)

    # Store in DuckDB
    meeting_id = _insert_meeting_db(conn, cfg.name, cfg.url, cfg.platform, str(mp4_path), cfg.start_time)
    word_count = len(result.text.split())
    _insert_meeting_transcript_db(conn, meeting_id, str(transcript_path), word_count, result.language)

    _show_summary(cfg.name, transcript_path, result.language, word_count, elapsed)

    # Auto-index into vector store
    from loominary.rag.indexer import auto_index_after_transcription
    auto_index_after_transcription(conn, transcript_path, "meeting")

    # Post-meeting wait + optional shutdown
    should_shutdown = questionary.confirm(
        "Shut down the computer after the post-meeting wait?", default=False
    ).ask()
    if should_shutdown:
        post_meeting_wait(minutes=10)
        shutdown_computer()
    else:
        console.print("[green]All done![/green]")


def _run_manual(conn) -> None:
    """Manual mode: prompt for meeting details, record until user types 'stop'."""
    from loominary.meeting.recorder import get_ffmpeg_exe, build_output_dir, record_indefinite
    from loominary.meeting.audio_devices import find_loopback_device
    from loominary.meeting.scheduler import open_meeting_url
    from loominary.meeting.transcriber import extract_audio, save_transcript

    # Collect meeting details interactively
    name = questionary.text("Meeting name:").ask()
    if not name:
        return

    url = questionary.text("Meeting URL (leave blank to skip opening browser):").ask() or ""

    platform = questionary.select(
        "Platform:",
        choices=["zoom", "teams", "generic", "goldcast"],
    ).ask()
    if platform is None:
        return

    # Pre-flight checks
    ffmpeg_exe = get_ffmpeg_exe()
    console.print("[cyan]Detecting audio loopback device...[/cyan]")
    loopback_device = find_loopback_device(ffmpeg_exe)
    console.print(f"[green]Audio device:[/green] {loopback_device}")

    # Prepare output directory
    started_at = datetime.now()
    _RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    output_dir = build_output_dir(_RECORDINGS_DIR, name, started_at)
    _setup_file_logging(output_dir)

    # Open browser if URL provided
    if url:
        open_meeting_url(url, platform)

    # Set up stop signal via stdin
    stop_event = threading.Event()

    def _stdin_monitor() -> None:
        console.print("[bold]Recording...[/bold] Type [yellow]stop[/yellow] and press Enter to stop recording.")
        while not stop_event.is_set():
            try:
                line = sys.stdin.readline()
                if not line:
                    logger.info("stdin closed — stopping recording.")
                    stop_event.set()
                    break
                if line.strip().lower() == "stop":
                    console.print("[yellow]Stop command received. Finishing recording...[/yellow]")
                    stop_event.set()
                    break
            except (EOFError, OSError):
                stop_event.set()
                break

    monitor_thread = threading.Thread(target=_stdin_monitor, daemon=True)
    monitor_thread.start()

    # Record
    mp4_path = record_indefinite(output_dir, loopback_device, ffmpeg_exe, stop_event)

    # Extract audio + transcribe
    wav_path = output_dir / "audio.wav"
    console.print("[cyan]Extracting audio...[/cyan]")
    extract_audio(mp4_path, wav_path, ffmpeg_exe)

    engine = _get_transcription_engine()
    console.print("[cyan]Transcribing... this may take a few minutes.[/cyan]")
    transcribe_start = time.time()
    result = engine.transcribe(str(wav_path))
    elapsed = time.time() - transcribe_start

    # Build transcript filename and save
    loom_config.LOOMINARY_TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    transcript_filename = _build_meeting_filename(name, started_at)
    transcript_path = loom_config.LOOMINARY_TRANSCRIPTS_DIR / transcript_filename

    segments = _extract_segments(result)
    save_transcript(segments, transcript_path, name, started_at)

    # Store in DuckDB
    meeting_id = _insert_meeting_db(conn, name, url, platform, str(mp4_path), started_at)
    word_count = len(result.text.split())
    _insert_meeting_transcript_db(conn, meeting_id, str(transcript_path), word_count, result.language)

    _show_summary(name, transcript_path, result.language, word_count, elapsed)

    # Auto-index into vector store
    from loominary.rag.indexer import auto_index_after_transcription
    auto_index_after_transcription(conn, transcript_path, "meeting")

    console.print("[green]All done![/green]")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _discover_meeting_configs() -> list[Path]:
    """Return sorted list of *.yaml / *.yml files in the meetings/ folder."""
    if not _MEETINGS_DIR.exists():
        return []
    files = sorted(
        [p for p in _MEETINGS_DIR.iterdir() if p.suffix.lower() in (".yaml", ".yml")]
    )
    return files


def _build_meeting_filename(name: str, dt: datetime) -> str:
    """Build transcript filename: meeting_YYYY-MM-DD_name-slug.txt"""
    from loominary.utils.file_naming import slugify
    date_str = dt.strftime("%Y-%m-%d")
    slug = slugify(name)
    return f"meeting_{date_str}_{slug}.txt"


def _get_transcription_engine():
    backend = loom_config.WHISPER_BACKEND
    model = loom_config.WHISPER_MODEL

    if backend == "faster-whisper":
        from loominary.transcription.faster_whisper_engine import FasterWhisperEngine
        return FasterWhisperEngine(model_size=model)
    elif backend == "openai-whisper":
        from loominary.transcription.whisper_engine import WhisperEngine
        return WhisperEngine(model_size=model)
    else:
        from loominary.transcription.faster_whisper_engine import FasterWhisperEngine
        return FasterWhisperEngine(model_size=model)


def _extract_segments(result) -> list:
    """
    Extract segment objects from a TranscriptResult.
    faster-whisper returns objects with .start/.end/.text;
    openai-whisper returns dicts — wrap them in a simple namespace.
    """
    raw = result.segments or []
    if not raw:
        return []
    # If the first item is a dict (openai-whisper), wrap in a namespace
    if isinstance(raw[0], dict):
        from types import SimpleNamespace
        return [
            SimpleNamespace(
                start=s.get("start", 0.0),
                end=s.get("end", 0.0),
                text=s.get("text", ""),
            )
            for s in raw
        ]
    return raw


def _insert_meeting_db(conn, name: str, url: str, platform: str, recording_path: str, start_time: datetime) -> int:
    from loominary.database.repository import insert_meeting
    return insert_meeting(conn, name, url, platform, recording_path, start_time)


def _insert_meeting_transcript_db(conn, meeting_id: int, transcript_path: str, word_count: int, language: str) -> None:
    from loominary.database.repository import insert_meeting_transcript
    insert_meeting_transcript(
        conn,
        meeting_id,
        transcript_path,
        word_count,
        loom_config.WHISPER_MODEL,
        loom_config.WHISPER_BACKEND,
        language,
    )


def _setup_file_logging(output_dir: Path) -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    fh = logging.FileHandler(output_dir / "recorder.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    root.addHandler(fh)


def _show_summary(name: str, transcript_path: Path, language: str, word_count: int, elapsed: float) -> None:
    m, s = divmod(int(elapsed), 60)
    h, m = divmod(m, 60)
    elapsed_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    table = Table(title="Meeting Transcription Complete", border_style="green")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Meeting", name)
    table.add_row("Language", language or "—")
    table.add_row("Word count", f"{word_count:,}")
    table.add_row("Time taken", elapsed_str)
    table.add_row("Transcript", str(transcript_path))
    table.add_row("SRT", str(transcript_path.with_suffix(".srt")))
    console.print(table)
