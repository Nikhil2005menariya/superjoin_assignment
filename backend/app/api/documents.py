import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

import aiosqlite
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File
from sse_starlette.sse import EventSourceResponse

from app.agents.document_agent import run_document_pipeline
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()


def _row_to_doc(row) -> dict:
    keys = ["id", "filename", "file_size", "page_count", "status",
            "error_msg", "metadata", "created_at", "updated_at"]
    return dict(zip(keys, row))


def _row_to_job(row) -> dict:
    keys = ["id", "doc_id", "status", "stage", "progress",
            "total_pages", "current_page", "message", "error_msg", "updated_at"]
    return dict(zip(keys, row))


# ─── Upload ───────────────────────────────────────────────────────────────────

@router.post("/documents")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.max_upload_size_mb} MB limit",
        )

    doc_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Save file to disk
    os.makedirs(settings.uploads_dir, exist_ok=True)
    file_path = os.path.join(settings.uploads_dir, f"{doc_id}.pdf")
    with open(file_path, "wb") as f:
        f.write(content)

    # Insert document and job records
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            """INSERT INTO documents (id, filename, file_path, file_size, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'queued', ?, ?)""",
            (doc_id, file.filename, file_path, len(content), now, now),
        )
        await db.execute(
            """INSERT INTO jobs (id, doc_id, status, stage, progress, message, created_at, updated_at)
               VALUES (?, ?, 'queued', 'pending', 0, 'Queued for processing', ?, ?)""",
            (job_id, doc_id, now, now),
        )
        await db.commit()

    # Kick off the LangGraph pipeline in the background
    background_tasks.add_task(run_document_pipeline, doc_id, job_id, file_path)

    logger.info("Uploaded doc %s (%s, %.2f MB)", doc_id, file.filename, size_mb)
    return {"doc_id": doc_id, "job_id": job_id, "filename": file.filename}


# ─── List documents ───────────────────────────────────────────────────────────

@router.get("/documents")
async def list_documents():
    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            """SELECT id, filename, file_size, page_count, status, error_msg,
                      metadata, created_at, updated_at
               FROM documents ORDER BY created_at DESC"""
        ) as cursor:
            rows = await cursor.fetchall()
    return [_row_to_doc(r) for r in rows]


# ─── Get document ─────────────────────────────────────────────────────────────

@router.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            """SELECT id, filename, file_size, page_count, status, error_msg,
                      metadata, created_at, updated_at
               FROM documents WHERE id = ?""",
            (doc_id,),
        ) as cursor:
            row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    return _row_to_doc(row)


# ─── Get job status ───────────────────────────────────────────────────────────

@router.get("/documents/{doc_id}/job")
async def get_job(doc_id: str):
    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            """SELECT id, doc_id, status, stage, progress, total_pages,
                      current_page, message, error_msg, updated_at
               FROM jobs WHERE doc_id = ? ORDER BY created_at DESC LIMIT 1""",
            (doc_id,),
        ) as cursor:
            row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return _row_to_job(row)


# ─── SSE: real-time progress ──────────────────────────────────────────────────

@router.get("/documents/{doc_id}/events")
async def document_events(doc_id: str):
    """Server-Sent Events stream for real-time processing progress."""

    async def event_generator():
        last_updated = ""
        consecutive_done = 0

        while True:
            try:
                async with aiosqlite.connect(settings.db_path) as db:
                    async with db.execute(
                        """SELECT id, doc_id, status, stage, progress, total_pages,
                                  current_page, message, error_msg, updated_at
                           FROM jobs WHERE doc_id = ? ORDER BY created_at DESC LIMIT 1""",
                        (doc_id,),
                    ) as cursor:
                        row = await cursor.fetchone()

                if not row:
                    yield {"data": json.dumps({"error": "job not found"})}
                    return

                job = _row_to_job(row)

                # Only push when something changed
                if job["updated_at"] != last_updated:
                    last_updated = job["updated_at"]
                    yield {"data": json.dumps(job)}

                if job["status"] in ("done", "failed"):
                    consecutive_done += 1
                    if consecutive_done >= 2:
                        return
                else:
                    consecutive_done = 0

            except Exception as exc:
                yield {"data": json.dumps({"error": str(exc)})}
                return

            await asyncio.sleep(0.8)

    return EventSourceResponse(event_generator())


# ─── Get chunks for a document ────────────────────────────────────────────────

@router.get("/documents/{doc_id}/chunks")
async def get_chunks(doc_id: str, level: str = None, page: int = None):
    conditions = ["doc_id = ?"]
    params = [doc_id]
    if level:
        conditions.append("level = ?")
        params.append(level)
    if page:
        conditions.append("page_num = ?")
        params.append(page)

    where = " AND ".join(conditions)
    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            f"""SELECT id, doc_id, parent_id, level, page_num, section_path,
                       raw_text, source_type, chunk_index
                FROM chunks WHERE {where} ORDER BY chunk_index""",
            params,
        ) as cursor:
            rows = await cursor.fetchall()

    keys = ["id", "doc_id", "parent_id", "level", "page_num",
            "section_path", "raw_text", "source_type", "chunk_index"]
    return [dict(zip(keys, r)) for r in rows]
