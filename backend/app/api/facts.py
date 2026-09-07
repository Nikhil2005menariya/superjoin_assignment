import json
import logging
import uuid
from typing import Optional

import aiosqlite
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from qdrant_client.models import Filter, FieldCondition, MatchValue, SparseVector, PointStruct

from app.config import get_settings
from app.database.qdrant_client import get_qdrant, COLLECTION_NAME
from app.services.embedder import embed_single
from app.services.retriever import hybrid_search

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()

_FACT_KEYS = [
    "id", "doc_id", "chunk_id", "statement", "subject", "predicate", "metric",
    "value_raw", "value_normalized", "unit_raw", "unit_canonical",
    "time_period_raw", "time_start", "time_end", "scope", "qualifier",
    "fact_type", "confidence", "evidence_verified", "exact_quote",
    "quote_start", "quote_end", "qdrant_point_id", "attributes", "created_at",
]


def _row_to_fact(row) -> dict:
    d = dict(zip(_FACT_KEYS, row))
    d["evidence_verified"] = bool(d["evidence_verified"])
    try:
        d["attributes"] = json.loads(d["attributes"] or "{}")
    except Exception:
        d["attributes"] = {}
    return d


# ─── List / filter facts ──────────────────────────────────────────────────────

@router.get("/facts")
async def list_facts(
    doc_id:   Optional[str] = None,
    subject:  Optional[str] = None,
    verified: Optional[bool] = None,
    fact_type: Optional[str] = None,
    limit:    int = Query(100, le=500),
    offset:   int = 0,
):
    conds, params = [], []
    if doc_id:
        conds.append("doc_id = ?"); params.append(doc_id)
    if subject:
        conds.append("subject LIKE ?"); params.append(f"%{subject}%")
    if verified is not None:
        conds.append("evidence_verified = ?"); params.append(int(verified))
    if fact_type:
        conds.append("fact_type = ?"); params.append(fact_type)

    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    params += [limit, offset]

    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            f"SELECT {','.join(_FACT_KEYS)} FROM facts {where} "
            f"ORDER BY confidence DESC LIMIT ? OFFSET ?",
            params,
        ) as cur:
            rows = await cur.fetchall()

    return [_row_to_fact(r) for r in rows]


# ─── Single fact ──────────────────────────────────────────────────────────────

@router.get("/facts/{fact_id}")
async def get_fact(fact_id: str):
    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            f"SELECT {','.join(_FACT_KEYS)} FROM facts WHERE id = ?", (fact_id,)
        ) as cur:
            row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Fact not found")
    return _row_to_fact(row)


# ─── Facts for a document ─────────────────────────────────────────────────────

@router.get("/documents/{doc_id}/facts")
async def get_document_facts(doc_id: str, verified_only: bool = False):
    cond = "doc_id = ?"
    params = [doc_id]
    if verified_only:
        cond += " AND evidence_verified = 1"

    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            f"SELECT {','.join(_FACT_KEYS)} FROM facts WHERE {cond} "
            f"ORDER BY confidence DESC",
            params,
        ) as cur:
            rows = await cur.fetchall()
    return [_row_to_fact(r) for r in rows]


# ─── Semantic search ──────────────────────────────────────────────────────────

@router.get("/facts/search/semantic")
async def search_facts(
    q:      str = Query(..., min_length=3),
    doc_id: Optional[str] = None,
    limit:  int = Query(20, le=100),
):
    """
    Three-stage hybrid retrieval: BM25 recall → dense ANN → ColBERT MaxSim rerank.
    Returns facts ranked by ColBERT late-interaction similarity.
    Falls back to dense-only if ColBERT vectors not yet available.
    """
    return await hybrid_search(query=q, doc_id=doc_id, limit=limit)


# ─── Reindex endpoint (backfill ColBERT for Phase-2 facts) ───────────────────

@router.post("/admin/reindex-colbert")
async def reindex_colbert(background_tasks: BackgroundTasks):
    """
    Backfill ColBERT vectors for all facts already indexed in Qdrant
    without colbert vectors (i.e. facts indexed in Phase 2).
    Runs in background — returns immediately.
    """
    background_tasks.add_task(_run_colbert_backfill)
    return {"status": "reindex started"}


async def _run_colbert_backfill():
    """Re-embed all Qdrant points that are missing the colbert vector."""
    import asyncio

    logger.info("ColBERT backfill: starting")
    qdrant = get_qdrant()

    # Scroll through all points
    offset = None
    total_updated = 0

    while True:
        result = await qdrant.scroll(
            collection_name=COLLECTION_NAME,
            with_payload=True,
            with_vectors=["colbert"],
            limit=50,
            offset=offset,
        )
        points, next_offset = result

        if not points:
            break

        # Only process points without colbert
        missing = [p for p in points if not p.vector or not p.vector.get("colbert")]

        if missing:
            statements = [p.payload.get("statement", "") for p in missing]
            ids = [p.id for p in missing]

            try:
                loop = asyncio.get_event_loop()
                from app.services.embedder import embed_colbert
                colbert_mats = await loop.run_in_executor(None, embed_colbert, statements)

                for point_id, colbert_vecs in zip(ids, colbert_mats):
                    await qdrant.update_vectors(
                        collection_name=COLLECTION_NAME,
                        points=[
                            {"id": point_id, "vector": {"colbert": colbert_vecs}}
                        ],
                    )
                total_updated += len(missing)
                logger.info("ColBERT backfill: updated %d points (total %d)", len(missing), total_updated)
            except Exception as e:
                logger.error("ColBERT backfill error: %s", e)

        if next_offset is None:
            break
        offset = next_offset

    logger.info("ColBERT backfill complete: %d facts updated", total_updated)


# ─── Stats ────────────────────────────────────────────────────────────────────

@router.get("/facts/stats/summary")
async def facts_summary():
    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            """SELECT
                 COUNT(*)                                          AS total,
                 SUM(evidence_verified)                           AS verified,
                 COUNT(DISTINCT doc_id)                           AS documents,
                 COUNT(DISTINCT subject)                          AS subjects,
                 AVG(confidence)                                  AS avg_confidence,
                 SUM(CASE WHEN fact_type='numerical'  THEN 1 END) AS numerical,
                 SUM(CASE WHEN fact_type='semantic'   THEN 1 END) AS semantic,
                 SUM(CASE WHEN fact_type='relational' THEN 1 END) AS relational
               FROM facts"""
        ) as cur:
            row = await cur.fetchone()

    keys = ["total", "verified", "documents", "subjects", "avg_confidence",
            "numerical", "semantic", "relational"]
    return dict(zip(keys, row))
