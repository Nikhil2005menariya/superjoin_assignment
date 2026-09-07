"""
Embedder service — fastembed-based, ONNX runtime (no heavy torch).
Provides:
  - dense  : BAAI/bge-large-en-v1.5  (1024-dim) for ANN retrieval
  - sparse : Qdrant/bm25             for keyword recall
Both models download automatically on first use into FASTEMBED_CACHE_PATH.
Singleton: loaded once per process to avoid repeated ONNX session creation.
"""

import logging
import os
from typing import Optional

import numpy as np

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

    logger.info("Loading dense embedding model bge-large-en-v1.5 …")
    _dense_model = TextEmbedding(
        model_name="BAAI/bge-large-en-v1.5",
        cache_dir=cache,
    )

    logger.info("Loading sparse BM25 model …")
    _sparse_model = SparseTextEmbedding(
        model_name="Qdrant/bm25",
        cache_dir=cache,
    )
    logger.info("Embedding models ready")


class EmbedResult:
    __slots__ = ("dense", "sparse_indices", "sparse_values")

    def __init__(
        self,
        dense: list[float],
        sparse_indices: list[int],
        sparse_values: list[float],
    ):
        self.dense         = dense
        self.sparse_indices = sparse_indices
        self.sparse_values  = sparse_values


def embed_texts(texts: list[str]) -> list[EmbedResult]:
    """
    Batch-embed a list of texts.
    Returns one EmbedResult per text.
    """
    _load_models()

    # Dense: bge-large
    dense_vecs = list(_dense_model.embed(texts))

    # Sparse: BM25
    sparse_vecs = list(_sparse_model.embed(texts))

    results = []
    for dv, sv in zip(dense_vecs, sparse_vecs):
        results.append(
            EmbedResult(
                dense=dv.tolist(),
                sparse_indices=sv.indices.tolist(),
                sparse_values=sv.values.tolist(),
            )
        )
    return results


def embed_single(text: str, context: Optional[str] = None) -> dict:
    """
    Embed one fact statement + optional surrounding context.
    Returns a dict ready for Qdrant upsert vectors.
    """
    texts = [text, context or text]
    results = embed_texts(texts)

    fact_emb    = results[0]
    context_emb = results[1]

    return {
        "dense":   fact_emb.dense,
        "context": context_emb.dense,
        "sparse":  {
            "indices": fact_emb.sparse_indices,
            "values":  fact_emb.sparse_values,
        },
    }
