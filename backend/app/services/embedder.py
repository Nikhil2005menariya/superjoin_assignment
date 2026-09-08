"""
Embedder service — fastembed ONNX, no torch.

Dense:  BAAI/bge-small-en-v1.5  (384-dim, ~130 MB) — semantic ANN retrieval
Sparse: Qdrant/bm25              (no RAM, computed on-the-fly) — keyword recall

bge-small is ~10× smaller than bge-large with competitive retrieval quality,
making it deployable on 1–2 GB instances.
ColBERT is excluded — its ONNX model has a fixed input-shape bug with fastembed.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_dense_model  = None
_sparse_model = None


def _load_models():
    global _dense_model, _sparse_model
    if _dense_model is not None:
        return

    from fastembed import TextEmbedding, SparseTextEmbedding

    cache = os.getenv("FASTEMBED_CACHE_PATH", "/tmp/fastembed_cache")
    os.makedirs(cache, exist_ok=True)

    logger.info("Loading dense model bge-small-en-v1.5 (~130 MB) …")
    _dense_model = TextEmbedding(
        model_name="BAAI/bge-small-en-v1.5",
        cache_dir=cache,
    )

    logger.info("Loading BM25 sparse model …")
    _sparse_model = SparseTextEmbedding(
        model_name="Qdrant/bm25",
        cache_dir=cache,
    )

    logger.info("Dense (384-dim) + BM25 models ready")


class EmbedResult:
    __slots__ = ("dense", "sparse_indices", "sparse_values")

    def __init__(
        self,
        dense: list[float],
        sparse_indices: list[int],
        sparse_values: list[float],
    ):
        self.dense          = dense
        self.sparse_indices = sparse_indices
        self.sparse_values  = sparse_values


def embed_texts(texts: list[str]) -> list[EmbedResult]:
    """Dense + BM25 batch embedding."""
    _load_models()

    dense_vecs  = list(_dense_model.embed(texts))
    sparse_vecs = list(_sparse_model.embed(texts))

    return [
        EmbedResult(
            dense=dv.tolist(),
            sparse_indices=sv.indices.tolist(),
            sparse_values=sv.values.tolist(),
        )
        for dv, sv in zip(dense_vecs, sparse_vecs)
    ]


def embed_query(query: str) -> dict:
    """Embed a search query for hybrid retrieval."""
    r = embed_texts([query])[0]
    return {
        "dense":          r.dense,
        "sparse_indices": r.sparse_indices,
        "sparse_values":  r.sparse_values,
    }


def embed_single(text: str, context: Optional[str] = None) -> dict:
    """Backwards-compatible single-text embed."""
    r = embed_texts([text])[0]
    return {
        "dense":  r.dense,
        "sparse": {"indices": r.sparse_indices, "values": r.sparse_values},
    }
