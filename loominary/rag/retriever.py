"""Hybrid search: BGE-M3 dense + BM25 sparse, fused with RRF in a single Qdrant
Query API call.

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
    """Run hybrid dense + sparse search, fused with RRF.

    Returns a list of dicts (payload + score) ordered best-first.
    """
    top_k = top_k or config.RAG_TOP_K
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
                limit=top_k * 2,
                filter=filter_cond,
            ),
            qm.Prefetch(
                query=qm.SparseVector(indices=sp_idx, values=sp_val),
                using="bm25",
                limit=top_k * 2,
                filter=filter_cond,
            ),
        ],
        query=qm.FusionQuery(fusion=qm.Fusion.RRF),
        limit=top_k,
        with_payload=True,
    )

    hits: List[Dict[str, Any]] = []
    for point in results.points:
        item = dict(point.payload or {})
        item["_score"] = point.score
        item["_id"] = point.id
        hits.append(item)
    return hits
