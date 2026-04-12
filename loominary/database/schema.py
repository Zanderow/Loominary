"""DuckDB schema definitions."""

CREATE_SHOWS = """
CREATE TABLE IF NOT EXISTS shows (
    spotify_id      VARCHAR PRIMARY KEY,
    name            VARCHAR NOT NULL,
    publisher       VARCHAR,
    description     TEXT,
    language        VARCHAR,
    total_episodes  INTEGER,
    rss_feed_url    VARCHAR,
    external_urls   JSON,
    images          JSON,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_EPISODES = """
CREATE TABLE IF NOT EXISTS episodes (
    spotify_id      VARCHAR PRIMARY KEY,
    show_spotify_id VARCHAR NOT NULL REFERENCES shows(spotify_id),
    name            VARCHAR NOT NULL,
    description     TEXT,
    duration_ms     INTEGER,
    release_date    DATE,
    rss_audio_url   VARCHAR,
    external_urls   JSON,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_TRANSCRIPTS_SEQ = "CREATE SEQUENCE IF NOT EXISTS transcripts_id_seq;"

CREATE_TRANSCRIPTS = """
CREATE TABLE IF NOT EXISTS transcripts (
    id                  BIGINT DEFAULT nextval('transcripts_id_seq') PRIMARY KEY,
    episode_spotify_id  VARCHAR NOT NULL REFERENCES episodes(spotify_id),
    local_file_path     VARCHAR NOT NULL,
    file_name           VARCHAR NOT NULL,
    word_count          INTEGER,
    whisper_model       VARCHAR NOT NULL,
    whisper_backend     VARCHAR NOT NULL,
    language_detected   VARCHAR,
    drive_file_id       VARCHAR,
    drive_url           VARCHAR,
    transcribed_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_MEETINGS_SEQ = "CREATE SEQUENCE IF NOT EXISTS meetings_id_seq;"

CREATE_MEETINGS = """
CREATE TABLE IF NOT EXISTS meetings (
    id               BIGINT DEFAULT nextval('meetings_id_seq') PRIMARY KEY,
    name             VARCHAR NOT NULL,
    url              VARCHAR,
    platform         VARCHAR,
    recording_path   VARCHAR,
    start_time       TIMESTAMP,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_MEETING_TRANSCRIPTS_SEQ = "CREATE SEQUENCE IF NOT EXISTS meeting_transcripts_id_seq;"

CREATE_MEETING_TRANSCRIPTS = """
CREATE TABLE IF NOT EXISTS meeting_transcripts (
    id               BIGINT DEFAULT nextval('meeting_transcripts_id_seq') PRIMARY KEY,
    meeting_id       BIGINT REFERENCES meetings(id),
    transcript_path  VARCHAR,
    word_count       INTEGER,
    whisper_model    VARCHAR,
    whisper_backend  VARCHAR,
    language         VARCHAR,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_RAG_INDEXED = """
CREATE TABLE IF NOT EXISTS rag_indexed (
    file_path     VARCHAR PRIMARY KEY,
    source_type   VARCHAR NOT NULL,   -- 'podcast' | 'meeting'
    source_id     VARCHAR,            -- episode_spotify_id or meeting_id (as text)
    file_hash     VARCHAR NOT NULL,
    chunk_count   INTEGER NOT NULL,
    embed_model   VARCHAR NOT NULL,
    indexed_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

ALL_STATEMENTS = [
    CREATE_SHOWS,
    CREATE_EPISODES,
    CREATE_TRANSCRIPTS_SEQ,
    CREATE_TRANSCRIPTS,
    CREATE_MEETINGS_SEQ,
    CREATE_MEETINGS,
    CREATE_MEETING_TRANSCRIPTS_SEQ,
    CREATE_MEETING_TRANSCRIPTS,
    CREATE_RAG_INDEXED,
]
