"""
Hybrid retrieval — BM25 + dense RRF fusion (bge-small-en-v1.5, 384-dim).

chunk_search  : BM25 + dense prefetch → RRF fusion on doc_chunks
hybrid_search : dense ANN on legacy facts collection
"""

import asyncio
import logging
from typing import Optional

from qdrant_client.models import (
    Filter, FieldCondition, MatchValue,
    Prefetch, SparseVector, Fusion, FusionQuery,
)

from app.database.qdrant_client import get_qdrant, COLLECTION_NAME, CHUNK_COLLECTION
from app.services.embedder import embed_texts

logger = logging.getLogger(__name__)

FINAL_LIMIT = 20


async def hybrid_search(
    query: str,
    doc_id: Optional[str] = None,
    limit: int = FINAL_LIMIT,
) -> list[dict]:
    """Dense ANN on the facts collection."""
    loop = asyncio.get_event_loop()
    results_list = await loop.run_in_executor(None, embed_texts, [query])
    dr = results_list[0]

    qdrant_filter = None
    if doc_id:
        qdrant_filter = Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
        )

    qdrant  = get_qdrant()
    results = await qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=("dense", dr.dense),
        query_filter=qdrant_filter,
        limit=limit,
        with_payload=True,
    )
    hits = [
        {
            "fact_id":    p.payload.get("fact_id"),
            "score":      round(p.score, 4),
            "statement":  p.payload.get("statement"),
            "subject":    p.payload.get("subject"),
            "doc_id":     p.payload.get("doc_id"),
            "confidence": p.payload.get("confidence"),
            "retrieval":  "dense",
        }
        for p in results
    ]
    logger.info("Dense search (facts): %d results", len(hits))
    return hits


async def chunk_search(
    query: str,
    doc_id: Optional[str] = None,
    limit: int = 6,
) -> list[dict]:
    """BM25 + dense hybrid search on doc_chunks with RRF fusion."""
    loop = asyncio.get_event_loop()
    results_list = await loop.run_in_executor(None, embed_texts, [query])
    dr = results_list[0]

    qdrant_filter = None
    if doc_id:
        qdrant_filter = Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
        )

    qdrant = get_qdrant()
    try:
        results = await qdrant.query_points(
            collection_name=CHUNK_COLLECTION,
            prefetch=[
                Prefetch(
                    query=SparseVector(indices=dr.sparse_indices, values=dr.sparse_values),
                    using="bm25",
                    limit=60,
                    filter=qdrant_filter,
                ),
                Prefetch(
                    query=dr.dense,
                    using="dense",
                    limit=60,
                    filter=qdrant_filter,
                ),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            with_payload=True,
            limit=limit,
            query_filter=qdrant_filter,
        )
        hits = results.points
        logger.info("BM25+dense RRF (chunks): %d results", len(hits))
    except Exception as exc:
        logger.warning("RRF search failed (%s) — dense fallback", exc)
        results = await qdrant.search(
            collection_name=CHUNK_COLLECTION,
            query_vector=("dense", dr.dense),
            query_filter=qdrant_filter,
            limit=limit,
            with_payload=True,
        )
        hits = results

    return [
        {
            "chunk_id":     p.payload.get("chunk_id"),
            "score":        round(p.score, 4),
            "text":         p.payload.get("text", ""),
            "level":        p.payload.get("level"),
            "page_num":     p.payload.get("page_num"),
            "section_path": p.payload.get("section_path"),
            "doc_id":       p.payload.get("doc_id"),
            "source_type":  p.payload.get("source_type"),
            "md_path":      p.payload.get("md_path"),
        }
        for p in hits
    ]
