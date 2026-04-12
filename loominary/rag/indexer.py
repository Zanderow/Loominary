"""Index transcript files (podcasts + meetings) into Qdrant.

Each file is hashed; if the hash matches what's already in `rag_indexed`, the
file is skipped. On change, all old chunks for that file_path are deleted from
Qdrant before re-inserting.
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Optional

from qdrant_client.http import models as qm

from loominary import config
from loominary.database import repository
from loominary.rag import embedder
from loominary.rag.chunker import chunk_text
from loominary.rag.qdrant import (
    delete_by_file_path,
    ensure_collection,
    get_client,
)
from loominary.utils.progress import console


def _file_hash(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for buf in iter(lambda: f.read(65536), b""):
            h.update(buf)
    return h.hexdigest()


def _build_metadata_prefix(payload: dict) -> str:
    """Short header prepended to each chunk before embedding so metadata is
    semantically searchable too."""
    if payload.get("source_type") == "podcast":
        bits = [
            f"Show: {payload.get('show_name', '')}",
            f"Episode: {payload.get('episode_title', '')}",
            f"Date: {payload.get('release_date', '')}",
        ]
    else:
        bits = [
            f"Meeting: {payload.get('meeting_name', '')}",
            f"Date: {payload.get('start_time', '')}",
            f"Platform: {payload.get('platform', '')}",
        ]
    return "\n".join(b for b in bits if b.split(": ", 1)[1]) + "\n\n"


def _resolve_payload(
    db_conn,
    file_path: Path,
    source_type: str,
) -> tuple[dict, Optional[str]]:
    """Build the per-file payload dict and the source_id (episode/meeting)."""
    p = str(file_path)
    if source_type == "podcast":
        meta = repository.get_podcast_metadata_for_file(db_conn, p) or {}
        payload = {
            "source_type": "podcast",
            "file_path": p,
            "file_name": file_path.name,
            "episode_id": meta.get("episode_id"),
            "episode_title": meta.get("episode_name"),
            "show_id": meta.get("show_id"),
            "show_name": meta.get("show_name"),
            "publisher": meta.get("publisher"),
            "release_date": meta.get("release_date"),
            "language": meta.get("language"),
        }
        return payload, meta.get("episode_id")

    meta = repository.get_meeting_metadata_for_file(db_conn, p) or {}
    payload = {
        "source_type": "meeting",
        "file_path": p,
        "file_name": file_path.name,
        "meeting_id": meta.get("meeting_id"),
        "meeting_name": meta.get("meeting_name"),
        "platform": meta.get("platform"),
        "url": meta.get("url"),
        "start_time": meta.get("start_time"),
        "language": meta.get("language"),
    }
    return payload, meta.get("meeting_id")


def index_file(
    db_conn,
    file_path: str | Path,
    source_type: str,
    *,
    force: bool = False,
) -> int:
    """Index a single transcript file. Returns the number of chunks written.

    Idempotent: if the file's content hash is unchanged and force=False, this
    is a no-op and returns 0.
    """
    path = Path(file_path)
    if not path.exists():
        console.print(f"[yellow]Skip (missing):[/yellow] {path}")
        return 0

    digest = _file_hash(path)
    existing = repository.get_rag_indexed(db_conn, str(path))
    if (
        existing
        and existing["file_hash"] == digest
        and existing["embed_model"] == config.EMBED_MODEL_PATH
        and not force
    ):
        return 0

    text = path.read_text(encoding="utf-8", errors="ignore")
    chunks = chunk_text(text)
    if not chunks:
        return 0

    file_payload, source_id = _resolve_payload(db_conn, path, source_type)
    prefix = _build_metadata_prefix(file_payload)

    embed_inputs = [prefix + c.text for c in chunks]
    dense_vecs = embedder.embed_dense(embed_inputs)
    sparse_vecs = embedder.embed_sparse(embed_inputs)

    ensure_collection()
    delete_by_file_path(str(path))

    points = []
    for chunk, dense, (sp_idx, sp_val) in zip(chunks, dense_vecs, sparse_vecs):
        payload = dict(file_payload)
        payload.update(
            {
                "chunk_index": chunk.index,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "text": chunk.text,
            }
        )
        point_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"{path}:{chunk.index}")
        )
        points.append(
            qm.PointStruct(
                id=point_id,
                vector={
                    "dense": dense,
                    "bm25": qm.SparseVector(indices=sp_idx, values=sp_val),
                },
                payload=payload,
            )
        )

    client = get_client()
    client.upsert(collection_name=config.QDRANT_COLLECTION, points=points, wait=True)

    repository.upsert_rag_indexed(
        db_conn,
        file_path=str(path),
        source_type=source_type,
        source_id=source_id,
        file_hash=digest,
        chunk_count=len(chunks),
        embed_model=config.EMBED_MODEL_PATH,
    )
    return len(chunks)


def reindex_all(db_conn, *, force: bool = False) -> dict:
    """Walk every transcript known to DuckDB and (re)index it."""
    files = repository.list_all_transcript_files(db_conn)
    stats = {"files": 0, "indexed": 0, "skipped": 0, "chunks": 0, "missing": 0}

    ensure_collection()

    for entry in files:
        stats["files"] += 1
        try:
            n = index_file(
                db_conn,
                entry["file_path"],
                entry["source_type"],
                force=force,
            )
        except FileNotFoundError:
            stats["missing"] += 1
            continue
        except Exception as e:
            console.print(f"[red]Index error for {entry['file_path']}: {e}[/red]")
            continue
        if n == 0:
            stats["skipped"] += 1
        else:
            stats["indexed"] += 1
            stats["chunks"] += n
            console.print(f"  [green]+[/green] {Path(entry['file_path']).name} ({n} chunks)")
    return stats


def auto_index_after_transcription(
    db_conn, file_path: str | Path, source_type: str
) -> None:
    """Best-effort hook called right after a new transcript is saved.

    Failures are logged but never raised — indexing must not break the main
    transcription pipeline.
    """
    try:
        n = index_file(db_conn, file_path, source_type)
        if n:
            console.print(f"[green]Indexed {n} chunks into vector store.[/green]")
    except Exception as e:
        console.print(f"[yellow]Auto-index skipped: {e}[/yellow]")
