"""Show search + paginated episode listing."""
import spotipy
from typing import List

from loominary.spotify.metadata import ShowMetadata, EpisodeMetadata, normalize_show, normalize_episode


def search_shows(sp: spotipy.Spotify, query: str, limit: int = 10) -> List[ShowMetadata]:
    """Search for podcast shows by keyword."""
    results = sp.search(q=query, type="show", limit=limit, market="US")
    shows = results.get("shows", {}).get("items", [])
    return [normalize_show(s) for s in shows if s]


def get_show(sp: spotipy.Spotify, show_id: str) -> ShowMetadata:
    """Fetch full show metadata by Spotify ID."""
    raw = sp.show(show_id, market="US")
    return normalize_show(raw)


def get_episode(sp: spotipy.Spotify, episode_id: str, show_id: str) -> EpisodeMetadata:
    """Fetch a single episode by Spotify ID."""
    raw = sp.episode(episode_id, market="US")
    return normalize_episode(raw, show_id)


def get_show_episodes(
    sp: spotipy.Spotify, show_id: str, limit: int = 20, offset: int = 0
) -> List[EpisodeMetadata]:
    """Fetch a page of episodes for a show."""
    results = sp.show_episodes(show_id, limit=limit, offset=offset, market="US")
    episodes = results.get("items", [])
    return [normalize_episode(e, show_id) for e in episodes if e]


def get_all_episodes(
    sp: spotipy.Spotify, show_id: str, max_episodes: int = 200
) -> List[EpisodeMetadata]:
    """Fetch all episodes for a show (paginated), up to max_episodes."""
    all_eps: List[EpisodeMetadata] = []
    offset = 0
    page_size = 50

    while len(all_eps) < max_episodes:
        batch = get_show_episodes(sp, show_id, limit=page_size, offset=offset)
        if not batch:
            break
        all_eps.extend(batch)
        offset += page_size
        if len(batch) < page_size:
            break

    return all_eps[:max_episodes]
