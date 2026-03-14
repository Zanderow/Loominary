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

ALL_STATEMENTS = [CREATE_SHOWS, CREATE_EPISODES, CREATE_TRANSCRIPTS_SEQ, CREATE_TRANSCRIPTS]
