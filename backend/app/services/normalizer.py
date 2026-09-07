"""
Domain-agnostic normalization layer.

Design principle: NO hardcoded currency symbols, fiscal year conventions,
unit lookup tables, or country-specific rules.

All semantic normalization (what unit is this? what fiscal year is this?)
is handled by the LLM during extraction — the LLM has world knowledge
about any domain's conventions and can handle:
  - "Crore" in an Indian report
  - "bn" in a European report
  - "Q4 FY24" in a US SaaS company (Oct-Dec)
  - "Q4 FY24" in an Indian company (Jan-Mar)
  - "£ thousand" in a UK filing
  - "MW installed capacity" in an energy report
  - "cases per 100k" in an epidemiology paper

This module only does:
  1. parse_numeric_value — strip formatting noise → float (truly universal)
  2. EntityRegistry — cosine-similarity dedup using embeddings (truly universal)
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Numeric value parsing ────────────────────────────────────────────────────
# Strips thousand separators, currency prefixes, and whitespace.
# Works for any locale's number formatting.

_FORMATTING_NOISE = re.compile(r"[^\d.\-+eE]")


def parse_numeric_value(raw: Optional[str]) -> Optional[float]:
    """
    Convert a raw value string to float.
    Handles: "21,302", "6.4%", "₹21,302", "$1.2bn", "1,234.56", "-0.3"
    Returns None if not parseable — does NOT throw.
    """
    if not raw:
        return None

    cleaned = raw.strip()

    # Handle parentheses as negative: (21,302) → -21302
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]

    # Strip everything except digits, dot, minus, plus, scientific notation
    cleaned = _FORMATTING_NOISE.sub("", cleaned)

    if not cleaned or cleaned in ("-", "+", "."):
        return None

    try:
        return float(cleaned)
    except ValueError:
        return None


# ─── Entity deduplication ────────────────────────────────────────────────────
# Uses cosine similarity on embeddings — no string-matching heuristics.
# Works equally well for "Delhivery Ltd." vs "Delhivery Limited",
# "RBI" vs "Reserve Bank of India", "Apple Inc." vs "Apple Computer",
# or any other domain's entity naming conventions.

class EntityRegistry:
    """
    Embedding-based entity deduplication.
    On first use the embedder loads lazily (models may not be ready yet).
    Falls back to exact-string dedup if embedder is unavailable.
    """

    SIMILARITY_THRESHOLD = 0.93  # cosine similarity above which two names = same entity

    def __init__(self):
        self._canonical: dict[str, list[str]] = {}   # canonical_name → [aliases]
        self._embeddings: dict[str, list[float]] = {} # canonical_name → embedding vector
        self._embedder_available = True

    def resolve(self, raw_name: Optional[str]) -> Optional[str]:
        """
        Return the canonical name for raw_name.
        Registers it as a new entity if nothing similar already exists.
        """
        if not raw_name or not raw_name.strip():
            return raw_name

        name = raw_name.strip()

        # Exact match short-circuit
        if name in self._canonical:
            return name

        # Check aliases across all canonicals
        for canon, aliases in self._canonical.items():
            if name in aliases:
                return canon

        # Embedding similarity
        if self._canonical and self._embedder_available:
            try:
                match = self._find_by_embedding(name)
                if match:
                    self._canonical[match].append(name)
                    return match
            except Exception as e:
                logger.debug("Entity embedding lookup failed: %s", e)
                self._embedder_available = False

        # New entity
        self._canonical[name] = [name]
        self._embeddings[name] = self._get_embedding(name) or []
        return name

    def _get_embedding(self, text: str) -> Optional[list[float]]:
        try:
            from app.services.embedder import embed_texts
            return embed_texts([text])[0].dense
        except Exception:
            return None

    def _find_by_embedding(self, name: str) -> Optional[str]:
        import math
        query_vec = self._get_embedding(name)
        if not query_vec or not self._embeddings:
            return None

        best_score, best_canon = 0.0, None
        qn = math.sqrt(sum(x * x for x in query_vec))

        for canon, vec in self._embeddings.items():
            if not vec:
                continue
            dot = sum(a * b for a, b in zip(query_vec, vec))
            n = math.sqrt(sum(x * x for x in vec))
            score = dot / (qn * n + 1e-9)
            if score > best_score:
                best_score, best_canon = score, canon

        return best_canon if best_score >= self.SIMILARITY_THRESHOLD else None

    def all_entities(self) -> dict[str, list[str]]:
        return dict(self._canonical)


_entity_registry = EntityRegistry()


def get_entity_registry() -> EntityRegistry:
    return _entity_registry


# ─── Fact normalization entry point ──────────────────────────────────────────
# Called after LLM extraction to post-process what the LLM returned.
# The LLM already provides: unit_canonical, value_normalized, time_start, time_end.
# We only: (a) parse value if LLM left it as a raw string, (b) resolve entity.

def normalize_fact(
    value_raw: Optional[str],
    value_normalized_llm: Optional[float],   # LLM-provided normalized value
    unit_canonical_llm: Optional[str],        # LLM-provided canonical unit
    time_start_llm: Optional[str],            # LLM-provided ISO date
    time_end_llm: Optional[str],              # LLM-provided ISO date
    subject: Optional[str],
) -> dict:
    """
    Finalize a fact's normalized fields.
    Trusts LLM outputs where present; only fills gaps with code-side logic.
    """
    # Value: prefer LLM's normalized float; fall back to parsing value_raw
    value_normalized = value_normalized_llm
    if value_normalized is None and value_raw:
        value_normalized = parse_numeric_value(value_raw)

    # Entity resolution via embeddings
    canonical_subject = _entity_registry.resolve(subject)

    return {
        "value_normalized":  value_normalized,
        "unit_canonical":    unit_canonical_llm,  # LLM owns this entirely
        "time_start":        time_start_llm,       # LLM owns this entirely
        "time_end":          time_end_llm,          # LLM owns this entirely
        "subject":           canonical_subject,
    }
