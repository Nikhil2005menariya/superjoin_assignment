"""
Unified LLM client — switches between AWS Bedrock and Groq via LLM_PROVIDER env var.

Set LLM_PROVIDER=bedrock  → Amazon Nova Lite (no rate limits, pay-per-token)
Set LLM_PROVIDER=groq     → qwen/qwen3.8-27b with 3-key rotation (free tier)

Default: groq (works immediately; switch to bedrock once AWS account is verified)
"""

import itertools
import logging
import os

from langchain_core.language_models import BaseChatModel
from app.config import get_settings

logger   = logging.getLogger(__name__)
settings = get_settings()

PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()

# ─── Groq rotator ─────────────────────────────────────────────────────────────

GROQ_MODEL = "qwen/qwen3.8-27b"

def _groq_keys() -> list[str]:
    keys = []
    for k in [settings.groq_api_key, settings.groq_api_key_2, settings.groq_api_key_3]:
        v = (k or "").strip()
        if v:
            keys.append(v)
    if not keys:
        raise RuntimeError("No Groq API keys configured")
    logger.info("Groq rotator: %d key(s) loaded", len(keys))
    return keys

_groq_cycle = None

def _next_groq_key() -> str:
    global _groq_cycle
    if _groq_cycle is None:
        _groq_cycle = itertools.cycle(_groq_keys())
    return next(_groq_cycle)


def _make_groq(json_mode: bool = False) -> BaseChatModel:
    from langchain_groq import ChatGroq
    kwargs: dict = dict(
        model=GROQ_MODEL,
        temperature=0,
        api_key=_next_groq_key(),
        max_tokens=700,
    )
    if json_mode:
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
    return ChatGroq(**kwargs)


# ─── Bedrock ──────────────────────────────────────────────────────────────────

BEDROCK_MODEL = "global.amazon.nova-2-lite-v1:0"  # Nova 2 Lite global inference profile, 8M TPM approved

def _make_bedrock(json_mode: bool = False) -> BaseChatModel:
    from app.services.bedrock_client import get_llm_json, get_llm
    return get_llm_json() if json_mode else get_llm()


# ─── Public API ───────────────────────────────────────────────────────────────

def get_llm() -> BaseChatModel:
    if PROVIDER == "bedrock":
        logger.debug("LLM: Bedrock Nova Lite")
        return _make_bedrock(json_mode=False)
    logger.debug("LLM: Groq %s", GROQ_MODEL)
    return _make_groq(json_mode=False)


def get_llm_json() -> BaseChatModel:
    if PROVIDER == "bedrock":
        logger.debug("LLM: Bedrock Nova Lite (JSON)")
        return _make_bedrock(json_mode=True)
    logger.debug("LLM: Groq %s (JSON)", GROQ_MODEL)
    return _make_groq(json_mode=True)
