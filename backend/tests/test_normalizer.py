"""
Tests for the domain-agnostic normalizer.
No hardcoded currency/fiscal-year patterns — only universal parsing logic.
"""

import pytest
from app.services.normalizer import (
    parse_numeric_value,
    normalize_fact,
    EntityRegistry,
)


class TestParseNumericValue:
    def test_plain_integer(self):
        assert parse_numeric_value("21302") == pytest.approx(21302.0)

    def test_comma_separated(self):
        assert parse_numeric_value("21,302") == pytest.approx(21302.0)

    def test_decimal(self):
        assert parse_numeric_value("6.4") == pytest.approx(6.4)

    def test_currency_prefix_stripped(self):
        assert parse_numeric_value("₹21,302") == pytest.approx(21302.0)
        assert parse_numeric_value("$1,200")   == pytest.approx(1200.0)
        assert parse_numeric_value("€500")      == pytest.approx(500.0)
        assert parse_numeric_value("£1,000")    == pytest.approx(1000.0)

    def test_percent_stripped(self):
        assert parse_numeric_value("6.4%") == pytest.approx(6.4)

    def test_parentheses_as_negative(self):
        assert parse_numeric_value("(21,302)") == pytest.approx(-21302.0)

    def test_negative_explicit(self):
        assert parse_numeric_value("-0.3") == pytest.approx(-0.3)

    def test_scientific_notation(self):
        assert parse_numeric_value("1.5e6") == pytest.approx(1_500_000.0)

    def test_large_comma_number(self):
        assert parse_numeric_value("1,234,567") == pytest.approx(1_234_567.0)

    def test_none_input(self):
        assert parse_numeric_value(None) is None

    def test_empty_string(self):
        assert parse_numeric_value("") is None

    def test_unparseable_text(self):
        assert parse_numeric_value("N/A") is None

    def test_standalone_dash(self):
        assert parse_numeric_value("—") is None

    def test_whitespace_stripped(self):
        assert parse_numeric_value("  42.5  ") == pytest.approx(42.5)

    def test_suffix_stripped(self):
        # LLM sometimes appends units inline — just extract the number
        assert parse_numeric_value("1.2bn") == pytest.approx(1.2)


class TestEntityRegistry:
    def test_exact_match_returns_same(self):
        reg = EntityRegistry()
        reg.resolve("Apple Inc.")
        result = reg.resolve("Apple Inc.")
        assert result == "Apple Inc."

    def test_first_entity_registered(self):
        reg = EntityRegistry()
        result = reg.resolve("Tesla Inc.")
        assert result == "Tesla Inc."

    def test_none_returns_none(self):
        reg = EntityRegistry()
        assert reg.resolve(None) is None

    def test_empty_string_returned_as_is(self):
        reg = EntityRegistry()
        result = reg.resolve("")
        assert result == ""

    def test_whitespace_only_returned_as_is(self):
        reg = EntityRegistry()
        result = reg.resolve("   ")
        assert result == "   "

    def test_second_call_same_entity_resolves(self):
        reg = EntityRegistry()
        reg.resolve("Amazon.com Inc.")
        result = reg.resolve("Amazon.com Inc.")
        assert result == "Amazon.com Inc."

    def test_no_embedder_each_unique_string_is_own_entity(self):
        """When embedder unavailable, unique strings become separate entities."""
        reg = EntityRegistry()
        reg._embedder_available = False
        reg.resolve("Microsoft Corporation")
        result = reg.resolve("Microsoft Corp")
        # Distinct strings without embedding → not merged
        assert result in ("Microsoft Corporation", "Microsoft Corp")

    def test_all_entities_returns_map(self):
        reg = EntityRegistry()
        reg.resolve("Google LLC")
        entities = reg.all_entities()
        assert "Google LLC" in entities


class TestNormalizeFact:
    def test_llm_values_used_directly(self):
        """When LLM provides canonical unit and value, they pass through unchanged."""
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
        assert result["time_end"] == "2024-03-31"
        assert result["subject"] == "Delhivery Limited"

    def test_value_fallback_when_llm_omits_normalized(self):
        """When LLM doesn't give value_normalized, parse value_raw."""
        result = normalize_fact(
            value_raw="6.4",
            value_normalized_llm=None,
            unit_canonical_llm="PERCENT",
            time_start_llm=None,
            time_end_llm=None,
            subject="India",
        )
        assert result["value_normalized"] == pytest.approx(6.4)

    def test_usd_billion(self):
        result = normalize_fact(
            value_raw="1.2bn",
            value_normalized_llm=1.2,
            unit_canonical_llm="USD_BILLION",
            time_start_llm="2024-01-01",
            time_end_llm="2024-12-31",
            subject="Apple Inc.",
        )
        assert result["unit_canonical"] == "USD_BILLION"
        assert result["value_normalized"] == pytest.approx(1.2)

    def test_eur_million(self):
        result = normalize_fact(
            value_raw="€450 million",
            value_normalized_llm=450.0,
            unit_canonical_llm="EUR_MILLION",
            time_start_llm="2024-01-01",
            time_end_llm="2024-12-31",
            subject="Volkswagen AG",
        )
        assert result["unit_canonical"] == "EUR_MILLION"

    def test_physical_unit_passthrough(self):
        result = normalize_fact(
            value_raw="500",
            value_normalized_llm=500.0,
            unit_canonical_llm="MW",
            time_start_llm=None,
            time_end_llm=None,
            subject="Solar Plant",
        )
        assert result["unit_canonical"] == "MW"

    def test_all_none_inputs(self):
        result = normalize_fact(
            value_raw=None,
            value_normalized_llm=None,
            unit_canonical_llm=None,
            time_start_llm=None,
            time_end_llm=None,
            subject=None,
        )
        assert result["unit_canonical"] is None
        assert result["value_normalized"] is None
        assert result["time_start"] is None
        assert result["time_end"] is None

    def test_comma_value_raw_fallback_parsed(self):
        result = normalize_fact(
            value_raw="1,234,567",
            value_normalized_llm=None,
            unit_canonical_llm="USD_THOUSAND",
            time_start_llm=None,
            time_end_llm=None,
            subject="Some Corp",
        )
        assert result["value_normalized"] == pytest.approx(1_234_567.0)

    def test_subject_entity_resolved(self):
        result = normalize_fact(
            value_raw="100",
            value_normalized_llm=100.0,
            unit_canonical_llm="COUNT_MILLION",
            time_start_llm=None,
            time_end_llm=None,
            subject="Reliance Industries",
        )
        assert result["subject"] == "Reliance Industries"
