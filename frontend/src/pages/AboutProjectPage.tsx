import React, { useState } from 'react'
import clsx from 'clsx'
import {
  Brain, Layers, Shield,
  Eye, Database, Search, FileText, Link2, BarChart2,
} from 'lucide-react'

// ─── helpers ─────────────────────────────────────────────────────────────────

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-6 text-xl font-semibold tracking-tight text-ink">
      {children}
    </h2>
  )
}

function Tag({ children, color = 'default' }: { children: React.ReactNode; color?: 'default' | 'blue' | 'green' | 'amber' }) {
  return (
    <span className={clsx(
      'inline-flex items-center rounded-xs border px-2.5 py-0.5 font-mono text-[11px] font-medium',
      color === 'default' && 'bg-stone border-hairline text-slate',
      color === 'blue'    && 'bg-blue-50 border-blue-200 text-blue-700',
      color === 'green'   && 'bg-pale-green border-deep-green/20 text-deep-green',
      color === 'amber'   && 'bg-amber-50 border-amber-200 text-amber-700',
    )}>
      {children}
    </span>
  )
}

// ─── Pipeline step ────────────────────────────────────────────────────────────

function PipelineStep({
  n, icon: Icon, title, desc, tags,
}: {
  n: number; icon: React.ElementType; title: string; desc: string; tags?: string[]
}) {
  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-sm bg-ink text-canvas">
          <Icon className="h-4 w-4" />
        </div>
        <div className="mt-1 flex-1 w-px bg-hairline" />
      </div>
      <div className="pb-8 pt-1">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-mono text-[10px] text-muted">STEP {n}</span>
        </div>
        <p className="text-sm font-semibold text-ink mb-1">{title}</p>
        <p className="text-sm text-body-muted leading-relaxed mb-2">{desc}</p>
        {tags && (
          <div className="flex flex-wrap gap-1.5">
            {tags.map(t => <Tag key={t}>{t}</Tag>)}
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Differentiator card ──────────────────────────────────────────────────────

function DiffCard({
  icon: Icon, title, desc, badge,
}: {
  icon: React.ElementType; title: string; desc: string; badge?: string
}) {
  return (
    <div className="rounded-sm border border-hairline bg-canvas p-5 hover:border-slate/40 transition-colors">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-xs bg-stone">
          <Icon className="h-4 w-4 text-slate" />
        </div>
        {badge && <Tag color="green">{badge}</Tag>}
      </div>
      <p className="mb-1.5 text-sm font-semibold text-ink">{title}</p>
      <p className="text-xs leading-relaxed text-body-muted">{desc}</p>
    </div>
  )
}

// ─── Tech stack chip ──────────────────────────────────────────────────────────

function StackChip({ name, role }: { name: string; role: string }) {
  return (
    <div className="flex items-center gap-2 rounded-xs border border-hairline bg-stone px-3 py-2">
      <span className="text-xs font-semibold text-ink">{name}</span>
      <span className="text-[10px] text-muted">{role}</span>
    </div>
  )
}


// ─── Main page ────────────────────────────────────────────────────────────────

export function AboutProjectPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-16 pb-20">

      {/* ── Hero ── */}
      <div className="rounded-sm border border-hairline bg-canvas overflow-hidden">
        <div className="px-8 py-10 border-b border-hairline">
          <h1 className="text-3xl font-semibold tracking-tight text-ink mb-3">
            Fact Knowledge Layer
          </h1>
          <p className="text-base text-body-muted leading-relaxed max-w-2xl">
            A multi-layer RAG system that extracts structured knowledge from financial PDF documents,
            builds a page-level knowledge graph with vision-augmented chart extraction,
            and answers natural-language questions with source attribution, confidence scoring,
            and automatic cross-document relationship classification.
          </p>
        </div>
        <div className="grid grid-cols-2 divide-x divide-hairline sm:grid-cols-4">
          {[
            { label: 'Documents processed', value: '2' },
            { label: 'Vectors indexed', value: '2,618' },
            { label: 'Questions benchmarked', value: '291' },
            { label: 'Cross-doc links', value: '156' },
          ].map(s => (
            <div key={s.label} className="px-6 py-4">
              <p className="text-2xl font-semibold tracking-tight text-ink">{s.value}</p>
              <p className="mt-0.5 font-mono text-[10px] uppercase tracking-wider text-muted">{s.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Pipeline ── */}
      <div>
        <SectionHeading>How it works — the pipeline</SectionHeading>
        <div className="rounded-sm border border-hairline bg-canvas px-6 pt-6 pb-2">
          <PipelineStep
            n={1} icon={FileText} title="PDF ingestion + page extraction"
            desc="PyMuPDF extracts text, coordinates, and embedded image metadata page-by-page. Pages with ≥ 8000 chars of text still receive a dedicated vision pass — no page is text-only by assumption."
            tags={['PyMuPDF', 'pdfplumber', 'page detection']}
          />
          <PipelineStep
            n={2} icon={Eye} title="Vision pass — chart & table extraction"
            desc="Every page with embedded images is re-rendered at 2× zoom to PNG and passed to Amazon Nova 2 Lite as a multimodal message with a structured chart extraction prompt. Outputs (CHART / DATA POINTS / TREND rows) are merged back into the page knowledge file."
            tags={['Nova 2 Lite', 'multimodal', '2× zoom render', 'structured extraction']}
          />
          <PipelineStep
            n={3} icon={Brain} title="Page Knowledge Graph — one LLM call per page"
            desc="A single Nova 2 Lite call per page produces a structured .md file with five sections: Summary, Key Metrics table (every number on the page), Key Facts, Visual Content (merged from vision pass), and Entity Mentions. These files are the retrieval backbone."
            tags={['Nova 2 Lite', 'structured .md', 'per-page KG']}
          />
          <PipelineStep
            n={4} icon={Database} title="Hybrid vector indexing"
            desc="Raw text chunks (not just page summaries) are indexed with BAAI/bge-small-en-v1.5 for dense 384-dim embeddings and Qdrant/bm25 for sparse IDF-weighted embeddings. Page summaries receive their own Qdrant points. Qdrant stores everything."
            tags={['bge-small-en-v1.5', 'BM25', 'Qdrant', 'SQLite']}
          />
          <PipelineStep
            n={5} icon={Search} title="BM25 + dense RRF fusion retrieval"
            desc="At query time, BM25 and dense arms each prefetch 60 candidates. Qdrant's Reciprocal Rank Fusion merges them into a single ranked list. Chunk payloads carry md_path pointers, so the matched page knowledge files are read and appended to the LLM context."
            tags={['RRF fusion', 'page-augmented context', 'md_path lookup']}
          />
          <PipelineStep
            n={6} icon={Link2} title="Cross-document linker — zero LLM calls"
            desc="After each document completes, embedding cosine similarity (threshold 0.68) detects topically related page pairs across all documents. Rule-based metric comparison then classifies each link as CORROBORATES, CONTRADICTS, RECONCILES, or RELATED — without any LLM call."
            tags={['embedding similarity', 'rule-based', 'CORROBORATES / CONTRADICTS']}
          />
        </div>
      </div>

      {/* ── Differentiators ── */}
      <div>
        <SectionHeading>What makes this approach different</SectionHeading>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <DiffCard
            icon={Brain} badge="Core novelty"
            title="Page Knowledge Graph"
            desc="Most RAG systems split documents into chunks and index text. We go further: one structured LLM call per page produces a knowledge file that explicitly lists every number, every named entity, and every visual element. Retrieval then augments chunks with the full page file — giving the LLM far richer context than chunks alone."
          />
          <DiffCard
            icon={Eye} badge="Vision-augmented"
            title="Dedicated chart extraction pass"
            desc="Charts and infographics are invisible to text-only chunkers. We re-render each image-bearing page at 2× zoom and extract structured rows (Metric | Value | Unit | Period) from every chart visible. This data is merged into the Key Metrics table in the page knowledge file."
          />
          <DiffCard
            icon={Search}
            title="Hybrid BM25 + dense fusion"
            desc="Pure dense vector search struggles with exact-match terms like ticker symbols, regulatory codes, and financial metric names. BM25 excels at these. RRF fusion combines both signals for better recall than either alone."
          />
          <DiffCard
            icon={Link2}
            title="Zero-LLM cross-doc linking"
            desc="Cross-document relationship classification (CORROBORATES / CONTRADICTS / RECONCILES) is done entirely with embedding cosine similarity and rule-based numeric comparison. No LLM calls means deterministic, fast, and cost-free linking at scale."
          />
          <DiffCard
            icon={Shield}
            title="Hallucination defense built-in"
            desc="The system prompt explicitly instructs the LLM to return LOW confidence and refuse to answer when the question references data not present in the retrieved evidence. All 5 out-of-scope hallucination test questions were correctly refused."
          />
          <DiffCard
            icon={BarChart2}
            title="Page-augmented retrieval context"
            desc="At query time, retrieved chunks resolve their md_path, and the full page knowledge file is appended to the LLM context. The LLM therefore sees both the specific matched passage AND the complete structured summary of that page — not just isolated text fragments."
          />
        </div>
      </div>

      {/* ── Benchmark results ── */}
      <div>
        <SectionHeading>Benchmark results — 291-question evaluation</SectionHeading>
        <div className="rounded-sm border border-hairline bg-canvas overflow-hidden">
          <div className="border-b border-hairline px-6 py-4">
            <p className="text-sm text-body-muted leading-relaxed">
              Evaluated against the Delhivery Prospectus 2022 (100 pages) across 9 question categories:
              offer structure, shareholding, financials, market data, operations, compliance, synthesis, cross-doc, and hallucination defense.
            </p>
          </div>
          <div className="divide-y divide-hairline">
            {[
              { batch: 'Offer structure & use of proceeds', qs: 30, pct: 96, note: 'IPO size, allocations, OFS/fresh split' },
              { batch: 'Selling shareholders & shareholding', qs: 20, pct: 90, note: 'Pre-offer %, acquisition costs, share counts' },
              { batch: 'Financial statements FY19–FY21', qs: 15, pct: 77, note: 'Revenue, losses, net worth, EBITDA margins' },
              { batch: 'Market & industry data', qs: 15, pct: 53, note: 'Market size projections, competitive landscape' },
              { batch: 'Operations & network KPIs', qs: 30, pct: 44, note: 'Sort centers, pin-codes, warehouse sqft' },
              { batch: 'Risk, compliance & governance', qs: 30, pct: 43, note: 'Risk factors, accounting policies, balance sheet' },
              { batch: 'Synthesis & analysis', qs: 8, pct: 75, note: 'Bull/bear case, path to profitability, competitive advantages' },
              { batch: 'Hallucination defense', qs: 5, pct: 100, note: 'All 5 out-of-scope questions correctly refused' },
            ].map(row => (
              <div key={row.batch} className="flex items-center gap-4 px-6 py-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-ink">{row.batch}</p>
                  <p className="text-xs text-muted">{row.note}</p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <div className="w-24 h-1.5 rounded-full bg-stone overflow-hidden">
                    <div
                      className={clsx('h-full rounded-full', row.pct >= 80 ? 'bg-deep-green' : row.pct >= 50 ? 'bg-amber-400' : 'bg-slate')}
                      style={{ width: `${row.pct}%` }}
                    />
                  </div>
                  <span className="w-10 text-right font-mono text-xs font-semibold text-ink">{row.pct}%</span>
                  <span className="w-8 text-right font-mono text-[10px] text-muted">{row.qs}q</span>
                </div>
              </div>
            ))}
          </div>
          <div className="border-t border-hairline bg-stone/40 px-6 py-3">
            <p className="text-xs text-body-muted">
              <strong className="text-ink">Note:</strong> 79 of 291 LOW answers were transient Bedrock ThrottlingErrors from running 5 concurrent batches simultaneously — not RAG failures.
              Sequential execution accuracy (65 questions) was <strong className="text-ink">86% HIGH</strong>.
            </p>
          </div>
        </div>
      </div>

      {/* ── Tech stack ── */}
      <div>
        <SectionHeading>Tech stack</SectionHeading>
        <div className="space-y-5">
          {[
            {
              layer: 'AI / LLM',
              items: [
                { name: 'Amazon Nova 2 Lite', role: 'all LLM calls via Bedrock' },
                { name: 'BAAI/bge-small-en-v1.5', role: 'dense embeddings (384-dim, ~130MB)' },
                { name: 'Qdrant/bm25', role: 'sparse BM25 IDF embeddings' },
                { name: 'fastembed', role: 'ONNX-accelerated embedding runtime' },
              ],
            },
            {
              layer: 'Vector store',
              items: [
                { name: 'Qdrant', role: 'dense + sparse, RRF fusion' },
                { name: 'SQLite', role: 'page_summaries, chunks, documents, jobs' },
              ],
            },
            {
              layer: 'Document processing',
              items: [
                { name: 'PyMuPDF (fitz)', role: 'PDF parsing + 2× zoom page render' },
                { name: 'pdfplumber', role: 'layout-aware text extraction' },
                { name: 'LangChain', role: 'LLM message wrapping' },
              ],
            },
            {
              layer: 'Backend',
              items: [
                { name: 'FastAPI', role: 'REST API + SSE job events' },
                { name: 'aiosqlite', role: 'async SQLite access' },
                { name: 'Python 3.11', role: 'asyncio throughout' },
              ],
            },
            {
              layer: 'Frontend',
              items: [
                { name: 'React 18', role: 'UI framework' },
                { name: 'TypeScript', role: 'type safety' },
                { name: 'Tailwind CSS', role: 'styling' },
                { name: 'react-markdown + remark-gfm', role: 'rich answer rendering' },
                { name: 'Vite', role: 'bundler' },
              ],
            },
            {
              layer: 'Infrastructure',
              items: [
                { name: 'Docker + Docker Compose', role: 'multi-service container orchestration' },
                { name: 'Nginx', role: 'reverse proxy, static file serving' },
                { name: 'AWS Bedrock', role: 'managed LLM and embedding API' },
              ],
            },
          ].map(group => (
            <div key={group.layer}>
              <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted">{group.layer}</p>
              <div className="flex flex-wrap gap-2">
                {group.items.map(i => <StackChip key={i.name} {...i} />)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Limitations ── */}
      <div>
        <SectionHeading>Limitations</SectionHeading>
        <div className="space-y-3">
          {[
            {
              n: '01',
              title: 'LLM-intensive ingestion',
              body: 'Every page goes through at least one Nova 2 Lite call to build its knowledge file, plus a second multimodal call if the page has images. For a 100-page document that\'s 100–180 LLM calls during ingestion — significantly more than a standard RAG pipeline that skips this step entirely. This makes ingestion slower and more expensive at scale compared to pure chunking approaches.',
            },
            {
              n: '02',
              title: 'Weak on multi-hop arithmetic',
              body: 'Questions that require chaining values across multiple pages — e.g. computing an implied CAGR from figures on page 5 and page 42 — often fail. The retrieval step surfaces both pages correctly, but the LLM struggles to perform multi-step arithmetic reliably over long context. A standard RAG system with a calculator tool would actually handle these better.',
            },
            {
              n: '03',
              title: 'Table structure partially lost in extraction',
              body: 'PyMuPDF flattens PDF tables into plain text, which loses merged cells, multi-row headers, and footnote associations. The vision pass recovers some of this from charts and infographics, but dense text-based financial tables (e.g. multi-column P&L statements) are still partially mis-structured after extraction.',
            },
          ].map(item => (
            <div key={item.n} className="flex gap-5 rounded-sm border border-hairline bg-canvas px-5 py-4">
              <span className="mt-0.5 font-mono text-2xl font-semibold text-hairline shrink-0 select-none leading-tight">
                {item.n}
              </span>
              <div>
                <p className="mb-1.5 text-sm font-semibold text-ink">{item.title}</p>
                <p className="text-sm text-body-muted leading-relaxed">{item.body}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  )
}
