"""
Phase 4 LangGraph agent: Cross-document relationship detection.

After a document's facts are indexed, this pipeline:
  1. Loads all verified facts from the new document
  2. Finds semantically similar facts from OTHER documents via Qdrant
  3. Asks Groq to classify each candidate pair as:
       CORROBORATES — same claim, compatible values
       CONTRADICTS  — same claim, incompatible values, same period/scope
       RECONCILES   — apparent conflict explained by context differences
       UNRELATED    — different claim, skip
  4. Persists non-UNRELATED relationships to SQLite

Auto-triggered by extraction_agent.persist_facts_node.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Literal, Optional, TypedDict, List

import aiosqlite
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from qdrant_client.models import Filter, FieldCondition, MatchAny, MatchValue

from app.config import get_settings
from app.database.qdrant_client import get_qdrant, COLLECTION_NAME
from app.services.groq_rotator import next_llm

logger = logging.getLogger(__name__)
settings = get_settings()

BATCH_SIZE    = 4   # pairs per Groq call
BATCH_DELAY   = 0.3
MIN_SIM_SCORE = 0.78  # minimum dense cosine similarity to consider a pair
MAX_CANDIDATES_PER_FACT = 5

SYSTEM_PROMPT = """You are a fact-comparison engine. Given two facts from different documents, classify their relationship.

CORROBORATES: Same entity and metric, compatible or identical values and time period. Both facts confirm the same claim.

CONTRADICTS: Same entity, same metric, same or overlapping time period — but materially different, irreconcilable values. One or both may be wrong, or they use incompatible definitions.

RECONCILES: Apparent conflict that can be explained by a specific, identifiable context difference:
  - Different reporting scopes (consolidated vs. standalone subsidiary)
  - Different geographies (country vs. global)
  - Different measurement methods (gross vs. net, GAAP vs. non-GAAP)
  - Different currencies without exchange rate applied
  - Different periods that partially overlap (annual vs. quarterly)

UNRELATED: The facts are about different entities, different metrics, or clearly different contexts. Do not classify — return UNRELATED.

Respond with ONLY valid JSON (no markdown):
{
  "type": "CORROBORATES" | "CONTRADICTS" | "RECONCILES" | "UNRELATED",
  "explanation": "one sentence",
  "reconciliation_context": "how to reconcile — only for RECONCILES, else null",
  "confidence": 0.0–1.0
}"""


# ─── State ────────────────────────────────────────────────────────────────────

class ComparisonState(TypedDict):
    doc_id:          str
    new_facts:       List[dict]
    candidate_pairs: List[dict]   # each: {fact_a, fact_b}
    relationships:   List[dict]
    error:           Optional[str]


# ─── helpers ──────────────────────────────────────────────────────────────────

def _fmt(fact: dict) -> str:
    parts = [f"Statement: {fact.get('statement', '')}"]
    if fact.get('subject'):   parts.append(f"Entity: {fact['subject']}")
    if fact.get('predicate'): parts.append(f"Metric: {fact['predicate']}")
    if fact.get('value_raw') and fact.get('unit_raw'):
        parts.append(f"Value: {fact['value_raw']} {fact['unit_raw']}")
    if fact.get('time_period_raw'):
        parts.append(f"Period: {fact['time_period_raw']}")
    if fact.get('scope'):     parts.append(f"Scope: {fact['scope']}")
    return " | ".join(parts)


# ─── nodes ────────────────────────────────────────────────────────────────────

async def load_new_facts_node(state: ComparisonState) -> ComparisonState:
    doc_id = state["doc_id"]
    try:
        async with aiosqlite.connect(settings.db_path) as db:
            async with db.execute(
                """SELECT id, statement, subject, predicate, value_raw, unit_raw,
                          unit_canonical, time_period_raw, time_start, time_end,
                          scope, fact_type, confidence, qdrant_point_id
                   FROM facts
                   WHERE doc_id = ? AND evidence_verified = 1
                   ORDER BY confidence DESC""",
                (doc_id,),
            ) as cur:
                rows = await cur.fetchall()

        keys = ["id", "statement", "subject", "predicate", "value_raw", "unit_raw",
                "unit_canonical", "time_period_raw", "time_start", "time_end",
                "scope", "fact_type", "confidence", "qdrant_point_id"]
        facts = [dict(zip(keys, r)) for r in rows]
        logger.info("[%s] Comparison: loaded %d verified facts", doc_id, len(facts))
        return {**state, "new_facts": facts}
    except Exception as e:
        return {**state, "error": str(e)}


async def find_candidate_pairs_node(state: ComparisonState) -> ComparisonState:
    """
    For each new fact, use Qdrant dense search to find semantically similar
    facts from other documents. Returns deduplicated candidate pairs.
    """
    doc_id    = state["doc_id"]
    new_facts = state["new_facts"]
    qdrant    = get_qdrant()
    loop      = asyncio.get_event_loop()

    if not new_facts:
        return {**state, "candidate_pairs": []}

    # Load existing facts from DB for payload lookup
    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            """SELECT id, statement, subject, predicate, value_raw, unit_raw,
                      unit_canonical, time_period_raw, time_start, time_end,
                      scope, fact_type, confidence, qdrant_point_id
               FROM facts WHERE doc_id != ? AND evidence_verified = 1""",
            (doc_id,),
        ) as cur:
            rows = await cur.fetchall()

    keys = ["id", "statement", "subject", "predicate", "value_raw", "unit_raw",
            "unit_canonical", "time_period_raw", "time_start", "time_end",
            "scope", "fact_type", "confidence", "qdrant_point_id"]
    existing_by_id = {r[0]: dict(zip(keys, r)) for r in rows}

    if not existing_by_id:
        logger.info("[%s] No existing facts to compare against", doc_id)
        return {**state, "candidate_pairs": []}

    # Filter for other-doc points in Qdrant
    other_doc_filter = Filter(
        must_not=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
    )

    seen_pairs: set[tuple[str, str]] = set()
    pairs: list[dict] = []

    from app.services.embedder import embed_texts

    # Batch embed all new fact statements
    statements = [f["statement"] for f in new_facts]
    try:
        embs = await loop.run_in_executor(None, embed_texts, statements)
    except Exception as e:
        logger.error("[%s] Embedding failed for comparison: %s", doc_id, e)
        return {**state, "candidate_pairs": []}

    for fact_a, emb in zip(new_facts, embs):
        if not emb.dense:
            continue
        try:
            results = await qdrant.search(
                collection_name=COLLECTION_NAME,
                query_vector=("dense", emb.dense),
                query_filter=other_doc_filter,
                limit=MAX_CANDIDATES_PER_FACT,
                score_threshold=MIN_SIM_SCORE,
                with_payload=True,
            )
        except Exception as e:
            logger.warning("[%s] Qdrant search error: %s", doc_id, e)
            continue

        for hit in results:
            fact_b_id = hit.payload.get("fact_id")
            if not fact_b_id or fact_b_id not in existing_by_id:
                continue

            # Canonical pair key — sorted so (A,B) == (B,A)
            key = tuple(sorted([fact_a["id"], fact_b_id]))
            if key in seen_pairs:
                continue
            seen_pairs.add(key)

            pairs.append({
                "fact_a": fact_a,
                "fact_b": existing_by_id[fact_b_id],
                "sim_score": hit.score,
            })

    logger.info("[%s] Found %d candidate pairs to classify", doc_id, len(pairs))
    return {**state, "candidate_pairs": pairs}


async def classify_relationships_node(state: ComparisonState) -> ComparisonState:
    """Send candidate pairs to Groq in batches for relationship classification."""
    doc_id = state["doc_id"]
    pairs  = state["candidate_pairs"]

    if not pairs:
        return {**state, "relationships": []}

    relationships: list[dict] = []
    total_batches = max(1, (len(pairs) + BATCH_SIZE - 1) // BATCH_SIZE)

    for bi, start in enumerate(range(0, len(pairs), BATCH_SIZE)):
        batch = pairs[start: start + BATCH_SIZE]

        user_msg = "\n\n---\n\n".join(
            f"Pair {i+1}:\nFact A: {_fmt(p['fact_a'])}\nFact B: {_fmt(p['fact_b'])}"
            for i, p in enumerate(batch)
        )
        user_msg += (
            f"\n\nRespond with a JSON array of {len(batch)} objects, one per pair, "
            f"in order: {{\"pairs\": [...]}}. Each object has type/explanation/reconciliation_context/confidence."
        )

        try:
            resp     = await next_llm(
                model_kwargs={"response_format": {"type": "json_object"}}
            ).ainvoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_msg),
            ])
            raw      = json.loads(resp.content)
            results  = raw.get("pairs", [])

            for pair, res in zip(batch, results):
                rel_type = str(res.get("type", "UNRELATED")).upper()
                if rel_type == "UNRELATED":
                    continue

                relationships.append({
                    "id":                     str(uuid.uuid4()),
                    "fact_a_id":              pair["fact_a"]["id"],
                    "fact_b_id":              pair["fact_b"]["id"],
                    "type":                   rel_type,
                    "explanation":            res.get("explanation", ""),
                    "reconciliation_context": res.get("reconciliation_context"),
                    "confidence":             float(res.get("confidence") or 0.5),
                })

        except (json.JSONDecodeError, Exception) as e:
            logger.warning("[%s] Classify batch %d error: %s", doc_id, bi, e)

        if bi < total_batches - 1:
            await asyncio.sleep(BATCH_DELAY)

    logger.info(
        "[%s] Classified %d relationships from %d pairs",
        doc_id, len(relationships), len(pairs),
    )
    return {**state, "relationships": relationships}


async def persist_relationships_node(state: ComparisonState) -> ComparisonState:
    """Write relationships to SQLite."""
    doc_id = state["doc_id"]
    rels   = state.get("relationships", [])

    if not rels:
        return state

    async with aiosqlite.connect(settings.db_path) as db:
        await db.executemany(
            """INSERT OR IGNORE INTO relationships
               (id, fact_a_id, fact_b_id, type, explanation, reconciliation_context, confidence, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            [
                (
                    r["id"], r["fact_a_id"], r["fact_b_id"],
                    r["type"], r["explanation"], r["reconciliation_context"],
                    r["confidence"], datetime.utcnow().isoformat(),
                )
                for r in rels
            ],
        )
        await db.commit()

    logger.info("[%s] Persisted %d relationships", doc_id, len(rels))
    return state


async def handle_error_node(state: ComparisonState) -> ComparisonState:
    logger.error("[%s] Comparison failed: %s", state["doc_id"], state.get("error"))
    return state


# ─── routing + graph ──────────────────────────────────────────────────────────

def route_on_error(state: ComparisonState) -> Literal["continue", "error"]:
    return "error" if state.get("error") else "continue"


def build_comparison_graph():
    g = StateGraph(ComparisonState)
    g.add_node("load_new_facts",       load_new_facts_node)
    g.add_node("find_candidates",      find_candidate_pairs_node)
    g.add_node("classify",             classify_relationships_node)
    g.add_node("persist_relationships",persist_relationships_node)
    g.add_node("handle_error",         handle_error_node)

    g.add_edge(START, "load_new_facts")
    for src, dst in [
        ("load_new_facts",  "find_candidates"),
        ("find_candidates", "classify"),
        ("classify",        "persist_relationships"),
    ]:
        g.add_conditional_edges(src, route_on_error, {
            "continue": dst, "error": "handle_error",
        })
    g.add_conditional_edges("persist_relationships", route_on_error, {
        "continue": END, "error": "handle_error",
    })
    g.add_edge("handle_error", END)
    return g.compile()


comparison_graph = build_comparison_graph()


async def run_comparison_pipeline(doc_id: str):
    logger.info("[%s] Starting Phase 4 comparison pipeline", doc_id)
    await comparison_graph.ainvoke({
        "doc_id":          doc_id,
        "new_facts":       [],
        "candidate_pairs": [],
        "relationships":   [],
        "error":           None,
    })
