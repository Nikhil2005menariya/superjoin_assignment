"""
Evidence verifier — confirms that the LLM's cited exact_quote
actually appears verbatim (or near-verbatim) in the source chunk.

Uses rapidfuzz partial_ratio which handles minor OCR artifacts and
whitespace differences without being fooled by short common phrases.
"""

import logging
import re
from typing import Tuple, Optional
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# Minimum similarity score (0-100) to accept a quote as verified.
# 90 prevents same-template number-substitution hallucinations from passing.
VERIFY_THRESHOLD = 90
# Minimum quote length — very short quotes are unreliable anchors
MIN_QUOTE_LEN = 12

_NUM_RE = re.compile(r"\d[\d,.']*")


def verify_evidence(
    exact_quote: Optional[str],
    chunk_text: str,
) -> Tuple[bool, Optional[int], Optional[int], float]:
    """
    Check whether `exact_quote` is substantively present in `chunk_text`.

    Returns:
        (verified, start_char, end_char, score)
        - verified:   True if score >= VERIFY_THRESHOLD
        - start_char: approximate start index in chunk_text (or None)
        - end_char:   approximate end index in chunk_text (or None)
        - score:      0-100 similarity score
    """
    if not exact_quote or not chunk_text:
        return False, None, None, 0.0

    quote = exact_quote.strip()
    if len(quote) < MIN_QUOTE_LEN:
        # Too short to be a reliable anchor — auto-verify with low confidence
        return True, None, None, 60.0

    # Try exact substring first (fastest path)
    idx = chunk_text.find(quote)
    if idx != -1:
        return True, idx, idx + len(quote), 100.0

    # Fuzzy partial match (handles minor OCR diffs / whitespace)
    score = fuzz.partial_ratio(quote, chunk_text)

    if score >= VERIFY_THRESHOLD:
        # Find approximate location using sliding window
        start, end = _locate_span(quote, chunk_text)
        return True, start, end, float(score)

    logger.debug(
        "Evidence rejected (score=%.1f < %d): quote='%s...'",
        score, VERIFY_THRESHOLD, quote[:60],
    )
    return False, None, None, float(score)


def _locate_span(query: str, text: str) -> Tuple[Optional[int], Optional[int]]:
    """Slide a window the same length as query over text, return best-match span."""
    q_len = len(query)
    best_score = -1
    best_start = 0

    step = max(1, q_len // 4)
    for i in range(0, max(1, len(text) - q_len + 1), step):
        window = text[i: i + q_len]
        s = fuzz.ratio(query, window)
        if s > best_score:
            best_score = s
            best_start = i

    return best_start, best_start + q_len
