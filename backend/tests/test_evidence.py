"""
Unit tests for the evidence verifier.
"""

import pytest
from app.services.evidence_verifier import verify_evidence


CHUNK_TEXT = (
    "Delhivery reported revenue of ₹21,302 Crore for FY2024, "
    "representing a growth of 12.5 per cent year-on-year. "
    "The company's EBITDA margin improved to 4.2 per cent in Q4 FY24. "
    "As of March 31, 2024, Delhivery served 18,793 pin codes across India."
)


class TestVerifyEvidence:
    def test_exact_match(self):
        ok, s, e, score = verify_evidence("revenue of ₹21,302 Crore for FY2024", CHUNK_TEXT)
        assert ok is True
        assert score == 100.0
        assert s is not None

    def test_near_match_whitespace_diff(self):
        ok, _, _, score = verify_evidence("18,793 pin codes  across India", CHUNK_TEXT)
        assert ok is True
        assert score >= 78

    def test_fabricated_quote_rejected(self):
        ok, _, _, score = verify_evidence(
            "Delhivery acquired 50 companies in FY2025 for a total of ₹500 billion",
            CHUNK_TEXT,
        )
        assert ok is False

    def test_very_short_quote_auto_verified(self):
        # < MIN_QUOTE_LEN → auto-verified with low confidence
        ok, _, _, score = verify_evidence("4.2", CHUNK_TEXT)
        assert ok is True

    def test_none_quote(self):
        ok, _, _, score = verify_evidence(None, CHUNK_TEXT)
        assert ok is False
        assert score == 0.0

    def test_empty_chunk(self):
        ok, _, _, score = verify_evidence("some quote", "")
        assert ok is False

    def test_span_returned_for_exact(self):
        quote = "EBITDA margin improved to 4.2 per cent"
        ok, s, e, _ = verify_evidence(quote, CHUNK_TEXT)
        assert ok is True
        assert s is not None
        assert e is not None
        assert e > s
