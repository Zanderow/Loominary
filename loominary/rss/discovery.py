"""4-layer RSS feed discovery + episode audio URL extraction."""
import hashlib
import hmac
import time
import difflib
import re
from typing import Optional
from urllib.parse import quote_plus

import feedparser
import requests

from loominary import config
from loominary.utils.progress import console


def discover_rss_feed(show_name: str, show_external_urls: dict) -> Optional[str]:
    """
    Attempt to find the RSS feed URL for a podcast show using a 4-layer fallback.
    Returns the feed URL or None if all methods fail.
    """
    # Layer 1: Spotify external_urls (rarely populated)
    rss = show_external_urls.get("rss") or show_external_urls.get("rss_feed")
    if rss:
        console.print(f"[dim]RSS: found in Spotify external_urls[/dim]")
        return rss

    # Layer 2: iTunes Search API
    rss = _itunes_lookup(show_name)
    if rss:
        console.print(f"[dim]RSS: found via iTunes Search API[/dim]")
        return rss

    # Layer 3: Podcast Index API
    if config.PODCAST_INDEX_API_KEY and config.PODCAST_INDEX_API_SECRET:
        rss = _podcast_index_lookup(show_name)
        if rss:
            console.print(f"[dim]RSS: found via Podcast Index API[/dim]")
            return rss

    # Layer 4: Spotify web page scrape
    rss = _spotify_page_scrape(show_name)
    if rss:
        console.print(f"[dim]RSS: found via Spotify page scrape[/dim]")
        return rss

    return None


def _itunes_lookup(show_name: str) -> Optional[str]:
    try:
        url = f"https://itunes.apple.com/search?term={quote_plus(show_name)}&entity=podcast&limit=5"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        results = data.get("results", [])
        if results:
            # Pick the closest match by name
            best = max(
                results,
                key=lambda r: difflib.SequenceMatcher(
                    None, show_name.lower(), r.get("collectionName", "").lower()
                ).ratio(),
            )
            return best.get("feedUrl")
    except Exception as e:
        console.print(f"[dim]iTunes lookup failed: {e}[/dim]")
    return None


def _podcast_index_lookup(show_name: str) -> Optional[str]:
    try:
        api_key = config.PODCAST_INDEX_API_KEY
        api_secret = config.PODCAST_INDEX_API_SECRET
        epoch = str(int(time.time()))
        hash_input = api_key + api_secret + epoch
        auth_hash = hashlib.sha1(hash_input.encode("utf-8")).hexdigest()

        headers = {
            "X-Auth-Date": epoch,
            "X-Auth-Key": api_key,
            "Authorization": auth_hash,
            "User-Agent": "Loominary/0.1",
        }
        url = f"https://api.podcastindex.org/api/1.0/search/byterm?q={quote_plus(show_name)}"
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        feeds = data.get("feeds", [])
        if feeds:
            best = max(
                feeds,
                key=lambda f: difflib.SequenceMatcher(
                    None, show_name.lower(), f.get("title", "").lower()
                ).ratio(),
            )
            return best.get("url")
    except Exception as e:
        console.print(f"[dim]Podcast Index lookup failed: {e}[/dim]")
    return None


def _spotify_page_scrape(show_name: str) -> Optional[str]:
    """Last resort: try to find RSS link via search result pages."""
    try:
        search_url = f"https://open.spotify.com/search/{quote_plus(show_name)}/podcasts"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(search_url, headers=headers, timeout=10)
        # Look for RSS link in HTML
        matches = re.findall(
            r'<link[^>]+type=["\']application/rss\+xml["\'][^>]+href=["\']([^"\']+)["\']',
            resp.text,
        )
        if matches:
            return matches[0]
    except Exception as e:
        console.print(f"[dim]Spotify page scrape failed: {e}[/dim]")
    return None


def find_episode_audio_url(
    rss_url: str,
    episode_name: str,
    release_date: Optional[str] = None,
    similarity_threshold: float = 0.80,
) -> Optional[str]:
    """
    Parse an RSS feed and find the audio URL for a specific episode.
    Matches by title similarity (≥ threshold) or release date as fallback.
    """
    try:
        feed = feedparser.parse(rss_url)
    except Exception as e:
        console.print(f"[red]Failed to parse RSS feed: {e}[/red]")
        return None

    entries = feed.get("entries", [])
    if not entries:
        return None

    # Try title similarity match
    best_entry = None
    best_score = 0.0
    for entry in entries:
        title = entry.get("title", "")
        score = difflib.SequenceMatcher(None, episode_name.lower(), title.lower()).ratio()
        if score > best_score:
            best_score = score
            best_entry = entry

    if best_score >= similarity_threshold and best_entry:
        return _extract_audio_url(best_entry)

    # Fallback: match by release date
    if release_date:
        date_prefix = str(release_date)[:10]
        for entry in entries:
            published = entry.get("published", "") or entry.get("updated", "")
            if date_prefix in published:
                url = _extract_audio_url(entry)
                if url:
                    return url

    # Return best match if at least partial
    if best_entry and best_score >= 0.5:
        console.print(
            f"[yellow]Best title match ({best_score:.0%}): {best_entry.get('title', '')}[/yellow]"
        )
        return _extract_audio_url(best_entry)

    return None


def _extract_audio_url(entry: dict) -> Optional[str]:
    """Extract the MP3/audio enclosure URL from an RSS entry."""
    enclosures = entry.get("enclosures", [])
    for enc in enclosures:
        url = enc.get("href") or enc.get("url")
        if url:
            return url

    # Some feeds use media:content
    media_content = entry.get("media_content", [])
    for mc in media_content:
        url = mc.get("url")
        if url:
            return url

    return None
