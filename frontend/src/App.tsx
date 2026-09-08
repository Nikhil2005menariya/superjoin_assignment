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
    { id: 'query',         label: 'Query' },
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
                    'Vision pass for charts/infographics (Nova 2 Lite)',
                    'Multi-granularity chunking',
                    'Page Knowledge Graph — 1 LLM call per page',
                    'bge-large dense + BM25 sparse indexing',
                    'ColBERT multi-vector late interaction',
                    'Cross-document relationship classification',
                    'Embedding similarity → CORROBORATES / CONTRADICTS / RECONCILES',
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
