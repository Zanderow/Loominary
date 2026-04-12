"""Qdrant client + collection bootstrap.

Single collection with named vectors:
- "dense": BGE-M3, 1024-dim, cosine
- "bm25": sparse BM25 (FastEmbed Qdrant/bm25)

Connection strategy:
1. If QDRANT_URL is set, try to connect to the remote Qdrant server.
2. If the server is unreachable, fall back to local file-based storage
   at ``data/qdrant_local/`` (no server required, uses qdrant_client's
   embedded mode).
"""
from __future__ import annotations

from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from loominary import config
from loominary.rag.embedder import DENSE_DIM
from loominary.utils.progress import console


_client: QdrantClient | None = None

QDRANT_LOCAL_PATH = Path(config.LOOMINARY_DB_PATH).parent / "qdrant_local"


def get_client() -> QdrantClient:
    global _client
    if _client is not None:
        return _client

    if config.QDRANT_URL:
        try:
            candidate = QdrantClient(url=config.QDRANT_URL, prefer_grpc=False, timeout=5.0)
            candidate.get_collections()
            _client = candidate
            return _client
        except Exception:
            console.print(
                f"[yellow]Qdrant server at {config.QDRANT_URL} is unreachable — "
                f"falling back to local storage at {QDRANT_LOCAL_PATH}[/yellow]"
            )

    QDRANT_LOCAL_PATH.mkdir(parents=True, exist_ok=True)
    _client = QdrantClient(path=str(QDRANT_LOCAL_PATH))
    return _client


def ensure_collection() -> None:
    """Create the collection on first use; idempotent."""
    client = get_client()
    if client.collection_exists(config.QDRANT_COLLECTION):
        return

    client.create_collection(
        collection_name=config.QDRANT_COLLECTION,
        vectors_config={
            "dense": qm.VectorParams(size=DENSE_DIM, distance=qm.Distance.COSINE),
        },
        sparse_vectors_config={
            "bm25": qm.SparseVectorParams(modifier=qm.Modifier.IDF),
        },
    )

    for field, schema in [
        ("source_type", qm.PayloadSchemaType.KEYWORD),
        ("file_path", qm.PayloadSchemaType.KEYWORD),
        ("episode_id", qm.PayloadSchemaType.KEYWORD),
        ("show_name", qm.PayloadSchemaType.KEYWORD),
        ("meeting_id", qm.PayloadSchemaType.KEYWORD),
    ]:
        try:
            client.create_payload_index(
                collection_name=config.QDRANT_COLLECTION,
                field_name=field,
                field_schema=schema,
            )
        except Exception:
            pass


def delete_by_file_path(file_path: str) -> None:
    """Remove all chunks belonging to a transcript file (used on re-index)."""
    client = get_client()
    if not client.collection_exists(config.QDRANT_COLLECTION):
        return
    client.delete(
        collection_name=config.QDRANT_COLLECTION,
        points_selector=qm.FilterSelector(
            filter=qm.Filter(
                must=[
                    qm.FieldCondition(
                        key="file_path",
                        match=qm.MatchValue(value=file_path),
                    )
                ]
            )
        ),
    )
