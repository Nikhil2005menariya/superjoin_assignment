"""
Relationships API — cross-document page-level relationships.

Returns data from the page_relationships table, enriched with page summaries
and document filenames.
"""

import logging
from typing import Optional

import aiosqlite
from fastapi import APIRouter, Query

from app.config import get_settings

logger   = logging.getLogger(__name__)
settings = get_settings()
router   = APIRouter()

_PAGE_REL_KEYS = [
    "id", "page_a_id", "page_b_id", "doc_a_id", "doc_b_id",
    "type", "explanation", "confidence", "created_at",
]


async def _enrich(db, row: tuple) -> dict:
    rel = dict(zip(_PAGE_REL_KEYS, row))

    async def fetch_page(pid: str) -> Optional[dict]:
        if not pid:
            return None
        async with db.execute(
            "SELECT page_num, summary, md_path FROM page_summaries WHERE id=?", (pid,)
        ) as cur:
            r = await cur.fetchone()
        return {"page_num": r[0], "summary": r[1], "md_path": r[2]} if r else None

    async def fetch_filename(did: str) -> str:
        if not did:
            return ""
        async with db.execute("SELECT filename FROM documents WHERE id=?", (did,)) as cur:
            r = await cur.fetchone()
        return r[0] if r else did[:8]

    rel["page_a"] = await fetch_page(rel["page_a_id"])
    rel["page_b"] = await fetch_page(rel["page_b_id"])
    rel["doc_a_filename"] = await fetch_filename(rel["doc_a_id"])
    rel["doc_b_filename"] = await fetch_filename(rel["doc_b_id"])
    return rel


@router.get("/relationships")
async def list_relationships(
    doc_id:   Optional[str] = None,
    rel_type: Optional[str] = None,
    limit:    int = Query(50, le=200),
    offset:   int = 0,
):
    filters, params = [], []
    if doc_id:
        filters.append("(doc_a_id=? OR doc_b_id=?)")
        params += [doc_id, doc_id]
    if rel_type:
        filters.append("type=?")
        params.append(rel_type)

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    params += [limit, offset]

    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            f"SELECT {', '.join(_PAGE_REL_KEYS)} FROM page_relationships "
            f"{where} ORDER BY confidence DESC, created_at DESC LIMIT ? OFFSET ?",
            params,
        ) as cur:
            rows = await cur.fetchall()
        enriched = [await _enrich(db, r) for r in rows]

    return enriched


@router.get("/relationships/stats/summary")
async def relationships_summary():
    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            """SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN type='CORROBORATES' THEN 1 ELSE 0 END) AS corroborates,
                SUM(CASE WHEN type='CONTRADICTS'  THEN 1 ELSE 0 END) AS contradicts,
                SUM(CASE WHEN type='RECONCILES'   THEN 1 ELSE 0 END) AS reconciles,
                SUM(CASE WHEN type='RELATED'      THEN 1 ELSE 0 END) AS related,
                AVG(confidence) AS avg_confidence
               FROM page_relationships"""
        ) as cur:
            row = await cur.fetchone()
    keys = ["total", "corroborates", "contradicts", "reconciles", "related", "avg_confidence"]
    return dict(zip(keys, row))


@router.get("/documents/{doc_id}/relationships")
async def get_document_relationships(doc_id: str):
    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            f"SELECT {', '.join(_PAGE_REL_KEYS)} FROM page_relationships "
            "WHERE doc_a_id=? OR doc_b_id=? ORDER BY confidence DESC",
            (doc_id, doc_id),
        ) as cur:
            rows = await cur.fetchall()
        return [await _enrich(db, r) for r in rows]
