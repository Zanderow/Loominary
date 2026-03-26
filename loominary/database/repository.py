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


def get_transcript_by_episode_id(
    conn: duckdb.DuckDBPyConnection, episode_spotify_id: str
) -> Optional[dict]:
    """Return transcript metadata if this exact episode has already been transcribed."""
    row = conn.execute(
        """
        SELECT t.id, t.file_name, t.local_file_path, t.word_count, t.transcribed_at,
               e.name AS episode_name, s.name AS show_name, e.release_date
        FROM transcripts t
        JOIN episodes e ON t.episode_spotify_id = e.spotify_id
        JOIN shows s ON e.show_spotify_id = s.spotify_id
        WHERE t.episode_spotify_id = ?
        LIMIT 1
        """,
        [episode_spotify_id],
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "file_name": row[1],
        "local_file_path": row[2],
        "word_count": row[3],
        "transcribed_at": row[4],
        "episode_name": row[5],
        "show_name": row[6],
        "release_date": row[7],
    }


def insert_meeting(
    conn: duckdb.DuckDBPyConnection,
    name: str,
    url: str,
    platform: str,
    recording_path: str,
    start_time,
) -> int:
    """Insert a meeting record and return its generated id."""
    result = conn.execute(
        """
        INSERT INTO meetings (name, url, platform, recording_path, start_time)
        VALUES (?, ?, ?, ?, ?)
        RETURNING id
        """,
        [name, url, platform, recording_path, start_time],
    ).fetchone()
    return result[0]


def insert_meeting_transcript(
    conn: duckdb.DuckDBPyConnection,
    meeting_id: int,
    transcript_path: str,
    word_count: int,
    whisper_model: str,
    whisper_backend: str,
    language: str,
) -> int:
    """Insert a meeting transcript record and return its generated id."""
    result = conn.execute(
        """
        INSERT INTO meeting_transcripts
            (meeting_id, transcript_path, word_count, whisper_model, whisper_backend, language)
        VALUES (?, ?, ?, ?, ?, ?)
        RETURNING id
        """,
        [meeting_id, transcript_path, word_count, whisper_model, whisper_backend, language],
    ).fetchone()
    return result[0]


def get_similar_transcripts(
    conn: duckdb.DuckDBPyConnection,
    show_spotify_id: str,
    episode_name: str,
    exclude_episode_id: str,
    limit: int = 5,
    min_similarity: float = 0.6,
) -> list:
    """Return up to *limit* transcribed episodes from the same show whose names
    are similar to *episode_name*, ordered by jaro_winkler similarity (descending).
    Episodes below *min_similarity* are excluded.
    """
    rows = conn.execute(
        """
        SELECT
            s.name AS show_name,
            e.name AS episode_name,
            e.release_date,
            t.file_name,
            t.local_file_path,
            t.word_count,
            t.transcribed_at,
            jaro_winkler_similarity(LOWER(e.name), LOWER(?)) AS similarity
        FROM transcripts t
        JOIN episodes e ON t.episode_spotify_id = e.spotify_id
        JOIN shows s ON e.show_spotify_id = s.spotify_id
        WHERE e.show_spotify_id = ?
          AND e.spotify_id != ?
        ORDER BY similarity DESC
        LIMIT ?
        """,
        [episode_name, show_spotify_id, exclude_episode_id, limit],
    ).fetchall()

    results = []
    for row in rows:
        similarity = row[7]
        if similarity >= min_similarity:
            results.append(
                {
                    "show_name": row[0],
                    "episode_name": row[1],
                    "release_date": str(row[2]) if row[2] else None,
                    "file_name": row[3],
                    "local_file_path": row[4],
                    "word_count": row[5],
                    "transcribed_at": row[6],
                    "similarity": similarity,
                }
            )
    return results
