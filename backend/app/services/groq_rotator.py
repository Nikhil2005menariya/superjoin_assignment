"""
Round-robin Groq API key rotator.
Each call to next_llm() returns a ChatGroq instance using the next key in cycle,
distributing load across all configured keys to multiply the effective rate limit.
"""

import itertools
import logging
from langchain_groq import ChatGroq
from app.config import get_settings

logger   = logging.getLogger(__name__)
settings = get_settings()

GROQ_MODEL = "qwen/qwen3.8-27b"


def _load_keys() -> list[str]:
    keys = []
    for raw in [settings.groq_api_key, settings.groq_api_key_2, settings.groq_api_key_3]:
        k = (raw or "").strip()
        if k:
            keys.append(k)
    if not keys:
        raise RuntimeError("No Groq API keys configured")
    logger.info("Groq key rotator: %d key(s) loaded", len(keys))
    return keys


_keys    = _load_keys()
_cycle   = itertools.cycle(_keys)
_key_idx = itertools.cycle(range(len(_keys)))


def next_llm(**kwargs) -> ChatGroq:
    """Return a ChatGroq instance using the next key in round-robin order."""
    key = next(_cycle)
    idx = next(_key_idx)
    logger.debug("Groq rotator: using key slot %d", idx + 1)
    return ChatGroq(
        model=GROQ_MODEL,
        temperature=0,
        api_key=key,
        max_tokens=700,   # stay under 1000 OTPM free-tier limit per call
        **kwargs,
    )


def next_llm_json(**kwargs) -> ChatGroq:
    """Same as next_llm but with JSON response_format pre-set."""
    return next_llm(
        model_kwargs={"response_format": {"type": "json_object"}},
        **kwargs,
    )
