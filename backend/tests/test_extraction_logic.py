"""
Tests for extraction pipeline logic — verify+normalize+embed flow.
LLM and Qdrant are mocked so these are deterministic and fast.
"""

import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ─── Normalizer integration ───────────────────────────────────────────────────

class TestNormalizerIntegration:
    """normalize_fact with realistic inputs from any domain."""

    def test_indian_company_revenue(self):
        from app.services.normalizer import normalize_fact
        result = normalize_fact(
            value_raw="21,302",
            value_normalized_llm=21302.0,
            unit_canonical_llm="INR_CRORE",
            time_start_llm="2023-04-01",
            time_end_llm="2024-03-31",
            subject="Delhivery Limited",
        )
        assert result["unit_canonical"] == "INR_CRORE"
        assert result["value_normalized"] == pytest.approx(21302.0)
        assert result["time_start"] == "2023-04-01"

    def test_us_company_revenue(self):
        from app.services.normalizer import normalize_fact
        result = normalize_fact(
            value_raw="$383.3 billion",
            value_normalized_llm=383.3,
            unit_canonical_llm="USD_BILLION",
            time_start_llm="2023-10-01",
            time_end_llm="2024-09-30",
            subject="Apple Inc.",
        )
        assert result["unit_canonical"] == "USD_BILLION"
        assert result["value_normalized"] == pytest.approx(383.3)

    def test_gdp_growth_rate(self):
        from app.services.normalizer import normalize_fact
        result = normalize_fact(
            value_raw="6.4",
            value_normalized_llm=6.4,
            unit_canonical_llm="PERCENT",
            time_start_llm="2024-04-01",
            time_end_llm="2025-03-31",
            subject="India",
        )
        assert result["unit_canonical"] == "PERCENT"
        assert result["value_normalized"] == pytest.approx(6.4)

    def test_energy_metric(self):
        from app.services.normalizer import normalize_fact
        result = normalize_fact(
            value_raw="500 MW",
            value_normalized_llm=500.0,
            unit_canonical_llm="MW",
            time_start_llm=None,
            time_end_llm=None,
            subject="Adani Green Energy",
        )
        assert result["unit_canonical"] == "MW"

    def test_entity_resolved_consistently(self):
        from app.services.normalizer import get_entity_registry
        reg = get_entity_registry()
        c1 = reg.resolve("Reserve Bank of India")
        c2 = reg.resolve("Reserve Bank of India")
        assert c1 == c2

    def test_fallback_parsing_when_llm_omits_value(self):
        from app.services.normalizer import normalize_fact
        result = normalize_fact(
            value_raw="6.4",
            value_normalized_llm=None,
            unit_canonical_llm="PERCENT",
            time_start_llm=None,
            time_end_llm=None,
            subject="GDP",
        )
        assert result["value_normalized"] == pytest.approx(6.4)


# ─── Evidence verifier integration ───────────────────────────────────────────

class TestEvidenceVerifierIntegration:
    """Realistic document texts from any domain."""

    def test_monetary_policy_fact_verified(self):
        from app.services.evidence_verifier import verify_evidence
        chunk = (
            "The Monetary Policy Committee (MPC) kept the repo rate unchanged at 6.50 per cent "
            "during 2024-25. Headline CPI inflation moderated to 4.6 per cent in FY25 from "
            "5.4 per cent in FY24."
        )
        ok, s, e, score = verify_evidence("repo rate unchanged at 6.50 per cent", chunk)
        assert ok is True
        assert score >= 90

    def test_hallucinated_number_rejected(self):
        from app.services.evidence_verifier import verify_evidence
        chunk = "Revenue was ₹21,302 Crore in FY24."
        ok, _, _, _ = verify_evidence("Revenue was ₹99,999 Crore in FY24", chunk)
        assert ok is False

    def test_gdp_projection_verified(self):
        from app.services.evidence_verifier import verify_evidence
        chunk = (
            "India's real GDP growth is projected at 6.2 percent in 2025 "
            "and 6.3 percent in 2026 under the IMF baseline."
        )
        ok, _, _, _ = verify_evidence("GDP growth is projected at 6.2 percent in 2025", chunk)
        assert ok is True

    def test_tech_company_earnings_verified(self):
        from app.services.evidence_verifier import verify_evidence
        chunk = "Apple reported net income of $93.7 billion for fiscal year 2024."
        ok, _, _, score = verify_evidence("net income of $93.7 billion for fiscal year 2024", chunk)
        assert ok is True

    def test_short_quote_auto_verified(self):
        from app.services.evidence_verifier import verify_evidence
        ok, _, _, score = verify_evidence("6.4%", "GDP growth was 6.4%")
        assert ok is True  # short quotes auto-verify


# ─── Extraction pipeline state machine ───────────────────────────────────────

class TestExtractionStateMachine:

    @pytest.mark.asyncio
    async def test_load_chunks_node_empty_doc(self):
        """load_chunks_node should return empty list for doc with no chunks."""
        from app.agents.extraction_agent import load_chunks_node

        with patch("app.agents.extraction_agent.aiosqlite.connect") as mock_connect:
            # Build the cursor mock
            mock_cursor = AsyncMock()
            mock_cursor.fetchall.return_value = []

            # aiosqlite db.execute() is a sync call returning an async context manager.
            # Use MagicMock (not AsyncMock) so calling it returns the cm directly.
            exec_cm = MagicMock()
            exec_cm.__aenter__ = AsyncMock(return_value=mock_cursor)
            exec_cm.__aexit__ = AsyncMock(return_value=False)

            mock_db = AsyncMock()
            mock_db.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db.__aexit__ = AsyncMock(return_value=False)
            mock_db.execute = MagicMock(return_value=exec_cm)

            mock_connect.return_value = mock_db

            with patch("app.agents.extraction_agent._update_job", new_callable=AsyncMock):
                state = await load_chunks_node({
                    "doc_id":    "test-doc",
                    "job_id":    "test-job",
                    "chunks":    [],
                    "raw_facts": [],
                    "facts":     [],
                    "progress":  0,
                    "error":     None,
                })

        assert state["chunks"] == []
        assert state["error"] is None

    @pytest.mark.asyncio
    async def test_verify_normalize_filters_empty_statements(self):
        """Facts with empty statement are dropped during verify+normalize."""
        from app.agents.extraction_agent import verify_normalize_node

        raw_facts = [
            # empty statement → should be dropped
            {
                "statement": "",
                "exact_quote": "x",
                "_chunk_ids": [],
                "confidence": 0.9,
            },
            # valid fact with LLM-provided canonical fields
            {
                "statement":        "GDP was 6.4%",
                "exact_quote":      "GDP was 6.4%",
                "_chunk_ids":       [],
                "confidence":       0.9,
                "value_raw":        "6.4",
                "unit_raw":         "%",
                "unit_canonical":   "PERCENT",
                "value_normalized": 6.4,
                "time_period_raw":  "FY25",
                "time_start":       "2024-04-01",
                "time_end":         "2025-03-31",
                "subject":          "India",
                "predicate":        "GDP growth rate",
                "scope":            None,
                "qualifier":        None,
                "fact_type":        "numerical",
            },
        ]

        state = await verify_normalize_node({
            "doc_id":    "test-doc",
            "job_id":    "test-job",
            "chunks":    [],
            "raw_facts": raw_facts,
            "facts":     [],
            "progress":  80,
            "error":     None,
        })

        assert all(f["statement"] for f in state["facts"])
        assert len(state["facts"]) == 1

    @pytest.mark.asyncio
    async def test_persist_facts_node_writes_to_db(self):
        """persist_facts_node should INSERT facts and update document status."""
        from app.agents.extraction_agent import persist_facts_node

        fake_fact = {
            "id":               str(uuid.uuid4()),
            "doc_id":           "doc-123",
            "chunk_id":         None,
            "statement":        "Revenue was $100 million in FY2024",
            "subject":          "Acme Corp",
            "predicate":        "revenue",
            "metric":           "revenue",
            "value_raw":        "100",
            "value_normalized": 100.0,
            "unit_raw":         "million",
            "unit_canonical":   "USD_MILLION",
            "time_period_raw":  "FY2024",
            "time_start":       "2023-01-01",
            "time_end":         "2023-12-31",
            "scope":            "consolidated",
            "qualifier":        None,
            "fact_type":        "numerical",
            "confidence":       0.92,
            "evidence_verified":True,
            "exact_quote":      "Revenue was $100 million",
            "quote_start":      0,
            "quote_end":        25,
            "qdrant_point_id":  str(uuid.uuid4()),
            "attributes":       {},
        }

        with patch("app.agents.extraction_agent.aiosqlite.connect") as mock_connect, \
             patch("app.agents.extraction_agent._update_doc", new_callable=AsyncMock), \
             patch("app.agents.extraction_agent._update_job", new_callable=AsyncMock):

            mock_db = AsyncMock()
            mock_db.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db.__aexit__ = AsyncMock(return_value=False)
            mock_db.executemany = AsyncMock()
            mock_db.commit = AsyncMock()
            mock_connect.return_value = mock_db

            result = await persist_facts_node({
                "doc_id":    "doc-123",
                "job_id":    "job-123",
                "chunks":    [],
                "raw_facts": [],
                "facts":     [fake_fact],
                "progress":  99,
                "error":     None,
            })

        mock_db.executemany.assert_called_once()
        mock_db.commit.assert_called_once()
        assert result["progress"] == 100
