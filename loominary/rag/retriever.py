"""Hybrid search: BGE-M3 dense + BM25 sparse, fused with RRF in a single Qdrant
Query API call, then reranked with a cross-encoder.

The hybrid stage casts a wide net (RAG_RERANK_CANDIDATES chunks); the reranker
scores each candidate against the query and keeps the best top_k. Candidates
scoring below RAG_MIN_RERANK_SCORE are dropped entirely, so an off-topic
question returns no hits rather than the least-bad matches.

Returns chunks with full payload for citations.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from qdrant_client.http import models as qm

from loominary import config
from loominary.rag import embedder
from loominary.rag.qdrant import ensure_collection, get_client


def hybrid_search(
    query: str,
    *,
    top_k: Optional[int] = None,
    source_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Run hybrid dense + sparse search, fused with RRF, then cross-encoder
    reranked and filtered by RAG_MIN_RERANK_SCORE.

    Returns a list of dicts (payload + score) ordered best-first.
    """
    top_k = top_k or config.RAG_TOP_K
    candidates = max(config.RAG_RERANK_CANDIDATES, top_k)
    ensure_collection()

    dense_vec = embedder.embed_dense([query])[0]
    sp_idx, sp_val = embedder.embed_sparse([query])[0]

    filter_cond = None
    if source_type:
        filter_cond = qm.Filter(
            must=[
                qm.FieldCondition(
                    key="source_type",
                    match=qm.MatchValue(value=source_type),
                )
            ]
        )

    client = get_client()
    results = client.query_points(
        collection_name=config.QDRANT_COLLECTION,
        prefetch=[
            qm.Prefetch(
                query=dense_vec,
                using="dense",
                limit=candidates,
                filter=filter_cond,
            ),
            qm.Prefetch(
                query=qm.SparseVector(indices=sp_idx, values=sp_val),
                using="bm25",
                limit=candidates,
                filter=filter_cond,
            ),
        ],
        query=qm.FusionQuery(fusion=qm.Fusion.RRF),
        limit=candidates,
        with_payload=True,
    )

    hits: List[Dict[str, Any]] = []
    for point in results.points:
        item = dict(point.payload or {})
        item["_rrf_score"] = point.score
        item["_id"] = point.id
        hits.append(item)

    return _rerank_and_filter(query, hits, top_k)


def _rerank_and_filter(
    query: str,
    hits: List[Dict[str, Any]],
    top_k: int,
) -> List[Dict[str, Any]]:
    """Score hits with the cross-encoder, drop low-relevance ones, keep top_k."""
    if not hits:
        return []

    scores = embedder.rerank(query, [hit.get("text", "") for hit in hits])
    for hit, score in zip(hits, scores):
        hit["_score"] = score

    hits.sort(key=lambda h: h["_score"], reverse=True)
    kept = [h for h in hits if h["_score"] >= config.RAG_MIN_RERANK_SCORE]
    return kept[:top_k]
