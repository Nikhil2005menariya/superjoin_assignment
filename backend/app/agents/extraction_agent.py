"""
Phase 2 LangGraph agent: Fact Extraction — rolling pipeline.

Graph:
  START → load_chunks → rolling_extract_embed → persist_facts → END
  Any node → handle_error → END on failure.

Rolling pipeline: each extraction batch is immediately verified, normalized,
embedded (dense + BM25 + ColBERT), and upserted to Qdrant — no waiting for
all batches to complete before embedding starts.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Literal, Optional, List, TypedDict

import aiosqlite
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from qdrant_client.models import PointStruct, SparseVector

from app.agents.state import DocumentState
from app.config import get_settings
from app.database.qdrant_client import get_qdrant, COLLECTION_NAME
from app.services.evidence_verifier import verify_evidence
from app.services.normalizer import normalize_fact
from app.services.llm_client import get_llm_json

logger   = logging.getLogger(__name__)
settings = get_settings()

BATCH_SIZE  = 3    # chunks per LLM call — smaller = less truncation risk
BATCH_DELAY = 0.05
EMBED_BATCH = 8    # facts per embedding call
UPSERT_BATCH = 50  # Qdrant upsert batch size — avoids WriteTimeout

SYSTEM_PROMPT = """You are a precise, domain-agnostic fact extraction engine.
Extract every specific, verifiable claim from the text given by the user.

A qualifying claim:
- Names a concrete entity (person, org, place, product, metric, economic indicator, etc.)
- States something specific and checkable about that entity
- Is EXPLICITLY stated — never inferred or implied

For each fact return these fields (use null for missing/unknown):
  statement       : one clear, self-contained declarative sentence
  exact_quote     : shortest verbatim substring proving this fact (word-for-word)
  subject         : the primary entity this fact is about — use the full official name (e.g. "Apple Inc." not "Apple", "Reserve Bank of India" not "RBI")
  predicate       : what is being claimed (e.g. "revenue", "net profit margin", "chairperson of", "headquarters in")
  value_raw       : the value exactly as written in the text (number, name, date, etc.)
  unit_raw        : unit exactly as written (%, Crore, million, USD, EUR, MW, kg, etc.)
  unit_canonical  : standardized unit code — use CURRENCY_SCALE for money (e.g. USD_MILLION, EUR_BILLION, INR_CRORE, GBP_THOUSAND, JPY_BILLION), PERCENT for %, COUNT_THOUSAND / COUNT_MILLION / COUNT_BILLION for plain counts, or the raw unit for physical/domain units (MW, MT, km, cases_per_100k, etc.). Use UNKNOWN if unclear.
  value_normalized: the numeric value converted to the canonical unit as a float (null if not applicable)
  time_period_raw : time reference exactly as written (FY24, Q4 2024, H1 2023, 2024-25, etc.)
  time_start      : ISO 8601 start date of the time period (YYYY-MM-DD). Infer from document context — e.g. if this is an Indian company FY24 = 2023-04-01; if US corporate FY24 = 2023-01-01; null if unknown.
  time_end        : ISO 8601 end date of the time period (YYYY-MM-DD). E.g. Indian FY24 = 2024-03-31. null if unknown.
  scope           : geographic/org scope (national, consolidated, standalone, segment name, global, etc.)
  qualifier       : any conditions or caveats
  fact_type       : "numerical" | "semantic" | "relational"
  confidence      : 0.0–1.0 — lower if value is ambiguous or context is incomplete

Return ONLY valid JSON: {"facts": [...]}. Empty text → {"facts": []}."""


# ─── helpers ──────────────────────────────────────────────────────────────────

async def _update_job(job_id: str, **kwargs):
    kwargs["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [job_id]
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(f"UPDATE jobs SET {set_clause} WHERE id = ?", values)
        await db.commit()


async def _update_doc(doc_id: str, status: str):
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "UPDATE documents SET status=?, updated_at=? WHERE id=?",
            (status, datetime.utcnow().isoformat(), doc_id),
        )
        await db.commit()


def _verify_and_normalize(raw_facts: list[dict], chunk_map: dict[str, str], doc_id: str) -> list[dict]:
    verified: list[dict] = []
    for rf in raw_facts:
        statement = (rf.get("statement") or "").strip()
        if not statement:
            continue

        exact_quote = rf.get("exact_quote") or ""
        chunk_ids   = rf.get("_chunk_ids", [])

        ev_verified, ev_start, ev_end, ev_score = False, None, None, 0.0
        matched_chunk_id = None
        for cid in chunk_ids:
            ok, s, e, sc = verify_evidence(exact_quote, chunk_map.get(cid, ""))
            if ok and sc > ev_score:
                ev_verified, ev_start, ev_end, ev_score = ok, s, e, sc
                matched_chunk_id = cid

        norm = normalize_fact(
            value_raw            = rf.get("value_raw"),
            value_normalized_llm = rf.get("value_normalized"),
            unit_canonical_llm   = rf.get("unit_canonical"),
            time_start_llm       = rf.get("time_start"),
            time_end_llm         = rf.get("time_end"),
            subject              = rf.get("subject"),
        )

        verified.append({
            "id":               str(uuid.uuid4()),
            "doc_id":           doc_id,
            "chunk_id":         matched_chunk_id,
            "statement":        statement,
            "subject":          norm["subject"],
            "predicate":        rf.get("predicate"),
            "metric":           rf.get("predicate"),
            "value_raw":        rf.get("value_raw"),
            "value_normalized": norm["value_normalized"],
            "unit_raw":         rf.get("unit_raw"),
            "unit_canonical":   norm["unit_canonical"],
            "time_period_raw":  rf.get("time_period_raw"),
            "time_start":       norm["time_start"],
            "time_end":         norm["time_end"],
            "scope":            rf.get("scope"),
            "qualifier":        rf.get("qualifier"),
            "fact_type":        rf.get("fact_type", "semantic"),
            "confidence":       float(rf.get("confidence") or 0.5),
            "evidence_verified": ev_verified,
            "exact_quote":      exact_quote,
            "quote_start":      ev_start,
            "quote_end":        ev_end,
            "qdrant_point_id":  None,
            "attributes":       {},
        })
    return verified


async def _embed_and_upsert(facts: list[dict], doc_id: str, qdrant) -> list[dict]:
    """Embed a batch of facts and upsert immediately to Qdrant."""
    from app.services.embedder import embed_texts, embed_colbert

    to_embed = [f for f in facts if f["evidence_verified"]]
    if not to_embed:
        return facts

    loop = asyncio.get_event_loop()
    points: list[PointStruct] = []

    for i in range(0, len(to_embed), EMBED_BATCH):
        batch      = to_embed[i: i + EMBED_BATCH]
        statements = [f["statement"] for f in batch]
        try:
            emb_results, colbert_results = await asyncio.gather(
                loop.run_in_executor(None, embed_texts, statements),
                loop.run_in_executor(None, embed_colbert, statements),
            )
            for fact, emb, colbert_vecs in zip(batch, emb_results, colbert_results):
                qid = str(uuid.uuid4())
                fact["qdrant_point_id"] = qid
                points.append(PointStruct(
                    id=qid,
                    vector={
                        "dense":   emb.dense,
                        "context": emb.dense,
                        "bm25":    SparseVector(indices=emb.sparse_indices, values=emb.sparse_values),
                        "colbert": colbert_vecs,
                    },
                    payload={
                        "doc_id":           fact["doc_id"],
                        "fact_id":          fact["id"],
                        "statement":        fact["statement"],
                        "subject":          fact["subject"],
                        "predicate":        fact["predicate"],
                        "metric":           fact["metric"],
                        "value_normalized": fact["value_normalized"],
                        "unit_canonical":   fact["unit_canonical"],
                        "time_start":       fact["time_start"],
                        "time_end":         fact["time_end"],
                        "scope":            fact["scope"],
                        "fact_type":        fact["fact_type"],
                        "confidence":       fact["confidence"],
                        "evidence_verified":fact["evidence_verified"],
                    },
                ))
        except Exception as e:
            logger.error("[%s] Embed error at batch %d: %s", doc_id, i // EMBED_BATCH, e)

    for ui in range(0, len(points), UPSERT_BATCH):
        await qdrant.upsert(collection_name=COLLECTION_NAME, points=points[ui:ui + UPSERT_BATCH])

    return facts


# ─── State ────────────────────────────────────────────────────────────────────

class ExtractionState(TypedDict):
    doc_id:   str
    job_id:   str
    chunks:   List[dict]
    facts:    List[dict]   # all verified facts (rolling accumulation)
    progress: int
    error:    Optional[str]


# ─── nodes ────────────────────────────────────────────────────────────────────

async def load_chunks_node(state: ExtractionState) -> ExtractionState:
    doc_id = state["doc_id"]
    logger.info("[%s] Loading chunks for extraction", doc_id)
    try:
        async with aiosqlite.connect(settings.db_path) as db:
            async with db.execute(
                """SELECT id, raw_text, section_path, page_num, source_type
                   FROM chunks
                   WHERE doc_id = ? AND level IN ('paragraph', 'table_row')
                   ORDER BY chunk_index""",
                (doc_id,),
            ) as cur:
                rows = await cur.fetchall()

        chunks = [{"id": r[0], "text": r[1], "section": r[2], "page": r[3], "source_type": r[4]} for r in rows]
        await _update_job(state["job_id"], stage="extracting", progress=5,
                          message=f"Loaded {len(chunks)} chunks — starting rolling extract + embed")
        logger.info("[%s] %d chunks loaded", doc_id, len(chunks))
        return {**state, "chunks": chunks, "progress": 5}
    except Exception as e:
        return {**state, "error": str(e)}


async def rolling_extract_embed_node(state: ExtractionState) -> ExtractionState:
    """
    Rolling pipeline: for each extraction batch →
      1. LLM extracts facts
      2. Verify + normalize immediately
      3. Embed (dense + BM25 + ColBERT) + upsert to Qdrant immediately
      4. Update UI progress live

    No waiting for all batches before embedding starts.
    """
    doc_id    = state["doc_id"]
    chunks    = state["chunks"]
    chunk_map = {c["id"]: c["text"] for c in chunks}
    qdrant    = get_qdrant()

    all_facts: list[dict] = []
    total_batches = max(1, (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE)
    total_indexed = 0

    logger.info("[%s] Rolling extract+embed: %d chunks in %d batches", doc_id, len(chunks), total_batches)

    for batch_i, start in enumerate(range(0, len(chunks), BATCH_SIZE)):
        batch = chunks[start: start + BATCH_SIZE]
        combined_text = "\n\n---\n\n".join(
            f"[Page {c['page']} | {c['section']}]\n{c['text']}" for c in batch
        )

        # ── 1. Extract ─────────────────────────────────────────────────────
        raw_facts: list[dict] = []
        try:
            resp = await get_llm_json().ainvoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=combined_text),
            ])
            content = resp.content
            try:
                raw_json = json.loads(content)
            except json.JSONDecodeError:
                # Truncated response — repair and recover partial facts
                from json_repair import repair_json
                raw_json = json.loads(repair_json(content))
                logger.debug("[%s] Batch %d: repaired truncated JSON", doc_id, batch_i + 1)

            raw_facts = raw_json.get("facts", [])
            for f in raw_facts:
                f["_chunk_ids"] = [c["id"] for c in batch]
                f["_page"]      = batch[0]["page"]
                f["_section"]   = batch[0]["section"]
        except Exception as e:
            logger.warning("[%s] LLM error batch %d: %s", doc_id, batch_i + 1, e)

        # ── 2. Verify + normalize ──────────────────────────────────────────
        verified = _verify_and_normalize(raw_facts, chunk_map, doc_id)

        # ── 3. Embed + upsert to Qdrant immediately ────────────────────────
        if verified:
            verified = await _embed_and_upsert(verified, doc_id, qdrant)
            total_indexed += sum(1 for f in verified if f.get("qdrant_point_id"))

        all_facts.extend(verified)

        # ── 4. Live UI progress ────────────────────────────────────────────
        pct = 5 + int(90 * (batch_i + 1) / total_batches)
        await _update_job(
            state["job_id"],
            stage="extracting",
            progress=pct,
            message=f"Batch {batch_i+1}/{total_batches} — {len(all_facts)} facts extracted, {total_indexed} indexed",
        )

        if batch_i < total_batches - 1:
            await asyncio.sleep(BATCH_DELAY)

    ev_count = sum(1 for f in all_facts if f["evidence_verified"])
    logger.info("[%s] Rolling pipeline done: %d facts, %d evidence-verified, %d indexed",
                doc_id, len(all_facts), ev_count, total_indexed)
    return {**state, "facts": all_facts, "progress": 95}


async def persist_facts_node(state: ExtractionState) -> ExtractionState:
    """Write all facts to SQLite, mark document done."""
    doc_id = state["doc_id"]
    facts  = state.get("facts", [])

    async with aiosqlite.connect(settings.db_path) as db:
        await db.executemany(
            """INSERT OR IGNORE INTO facts
               (id, doc_id, chunk_id, statement, subject, predicate, metric,
                value_raw, value_normalized, unit_raw, unit_canonical,
                time_period_raw, time_start, time_end, scope, qualifier,
                fact_type, confidence, evidence_verified, exact_quote,
                quote_start, quote_end, qdrant_point_id, attributes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [(
                f["id"], f["doc_id"], f["chunk_id"], f["statement"],
                f["subject"], f["predicate"], f["metric"],
                f["value_raw"], f["value_normalized"],
                f["unit_raw"], f["unit_canonical"],
                f["time_period_raw"], f["time_start"], f["time_end"],
                f["scope"], f["qualifier"], f["fact_type"],
                f["confidence"], int(f["evidence_verified"]),
                f["exact_quote"], f["quote_start"], f["quote_end"],
                f.get("qdrant_point_id"), json.dumps(f.get("attributes", {})),
            ) for f in facts],
        )
        await db.commit()

    verified_count = sum(1 for f in facts if f["evidence_verified"])
    await _update_doc(doc_id, "done")
    await _update_job(
        state["job_id"],
        status="done",
        stage="done",
        progress=100,
        message=f"Done — {len(facts)} facts extracted, {verified_count} evidence-verified",
    )
    logger.info("[%s] Phase 2 complete: %d facts (%d verified)", doc_id, len(facts), verified_count)

    from app.agents.comparison_agent import run_comparison_pipeline
    asyncio.create_task(run_comparison_pipeline(doc_id))
    return {**state, "progress": 100}


async def handle_error_node(state: ExtractionState) -> ExtractionState:
    err = state.get("error", "Unknown error")
    logger.error("[%s] Extraction failed: %s", state["doc_id"], err)
    await _update_doc(state["doc_id"], "failed")
    await _update_job(state["job_id"], status="failed", stage="failed",
                      error_msg=err, message=f"Extraction failed: {err}")
    return state


# ─── routing + graph ──────────────────────────────────────────────────────────

def route_on_error(state: ExtractionState) -> Literal["continue", "error"]:
    return "error" if state.get("error") else "continue"


def build_extraction_graph():
    g = StateGraph(ExtractionState)
    g.add_node("load_chunks",           load_chunks_node)
    g.add_node("rolling_extract_embed", rolling_extract_embed_node)
    g.add_node("persist_facts",         persist_facts_node)
    g.add_node("handle_error",          handle_error_node)

    g.add_edge(START, "load_chunks")
    g.add_conditional_edges("load_chunks", route_on_error,
                            {"continue": "rolling_extract_embed", "error": "handle_error"})
    g.add_conditional_edges("rolling_extract_embed", route_on_error,
                            {"continue": "persist_facts", "error": "handle_error"})
    g.add_conditional_edges("persist_facts", route_on_error,
                            {"continue": END, "error": "handle_error"})
    g.add_edge("handle_error", END)
    return g.compile()


extraction_graph = build_extraction_graph()


async def run_extraction_pipeline(doc_id: str, job_id: str):
    logger.info("[%s] Starting Phase 2 rolling extraction pipeline", doc_id)
    await extraction_graph.ainvoke({
        "doc_id": doc_id, "job_id": job_id,
        "chunks": [], "facts": [], "progress": 0, "error": None,
    })
