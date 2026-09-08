"""
Cross-document knowledge linker (zero extra LLM calls).

After page MD generation, searches Qdrant for pages from other documents
with high embedding similarity, then uses rule-based metric comparison to
classify each link:

  CORROBORATES — same metric name, values within 5%
  CONTRADICTS  — same metric name, values differ >15%, same unit
  RECONCILES   — same metric name, values differ >15%, different units
                 (e.g. Indian "Cr" vs global "M" — same figure, different scale)
  RELATED      — high semantic similarity, no metric overlap

Results are written to:
  • page_relationships SQLite table
  • ## Related Pages section appended to each .md file
"""

import asyncio
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path

import aiosqlite

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SIMILARITY_THRESHOLD = 0.68
MAX_LINKS_PER_PAGE   = 3


def _parse_metrics(md_content: str) -> dict[str, tuple[float, str]]:
    """Extract {metric_name: (value, unit)} from the ## Key Metrics table."""
    metrics: dict[str, tuple[float, str]] = {}
    in_table = False
    for line in md_content.splitlines():
        if "## Key Metrics" in line:
            in_table = True
            continue
        if in_table and line.startswith("##"):
            break
        if (in_table and line.startswith("|")
                and not line.startswith("|-")
                and "Metric" not in line):
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) < 2:
                continue
            name    = parts[0].strip()
            val_str = parts[1].strip()
            unit    = parts[2].strip() if len(parts) > 2 else ""
            if not name or not val_str or val_str in ("—", "_", ""):
                continue
            try:
                val = float(re.sub(r"[,%₹$]", "", val_str))
                metrics[name.lower()] = (val, unit)
            except ValueError:
                pass
    return metrics


def _classify(
    metrics_a: dict,
    metrics_b: dict,
    similarity: float,
) -> tuple[str, str]:
    common = set(metrics_a) & set(metrics_b)
    for name in common:
        val_a, unit_a = metrics_a[name]
        val_b, unit_b = metrics_b[name]
        if val_a == 0 or val_b == 0:
            continue
        diff = abs(val_a - val_b) / max(abs(val_a), abs(val_b))
        if diff < 0.05:
            return "CORROBORATES", (
                f'Both pages report "{name}" with matching values '
                f"({val_a} {unit_a} ≈ {val_b} {unit_b})"
            )
        if diff > 0.15:
            ua = unit_a.lower().strip("()")
            ub = unit_b.lower().strip("()")
            if ua != ub and ua and ub:
                return "RECONCILES", (
                    f'Both pages report "{name}" but in different units: '
                    f"{val_a} {unit_a} vs {val_b} {unit_b}. "
                    "Likely the same figure expressed in different scales."
                )
            return "CONTRADICTS", (
                f'Both pages report "{name}" with conflicting values: '
                f"{val_a} {unit_a} vs {val_b} {unit_b} ({diff:.0%} difference)"
            )

    if similarity > 0.78:
        return "RELATED", f"Thematically similar pages (similarity={similarity:.2f}), no overlapping metrics"
    return "RELATED", f"Semantic similarity: {similarity:.2f}"


async def _update_job(job_id: str, progress: int, message: str, stage: str = "linking"):
    try:
        async with aiosqlite.connect(settings.db_path) as db:
            await db.execute(
                "UPDATE jobs SET progress=?, message=?, stage=?, updated_at=? WHERE id=?",
                (progress, message, stage, datetime.utcnow().isoformat(), job_id),
            )
            await db.commit()
    except Exception as exc:
        logger.warning("Job update failed: %s", exc)


async def run_cross_doc_linking(doc_id: str, job_id: str):
    """
    Link pages of doc_id to similar pages in other documents already in Qdrant.
    Uses only dense embedding search + rule-based metric comparison — no LLM.
    """
    await _update_job(job_id, 96, "Cross-document linking…")

    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            "SELECT id, page_num, md_path, md_content, summary FROM page_summaries WHERE doc_id=?",
            (doc_id,),
        ) as cur:
            my_pages = await cur.fetchall()

    if not my_pages:
        logger.info("[%s] No page summaries — skipping cross-doc linking", doc_id)
        return

    from app.database.qdrant_client import get_qdrant, CHUNK_COLLECTION
    from app.services.embedder import embed_texts
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    qdrant = get_qdrant()
    loop   = asyncio.get_event_loop()
    total_links = 0

    for page_id, page_num, md_path, md_content, summary in my_pages:
        if not summary or len(summary.strip()) < 10:
            continue

        try:
            dense_r = await loop.run_in_executor(None, embed_texts, [summary[:1500]])
            qvec    = dense_r[0].dense
        except Exception as exc:
            logger.warning("[%s] Page %d embed for cross-doc failed: %s", doc_id, page_num, exc)
            continue

        try:
            hits = await qdrant.search(
                collection_name=CHUNK_COLLECTION,
                query_vector=("dense", qvec),
                query_filter=Filter(
                    must=[
                        FieldCondition(key="level", match=MatchValue(value="page_summary")),
                    ],
                    must_not=[
                        FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
                    ],
                ),
                limit=MAX_LINKS_PER_PAGE,
                with_payload=True,
            )
        except Exception as exc:
            logger.warning("[%s] Qdrant cross-doc search failed: %s", doc_id, exc)
            continue

        links = []
        metrics_a = _parse_metrics(md_content or "")

        for hit in hits:
            if hit.score < SIMILARITY_THRESHOLD:
                continue
            other_doc_id   = hit.payload.get("doc_id", "")
            other_page_num = hit.payload.get("page_num", 0)
            other_md_path  = hit.payload.get("md_path", "")
            other_chunk_id = hit.payload.get("chunk_id", "")
            similarity     = hit.score

            try:
                other_md = Path(other_md_path).read_text(encoding="utf-8") if other_md_path else ""
            except Exception:
                other_md = ""

            metrics_b = _parse_metrics(other_md)
            rel_type, explanation = _classify(metrics_a, metrics_b, similarity)

            links.append({
                "other_doc_id":   other_doc_id,
                "other_page_num": other_page_num,
                "other_md_path":  other_md_path,
                "other_chunk_id": other_chunk_id,
                "type":           rel_type,
                "explanation":    explanation,
                "similarity":     similarity,
            })

        if not links:
            continue

        # Append ## Related Pages block to this page's .md
        try:
            current_text = Path(md_path).read_text(encoding="utf-8")
            block = "\n\n## Related Pages\n"
            for lnk in links:
                block += (
                    f"- **{lnk['type']}** — "
                    f"doc:{lnk['other_doc_id'][:8]} · Page {lnk['other_page_num']} "
                    f"| {lnk['explanation']}\n"
                )
            Path(md_path).write_text(current_text + block, encoding="utf-8")
        except Exception as exc:
            logger.warning("[%s] Could not append related pages to %s: %s", doc_id, md_path, exc)

        # Persist to page_relationships
        async with aiosqlite.connect(settings.db_path) as db:
            for lnk in links:
                # Look up page_b_id from page_summaries
                async with db.execute(
                    "SELECT id FROM page_summaries WHERE doc_id=? AND page_num=?",
                    (lnk["other_doc_id"], lnk["other_page_num"]),
                ) as cur:
                    row = await cur.fetchone()
                page_b_id = row[0] if row else lnk["other_chunk_id"]

                await db.execute(
                    """INSERT OR IGNORE INTO page_relationships
                       (id, page_a_id, page_b_id, doc_a_id, doc_b_id, type, explanation, confidence, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (str(uuid.uuid4()), page_id, page_b_id,
                     doc_id, lnk["other_doc_id"],
                     lnk["type"], lnk["explanation"],
                     lnk["similarity"], datetime.utcnow().isoformat()),
                )
            await db.commit()

        total_links += len(links)

    logger.info("[%s] Cross-doc linking: %d links created", doc_id, total_links)
    await _update_job(job_id, 99, f"Linking complete — {total_links} cross-document relationships found")
