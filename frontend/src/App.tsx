import React, { useCallback, useEffect, useRef, useState } from 'react'
import clsx from 'clsx'
import { Document, Job, listDocuments, getJob } from './api/client'
import { UploadZone } from './components/UploadZone'
import { DocumentList } from './components/DocumentList'
import { RelationshipsPage } from './pages/RelationshipsPage'
import { QueryPage } from './pages/QueryPage'
import { AboutProjectPage } from './pages/AboutProjectPage'
import { AboutCreatorPage } from './pages/AboutCreatorPage'

interface DocEntry { doc: Document; job?: Job }
type Tab = 'documents' | 'relationships' | 'query' | 'project' | 'creator'

const ACTIVE_STATUSES = new Set(['queued', 'processing', 'chunked', 'embedding', 'generating', 'linking'])

export default function App() {
  const [entries, setEntries] = useState<DocEntry[]>([])
  const [tab, setTab]         = useState<Tab>('documents')
  const pollRef               = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadDocuments = useCallback(async () => {
    try {
      const docs = await listDocuments()

      // Fetch fresh job data for all non-done docs so progress survives page reload
      const active = docs.filter(d => ACTIVE_STATUSES.has(d.status))
      const jobResults = await Promise.allSettled(active.map(d => getJob(d.id)))
      const freshJobs: Record<string, Job> = {}
      active.forEach((d, i) => {
        const r = jobResults[i]
        if (r.status === 'fulfilled' && r.value) freshJobs[d.id] = r.value
      })

      setEntries(prev => {
        const prevJobMap = Object.fromEntries(prev.map(e => [e.doc.id, e.job]))
        return docs.map(doc => ({
          doc,
          job: freshJobs[doc.id] ?? prevJobMap[doc.id],
        }))
      })
    } catch {
      // silently ignore — retry on next interval
    }
  }, [])

  useEffect(() => {
    loadDocuments()
    pollRef.current = setInterval(loadDocuments, 4000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [loadDocuments])

  const handleUploadStart = useCallback((docId: string, filename: string) => {
    setEntries(prev => [{
      doc: {
        id: docId, filename, file_size: null, page_count: null,
        status: 'queued', error_msg: null,
        created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
      },
    }, ...prev])
  }, [])

  const handleJobUpdate = useCallback((docId: string, job: Job) => {
    setEntries(prev => prev.map(e =>
      e.doc.id === docId
        ? { doc: { ...e.doc, page_count: job.total_pages || e.doc.page_count }, job }
        : e
    ))
  }, [])

  const handleUploadDone = useCallback(() => { loadDocuments() }, [loadDocuments])
  const docs = entries.map(e => e.doc)

  const TABS: { id: Tab; label: string }[] = [
    { id: 'documents',     label: 'Documents' },
    { id: 'relationships', label: 'Relationships' },
    { id: 'query',         label: 'Ask' },
    { id: 'project',       label: 'About Project' },
    { id: 'creator',       label: 'About Creator' },
  ]

  return (
    <div className="min-h-screen bg-canvas">

      {/* Top nav */}
      <header className="border-b border-hairline bg-canvas">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-sm bg-ink">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <rect x="2" y="2" width="5" height="5" rx="1" fill="white"/>
                <rect x="9" y="2" width="5" height="5" rx="1" fill="white" fillOpacity=".5"/>
                <rect x="2" y="9" width="5" height="5" rx="1" fill="white" fillOpacity=".5"/>
                <rect x="9" y="9" width="5" height="5" rx="1" fill="white"/>
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold tracking-tight text-ink">Fact Knowledge Layer</p>
              <p className="text-xs text-muted">Extract · Verify · Compare</p>
            </div>
          </div>

          <div className="hidden items-center gap-1.5 md:flex">
            <span className="rounded-xs border border-hairline bg-stone px-2.5 py-1 font-mono text-[10px] text-muted">VIT 2026</span>
            <span className="rounded-xs border border-hairline bg-stone px-2.5 py-1 font-mono text-[10px] text-muted">Superjoin Assignment</span>
          </div>
        </div>
      </header>

      {/* Tab bar */}
      <div className="border-b border-hairline bg-canvas">
        <div className="mx-auto max-w-6xl px-6">
          <nav className="flex gap-0">
            {TABS.map(({ id, label }) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={clsx(
                  'border-b-2 px-5 py-3 text-sm font-medium transition-colors',
                  tab === id
                    ? 'border-ink text-ink'
                    : 'border-transparent text-muted hover:text-ink',
                )}
              >
                {label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Main */}
      <main className="mx-auto max-w-6xl px-6 py-10">
        {tab === 'documents' ? (
          <div className="space-y-6">

            {/* Page header */}
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-xl font-semibold tracking-tight text-ink">Documents</h1>
                <p className="mt-0.5 text-sm text-muted">
                  {entries.length === 0
                    ? 'Upload a PDF to begin'
                    : `${entries.filter(e => e.doc.status === 'done').length} of ${entries.length} ready`}
                </p>
              </div>
              <button
                onClick={() => setTab('query')}
                disabled={entries.filter(e => e.doc.status === 'done').length === 0}
                className={clsx(
                  'flex items-center gap-2 rounded-sm px-4 py-2 text-sm font-medium transition-colors',
                  entries.filter(e => e.doc.status === 'done').length > 0
                    ? 'bg-ink text-canvas hover:bg-ink/90'
                    : 'bg-stone text-muted cursor-not-allowed',
                )}
              >
                Ask now
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M3 7h8M7 3l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
            </div>

            <div className="grid gap-6 lg:grid-cols-5">

              {/* Left — upload + pipeline */}
              <div className="space-y-4 lg:col-span-2">

                {/* Upload zone */}
                <UploadZone
                  onUploadStart={handleUploadStart}
                  onJobUpdate={handleJobUpdate}
                  onUploadDone={handleUploadDone}
                />

                {/* Ingestion time hint */}
                <div className="flex items-start gap-2.5 rounded-xs border border-hairline bg-stone/50 px-3.5 py-3">
                  <svg className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted" viewBox="0 0 16 16" fill="none">
                    <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.2"/>
                    <path d="M8 5v3.5l2 1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
                  </svg>
                  <p className="text-xs text-muted leading-relaxed">
                    A 100-page PDF takes ~20 minutes to fully ingest — the system builds a knowledge file per page with vision extraction.
                    You can query <span className="text-slate font-medium">pre-ingested documents</span> immediately.
                  </p>
                </div>

                {/* Pipeline steps */}
                <div className="rounded-sm border border-hairline bg-canvas p-4">
                  <p className="mb-3 font-mono text-[10px] uppercase tracking-widest text-muted">Ingestion pipeline</p>
                  <ol className="space-y-2.5">
                    {[
                      ['Text extraction', 'pdfplumber + PyMuPDF per page'],
                      ['OCR fallback',    'Tesseract for scanned pages'],
                      ['Vision pass',     'Charts & tables via Nova 2 Lite'],
                      ['Chunking',        'Multi-granularity text splits'],
                      ['Page Knowledge Graph', '1 LLM call → structured .md per page'],
                      ['Hybrid indexing', 'bge-small dense + BM25 sparse → Qdrant'],
                      ['Cross-doc linking', 'Embedding similarity, zero LLM calls'],
                    ].map(([label, detail], i) => (
                      <li key={i} className="flex items-start gap-2.5">
                        <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-xs bg-stone font-mono text-[9px] font-semibold text-slate">
                          {i + 1}
                        </span>
                        <div>
                          <span className="text-xs font-medium text-ink">{label}</span>
                          <span className="text-xs text-muted"> — {detail}</span>
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
              </div>

              {/* Right — document list */}
              <div className="lg:col-span-3">
                <div className="mb-3 flex items-center justify-between">
                  <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
                    {entries.length > 0 ? `${entries.length} document${entries.length > 1 ? 's' : ''}` : 'No documents yet'}
                  </p>
                  <button onClick={loadDocuments} className="text-xs text-muted hover:text-ink transition-colors">
                    Refresh
                  </button>
                </div>
                <DocumentList entries={entries} onAskNow={() => setTab('query')} />
              </div>

            </div>
          </div>
        ) : tab === 'relationships' ? (
          <RelationshipsPage documents={docs} />
        ) : tab === 'query' ? (
          <QueryPage documents={docs} />
        ) : tab === 'project' ? (
          <AboutProjectPage />
        ) : (
          <AboutCreatorPage />
        )}
      </main>
    </div>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted">
      {children}
    </p>
  )
}
