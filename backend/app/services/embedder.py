"""
Embedder service — fastembed-based, ONNX runtime (no heavy torch).

Provides three embedding types, all loaded lazily as singletons:
  dense    : BAAI/bge-large-en-v1.5  (1024-dim) — semantic ANN retrieval
  sparse   : Qdrant/bm25             — keyword recall
  colbert  : colbert-ir/colbertv2.0  (128-dim per token) — MaxSim late interaction
"""

import logging
import os
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

_dense_model   = None
_sparse_model  = None
_colbert_model = None


def _load_dense_sparse():
    global _dense_model, _sparse_model
    if _dense_model is not None:
        return

    from fastembed import TextEmbedding, SparseTextEmbedding

    cache = os.getenv("FASTEMBED_CACHE_PATH", "/tmp/fastembed_cache")
    os.makedirs(cache, exist_ok=True)

    logger.info("Loading dense model bge-large-en-v1.5 …")
    _dense_model = TextEmbedding(model_name="BAAI/bge-large-en-v1.5", cache_dir=cache)

    logger.info("Loading sparse BM25 model …")
    _sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25", cache_dir=cache)

    logger.info("Dense + sparse models ready")


def _load_colbert():
    global _colbert_model
    if _colbert_model is not None:
        return

    from fastembed import LateInteractionTextEmbedding

    cache = os.getenv("FASTEMBED_CACHE_PATH", "/tmp/fastembed_cache")
    os.makedirs(cache, exist_ok=True)

    logger.info("Loading ColBERT model colbert-ir/colbertv2.0 …")
    _colbert_model = LateInteractionTextEmbedding(
        model_name="colbert-ir/colbertv2.0",
        cache_dir=cache,
    )
    logger.info("ColBERT model ready")


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
    """
    Dense + sparse batch embedding.
    Used during fact indexing (without ColBERT — that's called separately).
    """
    _load_dense_sparse()

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


def embed_colbert(texts: list[str]) -> list[list[list[float]]]:
    """
    ColBERT late-interaction embedding.

    Returns a list of token matrices — one per input text.
    Each token matrix is a list of 128-dim vectors (one per token).
    Format is directly usable as a Qdrant multi-vector point.
    """
    _load_colbert()
    token_mats = list(_colbert_model.embed(texts))
    return [mat.tolist() for mat in token_mats]


def embed_query(text: str) -> dict:
    """
    Embed a search query with all three methods.
    Returns a dict ready for the hybrid retrieval pipeline.
    """
    dense_sparse = embed_texts([text])[0]
    colbert_mats = embed_colbert([text])

    return {
        "dense":          dense_sparse.dense,
        "sparse_indices": dense_sparse.sparse_indices,
        "sparse_values":  dense_sparse.sparse_values,
        "colbert":        colbert_mats[0],   # list of 128-dim token vectors
    }


def embed_single(text: str, context: Optional[str] = None) -> dict:
    """
    Backwards-compatible: embed one text for context-aware upsert.
    """
    texts   = [text, context or text]
    results = embed_texts(texts)

    return {
        "dense":   results[0].dense,
        "context": results[1].dense,
        "sparse":  {
            "indices": results[0].sparse_indices,
            "values":  results[0].sparse_values,
        },
    }
