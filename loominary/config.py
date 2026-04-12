"""Load .env, validate required fields, expose typed constants."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(
            f"Missing required environment variable: {key}\n"
            f"Copy .env.example to .env and fill in the required values."
        )
    return val


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default)


# Spotify
SPOTIPY_CLIENT_ID: str = ""
SPOTIPY_CLIENT_SECRET: str = ""
SPOTIPY_REDIRECT_URI: str = "http://127.0.0.1:8888/callback"

# Transcription
WHISPER_BACKEND: str = _get("WHISPER_BACKEND", "faster-whisper")
WHISPER_MODEL: str = _get("WHISPER_MODEL", "small")
SAVE_SEGMENTS: bool = _get("SAVE_SEGMENTS", "false").lower() == "true"

# Podcast Index (optional)
PODCAST_INDEX_API_KEY: str = _get("PODCAST_INDEX_API_KEY")
PODCAST_INDEX_API_SECRET: str = _get("PODCAST_INDEX_API_SECRET")

# Google Drive (optional)
GOOGLE_CLIENT_SECRETS_FILE: str = _get("GOOGLE_CLIENT_SECRETS_FILE")
GOOGLE_DRIVE_FOLDER_NAME: str = _get("GOOGLE_DRIVE_FOLDER_NAME", "Loominary")

# Paths
LOOMINARY_DB_PATH: Path = Path(_get("LOOMINARY_DB_PATH", "./data/loominary.duckdb"))
LOOMINARY_TRANSCRIPTS_DIR: Path = Path(_get("LOOMINARY_TRANSCRIPTS_DIR", "./data/transcripts"))
LOOMINARY_TMP_DIR: Path = Path(_get("LOOMINARY_TMP_DIR", "./tmp"))

# RAG / Qdrant
QDRANT_URL: str = _get("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION: str = _get("QDRANT_COLLECTION", "loominary_rag")
EMBED_MODEL_PATH: str = _get("EMBED_MODEL_PATH", "BAAI/bge-m3")
EMBED_DEVICE: str = _get("EMBED_DEVICE", "auto")  # auto|cpu|cuda
SPARSE_MODEL_NAME: str = _get("SPARSE_MODEL_NAME", "Qdrant/bm25")
RAG_CHUNK_TOKENS: int = int(_get("RAG_CHUNK_TOKENS", "512"))
RAG_CHUNK_OVERLAP: int = int(_get("RAG_CHUNK_OVERLAP", "64"))
RAG_TOP_K: int = int(_get("RAG_TOP_K", "8"))
RAG_CONTEXT_K: int = int(_get("RAG_CONTEXT_K", "5"))

# Local LLM (llama.cpp server, OpenAI-compatible)
LLM_BASE_URL: str = _get("LLM_BASE_URL", "http://localhost:8080")
LLM_MODEL: str = _get("LLM_MODEL", "qwen3.5-35b-a3b")
LLM_CTX_SIZE: int = int(_get("LLM_CTX_SIZE", "8192"))
LLM_TEMPERATURE: float = float(_get("LLM_TEMPERATURE", "0.2"))
LLM_MAX_TOKENS: int = int(_get("LLM_MAX_TOKENS", "4096"))


def validate_spotify() -> None:
    """Fail fast if Spotify credentials are missing."""
    global SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, SPOTIPY_REDIRECT_URI
    SPOTIPY_CLIENT_ID = _require("SPOTIPY_CLIENT_ID")
    SPOTIPY_CLIENT_SECRET = _require("SPOTIPY_CLIENT_SECRET")
    SPOTIPY_REDIRECT_URI = _get("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback")


def validate_google_drive() -> None:
    """Fail fast if Google Drive config is missing."""
    global GOOGLE_CLIENT_SECRETS_FILE
    GOOGLE_CLIENT_SECRETS_FILE = _require("GOOGLE_CLIENT_SECRETS_FILE")
    if not Path(GOOGLE_CLIENT_SECRETS_FILE).exists():
        raise FileNotFoundError(
            f"Google client secrets file not found: {GOOGLE_CLIENT_SECRETS_FILE}"
        )
