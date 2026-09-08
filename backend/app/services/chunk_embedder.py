"""
Embeds document chunks into the doc_chunks Qdrant collection.

Dense (bge-small-en-v1.5, 384-dim) + BM25 sparse hybrid.
All embedding is local ONNX — no external API calls, no GPU needed.
"""

import asyncio
import logging
import uuid

from qdrant_client.models import PointStruct, SparseVector

from app.database.qdrant_client import get_qdrant, CHUNK_COLLECTION
from app.services.embedder import embed_texts

logger = logging.getLogger(__name__)

EMBED_LEVELS    = {"paragraph", "section", "table_row"}
EMBED_BATCH     = 32
UPSERT_BATCH    = 200
MIN_TEXT_LEN    = 30
MAX_EMBED_CHARS = 2000


async def embed_and_index_chunks(doc_id: str, chunks: list) -> int:
    """
    Embed all paragraph/section/table_row chunks with dense + BM25 and upsert
    to the doc_chunks Qdrant collection. Returns number of points indexed.
    """
    qdrant = get_qdrant()
    loop   = asyncio.get_event_loop()

    eligible = [
        c for c in chunks
        if c.level in EMBED_LEVELS and len((c.raw_text or "").strip()) >= MIN_TEXT_LEN
    ]

    if not eligible:
        logger.info("[%s] No eligible chunks to embed", doc_id)
        return 0

    logger.info("[%s] Embedding %d chunks (bge-small + BM25) into doc_chunks", doc_id, len(eligible))
    points: list[PointStruct] = []

    for i in range(0, len(eligible), EMBED_BATCH):
        batch = eligible[i : i + EMBED_BATCH]
        texts = [c.raw_text[:MAX_EMBED_CHARS] for c in batch]

        dense_results = await loop.run_in_executor(None, embed_texts, texts)

        for chunk, dr in zip(batch, dense_results):
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector={
                    "dense": dr.dense,
                    "bm25":  SparseVector(
                        indices=dr.sparse_indices,
                        values=dr.sparse_values,
                    ),
                },
                payload={
                    "chunk_id":     chunk.id,
                    "doc_id":       doc_id,
                    "text":         chunk.raw_text,
                    "level":        chunk.level,
                    "page_num":     chunk.page_num,
                    "section_path": chunk.section_path,
                    "source_type":  chunk.source_type,
                    "md_path":      getattr(chunk, "md_path", None),
                },
            ))

    total = 0
    for ui in range(0, len(points), UPSERT_BATCH):
        await qdrant.upsert(
            collection_name=CHUNK_COLLECTION,
            points=points[ui : ui + UPSERT_BATCH],
        )
        total += len(points[ui : ui + UPSERT_BATCH])
        logger.info("[%s] Upserted %d/%d chunk points", doc_id, total, len(points))

    logger.info("[%s] Chunk indexing complete: %d vectors", doc_id, total)
    return total
