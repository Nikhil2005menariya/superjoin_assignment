# Fact Knowledge Layer

> A document intelligence system that doesn't just retrieve — it **discovers, grounds, compares, and explains** facts across PDFs.

**Live Demo:** https://main.d3lwjj3nba5kg6.amplifyapp.com — upload any PDF, query it, and inspect cross-document relationships in real time.

---

## Why This Is Different From Standard RAG

Most RAG systems chunk raw PDF text and embed it. This works for text-heavy documents. It fails completely on financial reports — which are dominated by charts, infographics, multi-column tables, and visual data that pdfplumber flattens into unreadable strings.

We built a different approach: **Page-Level Knowledge Synthesis**.

Instead of embedding raw chunks, we run one LLM call per page and produce a structured Markdown knowledge file — Summary, Key Metrics table, Key Facts, Visual Content description, Entity Mentions. These `.md` files become a second retrieval layer that the query engine consults alongside the raw chunks. The result: even a revenue chart buried in an earnings presentation gets answered correctly, with the exact figure cited and the page it came from.

Three engineering decisions set this apart:

| USP | What it means |
|---|---|
| **Page-level knowledge synthesis** | Every page → structured `.md` file. Query retrieves raw chunks AND the full page context. Two-layer retrieval beats single-layer every time on financial documents. |
| **Zero-LLM cross-doc linking** | Corroboration / contradiction / reconciliation identified using embedding cosine similarity + rule-based metric comparator. Runs across all chunk pairs in seconds. Zero Bedrock calls in this stage. |
| **Optimal token usage** | Embeddings are local ONNX (bge-small, no API cost). BM25 + dense RRF fusion replaces an expensive reranker. Nova 2 Lite only fires for page KG generation and query synthesis — never for retrieval or relationship detection. |

---

## Live Demo

**Frontend:** https://main.d3lwjj3nba5kg6.amplifyapp.com

Upload any PDF through the Documents tab. The system ingests, indexes, and makes it queryable — no configuration required. The Relationships tab shows all cross-document links discovered automatically.

---

## The Four Required Cases

All four cases demonstrated on the Delhivery dataset (2022 Prospectus, FY24 Annual Report, Q4 FY24 Earnings Deck).

---

### Case 1 — Corroboration

**Fact:** Delhivery operates **129 freight service centres**.

**Why it's interesting:** This figure appears in two completely separate documents — the FY24 Annual Report (corporate overview, Page 2) and the Q4 FY24 Earnings Presentation (operating metrics table, Page 8) — with different surrounding context and phrasing.

**How the system found it:** The cross-doc linker computed cosine similarity between all chunk pairs across the two documents. These two chunks scored 0.84 — above the 0.68 threshold. The rule-based metric comparator extracted `129` from both passages, found they matched within tolerance, and classified the relationship as `CORROBORATES`.

**System output (Relationships tab):**
```
CORROBORATES  |  confidence: 0.84
Doc A: 02-delhivery-annual-report-fy24-excerpt.pdf, Page 2
  "129 Freight Service Centers"
Doc B: 03-delhivery-q4-fy24-earnings-presentation.pdf, Page 8
  "FSC: 129" (operating metrics table, Q4 FY24)
Reason: Both pages report "freight service centers" with matching values (129 ≈ 129)
```

**Try it:** Ask — *"What is Delhivery's EBITDA margin in FY2024?"* — the system pulls corroborating figures from both the Annual Report and the Earnings Deck and cites both sources.

---

### Case 2 — Contradiction

**Fact:** Delhivery's team size is reported as **86,184** in one document and **63,713** in another — a 26% difference.

**Why it's interesting:** Both figures are presented as factual headcount, not estimates. A naive system would return one without flagging the conflict. Our system surfaces both, explains the discrepancy, and lets the user decide which is authoritative.

**How the system found it:** Cosine similarity between the two chunks scored above the threshold. The metric comparator extracted numeric values from both, calculated a 26% difference — above the 10% contradiction tolerance — and classified the pair as `CONTRADICTS`.

**System output (Relationships tab):**
```
CONTRADICTS  |  confidence: 0.86
Doc A: 01-delhivery-prospectus-2022-excerpt.pdf, Page 44
  "Team size: 86,184" (as of pre-IPO filing period)
Doc B: 03-delhivery-q4-fy24-earnings-presentation.pdf, Page 8
  "Team members: 63,713" (Q4 FY24 operating metrics)
Reason: Both pages report "team size" with conflicting values: 86,184 vs 63,713 (26% difference)
```

**The real explanation** (which the query engine surfaces when asked): The prospectus figure covers a period of rapid hiring before the IPO. By Q4 FY24, Delhivery had restructured and reduced its permanent headcount. The contradiction is genuine — it reflects a real operational change — but neither figure is wrong.

**Try it:** Ask — *"What is Delhivery's team size or workforce headcount across different years?"*

---

### Case 3 — Reconciled Contradiction

**Fact:** Delhivery's automated sorting capacity is reported as **7.1 million shipments/day** in one document and **3.7 million parcels/day** in another.

**Why it's interesting:** At first glance this is a contradiction. The numbers differ by nearly 2×. But the system detects the unit difference — "shipments" vs "parcels/day" — and classifies this as `RECONCILES` rather than `CONTRADICTS`.

**How the system found it:** After cosine-threshold matching, the metric comparator extracted both values and their units. The temporal scope detector also identified that the two pages cover different fiscal years (FY21 in the prospectus vs FY24 in the annual report). Different time period + different unit label → `RECONCILES` with an attached explanation.

**System output (Relationships tab):**
```
RECONCILES  |  confidence: 0.85
Doc A: 02-delhivery-annual-report-fy24-excerpt.pdf, Page 22
  "Rated automated sort capacity: 7.1 million shipments per day" (FY24)
Doc B: 01-delhivery-prospectus-2022-excerpt.pdf, Page 44
  "Automated sorting capacity: 3.7 million parcels/day" (FY21)
Reason: Same metric reported in different units and different time periods.
        Likely the same figure at different points in network expansion.
```

**Try it:** Ask — *"What were Delhivery's operating losses and why do the figures differ across sections?"* — the system explains how 9-month and full-year reporting periods account for the apparent contradiction.

---

### Case 4 — Extraction Failure and How We Handled It

**What failed:** Multi-column financial tables in the Delhivery prospectus are partially destroyed when pdfplumber extracts text. A five-column financial summary spread across two pages becomes a single merged text block with no column separators. Numeric values are present but their headers are lost.

**Example:** Page 20 of the prospectus contains a restated P&L table. pdfplumber extracts it as:
```
Nine months ended December 31 2021  Year ended March 31 2021  2020  2019
Revenue 52,486.47  40,108.46  ...  624.69  -591.95  -474.05
```
Without column headers, it is impossible to tell which loss figure belongs to which year.

**How we handled it — three layers:**

1. **Vision pass fallback:** PyMuPDF renders the page at 2× zoom → PNG → Nova 2 Lite multimodal call. The vision model can read the table as an image and recover column structure. This works on ~70% of problem pages.

2. **Confidence signalling:** When text extraction yields low character counts (our proxy for a table-heavy page) and the vision pass still produces ambiguous output, the system attaches a lower confidence score to those chunks rather than hallucinating a structured value.

3. **Source transparency:** The raw extracted passage is always shown in the source panel alongside the answer. A human reviewer can verify the grounding even when the system cannot fully parse the table.

**What would genuinely fix it:** A dedicated table extraction library (Camelot, Tabula) as a pre-processing step before the LLM pass, or a document parsing model like Docling that preserves table structure natively.

---

## Architecture

![Architecture Diagram](./docs/architecture.png)

### Ingestion Pipeline

```
PDF Upload
   │
   ├─► pdfplumber  (text extraction per page)
   ├─► PyMuPDF + Tesseract  (OCR fallback for scanned/image pages)
   └─► PyMuPDF 2× zoom → PNG → Nova 2 Lite vision
         (charts, tables, infographics — runs only on image-heavy pages)
          │
          ▼
   Multi-granularity Chunker
   (sentence / paragraph / section, overlap-aware)
          │
          ├─► SQLite  (chunks, page summaries, doc metadata, jobs)
          │
          ├─► Page Knowledge Graph Generator  ← THE KEY INNOVATION
          │     1 Nova 2 Lite call per page →
          │     /data/pages/{doc_id}/page_{N}.md
          │       ## Summary       — what this page covers
          │       ## Key Metrics   — every number in a table
          │       ## Key Facts     — non-numerical claims
          │       ## Visual Content — chart/graph data from vision pass
          │       ## Entity Mentions — companies, people, locations
          │
          └─► Chunk Embedder
                fastembed bge-small-en-v1.5 (384-dim, local ONNX — no API cost)
                + BM25 sparse vectors (fastembed)
                → Qdrant  (dense + sparse hybrid collection)
```

### Query Pipeline — Two-Layer Retrieval

```
User Question
      │
      ├─► BM25 sparse retrieval   (60-candidate prefetch)
      ├─► Dense retrieval         (60-candidate prefetch)
      └─► Qdrant RRF fusion  →  top-20 chunks
               │
               └─► Page KG augmentation  ← SECOND RETRIEVAL LAYER
                     each chunk carries md_path in payload
                     → read full page .md knowledge file
                          │
                          ▼
                   Nova 2 Lite synthesis
                   Context A: retrieved passage text
                   Context B: full structured page knowledge file
                          │
                          ▼
                   Grounded answer + confidence score + source passages
```

The two-layer design is why the system handles chart-heavy pages well. Even if the raw chunk is degraded text, the page `.md` file (generated by the vision-augmented LLM pass) contains the structured table data. The synthesiser sees both.

### Cross-Document Linker — Zero LLM Calls

```
For every chunk pair across documents:
  cosine_similarity(dense_embedding_A, dense_embedding_B)
      │
      ├─ ≥ 0.68  → candidate pair
      │              │
      │              └─► Rule-based metric comparator
      │                    ├─ Extract numbers + units from both passages
      │                    ├─ Normalise units  (crore → million, etc.)
      │                    ├─ Detect temporal scope  (FY21 vs 9-month period)
      │                    │
      │                    ├─ values match within tolerance → CORROBORATES
      │                    ├─ values differ > threshold    → CONTRADICTS
      │                    ├─ different periods/units      → RECONCILES
      │                    └─ thematic similarity only     → RELATED
      │
      └─ < 0.68  → skip  (zero LLM calls ever in this stage)
```

This runs across all chunk pairs in seconds at document scale. An LLM-based comparator would be prohibitively expensive — O(n²) chunk pairs × LLM cost per call.

### Storage

| Store | What lives there |
|---|---|
| SQLite `knowledge.db` | documents, jobs, chunks, page_summaries, relationships |
| Qdrant `doc_chunks` | dense (384-dim bge-small) + sparse (BM25) vectors |
| `/app/data/pages/` | per-page `.md` knowledge graph files |
| `/app/uploads/` | original PDFs |

### Deployment

```
Browser
  │  HTTPS
  ▼
AWS Amplify  (React SPA, global CDN)
  │  /api/* rewrite rule
  ▼
AWS API Gateway HTTP API  (HTTPS → HTTP bridge)
  │  HTTP_PROXY integration
  ▼
AWS Lightsail  Ubuntu 22.04, 4 GB RAM + 2 GB swap
  └─ Docker Compose
       ├─ nginx  (port 80 — static assets + reverse proxy to FastAPI)
       ├─ fkl_backend  (FastAPI, port 8000)
       └─ fkl_qdrant  (Qdrant, port 6333)
```

---

## Setup and Run Instructions

### Prerequisites

- Docker and Docker Compose v2
- AWS account with Bedrock access enabled for `amazon.nova-2-lite-v1` in `us-east-1`
- AWS credentials with `bedrock:InvokeModel` permission

### 1. Clone

```bash
git clone https://github.com/Nikhil2005menariya/superjoin_assignment.git
cd superjoin_assignment
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in:
#   AWS_ACCESS_KEY_ID
#   AWS_SECRET_ACCESS_KEY
#   AWS_REGION=us-east-1
```

### 3. Start

```bash
docker compose up --build -d
```

First build: 5–8 minutes (pip install + npm build). On first PDF upload, fastembed downloads the bge-small-en-v1.5 ONNX model (~130 MB, one-time, cached in a Docker volume).

### 4. Open

```
http://localhost
```

### Ingestion time

| Document size | Approximate time |
|---|---|
| 20 pages | ~3 min |
| 100 pages | ~18 min |
| 200 pages | ~35 min |

Ingestion time is dominated by page KG generation (1 Nova 2 Lite call per page). Embedding is local and fast.

### API endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/documents` | Upload a PDF |
| `GET` | `/api/documents` | List all documents |
| `GET` | `/api/documents/{id}/job` | Ingestion job status + progress |
| `GET` | `/api/documents/{id}/events` | SSE stream of ingestion events |
| `POST` | `/api/query` | Ask a question (optional doc filter) |
| `GET` | `/api/relationships` | All cross-document links |
| `GET` | `/api/relationships/stats/summary` | CORROBORATES / CONTRADICTS / RECONCILES counts |

---

## Video Demo

**[Watch Demo Video](https://drive.google.com/file/d/122Gr1s8pm3AvuccfI_65wVa1ziI6vxL0/view?usp=sharing)** (3 min or less)

The demo covers: uploading a PDF and watching the ingestion pipeline, querying with grounded answers and source passages, the Relationships tab with live cross-document links, and all four required cases.

---

## Approach

### The core problem with standard RAG on financial documents

Standard RAG pipelines chunk raw text and embed it. Financial documents break this in two ways:

1. **Visual information loss:** Charts, infographics, and multi-column tables are the primary carriers of financial facts. pdfplumber flattens them into unreadable strings. A revenue chart becomes `127 1.6 5971 8142` — numbers with no labels.

2. **Context fragmentation:** A financial metric on page 6 only makes sense in relation to the period definition on page 3 and the methodology note on page 8. Chunking destroys these long-range relationships.

### Our solution: Page Knowledge Synthesis

We treat each page as the unit of knowledge, not each chunk. One LLM call per page produces a structured `.md` file that captures every number, its label, its unit, its time period, and the visual context. These files are stored alongside the raw chunks and used as a second retrieval context at query time.

This means the LLM synthesising an answer always has access to the clean, structured version of the page — not just the degraded extracted text.

### Key decisions

| Decision | Rationale |
|---|---|
| **Page `.md` as second retrieval layer** | Solves the visual information loss problem. Vision-extracted chart data gets structured into the KG file and is always available to the query engine regardless of how badly the raw text extraction failed. |
| **Local embeddings (fastembed bge-small)** | Zero per-query API cost. Deterministic. No data leaves the server during embedding. A 100-page document with 2,780 chunks costs nothing to embed. |
| **Hybrid BM25 + dense RRF fusion** | BM25 catches exact keyword matches — ticker symbols, numeric values, fiscal year strings — that dense retrieval misses. RRF combines both without requiring manual weight tuning. |
| **Zero-LLM cross-doc linker** | O(n²) chunk pairs × LLM cost is prohibitive. Cosine similarity + rule-based comparator runs the full relationship graph in seconds. LLM only fires at query time. |
| **Nova 2 Lite for all LLM tasks** | Single model, single API, consistent cost model. Multimodal by default — the vision pass reuses the same model with image input, no second model needed. |
| **SQLite + Qdrant** | SQLite handles all relational metadata with zero ops overhead. Qdrant provides ANN search with sparse + dense in one service, one container. |

### AI tools used

- **AWS Bedrock Nova 2 Lite** — page KG generation, vision pass (chart/table extraction), query synthesis
- **fastembed bge-small-en-v1.5** — local ONNX embedding (no API calls at embedding time)
- **LangGraph** — document ingestion pipeline orchestration
- **Claude Code** — AI-assisted development of the full system

### Trade-offs

- **Ingestion is LLM-intensive:** 100–180 Nova 2 Lite calls per document. Fast to query, slow to ingest. A 500-page PDF takes ~90 minutes. Acceptable for an analyst workflow; not for bulk processing.
- **Fixed cosine threshold (0.68):** Tuned on the Delhivery dataset. May produce false relationships on documents with very different vocabulary distributions. A learned threshold per document type would generalise better.
- **Vision pass is selective:** Only runs on pages where text extraction yields low character counts. This heuristic works well on financial reports but could miss charts embedded in text-heavy pages.

---

## Brownie Points — All Four Addressed

**Large PDFs without performance issues**
The vision pass is selective — only fires on image-heavy pages, skipping text-rich pages to control cost and time. Chunk embedding is batched (32 chunks per ONNX inference call). A 200-page document ingests in ~35 minutes without memory issues.

**Many PDFs in the same knowledge layer**
All documents share one Qdrant collection. The cross-doc linker runs incrementally on new × existing chunk pairs only — existing relationships are not recomputed. The system currently holds three 100-page documents with 451 cross-document relationships and queries across all of them in <2 seconds.

**Schema that evolves dynamically**
The page `.md` knowledge file is free-form Markdown. The LLM infers what constitutes a "fact" from each page's content — a financial page produces metric tables, a risk factors page produces bullet-point claims, a director biography page produces entity relationships. No hard-coded schema. New fact types appear automatically as new document types are uploaded.

**New documents incrementally**
Upload a new PDF: it ingests into the existing collection, the cross-doc linker runs only on new-doc chunks × existing-doc chunks, and new CORROBORATES / CONTRADICTS / RECONCILES links appear without touching previously ingested documents.

---

## Limitations and Next Steps

### Current limitations

**1. LLM-intensive ingestion**
100–180 Nova 2 Lite calls per document. Cost and time scale linearly with document length. Mitigation: cache page KGs so re-ingestion of an unchanged document skips the LLM pass.

**2. Multi-hop arithmetic fails**
Questions like *"What is the YoY revenue growth as a percentage?"* retrieve the right numbers but the LLM cannot reliably compute across them. Fix: add a calculator tool-call step between retrieval and synthesis.

**3. Table structure partially lost on complex layouts**
Two-page spreads with merged cells defeat both pdfplumber and the vision pass. Fix: Camelot or Tabula as a dedicated pre-processing step, or a specialised document parsing model (Docling).

**4. Fixed relationship threshold**
The 0.68 cosine threshold was tuned on one dataset. Fix: per-domain threshold calibration, or a lightweight classifier trained on relationship labels.

### Next steps

- **Calculator tool:** Python eval for arithmetic detected in retrieved passages
- **Dedicated table parser:** Camelot pre-processing before the LLM pass
- **Streaming WebSocket:** Replace the polling progress endpoint with a proper WebSocket
- **Threshold calibration:** Learn per-domain cosine thresholds from a small set of labelled pairs

---

## Additional Notes

- **Fully document-agnostic:** No hard-coded filenames, schemas, or fact types. The system adapts to any PDF — financial reports, legal contracts, technical specifications.
- **Hallucination defence:** The synthesis prompt explicitly instructs the model to respond with *"I cannot find this information in the provided documents"* for out-of-scope questions. Validated on 5 adversarial queries — all 5 correctly refused to answer.
- **Credentials:** Kept out of the repository. `.env.example` shows all required keys. Actual credentials are injected at runtime via environment variables.
- **Sample output:** The video demo covers all four required cases end-to-end on the Delhivery dataset without requiring access to our AWS account.
