"""Parse Spotify share URLs → IDs."""
import re
import requests
from typing import Optional, Tuple


_SPOTIFY_URL_RE = re.compile(
    r"open\.spotify\.com/(show|episode|podcast)/([A-Za-z0-9]+)"
)
_SPOTIFY_URI_RE = re.compile(r"spotify:(show|episode):([A-Za-z0-9]+)")


def parse_spotify_url(url: str) -> Optional[Tuple[str, str]]:
    """
    Parse a Spotify URL or URI and return (type, id).
    type is 'show' or 'episode'.
    Returns None if the URL is not recognized.
    """
    url = url.strip()

    # Try URI format first
    m = _SPOTIFY_URI_RE.search(url)
    if m:
        return m.group(1), m.group(2)

    # Try to follow short links (sp.app.link, spotify.link etc.)
    if "spotify.link" in url or "sp.app.link" in url:
        try:
            resp = requests.get(url, allow_redirects=True, timeout=5)
            url = resp.url
        except Exception:
            pass

    m = _SPOTIFY_URL_RE.search(url)
    if m:
        kind = m.group(1)
        if kind == "podcast":
            kind = "show"
        return kind, m.group(2)

    return None


def is_spotify_url(text: str) -> bool:
    """Return True if text looks like a Spotify URL or URI."""
    return bool(parse_spotify_url(text))
