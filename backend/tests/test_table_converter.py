"""
Unit tests for the deterministic table → NL converter.
"""

import pytest
from app.services.table_converter import table_to_nl_statements


class TestTableToNL:
    def test_basic_financial_table(self):
        table = [
            ["Metric",         "Q4 FY22", "Q4 FY23", "Q4 FY24"],
            ["Pin-code reach", "18,074",  "18,540",  "18,793"],
            ["Team size",      "60,373",  "57,307",  "63,713"],
        ]
        stmts = table_to_nl_statements(table, section_context="Operating Metrics")
        assert len(stmts) == 6  # 2 rows × 3 value columns
        assert any("18,793" in s for s in stmts)
        assert any("Q4 FY24" in s for s in stmts)
        assert any("Pin-code reach" in s for s in stmts)

    def test_single_row(self):
        table = [
            ["Period", "FY24"],
            ["Revenue", "21302"],
        ]
        stmts = table_to_nl_statements(table)
        assert len(stmts) == 1
        assert "21302" in stmts[0]

    def test_empty_cells_skipped(self):
        table = [
            ["Item",   "Value"],
            ["A",      "100"],
            ["B",      ""],
            ["C",      None],
        ]
        stmts = table_to_nl_statements(table)
        assert len(stmts) == 1  # only row A has a value
        assert "100" in stmts[0]

    def test_all_empty_table(self):
        table = [["H1", "H2"], [None, None], ["", ""]]
        stmts = table_to_nl_statements(table)
        assert stmts == []

    def test_too_short_table(self):
        stmts = table_to_nl_statements([["only header"]])
        assert stmts == []

    def test_context_prefix_included(self):
        table = [["Col"], ["Val", "42"]]
        stmts = table_to_nl_statements(table, section_context="Balance Sheet")
        assert all("Balance Sheet" in s for s in stmts)

    def test_no_row_label(self):
        table = [
            [None,  "2023", "2024"],
            [None,  "100",  "200"],
        ]
        stmts = table_to_nl_statements(table)
        assert len(stmts) >= 1
