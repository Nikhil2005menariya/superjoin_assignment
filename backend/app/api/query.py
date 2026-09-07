"""
Query API — natural-language question answering grounded in the fact knowledge layer.
"""

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.query_engine import answer_query

logger = logging.getLogger(__name__)
router = APIRouter()


class QueryRequest(BaseModel):
    question: str  = Field(..., min_length=3, max_length=1000)
    doc_id:   Optional[str] = None
    limit:    int  = Field(12, ge=1, le=30)


@router.post("/query")
async def query_knowledge_layer(req: QueryRequest):
    """
    Answer a natural-language question using verified facts from uploaded documents.

    The system:
      1. Retrieves the most relevant facts (BM25 + dense + ColBERT rerank)
      2. Grounds Groq's answer strictly to those facts — no parametric hallucination
      3. Returns the synthesized answer alongside the source facts with evidence quotes
    """
    return await answer_query(
        question=req.question,
        doc_id=req.doc_id,
        limit=req.limit,
    )


@router.get("/query/examples")
async def query_examples():
    """Return example questions to help users get started."""
    return [
        "What was the company's total revenue last fiscal year?",
        "Which documents contain contradicting figures for the same metric?",
        "What are the key growth metrics mentioned across all documents?",
        "What time periods are covered by the uploaded documents?",
        "Are there any facts about profit margins or EBITDA?",
        "What entities are mentioned most frequently across all documents?",
        "Which facts have the highest confidence scores?",
        "Are there any facts about headcount or employee numbers?",
    ]
