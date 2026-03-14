"""Streaming MP3 download + rich progress bar + auto-cleanup."""
import shutil
from pathlib import Path
from typing import Optional

import requests

from loominary.utils.progress import console, make_download_progress


def download_audio(
    url: str,
    dest_dir: Path,
    filename: str,
    chunk_size: int = 1024 * 64,
) -> Path:
    """
    Stream-download audio from url to dest_dir/filename.
    Shows a rich progress bar. Returns the path to the downloaded file.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename

    try:
        with requests.get(url, stream=True, timeout=30) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))

            with make_download_progress() as progress:
                task = progress.add_task(
                    "Downloading",
                    total=total if total > 0 else None,
                    filename=filename,
                )
                with open(dest_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            progress.update(task, advance=len(chunk))

    except requests.RequestException as e:
        if dest_path.exists():
            dest_path.unlink()
        raise RuntimeError(f"Download failed: {e}") from e

    console.print(f"[green]Downloaded:[/green] {dest_path}")
    return dest_path


def cleanup_audio(path: Path) -> None:
    """Delete a downloaded audio file after transcription."""
    try:
        path.unlink(missing_ok=True)
    except Exception as e:
        console.print(f"[yellow]Warning: could not delete temp file {path}: {e}[/yellow]")
