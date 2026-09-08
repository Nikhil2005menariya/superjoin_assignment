"""
SQL search agent — queries SQLite directly for structured fact lookups.

No LLM call. Extracts key terms from the question and runs parameterised
LIKE queries against the facts and chunks tables. Returns results in
milliseconds for numeric/entity lookups that would otherwise require
full vector retrieval + LLM synthesis.
"""

import logging
import re
from typing import Optional

import aiosqlite

from app.config import get_settings

logger   = logging.getLogger(__name__)
settings = get_settings()

_FACT_KEYS = [
    "id", "doc_id", "statement", "subject", "predicate",
    "value_raw", "unit_raw", "unit_canonical",
    "time_period_raw", "time_start", "time_end",
    "scope", "qualifier", "fact_type", "confidence",
    "evidence_verified", "exact_quote",
]

# Common time period aliases → normalised token
_TIME_ALIASES = {
    "fy24": "FY24", "fy 24": "FY24", "fy2024": "FY24",
    "fy23": "FY23", "fy 23": "FY23", "fy2023": "FY23",
    "fy22": "FY22", "fy2022": "FY22",
    "q4": "Q4", "q3": "Q3", "q2": "Q2", "q1": "Q1",
    "q4 fy24": "Q4 FY24", "q4 fy23": "Q4 FY23",
}

_STOP_WORDS = {
    "what", "was", "is", "are", "were", "the", "a", "an", "of", "in",
    "for", "and", "or", "to", "did", "does", "do", "by", "at", "from",
    "how", "much", "many", "tell", "me", "its", "their", "this", "that",
    "which", "show", "give", "find", "explain", "describe", "report",
    "document", "according", "based", "on", "about", "with", "than",
    "between", "compare", "versus", "vs", "total", "overall", "annual",
}


def _extract_terms(question: str) -> list[str]:
    """Pull meaningful content words + time refs from the question."""
    q_lower = question.lower()

    # Detect time periods first
    time_hits = []
    for alias, canonical in _TIME_ALIASES.items():
        if alias in q_lower:
            time_hits.append(canonical)

    # Tokenise and filter stop words
    tokens = re.findall(r"[a-zA-Z0-9']+", question)
    content = [
        t for t in tokens
        if len(t) > 2 and t.lower() not in _STOP_WORDS
    ]

    # Numbers as-is (e.g. "753", "487")
    numbers = re.findall(r"\d[\d,\.]*", question)

    return list(dict.fromkeys(content + numbers + time_hits))  # preserve order, dedup


def _build_fact_query(terms: list[str], doc_id: Optional[str]) -> tuple[str, list]:
    """Build a LIKE query that ORs across statement, subject, predicate."""
    if not terms:
        return "", []

    clauses, params = [], []
    for term in terms[:6]:  # cap at 6 terms to avoid exploding query
        like = f"%{term}%"
        clauses.append(
            "(statement LIKE ? OR subject LIKE ? OR predicate LIKE ? OR exact_quote LIKE ?)"
        )
        params.extend([like, like, like, like])

    where = "evidence_verified = 1 AND (" + " OR ".join(clauses) + ")"
    if doc_id:
        where = f"doc_id = ? AND " + where
        params = [doc_id] + params

    sql = f"SELECT {','.join(_FACT_KEYS)} FROM facts WHERE {where} ORDER BY confidence DESC LIMIT 15"
    return sql, params


def _build_chunk_query(terms: list[str], doc_id: Optional[str]) -> tuple[str, list]:
    """Search chunks table for relevant passages."""
    if not terms:
        return "", []

    clauses, params = [], []
    for term in terms[:4]:
        clauses.append("raw_text LIKE ?")
        params.append(f"%{term}%")

    where = "level IN ('paragraph','section','table_row') AND (" + " OR ".join(clauses) + ")"
    if doc_id:
        where = f"doc_id = ? AND " + where
        params = [doc_id] + params

    sql = f"SELECT id, doc_id, level, page_num, section_path, raw_text FROM chunks WHERE {where} LIMIT 8"
    return sql, params


async def sql_search(
    question: str,
    doc_id: Optional[str] = None,
) -> dict:
    """
    Run direct SQLite search. Returns:
      facts  — list of matching verified facts (with full metadata)
      chunks — list of matching passage snippets
    """
    terms = _extract_terms(question)
    logger.debug("SQL agent terms: %s", terms)

    fact_sql,  fact_params  = _build_fact_query(terms, doc_id)
    chunk_sql, chunk_params = _build_chunk_query(terms, doc_id)

    facts:  list[dict] = []
    chunks: list[dict] = []

    async with aiosqlite.connect(settings.db_path) as db:
        if fact_sql:
            async with db.execute(fact_sql, fact_params) as cur:
                rows = await cur.fetchall()
            facts = [dict(zip(_FACT_KEYS, r)) for r in rows]
            for f in facts:
                f["evidence_verified"] = bool(f["evidence_verified"])

        if chunk_sql:
            async with db.execute(chunk_sql, chunk_params) as cur:
                rows = await cur.fetchall()
            chunk_keys = ["id", "doc_id", "level", "page_num", "section_path", "raw_text"]
            chunks = [dict(zip(chunk_keys, r)) for r in rows]

    logger.info("SQL agent: %d facts, %d chunks for query '%s'", len(facts), len(chunks), question[:60])
    return {"facts": facts, "chunks": chunks, "terms": terms}
