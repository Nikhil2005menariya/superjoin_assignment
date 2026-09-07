"""
Multi-granularity chunker.
Produces four chunk levels from parsed pages:
  section    — full page or detected section block
  paragraph  — blank-line separated blocks (~3-7 sentences)
  sentence   — individual sentences
  table_row  — NL statements produced by table_converter
"""

import re
import uuid
import logging
from typing import List, Optional, Tuple

from app.models.schemas import ChunkData, PageData
from app.services.table_converter import table_to_nl_statements

logger = logging.getLogger(__name__)

# Regex for sentence splitting (handles common abbreviations poorly, but good enough)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\d\"])")
_HEADER_PATTERNS = re.compile(
    r"^(chapter|section|part|appendix|\d+[\.\)]\s|\b[A-Z][A-Z\s]{3,}\b)",
    re.IGNORECASE | re.MULTILINE,
)


def _detect_section(text: str, prev_section: str) -> str:
    """
    Heuristic: if the page/block starts with an all-caps or numbered heading,
    use it as the section name; otherwise inherit the previous section.
    """
    first_line = text.strip().split("\n")[0].strip()
    if len(first_line) < 120 and _HEADER_PATTERNS.match(first_line):
        return first_line[:120]
    return prev_section


def _split_paragraphs(text: str) -> List[str]:
    blocks = re.split(r"\n{2,}", text)
    return [b.strip() for b in blocks if b.strip() and len(b.strip()) >= 20]


def _split_sentences(text: str) -> List[str]:
    parts = _SENT_SPLIT.split(text)
    return [p.strip() for p in parts if len(p.strip()) >= 15]


class Chunker:
    def chunk(self, pages: List[PageData], doc_id: str) -> List[ChunkData]:
        all_chunks: List[ChunkData] = []
        current_section = "Document Start"
        chunk_index = 0

        for page in pages:
            if not page.text.strip() and not page.tables:
                continue

            # Detect section transition
            current_section = _detect_section(page.text, current_section)

            # --- Section-level chunk (one per page) ---
            section_id = str(uuid.uuid4())
            all_chunks.append(
                ChunkData(
                    id=section_id,
                    doc_id=doc_id,
                    parent_id=None,
                    level="section",
                    page_num=page.page_num,
                    section_path=current_section,
                    raw_text=page.text,
                    source_type=page.source_type,
                    chunk_index=chunk_index,
                )
            )
            chunk_index += 1

            # --- Paragraph + sentence chunks ---
            paragraphs = _split_paragraphs(page.text)
            for para in paragraphs:
                para_id = str(uuid.uuid4())
                all_chunks.append(
                    ChunkData(
                        id=para_id,
                        doc_id=doc_id,
                        parent_id=section_id,
                        level="paragraph",
                        page_num=page.page_num,
                        section_path=current_section,
                        raw_text=para,
                        source_type=page.source_type,
                        chunk_index=chunk_index,
                    )
                )
                chunk_index += 1

                for sent in _split_sentences(para):
                    all_chunks.append(
                        ChunkData(
                            id=str(uuid.uuid4()),
                            doc_id=doc_id,
                            parent_id=para_id,
                            level="sentence",
                            page_num=page.page_num,
                            section_path=current_section,
                            raw_text=sent,
                            source_type=page.source_type,
                            chunk_index=chunk_index,
                        )
                    )
                    chunk_index += 1

            # --- Table row chunks ---
            for table in page.tables:
                stmts = table_to_nl_statements(
                    table=table,
                    section_context=current_section,
                    page_num=page.page_num,
                )
                for stmt in stmts:
                    all_chunks.append(
                        ChunkData(
                            id=str(uuid.uuid4()),
                            doc_id=doc_id,
                            parent_id=section_id,
                            level="table_row",
                            page_num=page.page_num,
                            section_path=current_section,
                            raw_text=stmt,
                            source_type="table",
                            chunk_index=chunk_index,
                        )
                    )
                    chunk_index += 1

        logger.info(
            "Chunked doc %s: %d pages → %d chunks",
            doc_id,
            len(pages),
            len(all_chunks),
        )
        return all_chunks
