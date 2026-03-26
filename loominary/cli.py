"""Interactive menus + full workflow orchestration."""
import json
import sys
import time
from pathlib import Path
from typing import Optional

import questionary
from rich.table import Table
from rich.panel import Panel

from loominary import config
from loominary.utils.progress import console
from loominary.utils.file_naming import build_filename, unique_path
from loominary.spotify.link_parser import parse_spotify_url
from loominary.spotify.metadata import ShowMetadata, EpisodeMetadata


def run(db_conn, sp) -> None:
    """Main interactive workflow."""
    console.print(
        Panel.fit(
            "[bold cyan]Loominary[/bold cyan] — Podcast Transcription Tool",
            border_style="cyan",
        )
    )

    while True:
        action = questionary.select(
            "What would you like to do?",
            choices=[
                "Search for a podcast",
                "Paste a Spotify link",
                "Quit",
            ],
        ).ask()

        if action is None or action == "Quit":
            console.print("[dim]Goodbye.[/dim]")
            break
        elif action == "Search for a podcast":
            _search_workflow(db_conn, sp)
        elif action == "Paste a Spotify link":
            _link_workflow(db_conn, sp)


def _search_workflow(db_conn, sp) -> None:
    from loominary.spotify.search import search_shows, get_show_episodes, get_show

    query = questionary.text("Search for a podcast:").ask()
    if not query:
        return

    with console.status("[cyan]Searching Spotify...[/cyan]"):
        shows = search_shows(sp, query, limit=8)

    if not shows:
        console.print("[red]No shows found.[/red]")
        return

    choices = [f"{s.name} — {s.publisher}" for s in shows] + ["Cancel"]
    selected = questionary.select("Select a show:", choices=choices).ask()
    if not selected or selected == "Cancel":
        return

    show = shows[choices.index(selected)]
    _process_show(db_conn, sp, show)


def _link_workflow(db_conn, sp) -> None:
    from loominary.spotify.search import get_show, get_episode

    url = questionary.text("Paste Spotify URL or URI:").ask()
    if not url:
        return

    parsed = parse_spotify_url(url)
    if not parsed:
        console.print("[red]Could not parse Spotify URL.[/red]")
        return

    kind, spotify_id = parsed

    if kind == "show":
        with console.status("[cyan]Fetching show...[/cyan]"):
            show = get_show(sp, spotify_id)
        _process_show(db_conn, sp, show)

    elif kind == "episode":
        with console.status("[cyan]Fetching episode...[/cyan]"):
            raw_ep = sp.episode(spotify_id, market="US")
            show_id = raw_ep.get("show", {}).get("id", "")
            show_raw = raw_ep.get("show", {})

        from loominary.spotify.metadata import normalize_show, normalize_episode
        show = normalize_show({**show_raw, "id": show_id or "unknown"})
        episode = normalize_episode(raw_ep, show.spotify_id)
        _process_episode(db_conn, show, episode)


def _process_show(db_conn, sp, show: ShowMetadata) -> None:
    from loominary.spotify.search import get_show_episodes
    from loominary.database import repository

    console.print(f"\n[bold]{show.name}[/bold] by {show.publisher} ({show.total_episodes} episodes)")
    repository.upsert_show(db_conn, show.to_db_dict())

    with console.status("[cyan]Fetching episodes...[/cyan]"):
        episodes = get_show_episodes(sp, show.spotify_id, limit=20)

    if not episodes:
        console.print("[red]No episodes found.[/red]")
        return

    choices = [f"{e.release_date or '???'} — {e.name[:80]}" for e in episodes] + ["Cancel"]
    selected = questionary.select("Select an episode:", choices=choices).ask()
    if not selected or selected == "Cancel":
        return

    episode = episodes[choices.index(selected)]
    _process_episode(db_conn, show, episode)


def _process_episode(db_conn, show: ShowMetadata, episode: EpisodeMetadata) -> None:
    from loominary.database import repository
    from loominary.rss.discovery import discover_rss_feed, find_episode_audio_url
    from loominary.rss.downloader import download_audio, cleanup_audio

    # Upsert show + episode
    repository.upsert_show(db_conn, show.to_db_dict())
    repository.upsert_episode(db_conn, episode.to_db_dict())

    console.print(f"\n[bold]Episode:[/bold] {episode.name}")

    # --- Duplicate detection ---
    # 1. Exact match: same Spotify episode ID already has a transcript
    existing = repository.get_transcript_by_episode_id(db_conn, episode.spotify_id)
    if existing:
        _show_existing_transcript(existing)
        console.print("[yellow]This episode has already been transcribed. Skipping.[/yellow]")
        return

    # 2. Similar matches within the same show
    similar = repository.get_similar_transcripts(
        db_conn, show.spotify_id, episode.name, episode.spotify_id
    )
    if similar:
        proceed = _ask_about_similar(similar)
        if not proceed:
            return

    # Check cached RSS + audio URL
    audio_url = repository.get_episode_audio_url(db_conn, episode.spotify_id)
    rss_url = None

    if not audio_url:
        rss_url = repository.get_show_rss(db_conn, show.spotify_id)

        if not rss_url:
            console.print("[cyan]Discovering RSS feed...[/cyan]")
            rss_url = discover_rss_feed(show.name, show.external_urls)
            if not rss_url:
                console.print(
                    "[red]Could not find RSS feed for this podcast.[/red]\n"
                    "[dim]Try: Is this a Spotify-exclusive podcast? Check if it has a public RSS feed.[/dim]"
                )
                return
            repository.update_show_rss(db_conn, show.spotify_id, rss_url)

        console.print("[cyan]Finding episode audio URL in RSS feed...[/cyan]")
        audio_url = find_episode_audio_url(rss_url, episode.name, episode.release_date)
        if not audio_url:
            console.print("[red]Could not find this episode's audio URL in the RSS feed.[/red]")
            return
        repository.update_episode_audio_url(db_conn, episode.spotify_id, audio_url)

    # Build filename
    filename_base = build_filename(episode.release_date, show.name, episode.name, ext=".mp3", prefix="podcast")
    tmp_path = unique_path(config.LOOMINARY_TMP_DIR / "audio", filename_base)

    # Download
    try:
        audio_path = download_audio(audio_url, tmp_path.parent, tmp_path.name)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        return

    # Transcribe
    engine = _get_transcription_engine()
    transcribe_start = time.time()
    try:
        result = engine.transcribe(str(audio_path))
    except MemoryError as e:
        console.print(f"[red]Out of memory:[/red] {e}")
        console.print(
            "[yellow]Tip:[/yellow] Set [bold]WHISPER_BACKEND=faster-whisper[/bold] in .env — "
            "it uses ~4x less RAM and handles long episodes without chunking."
        )
        cleanup_audio(audio_path)
        return
    except Exception as e:
        console.print(f"[red]Transcription failed:[/red] {e}")
        cleanup_audio(audio_path)
        return
    finally:
        cleanup_audio(audio_path)
    transcribe_elapsed = time.time() - transcribe_start

    # Save transcript
    txt_filename = build_filename(episode.release_date, show.name, episode.name, ext=".txt", prefix="podcast")
    config.LOOMINARY_TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    txt_path = unique_path(config.LOOMINARY_TRANSCRIPTS_DIR, txt_filename)
    txt_path.write_text(result.text, encoding="utf-8")
    console.print(f"[green]Transcript saved:[/green] {txt_path}")

    # Optionally save segments JSON
    if config.SAVE_SEGMENTS and result.segments:
        seg_path = txt_path.with_suffix(".segments.json")
        seg_path.write_text(json.dumps(result.segments, indent=2), encoding="utf-8")
        console.print(f"[green]Segments saved:[/green] {seg_path}")

    # Store in DB
    word_count = len(result.text.split())
    transcript_record = {
        "episode_spotify_id": episode.spotify_id,
        "local_file_path": str(txt_path),
        "file_name": txt_path.name,
        "word_count": word_count,
        "whisper_model": config.WHISPER_MODEL,
        "whisper_backend": config.WHISPER_BACKEND,
        "language_detected": result.language,
    }
    transcript_id = repository.insert_transcript(db_conn, transcript_record)

    _show_summary(episode, txt_path, result, word_count, transcribe_elapsed)

    # Optional Google Drive upload
    if config.GOOGLE_CLIENT_SECRETS_FILE:
        upload = questionary.confirm("Upload transcript to Google Drive?", default=False).ask()
        if upload:
            _upload_to_drive(db_conn, transcript_id, txt_path, show.name)


def _show_existing_transcript(existing: dict) -> None:
    """Print a summary table for an already-transcribed episode."""
    table = Table(title="Transcript Already Exists", border_style="yellow")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Show", existing.get("show_name") or "—")
    table.add_row("Episode", existing.get("episode_name") or "—")
    table.add_row("Release date", str(existing.get("release_date") or "—"))
    table.add_row("File", existing.get("file_name") or "—")
    table.add_row(
        "Word count",
        f"{existing['word_count']:,}" if existing.get("word_count") else "—",
    )
    table.add_row("Transcribed at", str(existing.get("transcribed_at") or "—"))
    table.add_row("Path", existing.get("local_file_path") or "—")
    console.print(table)


def _ask_about_similar(similar: list) -> bool:
    """Show top similar transcripts and ask the user whether to proceed.

    Returns True if the user wants to go ahead with transcription, False to stop.
    """
    console.print(
        "\n[yellow]Similar transcripts were found in this show.[/yellow] "
        "Is the episode you selected already among these?"
    )

    choice_labels = []
    for s in similar:
        date_str = s.get("release_date") or "????"
        pct = int(s["similarity"] * 100)
        label = f"{date_str} — {s['episode_name'][:70]}  [{pct}% match]  ({s['file_name']})"
        choice_labels.append(label)

    proceed_label = "None of these — proceed with transcription"
    cancel_label = "Cancel"
    all_choices = choice_labels + [proceed_label, cancel_label]

    selected = questionary.select(
        "Select a match if it already exists, or choose to proceed:",
        choices=all_choices,
    ).ask()

    if selected is None or selected == cancel_label:
        return False

    if selected == proceed_label:
        return True

    # User identified one of the similar results as the existing transcript
    idx = choice_labels.index(selected)
    matched = similar[idx]
    _show_existing_transcript(matched)
    console.print("[yellow]Transcription cancelled — existing transcript shown above.[/yellow]")
    return False


def _show_summary(episode: EpisodeMetadata, txt_path: Path, result, word_count: int, elapsed: float = 0.0) -> None:
    m, s = divmod(int(elapsed), 60)
    h, m = divmod(m, 60)
    elapsed_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    table = Table(title="Transcription Complete", border_style="green")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Episode", episode.name[:60])
    table.add_row("Language", result.language)
    table.add_row("Word count", f"{word_count:,}")
    table.add_row("Time taken", elapsed_str)
    table.add_row("Output file", str(txt_path))
    console.print(table)


def _upload_to_drive(db_conn, transcript_id: int, txt_path: Path, show_name: str) -> None:
    from loominary.database import repository

    try:
        from loominary.auth.google_auth import get_drive_service
        from loominary.drive.uploader import upload_transcript
        service = get_drive_service()
        file_id, web_link = upload_transcript(service, txt_path, show_name)
        repository.update_transcript_drive(db_conn, transcript_id, file_id, web_link)
        console.print(f"[green]Drive link:[/green] {web_link}")
    except Exception as e:
        console.print(f"[red]Google Drive upload failed: {e}[/red]")


def _get_transcription_engine():
    backend = config.WHISPER_BACKEND
    model = config.WHISPER_MODEL

    if backend == "faster-whisper":
        from loominary.transcription.faster_whisper_engine import FasterWhisperEngine
        return FasterWhisperEngine(model_size=model)
    elif backend == "openai-whisper":
        from loominary.transcription.whisper_engine import WhisperEngine
        return WhisperEngine(model_size=model)
    else:
        console.print(f"[yellow]Unknown backend '{backend}', defaulting to faster-whisper.[/yellow]")
        from loominary.transcription.faster_whisper_engine import FasterWhisperEngine
        return FasterWhisperEngine(model_size=model)
