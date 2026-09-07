import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Brain, FileText, Sparkles } from 'lucide-react'
import clsx from 'clsx'
import { Document, Job, listDocuments } from './api/client'
import { UploadZone } from './components/UploadZone'
import { DocumentList } from './components/DocumentList'
import { FactsPage } from './pages/FactsPage'

interface DocEntry { doc: Document; job?: Job }
type Tab = 'documents' | 'facts'

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

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600">
              <Brain className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900">Fact Knowledge Layer</h1>
              <p className="text-xs text-gray-500">Extract · Verify · Compare facts across any document</p>
            </div>
          </div>
          <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-medium text-green-700">
            Phase 3 — ColBERT Hybrid Retrieval
          </span>
        </div>
      </header>

      {/* Pipeline stepper */}
      <div className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-3">
          <ol className="flex items-center gap-1 text-xs">
            {[
              { n: 1, label: 'Doc Intelligence', done: true },
              { n: 2, label: 'Fact Extraction',  done: true },
              { n: 3, label: 'ColBERT Indexing', done: false, active: true },
              { n: 4, label: 'KG Comparison',    done: false },
              { n: 5, label: 'Query & UI',        done: false },
            ].map(({ n, label, done, active }) => (
              <React.Fragment key={n}>
                <li className={clsx(
                  'flex items-center gap-1.5 rounded-full px-3 py-1 font-medium',
                  done   ? 'bg-green-600 text-white'  :
                  active ? 'bg-brand-600 text-white'  :
                           'text-gray-400'
                )}>
                  <span className={clsx('flex h-4 w-4 items-center justify-center rounded-full text-[10px]',
                    done || active ? 'bg-white/20' : 'bg-gray-200'
                  )}>{n}</span>
                  {label}
                </li>
                {n < 5 && <span className="text-gray-300">›</span>}
              </React.Fragment>
            ))}
          </ol>
        </div>
      </div>

      {/* Tab bar */}
      <div className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-6xl px-6">
          <nav className="flex gap-0">
            {([
              { id: 'documents', label: 'Documents', Icon: FileText },
              { id: 'facts',     label: 'Facts',     Icon: Sparkles },
            ] as const).map(({ id, label, Icon }) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={clsx(
                  'flex items-center gap-2 border-b-2 px-5 py-3 text-sm font-medium transition-colors',
                  tab === id
                    ? 'border-brand-600 text-brand-700'
                    : 'border-transparent text-gray-500 hover:text-gray-700',
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Main content */}
      <main className="mx-auto max-w-6xl px-6 py-8">
        {tab === 'documents' ? (
          <div className="grid gap-8 lg:grid-cols-5">
            <div className="lg:col-span-2">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">Upload Document</h2>
              <UploadZone
                onUploadStart={handleUploadStart}
                onJobUpdate={handleJobUpdate}
                onUploadDone={handleUploadDone}
              />
              <div className="mt-4 rounded-xl border border-gray-200 bg-white p-4">
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Phase 1 + 2 Pipeline</h3>
                <ol className="space-y-1.5 text-xs text-gray-600">
                  {[
                    'Page type detection (text-native vs scanned)',
                    'pdfplumber layout extraction with coordinates',
                    'OCR fallback (tesseract) for image pages',
                    'Table → NL deterministic conversion',
                    'Multi-granularity chunking (section/para/sentence/table_row)',
                    'Groq llama-3.3-70b fact extraction (JSON mode)',
                    'rapidfuzz evidence verification per fact',
                    'Unit + time + entity normalization',
                    'bge-large dense + BM25 sparse → Qdrant',
                  ].map((s, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-brand-100 text-[10px] font-bold text-brand-700">{i + 1}</span>
                      {s}
                    </li>
                  ))}
                </ol>
              </div>
            </div>
            <div className="lg:col-span-3">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
                  Documents ({entries.length})
                </h2>
                <button onClick={loadDocuments} className="text-xs text-brand-600 hover:underline">Refresh</button>
              </div>
              <DocumentList entries={entries} />
            </div>
          </div>
        ) : (
          <FactsPage documents={docs} />
        )}
      </main>
    </div>
  )
}
