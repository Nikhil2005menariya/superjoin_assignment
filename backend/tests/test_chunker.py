"""
Unit tests for the multi-granularity chunker.
"""

import pytest
from app.services.chunker import Chunker
from app.models.schemas import PageData


@pytest.fixture
def chunker():
    return Chunker()


def make_page(page_num: int, text: str, tables=None, source_type="text") -> PageData:
    return PageData(
        page_num=page_num,
        text=text,
        tables=tables or [],
        words=[],
        source_type=source_type,
        char_count=len(text),
    )


class TestChunker:
    def test_produces_section_and_paragraph_chunks(self, chunker):
        pages = [
            make_page(1, "Revenue was ₹21,302 Crore in FY24.\n\nEBITDA margin was 4.2 per cent.")
        ]
        chunks = chunker.chunk(pages, "doc-001")
        levels = {c.level for c in chunks}
        assert "section" in levels
        assert "paragraph" in levels

    def test_produces_sentence_chunks(self, chunker):
        pages = [make_page(1, "Revenue grew 12%. EBITDA improved. Margins expanded.")]
        chunks = chunker.chunk(pages, "doc-002")
        sentences = [c for c in chunks if c.level == "sentence"]
        assert len(sentences) >= 1

    def test_table_rows_become_table_row_chunks(self, chunker):
        table = [
            ["Metric", "FY23", "FY24"],
            ["Revenue", "10000", "21302"],
            ["EBITDA",  "500",   "900"],
        ]
        pages = [make_page(1, "Summary of financials.", tables=[table])]
        chunks = chunker.chunk(pages, "doc-003")
        tr_chunks = [c for c in chunks if c.level == "table_row"]
        assert len(tr_chunks) == 4  # 2 data rows × 2 value cols

    def test_doc_id_propagated(self, chunker):
        pages = [make_page(1, "Some text about India GDP.")]
        chunks = chunker.chunk(pages, "my-doc-id")
        assert all(c.doc_id == "my-doc-id" for c in chunks)

    def test_page_num_preserved(self, chunker):
        pages = [make_page(7, "Text on page seven.")]
        chunks = chunker.chunk(pages, "doc-004")
        assert all(c.page_num == 7 for c in chunks)

    def test_parent_child_links(self, chunker):
        pages = [make_page(1, "Para one text here.\n\nPara two text here.")]
        chunks = chunker.chunk(pages, "doc-005")
        sections = [c for c in chunks if c.level == "section"]
        paragraphs = [c for c in chunks if c.level == "paragraph"]
        assert len(sections) >= 1
        # Paragraphs should have a parent_id pointing to a section
        section_ids = {c.id for c in sections}
        for p in paragraphs:
            assert p.parent_id in section_ids

    def test_empty_pages_skipped(self, chunker):
        pages = [
            make_page(1, ""),
            make_page(2, "Actual content here about GDP growth of 6.4%."),
        ]
        chunks = chunker.chunk(pages, "doc-006")
        assert len(chunks) > 0
        assert all(c.page_num == 2 for c in chunks)

    def test_ocr_source_type_preserved(self, chunker):
        pages = [make_page(3, "OCR extracted text.", source_type="ocr")]
        chunks = chunker.chunk(pages, "doc-007")
        # section chunk should retain ocr source type
        sections = [c for c in chunks if c.level == "section"]
        assert sections[0].source_type == "ocr"

    def test_chunk_index_monotonic(self, chunker):
        pages = [
            make_page(1, "First page content.\n\nSecond paragraph."),
            make_page(2, "Second page content here."),
        ]
        chunks = chunker.chunk(pages, "doc-008")
        indices = [c.chunk_index for c in chunks]
        assert indices == sorted(indices)
