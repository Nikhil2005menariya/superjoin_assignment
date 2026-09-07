"""
Phase 1 LangGraph agent: Document Intelligence pipeline.

Graph:
  START → validate → parse_pages → chunk_document → persist_chunks → END
                ↓ (on error at any node)
           handle_error → END

Each node updates the job record in SQLite so the SSE stream
can push real-time progress to the frontend.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Literal

import aiosqlite
from langgraph.graph import StateGraph, START, END

from app.agents.state import DocumentState
from app.config import get_settings
from app.services.pdf_parser import PDFParser
from app.services.chunker import Chunker

logger = logging.getLogger(__name__)
settings = get_settings()

parser = PDFParser()
chunker = Chunker()


# ─── helpers ──────────────────────────────────────────────────────────────────

async def _update_job(job_id: str, **kwargs):
    kwargs["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [job_id]
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(f"UPDATE jobs SET {set_clause} WHERE id = ?", values)
        await db.commit()


async def _update_doc_status(doc_id: str, status: str, error_msg: str = None):
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "UPDATE documents SET status = ?, error_msg = ?, updated_at = ? WHERE id = ?",
            (status, error_msg, datetime.utcnow().isoformat(), doc_id),
        )
        await db.commit()


# ─── nodes ────────────────────────────────────────────────────────────────────

async def validate_node(state: DocumentState) -> DocumentState:
    """Check the PDF is a valid, readable file."""
    logger.info("[%s] Validating PDF: %s", state["doc_id"], state["file_path"])
    try:
        page_count = PDFParser.get_page_count(state["file_path"])
        await _update_job(
            state["job_id"],
            stage="parsing",
            progress=5,
            total_pages=page_count,
            message=f"Validated — {page_count} pages detected",
        )
        async with aiosqlite.connect(settings.db_path) as db:
            await db.execute(
                "UPDATE documents SET page_count = ?, updated_at = ? WHERE id = ?",
                (page_count, datetime.utcnow().isoformat(), state["doc_id"]),
            )
            await db.commit()
        return {**state, "total_pages": page_count, "stage": "parsing", "progress": 5}
    except Exception as exc:
        return {**state, "error": str(exc)}


async def parse_pages_node(state: DocumentState) -> DocumentState:
    """Parse every page: text-native via pdfplumber, image pages via OCR."""
    logger.info("[%s] Parsing %d pages", state["doc_id"], state["total_pages"])
    try:
        pages = parser.parse(state["file_path"])
        progress = 40
        await _update_job(
            state["job_id"],
            stage="chunking",
            progress=progress,
            current_page=len(pages),
            message=f"Parsed {len(pages)} pages",
        )
        return {**state, "pages": pages, "stage": "chunking", "progress": progress}
    except Exception as exc:
        logger.exception("Parse error for doc %s", state["doc_id"])
        return {**state, "error": str(exc)}


async def chunk_document_node(state: DocumentState) -> DocumentState:
    """Multi-granularity chunking: section / paragraph / sentence / table_row."""
    logger.info("[%s] Chunking document", state["doc_id"])
    try:
        chunks = chunker.chunk(state["pages"], state["doc_id"])
        await _update_job(
            state["job_id"],
            stage="persisting",
            progress=70,
            message=f"Created {len(chunks)} chunks",
        )
        return {**state, "chunks": chunks, "stage": "persisting", "progress": 70}
    except Exception as exc:
        logger.exception("Chunking error for doc %s", state["doc_id"])
        return {**state, "error": str(exc)}


async def persist_chunks_node(state: DocumentState) -> DocumentState:
    """Write all chunks to SQLite and mark document as ready for Phase 2."""
    logger.info("[%s] Persisting %d chunks", state["doc_id"], len(state.get("chunks", [])))
    try:
        chunks = state.get("chunks", [])
        async with aiosqlite.connect(settings.db_path) as db:
            await db.executemany(
                """
                INSERT OR IGNORE INTO chunks
                    (id, doc_id, parent_id, level, page_num, section_path,
                     raw_text, bbox, source_type, chunk_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        c.id,
                        c.doc_id,
                        c.parent_id,
                        c.level,
                        c.page_num,
                        c.section_path,
                        c.raw_text,
                        json.dumps(c.bbox),
                        c.source_type,
                        c.chunk_index,
                    )
                    for c in chunks
                ],
            )
            await db.commit()

        # Update document status and hand off to Phase 2
        await _update_doc_status(state["doc_id"], "chunked")
        await _update_job(
            state["job_id"],
            status="done",
            stage="done",
            progress=100,
            message=f"Phase 1 complete — {len(chunks)} chunks stored. Launching fact extraction…",
        )
        logger.info("[%s] Phase 1 done: %d chunks persisted — firing Phase 2", state["doc_id"], len(chunks))

        # Fire Phase 2 as a background asyncio task (non-blocking)
        from app.agents.extraction_agent import run_extraction_pipeline
        extraction_job_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        async with aiosqlite.connect(settings.db_path) as db:
            await db.execute(
                """INSERT INTO jobs (id, doc_id, status, stage, progress, total_pages, message, created_at, updated_at)
                   VALUES (?, ?, 'queued', 'pending', 0, ?, 'Fact extraction queued', ?, ?)""",
                (extraction_job_id, state["doc_id"], state.get("total_pages", 0), now, now),
            )
            await db.commit()
        asyncio.create_task(run_extraction_pipeline(state["doc_id"], extraction_job_id))

        return {**state, "stage": "done", "progress": 100}
    except Exception as exc:
        logger.exception("Persist error for doc %s", state["doc_id"])
        return {**state, "error": str(exc)}


async def handle_error_node(state: DocumentState) -> DocumentState:
    """Record failure in SQLite."""
    err = state.get("error", "Unknown error")
    logger.error("[%s] Processing failed: %s", state["doc_id"], err)
    await _update_doc_status(state["doc_id"], "failed", error_msg=err)
    await _update_job(
        state["job_id"],
        status="failed",
        stage="failed",
        error_msg=err,
        message=f"Failed: {err}",
    )
    return state


# ─── routing ──────────────────────────────────────────────────────────────────

def route_on_error(state: DocumentState) -> Literal["continue", "error"]:
    return "error" if state.get("error") else "continue"


# ─── graph compilation ────────────────────────────────────────────────────────

def build_document_graph():
    g = StateGraph(DocumentState)

    g.add_node("validate",       validate_node)
    g.add_node("parse_pages",    parse_pages_node)
    g.add_node("chunk_document", chunk_document_node)
    g.add_node("persist_chunks", persist_chunks_node)
    g.add_node("handle_error",   handle_error_node)

    g.add_edge(START, "validate")

    g.add_conditional_edges("validate", route_on_error, {
        "continue": "parse_pages",
        "error":    "handle_error",
    })
    g.add_conditional_edges("parse_pages", route_on_error, {
        "continue": "chunk_document",
        "error":    "handle_error",
    })
    g.add_conditional_edges("chunk_document", route_on_error, {
        "continue": "persist_chunks",
        "error":    "handle_error",
    })
    g.add_conditional_edges("persist_chunks", route_on_error, {
        "continue": END,
        "error":    "handle_error",
    })

    g.add_edge("handle_error", END)

    return g.compile()


document_graph = build_document_graph()


# ─── entry point ──────────────────────────────────────────────────────────────

async def run_document_pipeline(doc_id: str, job_id: str, file_path: str):
    """Called as a FastAPI background task."""
    initial_state: DocumentState = {
        "doc_id":      doc_id,
        "job_id":      job_id,
        "file_path":   file_path,
        "pages":       [],
        "total_pages": 0,
        "chunks":      [],
        "stage":       "pending",
        "progress":    0,
        "message":     "Starting document intelligence pipeline",
        "error":       None,
    }
    await document_graph.ainvoke(initial_state)
