"""
Page Knowledge Graph generator.

For each page of a document, a single Amazon Nova 2 Lite call produces a
structured Markdown file:

    /data/pages/{doc_id}/page_{N}.md
        ## Summary          — 2-3 sentence description
        ## Key Metrics      — every number on the page in a table
        ## Key Facts        — non-numerical claims with source quotes
        ## Visual Content   — chart/graph data extracted via vision pass
        ## Entity Mentions  — companies, products, people, locations

Vision pass (dedicated, per-page):
    Every page that has embedded images gets a second Nova Lite multimodal call
    that re-renders the page at 2× zoom and extracts structured chart data.
    Results are merged into Key Metrics (extra rows) and Visual Content section.
"""

import asyncio
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

import aiosqlite

from app.config import get_settings
from app.services.bedrock_client import _BedrockChat

logger = logging.getLogger(__name__)
settings = get_settings()

_llm = _BedrockChat()
_bedrock_sem = asyncio.Semaphore(2)  # max 2 concurrent Bedrock calls to avoid OOM on 4 GB instance

MAX_PAGE_CHARS = 5000

_SYSTEM = """You are a document intelligence agent producing a structured knowledge file for one page of a business or financial document.

This file will be used directly by an AI retrieval system — be exhaustive with every number, date, percentage, and named entity.

Output EXACTLY this Markdown structure with no preamble:

## Summary
2-3 sentences describing what this page covers and why it matters.

## Key Metrics
| Metric | Value | Unit | Time Period | Scope |
|--------|-------|------|------------|-------|
One row per numerical data point. Capture EVERY number on the page (revenue, headcount, percentages, ratios, dates, counts). Use — for unknown cells.
If no metrics exist, write exactly: _No numerical metrics on this page._

## Key Facts
- [FACT] <claim> (quote: "<exact words from document>")
Non-numerical claims: company relationships, product descriptions, risk factors, strategic points. Omit this section if none.

## Visual Content
Describe any charts, graphs, tables, or diagrams. Note axis labels, legend items, visible data values, and trend direction.
If no visual content, write exactly: _No visual elements._

## Entity Mentions
- **Companies**: <comma-separated list, or None>
- **Products/Services**: <comma-separated list, or None>
- **People**: <comma-separated list, or None>
- **Locations**: <comma-separated list, or None>

Return ONLY the Markdown above. No explanation. No commentary."""


# ── Vision helpers ────────────────────────────────────────────────────────────

def _render_page_to_bytes(pdf_path: str, page_num: int) -> bytes | None:
    """Render a PDF page at 2× zoom to PNG bytes using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        page = doc[page_num - 1]  # 0-indexed
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_bytes = pix.tobytes("png")
        doc.close()
        return img_bytes
    except Exception as exc:
        logger.warning("Page render failed (page %d, %s): %s", page_num, pdf_path, exc)
        return None


def _page_has_images(pdf_path: str, page_num: int) -> bool:
    """Return True if PyMuPDF finds embedded images on this page."""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        has = len(doc[page_num - 1].get_images(full=False)) > 0
        doc.close()
        return has
    except Exception:
        return False


def _extract_vision_metric_rows(vision_text: str) -> list[str]:
    """
    Parse pipe-table rows from vision output so we can append them to Key Metrics.
    Skips header/separator rows and CHART:/TREND: lines.
    """
    rows = []
    for line in vision_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if re.match(r"^\|[\s\-|]+\|$", stripped):  # separator row
            continue
        if "Metric" in stripped and "Value" in stripped:  # header row
            continue
        rows.append(stripped)
    return rows


def _merge_vision_into_md(md: str, vision_text: str, page_num: int) -> str:
    """
    Merge vision-extracted chart data into the page MD:
      1. Append chart metric rows to ## Key Metrics table
      2. Replace ## Visual Content section with full vision output
    """
    if not vision_text.strip():
        return md

    # 1. Append rows to Key Metrics
    extra_rows = _extract_vision_metric_rows(vision_text)
    if extra_rows:
        no_metrics_marker = "_No numerical metrics on this page._"
        if no_metrics_marker in md:
            header = "| Metric | Value | Unit | Time Period | Scope |\n|--------|-------|------|------------|-------|"
            md = md.replace(
                no_metrics_marker,
                header + "\n" + "\n".join(extra_rows),
            )
        else:
            # Find end of existing Key Metrics table and append
            km_end = md.find("\n## ", md.find("## Key Metrics") + 1)
            if km_end == -1:
                km_end = len(md)
            md = md[:km_end].rstrip() + "\n" + "\n".join(extra_rows) + "\n" + md[km_end:]

    # 2. Replace Visual Content section
    vis_start = md.find("## Visual Content")
    if vis_start != -1:
        vis_end = md.find("\n## ", vis_start + 1)
        if vis_end == -1:
            vis_end = len(md)
        formatted_vision = f"## Visual Content\n\n{vision_text.strip()}"
        md = md[:vis_start] + formatted_vision + md[vis_end:]

    return md


async def _get_doc_file_path(doc_id: str) -> str | None:
    """Look up the original PDF file path from SQLite."""
    try:
        async with aiosqlite.connect(settings.db_path) as db:
            async with db.execute(
                "SELECT file_path FROM documents WHERE id=?", (doc_id,)
            ) as cur:
                row = await cur.fetchone()
        return row[0] if row else None
    except Exception as exc:
        logger.warning("Could not fetch file_path for doc %s: %s", doc_id, exc)
        return None


# ── Main generation function ──────────────────────────────────────────────────

async def generate_page_md(
    doc_id: str,
    page_num: int,
    page_text: str,
    pages_dir: Path,
    pdf_path: str | None = None,
) -> tuple[str, str]:
    """
    Call Nova Lite once per page → save .md → return (md_path, full_md_content).
    If pdf_path is given, also run a dedicated vision pass and merge chart data.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    trimmed = page_text[:MAX_PAGE_CHARS]
    user_msg = f"Document page {page_num}:\n\n{trimmed}"

    try:
        async with _bedrock_sem:
            resp = await _llm.ainvoke([
                SystemMessage(content=_SYSTEM),
                HumanMessage(content=user_msg),
            ])
        md_body = resp.content.strip()
    except Exception as exc:
        logger.warning("[%s] LLM failed for page %d: %s", doc_id, page_num, exc)
        md_body = (
            f"## Summary\nPage {page_num} — knowledge extraction failed: {exc}\n\n"
            "## Key Metrics\n_No numerical metrics on this page._\n\n"
            "## Key Facts\n\n"
            "## Visual Content\n_No visual elements._\n\n"
            "## Entity Mentions\n"
            "- **Companies**: None\n- **Products/Services**: None\n"
            "- **People**: None\n- **Locations**: None"
        )

    header = f"# Page {page_num} — doc:{doc_id[:8]}\n\n"
    full_md = header + md_body

    # ── Dedicated vision pass (runs if PDF path available + page has images) ──
    if pdf_path and os.path.exists(pdf_path):
        loop = asyncio.get_event_loop()
        has_images = await loop.run_in_executor(None, _page_has_images, pdf_path, page_num)
        if has_images:
            img_bytes = await loop.run_in_executor(None, _render_page_to_bytes, pdf_path, page_num)
            if img_bytes:
                from app.services.bedrock_client import vision_extract_page
                context = f"Page {page_num}. Text layer: {page_text.strip()[:600]}"
                try:
                    vision_text = await loop.run_in_executor(
                        None, vision_extract_page, img_bytes, context
                    )
                    if vision_text:
                        full_md = _merge_vision_into_md(full_md, vision_text, page_num)
                        logger.info(
                            "[%s] Vision pass page %d: merged %d chars",
                            doc_id, page_num, len(vision_text),
                        )
                except Exception as exc:
                    logger.warning("[%s] Vision merge failed page %d: %s", doc_id, page_num, exc)

    doc_dir = pages_dir / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    md_path = doc_dir / f"page_{page_num}.md"
    md_path.write_text(full_md, encoding="utf-8")

    return str(md_path), full_md


def _extract_summary(md_content: str) -> str:
    m = re.search(r"## Summary\n(.*?)(?=\n##|\Z)", md_content, re.DOTALL)
    return m.group(1).strip() if m else md_content[:300]


async def _embed_page_summary(
    qdrant, loop, doc_id: str, page_num: int, page_id: str, md_path: str, summary: str
):
    """Upsert page-summary embedding (dense + BM25) into the doc_chunks collection."""
    if not summary or len(summary.strip()) < 10:
        return

    from app.database.qdrant_client import CHUNK_COLLECTION
    from app.services.embedder import embed_texts
    from qdrant_client.models import PointStruct, SparseVector

    text = summary[:2000]
    dense_results = await loop.run_in_executor(None, embed_texts, [text])
    dr = dense_results[0]

    point = PointStruct(
        id=str(uuid.uuid4()),
        vector={
            "dense": dr.dense,
            "bm25":  SparseVector(indices=dr.sparse_indices, values=dr.sparse_values),
        },
        payload={
            "chunk_id":     page_id,
            "doc_id":       doc_id,
            "text":         summary,
            "level":        "page_summary",
            "page_num":     page_num,
            "section_path": f"Page {page_num}",
            "source_type":  "page_md",
            "md_path":      md_path,
        },
    )
    await qdrant.upsert(collection_name=CHUNK_COLLECTION, points=[point])


async def _update_job(job_id: str, progress: int, message: str, status: str = "processing", stage: str = "generating"):
    try:
        async with aiosqlite.connect(settings.db_path) as db:
            await db.execute(
                "UPDATE jobs SET progress=?, message=?, status=?, stage=?, updated_at=? WHERE id=?",
                (progress, message, status, stage, datetime.utcnow().isoformat(), job_id),
            )
            await db.commit()
    except Exception as exc:
        logger.warning("Job update failed: %s", exc)


async def run_page_graph_pipeline(doc_id: str, job_id: str, chunks: list):
    """
    Background task launched after chunk persist.
    Generates one .md file per page (with vision), embeds each summary, then cross-doc linking.
    Drives job progress from 75 → 99%.
    """
    from app.database.qdrant_client import get_qdrant

    pages_dir = Path(settings.pages_dir)
    qdrant    = get_qdrant()
    loop      = asyncio.get_event_loop()

    # Look up the original PDF path for vision re-render
    pdf_path = await _get_doc_file_path(doc_id)
    if pdf_path:
        logger.info("[%s] PDF path for vision: %s", doc_id, pdf_path)
    else:
        logger.warning("[%s] PDF path not found — vision pass will be skipped", doc_id)

    # Aggregate chunk text per page
    page_texts: dict[int, str] = {}
    for chunk in chunks:
        pn = chunk.page_num
        if pn and chunk.raw_text:
            page_texts.setdefault(pn, "")
            page_texts[pn] += chunk.raw_text + "\n"

    sorted_pages = sorted(page_texts.keys())
    total = len(sorted_pages)
    if total == 0:
        logger.warning("[%s] No pages found in chunks", doc_id)
        await _update_job(job_id, 100, "Done (no pages to process)", status="done", stage="done")
        return

    logger.info("[%s] Generating page knowledge graph: %d pages", doc_id, total)
    await _update_job(job_id, 75, f"Building page knowledge graph — {total} pages…")

    async with aiosqlite.connect(settings.db_path) as db:
        for idx, page_num in enumerate(sorted_pages):
            page_text = page_texts[page_num]
            progress  = 75 + int((idx / total) * 20)  # 75 → 95%

            try:
                md_path, full_md = await generate_page_md(
                    doc_id, page_num, page_text, pages_dir, pdf_path=pdf_path
                )
            except Exception as exc:
                logger.warning("[%s] Page %d MD generation failed: %s", doc_id, page_num, exc)
                continue

            summary   = _extract_summary(full_md)
            has_visual = (
                "## Visual Content" in full_md
                and "_No visual elements." not in full_md
                and "NO_VISUAL_DATA" not in full_md
            )

            page_id = str(uuid.uuid4())
            await db.execute(
                """INSERT OR REPLACE INTO page_summaries
                   (id, doc_id, page_num, md_path, md_content, summary, has_visual, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (page_id, doc_id, page_num, md_path, full_md, summary,
                 int(has_visual), datetime.utcnow().isoformat()),
            )
            await db.execute(
                "UPDATE chunks SET md_path=? WHERE doc_id=? AND page_num=?",
                (md_path, doc_id, page_num),
            )
            await db.commit()

            await _update_job(job_id, progress, f"Page {idx+1}/{total} — knowledge file built")

            try:
                await _embed_page_summary(qdrant, loop, doc_id, page_num, page_id, md_path, summary)
            except Exception as exc:
                logger.warning("[%s] Page %d embed failed: %s", doc_id, page_num, exc)

    logger.info("[%s] Page graph complete — starting cross-doc linking", doc_id)

    try:
        from app.services.cross_doc_linker import run_cross_doc_linking
        await run_cross_doc_linking(doc_id, job_id)
    except Exception as exc:
        logger.warning("[%s] Cross-doc linking failed: %s", doc_id, exc)

    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "UPDATE documents SET status='done', updated_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), doc_id),
        )
        await db.commit()

    await _update_job(job_id, 100, f"Ready — {total} page knowledge files built", status="done", stage="done")
    logger.info("[%s] Full pipeline complete", doc_id)
