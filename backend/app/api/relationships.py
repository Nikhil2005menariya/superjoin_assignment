"""
Relationships API — cross-document fact comparison results.
"""

import logging
from typing import Optional

import aiosqlite
from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings

logger   = logging.getLogger(__name__)
settings = get_settings()
router   = APIRouter()

_REL_KEYS = [
    "id", "fact_a_id", "fact_b_id", "type",
    "explanation", "reconciliation_context", "confidence", "created_at",
]

_FACT_KEYS = [
    "id", "doc_id", "statement", "subject", "predicate",
    "value_raw", "unit_raw", "time_period_raw", "fact_type", "confidence",
]


async def _enrich_relationship(db, row: tuple) -> dict:
    """Attach lightweight fact summaries to a relationship row."""
    rel = dict(zip(_REL_KEYS, row))

    async def fetch_fact(fid: str) -> Optional[dict]:
        async with db.execute(
            f"SELECT {','.join(_FACT_KEYS)} FROM facts WHERE id = ?", (fid,)
        ) as cur:
            r = await cur.fetchone()
        return dict(zip(_FACT_KEYS, r)) if r else None

    rel["fact_a"] = await fetch_fact(rel["fact_a_id"])
    rel["fact_b"] = await fetch_fact(rel["fact_b_id"])
    return rel


# ─── List relationships ───────────────────────────────────────────────────────

@router.get("/relationships")
async def list_relationships(
    doc_id:   Optional[str] = None,
    rel_type: Optional[str] = None,
    limit:    int = Query(50, le=200),
    offset:   int = 0,
):
    """
    List cross-document relationships, optionally filtered by document or type.
    """
    async with aiosqlite.connect(settings.db_path) as db:
        if doc_id:
            # Join through facts table to filter by doc
            async with db.execute(
                f"""SELECT r.{', r.'.join(_REL_KEYS)}
                    FROM relationships r
                    JOIN facts fa ON fa.id = r.fact_a_id
                    JOIN facts fb ON fb.id = r.fact_b_id
                    WHERE (fa.doc_id = ? OR fb.doc_id = ?)
                      {f"AND r.type = ?" if rel_type else ""}
                    ORDER BY r.confidence DESC, r.created_at DESC
                    LIMIT ? OFFSET ?""",
                ([doc_id, doc_id] + ([rel_type] if rel_type else []) + [limit, offset]),
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute(
                f"""SELECT {', '.join(_REL_KEYS)} FROM relationships
                    {f"WHERE type = ?" if rel_type else ""}
                    ORDER BY confidence DESC, created_at DESC
                    LIMIT ? OFFSET ?""",
                (([rel_type] if rel_type else []) + [limit, offset]),
            ) as cur:
                rows = await cur.fetchall()

        enriched = [await _enrich_relationship(db, r) for r in rows]

    return enriched


# ─── Single relationship ──────────────────────────────────────────────────────

@router.get("/relationships/{rel_id}")
async def get_relationship(rel_id: str):
    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            f"SELECT {', '.join(_REL_KEYS)} FROM relationships WHERE id = ?", (rel_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Relationship not found")
        return await _enrich_relationship(db, row)


# ─── Relationships for a fact ─────────────────────────────────────────────────

@router.get("/facts/{fact_id}/relationships")
async def get_fact_relationships(fact_id: str):
    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            f"""SELECT {', '.join(_REL_KEYS)} FROM relationships
                WHERE fact_a_id = ? OR fact_b_id = ?
                ORDER BY confidence DESC""",
            (fact_id, fact_id),
        ) as cur:
            rows = await cur.fetchall()
        return [await _enrich_relationship(db, r) for r in rows]


# ─── Relationships for a document ────────────────────────────────────────────

@router.get("/documents/{doc_id}/relationships")
async def get_document_relationships(doc_id: str):
    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            f"""SELECT r.{', r.'.join(_REL_KEYS)}
                FROM relationships r
                JOIN facts fa ON fa.id = r.fact_a_id
                JOIN facts fb ON fb.id = r.fact_b_id
                WHERE fa.doc_id = ? OR fb.doc_id = ?
                ORDER BY r.confidence DESC""",
            (doc_id, doc_id),
        ) as cur:
            rows = await cur.fetchall()
        return [await _enrich_relationship(db, r) for r in rows]


# ─── Stats ────────────────────────────────────────────────────────────────────

@router.get("/relationships/stats/summary")
async def relationships_summary():
    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            """SELECT
                 COUNT(*) AS total,
                 SUM(CASE WHEN type='CORROBORATES' THEN 1 END) AS corroborates,
                 SUM(CASE WHEN type='CONTRADICTS'  THEN 1 END) AS contradicts,
                 SUM(CASE WHEN type='RECONCILES'   THEN 1 END) AS reconciles,
                 AVG(confidence) AS avg_confidence
               FROM relationships"""
        ) as cur:
            row = await cur.fetchone()

    keys = ["total", "corroborates", "contradicts", "reconciles", "avg_confidence"]
    return dict(zip(keys, row))
