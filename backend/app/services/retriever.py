"""
Three-stage hybrid retrieval pipeline.

Stage 1 — Prefetch candidates (recall):
  1a. BM25 sparse search  → top-100 keyword matches
  1b. bge-large dense ANN → top-100 semantic matches
      Union of both = up to 200 unique candidates

Stage 2 — ColBERT MaxSim rerank (precision):
  Qdrant native multi-vector MAX_SIM scores each candidate.
  Returns final top-k, ranked by ColBERT relevance.

Fallback: if ColBERT returns nothing (e.g. no points indexed yet with colbert
vectors), automatically falls back to dense-only results.
"""

import asyncio
import logging
from typing import Optional

from qdrant_client.models import Filter, FieldCondition, MatchValue, Prefetch, SparseVector

from app.database.qdrant_client import get_qdrant, COLLECTION_NAME
from app.services.embedder import embed_query  # module-level so tests can patch it

logger = logging.getLogger(__name__)

# Candidate pool sizes per stage
SPARSE_CANDIDATES = 100
DENSE_CANDIDATES  = 100
FINAL_LIMIT       = 20


async def hybrid_search(
    query: str,
    doc_id: Optional[str] = None,
    limit: int = FINAL_LIMIT,
) -> list[dict]:
    """
    Run the three-stage hybrid retrieval pipeline for a text query.

    Returns a list of hit dicts: {fact_id, score, statement, subject, doc_id, confidence}.
    """
    loop = asyncio.get_event_loop()

    # Embed in thread pool — ONNX is CPU-bound
    query_emb = await loop.run_in_executor(None, embed_query, query)

    qdrant_filter = None
    if doc_id:
        qdrant_filter = Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
        )

    qdrant = get_qdrant()

    # ── Stage 1+2: prefetch with BM25 + dense, rerank with ColBERT ─────────
    try:
        results = await qdrant.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                Prefetch(
                    query=SparseVector(
                        indices=query_emb["sparse_indices"],
                        values=query_emb["sparse_values"],
                    ),
                    using="bm25",
                    limit=SPARSE_CANDIDATES,
                    filter=qdrant_filter,
                ),
                Prefetch(
                    query=query_emb["dense"],
                    using="dense",
                    limit=DENSE_CANDIDATES,
                    filter=qdrant_filter,
                ),
            ],
            query=query_emb["colbert"],   # list of 128-dim token vectors → MaxSim
            using="colbert",
            with_payload=True,
            limit=limit,
            query_filter=qdrant_filter,
        )

        hits = _format_hits(results.points)

        if hits:
            logger.info(
                "ColBERT hybrid search: %d results (top score %.4f)",
                len(hits), hits[0]["score"],
            )
            return hits

        logger.info("ColBERT returned no results — falling back to dense search")

    except Exception as e:
        logger.warning("ColBERT hybrid search failed (%s) — falling back to dense", e)

    # ── Fallback: dense-only search ─────────────────────────────────────────
    results = await qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=("dense", query_emb["dense"]),
        query_filter=qdrant_filter,
        limit=limit,
        with_payload=True,
    )
    hits = _format_hits(results)
    logger.info("Dense fallback: %d results", len(hits))
    return hits


def _format_hits(points) -> list[dict]:
    return [
        {
            "fact_id":    p.payload.get("fact_id"),
            "score":      round(p.score, 4),
            "statement":  p.payload.get("statement"),
            "subject":    p.payload.get("subject"),
            "doc_id":     p.payload.get("doc_id"),
            "confidence": p.payload.get("confidence"),
            "retrieval":  "colbert_hybrid",
        }
        for p in points
    ]
