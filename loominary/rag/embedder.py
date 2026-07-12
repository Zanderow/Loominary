"""BGE-M3 dense embedder + FastEmbed BM25 sparse encoder + BGE cross-encoder reranker.

All models are loaded once and cached. Designed to run fully offline once the
weights are baked into the image (or pre-cached on the host).
"""
from __future__ import annotations

from typing import Iterable, List, Tuple

from loominary import config


_dense_model = None
_sparse_model = None
_reranker = None


def _resolve_device() -> str:
    if config.EMBED_DEVICE != "auto":
        return config.EMBED_DEVICE
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def get_dense_model():
    global _dense_model
    if _dense_model is None:
        from FlagEmbedding import BGEM3FlagModel
        device = _resolve_device()
        _dense_model = BGEM3FlagModel(
            config.EMBED_MODEL_PATH,
            use_fp16=(device == "cuda"),
            device=device,
        )
    return _dense_model


def get_sparse_model():
    global _sparse_model
    if _sparse_model is None:
        from fastembed import SparseTextEmbedding
        _sparse_model = SparseTextEmbedding(model_name=config.SPARSE_MODEL_NAME)
    return _sparse_model


def embed_dense(texts: List[str]) -> List[List[float]]:
    model = get_dense_model()
    out = model.encode(
        texts,
        batch_size=8,
        max_length=config.RAG_CHUNK_TOKENS + 64,
        return_dense=True,
        return_sparse=False,
        return_colbert_vecs=False,
    )
    return [v.tolist() for v in out["dense_vecs"]]


def get_reranker():
    global _reranker
    if _reranker is None:
        from FlagEmbedding import FlagReranker
        device = _resolve_device()
        _reranker = FlagReranker(
            config.RERANK_MODEL_PATH,
            use_fp16=(device == "cuda"),
            devices=device,
            normalize=True,  # sigmoid -> scores in [0, 1], comparable across queries
        )
    return _reranker


def rerank(query: str, texts: List[str]) -> List[float]:
    """Score each text's relevance to the query with the cross-encoder.

    Returns one score per text, in [0, 1] (higher = more relevant).
    """
    if not texts:
        return []
    model = get_reranker()
    scores = model.compute_score([[query, t] for t in texts])
    if isinstance(scores, float):  # single pair returns a bare float
        scores = [scores]
    return [float(s) for s in scores]


def embed_sparse(texts: List[str]) -> List[Tuple[List[int], List[float]]]:
    """Returns (indices, values) pairs ready for Qdrant SparseVector."""
    model = get_sparse_model()
    out = []
    for emb in model.embed(texts):
        out.append((emb.indices.tolist(), emb.values.tolist()))
    return out


DENSE_DIM = 1024  # BGE-M3 dense embedding dimension
