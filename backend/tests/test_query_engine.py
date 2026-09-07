"""Tests for query_engine.py — grounded NL answer engine."""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.query_engine import _build_facts_context, _load_facts_by_ids, answer_query


# ─── _build_facts_context ────────────────────────────────────────────────────

def _make_fact(**kwargs) -> dict:
    defaults = dict(
        id="f1", doc_id="d1", statement="Revenue was $10B",
        subject="Company A", predicate="had revenue", value_raw="10",
        unit_raw="USD billion", unit_canonical="USD_BILLION",
        time_period_raw="FY2023", time_start="2023-01-01", time_end="2023-12-31",
        scope="consolidated", qualifier=None, fact_type="financial_metric",
        confidence=0.92, evidence_verified=True,
        exact_quote="Total revenue reached $10 billion for fiscal year 2023.",
    )
    defaults.update(kwargs)
    return defaults


class TestBuildFactsContext:
    def test_single_fact_includes_statement(self):
        ctx = _build_facts_context([_make_fact()])
        assert "Revenue was $10B" in ctx

    def test_includes_quote(self):
        ctx = _build_facts_context([_make_fact()])
        assert "Total revenue reached" in ctx

    def test_includes_time_period(self):
        ctx = _make_fact()
        ctx_str = _build_facts_context([ctx])
        assert "FY2023" in ctx_str

    def test_includes_scope(self):
        ctx_str = _build_facts_context([_make_fact()])
        assert "consolidated" in ctx_str

    def test_fact_numbered(self):
        facts = [_make_fact(statement=f"Fact {i}", exact_quote=None, time_period_raw=None, scope=None) for i in range(3)]
        ctx = _build_facts_context(facts)
        assert "[1]" in ctx
        assert "[2]" in ctx
        assert "[3]" in ctx

    def test_missing_quote_no_error(self):
        f = _make_fact(exact_quote=None)
        ctx = _build_facts_context([f])
        assert "Source quote" not in ctx

    def test_empty_list(self):
        assert _build_facts_context([]) == ""


# ─── _load_facts_by_ids ──────────────────────────────────────────────────────

FACT_KEYS = [
    "id", "doc_id", "statement", "subject", "predicate",
    "value_raw", "unit_raw", "unit_canonical",
    "time_period_raw", "time_start", "time_end", "scope",
    "qualifier", "fact_type", "confidence",
    "evidence_verified", "exact_quote",
]


def _mock_db_context(rows):
    """Build a mock aiosqlite context manager that returns given rows."""
    cursor = MagicMock()
    cursor.fetchall = AsyncMock(return_value=rows)

    exec_cm = MagicMock()
    exec_cm.__aenter__ = AsyncMock(return_value=cursor)
    exec_cm.__aexit__ = AsyncMock(return_value=False)

    db = MagicMock()
    db.execute = MagicMock(return_value=exec_cm)

    db_cm = MagicMock()
    db_cm.__aenter__ = AsyncMock(return_value=db)
    db_cm.__aexit__ = AsyncMock(return_value=False)
    return db_cm


@pytest.mark.asyncio
async def test_load_facts_empty_ids():
    result = await _load_facts_by_ids([])
    assert result == []


@pytest.mark.asyncio
async def test_load_facts_returns_dicts():
    row = tuple(["val"] * len(FACT_KEYS))
    db_cm = _mock_db_context([row])
    with patch("app.services.query_engine.aiosqlite.connect", return_value=db_cm):
        result = await _load_facts_by_ids(["fact-1"])
    assert isinstance(result, list)
    assert result[0]["id"] == "val"
    assert result[0]["statement"] == "val"


@pytest.mark.asyncio
async def test_load_facts_multiple_ids():
    row = tuple(["x"] * len(FACT_KEYS))
    rows = [row, row]
    db_cm = _mock_db_context(rows)
    with patch("app.services.query_engine.aiosqlite.connect", return_value=db_cm):
        result = await _load_facts_by_ids(["f1", "f2"])
    assert len(result) == 2


# ─── answer_query ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_answer_query_no_hits():
    with patch("app.services.query_engine.hybrid_search", new_callable=AsyncMock, return_value=[]):
        result = await answer_query("What is revenue?")
    assert result["confidence"] == "LOW"
    assert "No verified facts" in result["answer"]


@pytest.mark.asyncio
async def test_answer_query_groq_synthesis():
    hits = [{"fact_id": "f1", "score": 0.9, "retrieval": "colbert_hybrid"}]
    fact_row = tuple(["f1", "d1", "Revenue was $10B", "Company A", "had revenue",
                      "10", "USD billion", "USD_BILLION",
                      "FY2023", "2023-01-01", "2023-12-31", "consolidated",
                      None, "financial_metric", 0.92, 1,
                      "Total revenue reached $10 billion."])

    db_cm = _mock_db_context([fact_row])
    mock_llm_resp = MagicMock()
    mock_llm_resp.content = "Revenue was $10B in FY2023.\n\nCONFIDENCE: HIGH"

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_resp)

    with (
        patch("app.services.query_engine.hybrid_search", new_callable=AsyncMock, return_value=hits),
        patch("app.services.query_engine.aiosqlite.connect", return_value=db_cm),
        patch("app.services.query_engine.ChatGroq", return_value=mock_llm),
    ):
        result = await answer_query("What is revenue?")

    assert "Revenue" in result["answer"]
    assert result["confidence"] == "HIGH"
    assert len(result["source_facts"]) == 1
    assert result["retrieval_meta"]["hits"] == 1
    assert result["retrieval_meta"]["used"] == 1
    assert result["retrieval_meta"]["method"] == "colbert_hybrid"


@pytest.mark.asyncio
async def test_answer_query_groq_failure_returns_fallback():
    hits = [{"fact_id": "f1", "score": 0.9, "retrieval": "dense"}]
    fact_row = tuple(["f1", "d1", "Revenue was $10B", None, None,
                      None, None, None, None, None, None, None,
                      None, "financial_metric", 0.8, 1, None])

    db_cm = _mock_db_context([fact_row])
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=Exception("Groq rate limit"))

    with (
        patch("app.services.query_engine.hybrid_search", new_callable=AsyncMock, return_value=hits),
        patch("app.services.query_engine.aiosqlite.connect", return_value=db_cm),
        patch("app.services.query_engine.ChatGroq", return_value=mock_llm),
    ):
        result = await answer_query("What is revenue?")

    assert result["confidence"] == "LOW"
    assert result["caveat"] is not None
    assert len(result["source_facts"]) == 1


@pytest.mark.asyncio
async def test_answer_query_medium_confidence_default():
    hits = [{"fact_id": "f1", "score": 0.88, "retrieval": "dense"}]
    fact_row = tuple(["f1", "d1", "Headcount is 5000", None, None,
                      None, None, None, None, None, None, None,
                      None, "operational", 0.75, 1, None])

    db_cm = _mock_db_context([fact_row])
    mock_llm_resp = MagicMock()
    # No CONFIDENCE tag → should default to MEDIUM
    mock_llm_resp.content = "The company has 5000 employees."

    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_llm_resp)

    with (
        patch("app.services.query_engine.hybrid_search", new_callable=AsyncMock, return_value=hits),
        patch("app.services.query_engine.aiosqlite.connect", return_value=db_cm),
        patch("app.services.query_engine.ChatGroq", return_value=mock_llm),
    ):
        result = await answer_query("How many employees?")

    assert result["confidence"] == "MEDIUM"
