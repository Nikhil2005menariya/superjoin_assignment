"""
AWS Bedrock LLM client — boto3 direct, wrapped as a LangChain-compatible object.

langchain_aws ChatBedrock/ChatBedrockConverse both reject inference profile IDs
(e.g. global.amazon.nova-2-lite-v1:0) internally. This thin wrapper calls the
Converse API directly and exposes the same ainvoke/invoke interface the agents use.
"""

import asyncio
import logging
import os
from typing import Any, List, Optional

import boto3
from botocore.config import Config
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.config import get_settings

logger   = logging.getLogger(__name__)
settings = get_settings()

INFERENCE_PROFILE = "global.amazon.nova-2-lite-v1:0"

_BOTO_CFG = Config(retries={"max_attempts": 3, "mode": "adaptive"})


def _client():
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
        config=_BOTO_CFG,
    )


def _to_converse(messages: List[BaseMessage]) -> tuple[Optional[str], List[dict]]:
    """Split LangChain messages into Bedrock system string + messages list."""
    system_text: Optional[str] = None
    conv: List[dict] = []
    for m in messages:
        if isinstance(m, SystemMessage):
            system_text = m.content
        elif isinstance(m, HumanMessage):
            conv.append({"role": "user", "content": [{"text": m.content}]})
        elif isinstance(m, AIMessage):
            conv.append({"role": "assistant", "content": [{"text": m.content}]})
    return system_text, conv


class _BedrockChat:
    """Minimal LangChain-compatible Bedrock chat wrapper using boto3 directly."""

    def __init__(self, max_tokens: int = 1024):
        self.max_tokens = max_tokens

    @staticmethod
    def _strip_fences(text: str) -> str:
        """Strip ```json ... ``` or ``` ... ``` markdown wrappers if present."""
        t = text.strip()
        if t.startswith("```"):
            lines = t.splitlines()
            # drop first line (```json or ```) and last line (```)
            inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            t = "\n".join(inner).strip()
        return t

    def _call_sync(self, messages: List[BaseMessage]) -> AIMessage:
        system_text, conv = _to_converse(messages)
        kwargs: dict[str, Any] = dict(
            modelId=INFERENCE_PROFILE,
            messages=conv,
            inferenceConfig={"maxTokens": self.max_tokens},
        )
        if system_text:
            kwargs["system"] = [{"text": system_text}]

        c = _client()
        resp = c.converse(**kwargs)
        text = self._strip_fences(resp["output"]["message"]["content"][0]["text"])
        return AIMessage(content=text)

    async def ainvoke(self, messages: List[BaseMessage], **_) -> AIMessage:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._call_sync, messages)

    def invoke(self, messages: List[BaseMessage], **_) -> AIMessage:
        return self._call_sync(messages)


def get_llm(max_tokens: int = 5120) -> _BedrockChat:
    return _BedrockChat(max_tokens=max_tokens)


def get_llm_json(max_tokens: int = 5120) -> _BedrockChat:
    # JSON enforced via system prompt ("Return ONLY valid JSON: {...}")
    return _BedrockChat(max_tokens=max_tokens)


_VISION_PROMPT = """\
You are a chart and data extraction specialist analyzing a PDF slide or page image.

Your task: extract EVERY number, label, and data point visible in charts, graphs, \
tables, and infographics on this page.

Output format — for each visual element:

CHART: <title or description of the chart/visual>
| Metric | Value | Unit | Period | Notes |
|--------|-------|------|--------|-------|
<one row per visible data point — bars, lines, pie slices, table cells, callout numbers>
TREND: <one sentence describing direction or key takeaway>

Rules:
- Read bar heights, line points, pie percentages, axis labels, legend text, footnotes
- Include both absolute values AND percentages when shown
- If axis shows time (quarters, years) include it in the Period column
- Repeat the CHART block for every distinct chart/table on the page
- If no visual data exists on the page, output exactly: NO_VISUAL_DATA
- Do NOT skip any number. If a value is approximate, prefix with ~
"""


def vision_extract_page(image_bytes: bytes, page_context: str = "") -> str:
    """Send a rendered PDF page image to Nova Lite and extract structured chart data."""
    prompt = _VISION_PROMPT
    if page_context:
        prompt += f"\n\nPage context (from PDF text layer): {page_context[:600]}"

    content = [
        {"image": {"format": "png", "source": {"bytes": image_bytes}}},
        {"text": prompt},
    ]
    kwargs = dict(
        modelId=INFERENCE_PROFILE,
        messages=[{"role": "user", "content": content}],
        inferenceConfig={"maxTokens": 2048},
    )
    try:
        resp = _client().converse(**kwargs)
        result = resp["output"]["message"]["content"][0]["text"].strip()
        if result == "NO_VISUAL_DATA":
            return ""
        return result
    except Exception as e:
        logger.warning("Vision extraction failed: %s", e)
        return ""
