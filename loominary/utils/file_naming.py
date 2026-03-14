"""Slug builder + filename collision handling."""
import re
from pathlib import Path
from datetime import date


def slugify(text: str, max_len: int = 50) -> str:
    """Convert text to a URL/filename-safe slug."""
    text = text.lower()
    text = text.replace("&", "and")
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "_", text.strip())
    text = re.sub(r"-+", "-", text)
    return text[:max_len].strip("_-")


def build_filename(
    release_date: str | date | None,
    show_name: str,
    episode_name: str,
    ext: str = ".txt",
) -> str:
    """Build a standardized filename from show/episode metadata."""
    if isinstance(release_date, date):
        date_str = release_date.isoformat()
    elif release_date:
        date_str = str(release_date)[:10]
    else:
        date_str = "unknown-date"

    show_slug = slugify(show_name)
    ep_slug = slugify(episode_name)
    return f"{date_str}_{show_slug}_{ep_slug}{ext}"


def unique_path(directory: Path, filename: str) -> Path:
    """Return a non-colliding path, appending _2, _3, etc. if needed."""
    path = directory / filename
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = directory / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
