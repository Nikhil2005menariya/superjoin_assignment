import React, { useCallback, useEffect, useRef, useState } from 'react'
import clsx from 'clsx'
import { Document, Job, listDocuments } from './api/client'
import { UploadZone } from './components/UploadZone'
import { DocumentList } from './components/DocumentList'
import { FactsPage } from './pages/FactsPage'
import { RelationshipsPage } from './pages/RelationshipsPage'

interface DocEntry { doc: Document; job?: Job }
type Tab = 'documents' | 'facts' | 'relationships'

const PHASES = [
  { n: 1, label: 'Document Intelligence', done: true },
  { n: 2, label: 'Fact Extraction',       done: true },
  { n: 3, label: 'ColBERT Indexing',      done: true },
  { n: 4, label: 'Cross-Doc Comparison',  done: false, active: true },
  { n: 5, label: 'Query Interface',       done: false },
]

export default function App() {
  const [entries, setEntries] = useState<DocEntry[]>([])
  const [tab, setTab]         = useState<Tab>('documents')
  const pollRef               = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadDocuments = useCallback(async () => {
    const docs = await listDocuments()
    setEntries(prev => {
      const jobMap = Object.fromEntries(prev.map(e => [e.doc.id, e.job]))
      return docs.map(doc => ({ doc, job: jobMap[doc.id] }))
    })
  }, [])

  useEffect(() => {
    loadDocuments()
    pollRef.current = setInterval(loadDocuments, 5000)
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
    { id: 'facts',         label: 'Facts' },
    { id: 'relationships', label: 'Relationships' },
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

          {/* Phase stepper */}
          <ol className="hidden items-center gap-1 md:flex">
            {PHASES.map(({ n, label, done, active }) => (
              <React.Fragment key={n}>
                <li className={clsx(
                  'flex items-center gap-1.5 rounded-pill px-3 py-1 text-xs font-medium transition-colors',
                  done   ? 'bg-ink text-canvas' :
                  active ? 'bg-stone text-ink border border-hairline' :
                           'text-muted',
                )}>
                  <span className={clsx(
                    'flex h-3.5 w-3.5 items-center justify-center rounded-full text-[9px] font-semibold',
                    done || active ? 'bg-white/20' : 'bg-hairline',
                    !done && !active && 'text-muted bg-transparent',
                  )}>
                    {n}
                  </span>
                  {label}
                </li>
                {n < 5 && <span className="text-hairline text-xs">›</span>}
              </React.Fragment>
            ))}
          </ol>
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
          <div className="grid gap-10 lg:grid-cols-5">
            <div className="lg:col-span-2">
              <SectionLabel>Upload</SectionLabel>
              <UploadZone
                onUploadStart={handleUploadStart}
                onJobUpdate={handleJobUpdate}
                onUploadDone={handleUploadDone}
              />
              <div className="mt-6">
                <SectionLabel>Pipeline</SectionLabel>
                <ol className="mt-3 space-y-2">
                  {[
                    'Page type detection — text vs. scanned',
                    'Layout extraction with coordinates (pdfplumber)',
                    'OCR fallback for image pages (Tesseract)',
                    'Deterministic table → natural language',
                    'Multi-granularity chunking',
                    'Groq llama-3.3-70b fact extraction',
                    'rapidfuzz evidence verification',
                    'Domain-agnostic unit + time normalization',
                    'bge-large dense + BM25 sparse indexing',
                    'ColBERT multi-vector late interaction',
                    'Cross-document relationship classification',
                  ].map((s, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-xs text-body-muted">
                      <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-xs bg-stone font-mono text-[9px] font-semibold text-slate">
                        {i + 1}
                      </span>
                      {s}
                    </li>
                  ))}
                </ol>
              </div>
            </div>
            <div className="lg:col-span-3">
              <div className="mb-4 flex items-center justify-between">
                <SectionLabel>Documents ({entries.length})</SectionLabel>
                <button onClick={loadDocuments} className="text-xs text-muted hover:text-ink underline underline-offset-2">
                  Refresh
                </button>
              </div>
              <DocumentList entries={entries} />
            </div>
          </div>
        ) : tab === 'facts' ? (
          <FactsPage documents={docs} />
        ) : (
          <RelationshipsPage documents={docs} />
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
