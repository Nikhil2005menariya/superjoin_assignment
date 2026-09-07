import json
import logging
from typing import Optional

import aiosqlite
from fastapi import APIRouter, HTTPException, Query
from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.config import get_settings
from app.database.qdrant_client import get_qdrant, COLLECTION_NAME
from app.services.embedder import embed_single

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
    Hybrid dense search via Qdrant.
    Embeds the query with bge-large and retrieves the top-k most similar facts.
    Phase 3 will add ColBERT reranking on top.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    emb = await loop.run_in_executor(None, embed_single, q)
    dense_vec = emb["dense"]

    qdrant_filter = None
    if doc_id:
        qdrant_filter = Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
        )

    qdrant = get_qdrant()
    results = await qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=("dense", dense_vec),
        query_filter=qdrant_filter,
        limit=limit,
        with_payload=True,
    )

    hits = []
    for r in results:
        hits.append({
            "fact_id":    r.payload.get("fact_id"),
            "score":      round(r.score, 4),
            "statement":  r.payload.get("statement"),
            "subject":    r.payload.get("subject"),
            "doc_id":     r.payload.get("doc_id"),
            "confidence": r.payload.get("confidence"),
        })
    return hits


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
