"""ShowMetadata + EpisodeMetadata dataclasses + normalizers."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ShowMetadata:
    spotify_id: str
    name: str
    publisher: str = ""
    description: str = ""
    language: str = ""
    total_episodes: int = 0
    rss_feed_url: Optional[str] = None
    external_urls: dict = field(default_factory=dict)
    images: list = field(default_factory=list)

    def to_db_dict(self) -> dict:
        return {
            "spotify_id": self.spotify_id,
            "name": self.name,
            "publisher": self.publisher,
            "description": self.description,
            "language": self.language,
            "total_episodes": self.total_episodes,
            "rss_feed_url": self.rss_feed_url,
            "external_urls": self.external_urls,
            "images": self.images,
        }


@dataclass
class EpisodeMetadata:
    spotify_id: str
    show_spotify_id: str
    name: str
    description: str = ""
    duration_ms: int = 0
    release_date: Optional[str] = None
    rss_audio_url: Optional[str] = None
    external_urls: dict = field(default_factory=dict)

    def to_db_dict(self) -> dict:
        return {
            "spotify_id": self.spotify_id,
            "show_spotify_id": self.show_spotify_id,
            "name": self.name,
            "description": self.description,
            "duration_ms": self.duration_ms,
            "release_date": self.release_date,
            "rss_audio_url": self.rss_audio_url,
            "external_urls": self.external_urls,
        }


def normalize_show(raw: dict) -> ShowMetadata:
    """Convert raw Spotipy show dict to ShowMetadata."""
    return ShowMetadata(
        spotify_id=raw["id"],
        name=raw.get("name", ""),
        publisher=raw.get("publisher", ""),
        description=raw.get("description", ""),
        language=raw.get("language", ""),
        total_episodes=raw.get("total_episodes", 0),
        external_urls=raw.get("external_urls", {}),
        images=raw.get("images", []),
    )


def normalize_episode(raw: dict, show_spotify_id: str) -> EpisodeMetadata:
    """Convert raw Spotipy episode dict to EpisodeMetadata."""
    return EpisodeMetadata(
        spotify_id=raw["id"],
        show_spotify_id=show_spotify_id,
        name=raw.get("name", ""),
        description=raw.get("description", ""),
        duration_ms=raw.get("duration_ms", 0),
        release_date=raw.get("release_date"),
        external_urls=raw.get("external_urls", {}),
    )
