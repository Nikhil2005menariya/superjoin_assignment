"""
PDF parsing service.
Strategy per page:
  - text-native (char_count >= 50): pdfplumber for layout-aware text + structural tables
  - image-based (char_count < 50):  pymupdf renders page → pytesseract OCR
"""

import io
import logging
from pathlib import Path
from typing import List, Optional

import pdfplumber
import fitz  # PyMuPDF
import pytesseract
from PIL import Image

from app.models.schemas import PageData

logger = logging.getLogger(__name__)

# Minimum characters to consider a page text-native
TEXT_PAGE_THRESHOLD = 50


class PDFParser:
    def parse(self, file_path: str) -> List[PageData]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {file_path}")

        results: List[PageData] = []

        with pdfplumber.open(file_path) as plumber_doc:
            fitz_doc = fitz.open(file_path)

            for page_num, plumber_page in enumerate(plumber_doc.pages):
                page_data = self._parse_page(
                    plumber_page=plumber_page,
                    fitz_page=fitz_doc[page_num],
                    page_num=page_num + 1,
                )
                results.append(page_data)
                logger.debug(
                    "Page %d: source=%s chars=%d tables=%d",
                    page_num + 1,
                    page_data.source_type,
                    page_data.char_count,
                    len(page_data.tables),
                )

            fitz_doc.close()

        return results

    def _parse_page(
        self,
        plumber_page,
        fitz_page,
        page_num: int,
    ) -> PageData:
        # Try text-native extraction first
        raw_text = plumber_page.extract_text() or ""
        char_count = len(raw_text.strip())

        if char_count >= TEXT_PAGE_THRESHOLD:
            # Text-native path
            tables = self._extract_tables(plumber_page)
            words = plumber_page.extract_words() or []
            return PageData(
                page_num=page_num,
                text=raw_text,
                tables=tables,
                words=words,
                source_type="text",
                char_count=char_count,
            )

        # Image-based: OCR with tesseract
        try:
            ocr_text = self._ocr_page(fitz_page)
            return PageData(
                page_num=page_num,
                text=ocr_text,
                tables=[],
                words=[],
                source_type="ocr",
                char_count=len(ocr_text.strip()),
            )
        except Exception as e:
            logger.warning("OCR failed for page %d: %s", page_num, e)
            return PageData(
                page_num=page_num,
                text="",
                tables=[],
                words=[],
                source_type="ocr_failed",
                char_count=0,
            )

    def _extract_tables(self, plumber_page) -> List[List[List[Optional[str]]]]:
        """Extract all tables from a pdfplumber page as list-of-rows."""
        try:
            raw_tables = plumber_page.extract_tables()
            if not raw_tables:
                return []
            # Normalize: ensure every cell is str or None
            normalized = []
            for table in raw_tables:
                norm_table = []
                for row in table:
                    norm_row = [str(cell).strip() if cell is not None else None for cell in row]
                    norm_table.append(norm_row)
                normalized.append(norm_table)
            return normalized
        except Exception as e:
            logger.warning("Table extraction failed: %s", e)
            return []

    def _ocr_page(self, fitz_page) -> str:
        """Render page at 2× zoom and run tesseract."""
        mat = fitz.Matrix(2.0, 2.0)
        pix = fitz_page.get_pixmap(matrix=mat, alpha=False)
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))
        text = pytesseract.image_to_string(img, lang="eng", config="--oem 3 --psm 6")
        return text.strip()

    @staticmethod
    def get_page_count(file_path: str) -> int:
        with fitz.open(file_path) as doc:
            return len(doc)
