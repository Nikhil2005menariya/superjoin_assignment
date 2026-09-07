"""
Deterministic table → natural language converter.
Converts each (row-header × column-header × value) triple into a standalone
fact-candidate sentence.  No LLM involved — fast, zero hallucination.
"""

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)

_EMPTY = {"", "-", "—", "n/a", "na", "nil", "none", "--"}


def _is_empty(cell: Optional[str]) -> bool:
    return cell is None or cell.strip().lower() in _EMPTY


def _clean(s: Optional[str]) -> str:
    if s is None:
        return ""
    return re.sub(r"\s+", " ", s.strip())


def table_to_nl_statements(
    table: List[List[Optional[str]]],
    section_context: str = "",
    page_num: int = 0,
) -> List[str]:
    """
    Convert a 2-D table (list of rows) to natural language statements.

    Assumes the first row contains column headers and the first column
    contains row labels (typical financial/report table layout).
    Falls back gracefully for tables without clear headers.
    """
    if not table or len(table) < 2:
        return []

    # Extract and clean headers from first row
    raw_headers = [_clean(c) for c in table[0]]
    if all(not h for h in raw_headers):
        # No usable header row — use positional labels
        raw_headers = [f"Column {i+1}" for i in range(len(table[0]))]

    statements: List[str] = []
    ctx_prefix = f"[{section_context}] " if section_context else ""

    for row in table[1:]:
        if not row or all(_is_empty(c) for c in row):
            continue

        row_label = _clean(row[0]) if not _is_empty(row[0]) else None

        for col_idx, cell in enumerate(row[1:], start=1):
            if _is_empty(cell):
                continue

            col_header = raw_headers[col_idx] if col_idx < len(raw_headers) else f"Column {col_idx}"
            if not col_header:
                col_header = f"Column {col_idx}"

            value = _clean(cell)

            if row_label:
                stmt = f"{ctx_prefix}{row_label} — {col_header}: {value}"
            else:
                stmt = f"{ctx_prefix}{col_header}: {value}"

            statements.append(stmt)

    if statements:
        logger.debug(
            "Table on page %d → %d NL statements (section: %s)",
            page_num,
            len(statements),
            section_context or "unknown",
        )

    return statements
