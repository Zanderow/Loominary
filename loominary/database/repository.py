"""DuckDB repository: upsert_show, upsert_episode, insert_transcript, etc."""
import json
import duckdb
from pathlib import Path
from typing import Optional

from loominary.database.schema import ALL_STATEMENTS


_conn: Optional[duckdb.DuckDBPyConnection] = None


def get_connection(db_path: Path) -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _conn = duckdb.connect(str(db_path))
        _init_schema(_conn)
    return _conn


def _init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    for stmt in ALL_STATEMENTS:
        conn.execute(stmt)


def upsert_show(conn: duckdb.DuckDBPyConnection, show: dict) -> None:
    conn.execute(
        """
        INSERT INTO shows (spotify_id, name, publisher, description, language,
                           total_episodes, rss_feed_url, external_urls, images)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (spotify_id) DO UPDATE SET
            name = excluded.name,
            publisher = excluded.publisher,
            description = excluded.description,
            language = excluded.language,
            total_episodes = excluded.total_episodes,
            rss_feed_url = COALESCE(excluded.rss_feed_url, shows.rss_feed_url),
            external_urls = excluded.external_urls,
            images = excluded.images,
            updated_at = now()
        """,
        [
            show["spotify_id"],
            show["name"],
            show.get("publisher"),
            show.get("description"),
            show.get("language"),
            show.get("total_episodes"),
            show.get("rss_feed_url"),
            json.dumps(show.get("external_urls", {})),
            json.dumps(show.get("images", [])),
        ],
    )


def upsert_episode(conn: duckdb.DuckDBPyConnection, episode: dict) -> None:
    conn.execute(
        """
        INSERT INTO episodes (spotify_id, show_spotify_id, name, description,
                              duration_ms, release_date, rss_audio_url, external_urls)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (spotify_id) DO UPDATE SET
            name = excluded.name,
            description = excluded.description,
            duration_ms = excluded.duration_ms,
            release_date = excluded.release_date,
            rss_audio_url = COALESCE(excluded.rss_audio_url, episodes.rss_audio_url),
            external_urls = excluded.external_urls
        """,
        [
            episode["spotify_id"],
            episode["show_spotify_id"],
            episode["name"],
            episode.get("description"),
            episode.get("duration_ms"),
            episode.get("release_date"),
            episode.get("rss_audio_url"),
            json.dumps(episode.get("external_urls", {})),
        ],
    )


def insert_transcript(conn: duckdb.DuckDBPyConnection, transcript: dict) -> int:
    result = conn.execute(
        """
        INSERT INTO transcripts (episode_spotify_id, local_file_path, file_name,
                                  word_count, whisper_model, whisper_backend,
                                  language_detected, drive_file_id, drive_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id
        """,
        [
            transcript["episode_spotify_id"],
            transcript["local_file_path"],
            transcript["file_name"],
            transcript.get("word_count"),
            transcript["whisper_model"],
            transcript["whisper_backend"],
            transcript.get("language_detected"),
            transcript.get("drive_file_id"),
            transcript.get("drive_url"),
        ],
    ).fetchone()
    return result[0]


def update_transcript_drive(
    conn: duckdb.DuckDBPyConnection,
    transcript_id: int,
    drive_file_id: str,
    drive_url: str,
) -> None:
    conn.execute(
        "UPDATE transcripts SET drive_file_id = ?, drive_url = ? WHERE id = ?",
        [drive_file_id, drive_url, transcript_id],
    )


def update_show_rss(
    conn: duckdb.DuckDBPyConnection, show_spotify_id: str, rss_url: str
) -> None:
    conn.execute(
        "UPDATE shows SET rss_feed_url = ?, updated_at = now() WHERE spotify_id = ?",
        [rss_url, show_spotify_id],
    )


def update_episode_audio_url(
    conn: duckdb.DuckDBPyConnection, episode_spotify_id: str, audio_url: str
) -> None:
    conn.execute(
        "UPDATE episodes SET rss_audio_url = ? WHERE spotify_id = ?",
        [audio_url, episode_spotify_id],
    )


def get_show_rss(conn: duckdb.DuckDBPyConnection, show_spotify_id: str) -> Optional[str]:
    row = conn.execute(
        "SELECT rss_feed_url FROM shows WHERE spotify_id = ?", [show_spotify_id]
    ).fetchone()
    return row[0] if row else None


def get_episode_audio_url(
    conn: duckdb.DuckDBPyConnection, episode_spotify_id: str
) -> Optional[str]:
    row = conn.execute(
        "SELECT rss_audio_url FROM episodes WHERE spotify_id = ?", [episode_spotify_id]
    ).fetchone()
    return row[0] if row else None
