"""
Page-augmented query engine.

Retrieval flow:
  1. Parallel: SQL keyword search on chunks + Qdrant hybrid chunk search
  2. Collect top-k matched chunk passages (exact text that hit the query)
  3. For each unique (doc_id, page_num) in the hits → look up md_path from page_summaries
  4. Read page MD files → structured knowledge: Summary, Key Metrics, Key Facts, Visual Content
  5. Single Amazon Nova 2 Lite synthesis using BOTH matched passages + full page knowledge

This gives the LLM:
  - Precision: the exact chunk text that semantically matched the query
  - Breadth:   the full structured knowledge of every page that was hit (metrics tables,
               visual data from charts, entity lists, cross-doc relationships)
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

import aiosqlite
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import get_settings
from app.services.retriever import chunk_search
from app.services.sql_agent import sql_search
from app.services.llm_client import get_llm

logger   = logging.getLogger(__name__)
settings = get_settings()

MAX_CHUNK_HITS  = 8   # top-k semantic chunks
MAX_MD_PAGES    = 6   # max page MD files to read (expanded from chunk hits)
MAX_MD_CHARS    = 2500  # cap per MD file to stay within token budget

_SYSTEM = """You are a precise, grounded answer engine for a document Fact Knowledge Layer.

You receive two tiers of evidence for every question:

[A] MATCHED PASSAGES — exact text excerpts from the document that semantically matched the query.
    These are the most directly relevant pieces of text to your answer.

[B] PAGE KNOWLEDGE FILES — structured knowledge extracted from the pages containing those passages.
    Each file has: Summary, Key Metrics (table of all numbers on the page), Key Facts,
    Visual Content (charts/graphs), and Entity Mentions.
    Use these for precise figures, chart data, and comprehensive context.

Rules:
1. Answer ONLY from the provided evidence. Never use external knowledge.
2. For specific numeric claims, prefer values from the Key Metrics tables in [B] — they are
   extracted from both text AND visual content (charts, infographics).
3. If the same metric appears across multiple pages with different values, flag the discrepancy
   and note whether it is explained by different time periods, scopes, or units.
4. For trend/causal questions, use the Summary and Key Facts sections in [B].
5. For chart/graph data questions, use the Visual Content sections in [B].
6. If evidence conflicts across documents, state both values with their sources.
7. If the answer is not in any evidence, say so clearly — never guess.
8. Cite sources: "(Page N, doc:XXXXXXXX)"

End your answer with: CONFIDENCE: HIGH | MEDIUM | LOW"""


def _read_md(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception:
        return ""


async def _get_md_paths_for_pages(page_keys: list[tuple[str, int]]) -> dict[tuple[str, int], str]:
    """Look up md_path from page_summaries for a list of (doc_id, page_num) tuples."""
    if not page_keys:
        return {}
    async with aiosqlite.connect(settings.db_path) as db:
        result = {}
        for doc_id, page_num in page_keys:
            async with db.execute(
                "SELECT md_path FROM page_summaries WHERE doc_id=? AND page_num=?",
                (doc_id, page_num),
            ) as cur:
                row = await cur.fetchone()
            if row and row[0]:
                result[(doc_id, page_num)] = row[0]
        return result


def _dedup_chunks(chunks: list[dict]) -> list[dict]:
    seen, out = set(), []
    for c in chunks:
        key = (c.get("text") or "")[:100].strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(c)
    return out


def _build_context(chunk_hits: list[dict], md_contents: list[tuple[str, int, str]]) -> str:
    parts = []

    if chunk_hits:
        parts.append("=== [A] MATCHED PASSAGES ===")
        for i, c in enumerate(chunk_hits, 1):
            doc_tag = f"doc:{str(c.get('doc_id',''))[:8]}"
            loc = f"Page {c.get('page_num','?')} ({doc_tag})"
            if c.get("section_path"):
                loc += f" — {c['section_path'][:50]}"
            if "vision" in str(c.get("source_type", "")):
                loc += " [VISUAL]"
            parts.append(f"[A{i}] {loc}\n{str(c.get('text',''))[:500]}")

    if md_contents:
        parts.append("\n=== [B] PAGE KNOWLEDGE FILES ===")
        for doc_id, page_num, content in md_contents:
            doc_tag = f"doc:{doc_id[:8]}"
            parts.append(f"--- Page {page_num} ({doc_tag}) ---\n{content[:MAX_MD_CHARS]}")

    return "\n\n".join(parts)


async def answer_query(
    question: str,
    doc_id: Optional[str] = None,
    limit: int = MAX_CHUNK_HITS,
) -> dict:
    # ── Step 1: parallel retrieval ────────────────────────────────────────────
    sql_result, chunk_hits = await asyncio.gather(
        sql_search(question, doc_id),
        chunk_search(query=question, doc_id=doc_id, limit=limit),
    )

    # Merge and dedup chunk hits
    sql_chunk_hits = [
        {"text": c["raw_text"], "page_num": c.get("page_num"),
         "section_path": c.get("section_path"), "doc_id": c.get("doc_id"),
         "source_type": "sql", "level": c.get("level")}
        for c in sql_result.get("chunks", [])
    ]
    all_chunks = _dedup_chunks(chunk_hits + sql_chunk_hits)[:MAX_CHUNK_HITS]

    # ── Step 2: collect MD paths — from chunk payload first, SQLite as fallback ─
    direct_md_paths: dict[tuple[str, int], str] = {}
    seen_pages_no_md: list[tuple[str, int]] = []

    for c in all_chunks:
        d = c.get("doc_id") or doc_id or ""
        p = c.get("page_num") or 0
        if not (d and p):
            continue
        mp = c.get("md_path")
        if mp:
            direct_md_paths[(d, p)] = mp
        else:
            seen_pages_no_md.append((d, p))

    # SQLite fallback for chunks that don't have md_path in payload yet
    fallback = await _get_md_paths_for_pages(seen_pages_no_md[:MAX_MD_PAGES])

    md_path_map = {**direct_md_paths, **fallback}

    # ── Step 4: read MD files ─────────────────────────────────────────────────
    md_contents: list[tuple[str, int, str]] = []
    for (d, p), mp in md_path_map.items():
        content = _read_md(mp)
        if content:
            md_contents.append((d, p, content))
    md_contents.sort(key=lambda x: x[1])  # sort by page number

    # ── No evidence at all ────────────────────────────────────────────────────
    if not all_chunks and not md_contents:
        return {
            "answer": "No relevant content found for this query. Upload and process documents first.",
            "source_facts": [],
            "confidence": "LOW",
            "retrieval_meta": {
                "hits": 0, "md_files": 0, "chunks": 0, "method": "page_augmented"
            },
            "caveat": "No documents have been processed yet.",
        }

    # ── Step 5: build context + single LLM call ───────────────────────────────
    context = _build_context(all_chunks, md_contents)
    user_msg = f"Evidence from the knowledge base:\n\n{context}\n\nQuestion: {question}"

    llm = get_llm()
    try:
        resp = await llm.ainvoke([
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=user_msg),
        ])
        raw = resp.content.strip()
    except Exception as exc:
        logger.error("LLM synthesis failed: %s", exc)
        return {
            "answer": "Synthesis failed — please retry.",
            "source_facts": [],
            "confidence": "LOW",
            "retrieval_meta": {
                "hits": len(all_chunks), "md_files": len(md_contents),
                "chunks": len(all_chunks), "method": "page_augmented"
            },
            "caveat": str(exc),
        }

    confidence = "MEDIUM"
    answer = raw
    for line in reversed(raw.splitlines()):
        if line.upper().startswith("CONFIDENCE:"):
            tag = line.split(":", 1)[1].strip().upper()
            if tag in ("HIGH", "MEDIUM", "LOW"):
                confidence = tag
            answer = raw[: raw.rfind(line)].strip()
            break

    source_passages = [
        {
            "text":         str(c.get("text", ""))[:600],
            "page_num":     c.get("page_num"),
            "doc_id":       c.get("doc_id"),
            "section_path": c.get("section_path"),
            "source_type":  c.get("source_type"),
            "score":        c.get("score"),
        }
        for c in all_chunks[:8]
        if c.get("text")
    ]

    return {
        "answer":       answer,
        "source_facts": source_passages,
        "confidence":   confidence,
        "retrieval_meta": {
            "hits":     len(all_chunks),
            "md_files": len(md_contents),
            "chunks":   len(all_chunks),
            "method":   "page_augmented",
        },
        "caveat": None,
    }
