import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Brain, Github } from 'lucide-react'
import { Document, Job, listDocuments, getJob } from './api/client'
import { UploadZone } from './components/UploadZone'
import { DocumentList } from './components/DocumentList'

interface DocEntry {
  doc: Document
  job?: Job
}

export default function App() {
  const [entries, setEntries] = useState<DocEntry[]>([])
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadDocuments = useCallback(async () => {
    const docs = await listDocuments()
    setEntries((prev) => {
      const jobMap = Object.fromEntries(prev.map((e) => [e.doc.id, e.job]))
      return docs.map((doc) => ({ doc, job: jobMap[doc.id] }))
    })
  }, [])

  useEffect(() => {
    loadDocuments()
    pollRef.current = setInterval(loadDocuments, 5000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [loadDocuments])

  const handleUploadStart = useCallback((docId: string, filename: string) => {
    setEntries((prev) => [
      {
        doc: {
          id: docId,
          filename,
          file_size: null,
          page_count: null,
          status: 'queued',
          error_msg: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        job: undefined,
      },
      ...prev,
    ])
  }, [])

  const handleJobUpdate = useCallback((docId: string, job: Job) => {
    setEntries((prev) =>
      prev.map((e) =>
        e.doc.id === docId
          ? { doc: { ...e.doc, status: job.status === 'done' ? 'chunked' : e.doc.status, page_count: job.total_pages || e.doc.page_count }, job }
          : e
      )
    )
  }, [])

  const handleUploadDone = useCallback((_docId: string) => {
    loadDocuments()
  }, [loadDocuments])

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
              <p className="text-xs text-gray-500">Extract · Link · Compare facts across any document</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-medium text-green-700">
              Phase 1 — Document Intelligence
            </span>
          </div>
        </div>
      </header>

      {/* Pipeline steps */}
      <div className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-3">
          <ol className="flex items-center gap-1 text-xs">
            {[
              { n: 1, label: 'Doc Intelligence', active: true },
              { n: 2, label: 'Fact Extraction',  active: false },
              { n: 3, label: 'ColBERT Indexing', active: false },
              { n: 4, label: 'KG Comparison',    active: false },
              { n: 5, label: 'Query & UI',        active: false },
            ].map(({ n, label, active }) => (
              <React.Fragment key={n}>
                <li className={`flex items-center gap-1.5 rounded-full px-3 py-1 font-medium ${active ? 'bg-brand-600 text-white' : 'text-gray-400'}`}>
                  <span className={`flex h-4 w-4 items-center justify-center rounded-full text-[10px] ${active ? 'bg-white/20' : 'bg-gray-200'}`}>{n}</span>
                  {label}
                </li>
                {n < 5 && <span className="text-gray-300">›</span>}
              </React.Fragment>
            ))}
          </ol>
        </div>
      </div>

      {/* Main */}
      <main className="mx-auto max-w-6xl px-6 py-8">
        <div className="grid gap-8 lg:grid-cols-5">
          {/* Upload — 2 cols */}
          <div className="lg:col-span-2">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">Upload Document</h2>
            <UploadZone
              onUploadStart={handleUploadStart}
              onJobUpdate={handleJobUpdate}
              onUploadDone={handleUploadDone}
            />

            {/* What happens info box */}
            <div className="mt-4 rounded-xl border border-gray-200 bg-white p-4">
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Phase 1 Pipeline</h3>
              <ol className="space-y-1.5 text-xs text-gray-600">
                {[
                  'Detect page type (text-native vs scanned)',
                  'pdfplumber layout extraction with coordinates',
                  'OCR fallback (tesseract) for image pages',
                  'Structural table detection → NL conversion',
                  'Multi-granularity chunking (section / para / sentence / table row)',
                  'SQLite persistence + Qdrant collection ready',
                ].map((step, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-brand-100 text-[10px] font-bold text-brand-700">{i + 1}</span>
                    {step}
                  </li>
                ))}
              </ol>
            </div>
          </div>

          {/* Document list — 3 cols */}
          <div className="lg:col-span-3">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
                Documents ({entries.length})
              </h2>
              <button onClick={loadDocuments} className="text-xs text-brand-600 hover:underline">
                Refresh
              </button>
            </div>
            <DocumentList entries={entries} />
          </div>
        </div>
      </main>
    </div>
  )
}
