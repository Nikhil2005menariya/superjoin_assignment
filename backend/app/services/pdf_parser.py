"""
PDF parsing service.
Strategy per page:
  1. pdfplumber extracts text + tables (always)
  2. If page has embedded images AND text < VISION_THRESHOLD:
       → render page image → Nova Lite vision → append chart/infographic data
  3. If page char_count < TEXT_PAGE_THRESHOLD after step 1:
       → pytesseract OCR fallback
"""

import io
import logging
import os
from pathlib import Path
from typing import List, Optional

import pdfplumber
import fitz  # PyMuPDF
import pytesseract
from PIL import Image

from app.models.schemas import PageData

logger = logging.getLogger(__name__)

TEXT_PAGE_THRESHOLD = 50    # chars below which we run OCR
VISION_THRESHOLD    = 8000  # run vision on ALL pages with images regardless of text length
VISION_ENABLED      = os.getenv("VISION_ENABLED", "true").lower() == "true"


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
        # Step 1: text extraction
        raw_text   = plumber_page.extract_text() or ""
        char_count = len(raw_text.strip())
        tables     = self._extract_tables(plumber_page)
        words      = plumber_page.extract_words() or []
        source_type = "text" if char_count >= TEXT_PAGE_THRESHOLD else "ocr"

        # Step 2: OCR fallback for image-only pages
        if char_count < TEXT_PAGE_THRESHOLD:
            try:
                raw_text   = self._ocr_page(fitz_page)
                char_count = len(raw_text.strip())
                tables     = []
                words      = []
            except Exception as e:
                logger.warning("OCR failed for page %d: %s", page_num, e)
                raw_text   = ""
                char_count = 0
                source_type = "ocr_failed"

        # Step 3: vision pass for pages with embedded images (charts, infographics)
        # Pass surrounding text so the model understands the page topic/context
        vision_text = ""
        if VISION_ENABLED and char_count < VISION_THRESHOLD and self._has_images(fitz_page):
            vision_text = self._vision_pass(fitz_page, page_num, surrounding_text=raw_text)
            if vision_text:
                raw_text    = raw_text + "\n\n[VISUAL CONTENT]\n" + vision_text
                char_count  = len(raw_text.strip())
                source_type = source_type + "+vision"

        return PageData(
            page_num=page_num,
            text=raw_text,
            tables=tables,
            words=words,
            source_type=source_type,
            char_count=char_count,
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

    def _has_images(self, fitz_page) -> bool:
        """Return True if the page contains embedded raster images (charts/photos)."""
        try:
            return len(fitz_page.get_images(full=False)) > 0
        except Exception:
            return False

    def _vision_pass(self, fitz_page, page_num: int, surrounding_text: str = "") -> str:
        """Render page → Nova Lite vision → extract chart/infographic data.
        surrounding_text is the pdfplumber text from the same page, giving the
        model topic context so it can label chart axes/values correctly."""
        try:
            from app.services.bedrock_client import vision_extract_page
            mat = fitz.Matrix(1.5, 1.5)
            pix = fitz_page.get_pixmap(matrix=mat, alpha=False)
            img_bytes = pix.tobytes("png")
            # Pass up to 500 chars of surrounding text as context
            context = f"Page {page_num}"
            if surrounding_text.strip():
                context += f". Page text context: {surrounding_text.strip()[:500]}"
            result = vision_extract_page(img_bytes, page_context=context)
            if result:
                logger.info("Vision pass page %d: extracted %d chars", page_num, len(result))
            return result
        except Exception as e:
            logger.warning("Vision pass failed for page %d: %s", page_num, e)
            return ""

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
