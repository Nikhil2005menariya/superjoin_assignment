"""
Natural-language query engine — grounded in the verified fact knowledge layer.

Flow:
  1. Hybrid retrieval (BM25 + dense + ColBERT rerank) → top-K candidate facts
  2. Load full fact rows from SQLite (with evidence quotes)
  3. Build a Groq prompt: answer STRICTLY from the retrieved verified facts
  4. Return structured response: answer + source_facts + confidence + caveat

The system never answers from Groq's parametric knowledge — only from facts
that have been extracted, evidence-verified, and indexed from uploaded documents.
This makes every answer fully traceable to source text.
"""

import asyncio
import json
import logging
from typing import Optional

import aiosqlite
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import get_settings
from app.services.retriever import hybrid_search
from app.services.llm_client import get_llm

logger   = logging.getLogger(__name__)
settings = get_settings()

MAX_FACTS   = 12   # facts sent to Groq in context

SYSTEM_PROMPT = """You are a precise, grounded answer engine for a Fact Knowledge Layer.

Rules you MUST follow:
1. Answer ONLY using the verified facts provided below. Do not use external knowledge.
2. If the facts do not contain enough information to fully answer the question, say so clearly.
3. Be concise. 2–4 sentences unless the question demands more detail.
4. Where relevant, mention the source period, entity, or scope of the fact.
5. If facts from different documents disagree, explicitly note the discrepancy.
6. Never invent numbers, dates, or claims not present in the facts.

At the end of your answer, on a new line starting with "CONFIDENCE:", rate your confidence
in the answer as HIGH, MEDIUM, or LOW based on how well the retrieved facts answer the question."""

_FACT_DETAIL_KEYS = [
    "id", "doc_id", "statement", "subject", "predicate",
    "value_raw", "unit_raw", "unit_canonical",
    "time_period_raw", "time_start", "time_end", "scope",
    "qualifier", "fact_type", "confidence",
    "evidence_verified", "exact_quote",
]


async def _load_facts_by_ids(fact_ids: list[str]) -> list[dict]:
    if not fact_ids:
        return []
    placeholders = ",".join("?" * len(fact_ids))
    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            f"SELECT {','.join(_FACT_DETAIL_KEYS)} FROM facts "
            f"WHERE id IN ({placeholders}) AND evidence_verified = 1 "
            f"ORDER BY confidence DESC",
            fact_ids,
        ) as cur:
            rows = await cur.fetchall()
    return [dict(zip(_FACT_DETAIL_KEYS, r)) for r in rows]


def _build_facts_context(facts: list[dict]) -> str:
    lines = []
    for i, f in enumerate(facts, 1):
        parts = [f"[{i}] {f['statement']}"]
        if f.get("exact_quote"):
            parts.append(f'    Source quote: "{f["exact_quote"]}"')
        meta = []
        if f.get("time_period_raw"):
            meta.append(f"period: {f['time_period_raw']}")
        if f.get("scope"):
            meta.append(f"scope: {f['scope']}")
        if meta:
            parts.append(f"    ({', '.join(meta)})")
        lines.append("\n".join(parts))
    return "\n\n".join(lines)


async def answer_query(
    question: str,
    doc_id: Optional[str] = None,
    limit: int = MAX_FACTS,
) -> dict:
    """
    Answer a natural-language question using only retrieved, verified facts.
    Returns:
      answer         — synthesized text response
      source_facts   — list of fact dicts used to ground the answer
      confidence     — HIGH | MEDIUM | LOW (Groq self-assessment)
      retrieval_meta — info about how many candidates were found
      caveat         — if facts are insufficient, a note about coverage gaps
    """
    # ── Stage 1: hybrid retrieval ─────────────────────────────────────────────
    hits = await hybrid_search(query=question, doc_id=doc_id, limit=limit)
    fact_ids = [h["fact_id"] for h in hits if h.get("fact_id")]

    # ── Stage 2: load full facts from SQLite ──────────────────────────────────
    source_facts = await _load_facts_by_ids(fact_ids)

    if not source_facts:
        return {
            "answer":         "No verified facts were found for this query in the uploaded documents.",
            "source_facts":   [],
            "confidence":     "LOW",
            "retrieval_meta": {"hits": 0, "method": hits[0].get("retrieval") if hits else "none"},
            "caveat":         "Upload and process relevant documents first.",
        }

    # ── Stage 3: Groq synthesis ───────────────────────────────────────────────
    facts_context = _build_facts_context(source_facts)
    user_msg      = (
        f"Verified facts from the knowledge base ({len(source_facts)} facts):\n\n"
        f"{facts_context}\n\n"
        f"Question: {question}"
    )

    llm = get_llm()

    try:
        resp   = await llm.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ])
        raw    = resp.content.strip()

        # Extract confidence tag
        confidence = "MEDIUM"
        answer     = raw
        for line in raw.splitlines():
            if line.upper().startswith("CONFIDENCE:"):
                tag = line.split(":", 1)[1].strip().upper()
                if tag in ("HIGH", "MEDIUM", "LOW"):
                    confidence = tag
                answer = raw[: raw.rfind(line)].strip()
                break

    except Exception as e:
        logger.error("Groq synthesis failed: %s", e)
        return {
            "answer":       "Synthesis failed — the retrieved facts are listed below.",
            "source_facts": source_facts,
            "confidence":   "LOW",
            "retrieval_meta": {"hits": len(hits), "method": hits[0].get("retrieval") if hits else "none"},
            "caveat":       str(e),
        }

    return {
        "answer":         answer,
        "source_facts":   source_facts,
        "confidence":     confidence,
        "retrieval_meta": {
            "hits":   len(hits),
            "used":   len(source_facts),
            "method": hits[0].get("retrieval") if hits else "none",
        },
        "caveat": None,
    }
