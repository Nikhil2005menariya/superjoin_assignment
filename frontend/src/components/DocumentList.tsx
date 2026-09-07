import React, { useState } from 'react'
import { FileText, ChevronDown, ChevronUp, AlertCircle, CheckCircle, Clock, Loader2, XCircle } from 'lucide-react'
import clsx from 'clsx'
import { Document, Job, getChunks, Chunk } from '../api/client'

interface DocEntry {
  doc: Document
  job?: Job
}

interface Props {
  entries: DocEntry[]
}

const STATUS_CONFIG: Record<string, { label: string; color: string; Icon: React.FC<any> }> = {
  queued:     { label: 'Queued',     color: 'text-gray-500  bg-gray-100',   Icon: Clock },
  processing: { label: 'Parsing',    color: 'text-blue-600  bg-blue-100',   Icon: Loader2 },
  chunked:    { label: 'Chunked',    color: 'text-indigo-600 bg-indigo-100', Icon: CheckCircle },
  extracting: { label: 'Extracting', color: 'text-violet-600 bg-violet-100', Icon: Loader2 },
  embedding:  { label: 'Embedding',  color: 'text-cyan-600  bg-cyan-100',   Icon: Loader2 },
  comparing:  { label: 'Comparing',  color: 'text-amber-600 bg-amber-100',  Icon: Loader2 },
  done:       { label: 'Done',       color: 'text-green-700 bg-green-100',  Icon: CheckCircle },
  failed:     { label: 'Failed',     color: 'text-red-600   bg-red-100',    Icon: XCircle },
}

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG['queued']
  const { label, color, Icon } = cfg
  const spin = ['processing', 'extracting', 'embedding', 'comparing'].includes(status)
  return (
    <span className={clsx('inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium', color)}>
      <Icon className={clsx('h-3 w-3', spin && 'animate-spin')} />
      {label}
    </span>
  )
}

function ProgressBar({ value, active }: { value: number; active: boolean }) {
  return (
    <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-gray-200">
      <div
        className={clsx(
          'h-full rounded-full bg-brand-500 transition-all duration-500',
          active && 'progress-active',
        )}
        style={{ width: `${value}%` }}
      />
    </div>
  )
}

function ChunkStats({ docId }: { docId: string }) {
  const [chunks, setChunks] = useState<Chunk[] | null>(null)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    if (chunks) return
    setLoading(true)
    try {
      const all = await getChunks(docId)
      setChunks(all)
    } finally {
      setLoading(false)
    }
  }

  const byLevel = chunks
    ? chunks.reduce<Record<string, number>>((acc, c) => {
        acc[c.level] = (acc[c.level] ?? 0) + 1
        return acc
      }, {})
    : null

  return (
    <div className="mt-3">
      <button
        onClick={load}
        className="text-xs text-brand-600 hover:underline"
      >
        {loading ? 'Loading chunks…' : chunks ? 'Chunk breakdown' : 'Show chunk breakdown'}
      </button>
      {byLevel && (
        <div className="mt-2 flex flex-wrap gap-2">
          {Object.entries(byLevel).map(([level, count]) => (
            <span key={level} className="rounded-md bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
              {level}: <strong>{count}</strong>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export function DocumentList({ entries }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null)

  if (!entries.length) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-gray-200 p-12 text-center">
        <FileText className="h-10 w-10 text-gray-300" />
        <p className="text-sm text-gray-500">No documents yet — upload a PDF to get started</p>
      </div>
    )
  }

  return (
    <ul className="space-y-3">
      {entries.map(({ doc, job }) => {
        const isExpanded = expanded === doc.id
        const isActive = job && !['done', 'failed', 'chunked'].includes(job.status ?? doc.status)

        return (
          <li key={doc.id} className="rounded-xl border border-gray-200 bg-white shadow-sm">
            <button
              className="flex w-full items-start gap-4 p-4 text-left"
              onClick={() => setExpanded(isExpanded ? null : doc.id)}
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-50">
                <FileText className="h-5 w-5 text-brand-600" />
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="truncate text-sm font-semibold text-gray-800">{doc.filename}</p>
                  <StatusBadge status={doc.status} />
                </div>

                <div className="mt-0.5 flex gap-3 text-xs text-gray-400">
                  {doc.file_size && <span>{(doc.file_size / 1024 / 1024).toFixed(1)} MB</span>}
                  {doc.page_count && <span>{doc.page_count} pages</span>}
                  <span>{new Date(doc.created_at).toLocaleString()}</span>
                </div>

                {job && (
                  <div className="mt-2">
                    <div className="flex items-center justify-between text-xs text-gray-500">
                      <span>{job.message ?? job.stage}</span>
                      <span>{job.progress}%</span>
                    </div>
                    <ProgressBar value={job.progress} active={!!isActive} />
                  </div>
                )}

                {doc.error_msg && (
                  <div className="mt-2 flex items-center gap-1.5 text-xs text-red-600">
                    <AlertCircle className="h-3.5 w-3.5" />
                    {doc.error_msg}
                  </div>
                )}
              </div>

              <div className="shrink-0 text-gray-400">
                {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              </div>
            </button>

            {isExpanded && (
              <div className="border-t border-gray-100 px-4 pb-4 pt-3">
                <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
                  <div>
                    <dt className="text-gray-400">Document ID</dt>
                    <dd className="mt-0.5 font-mono text-gray-600 break-all">{doc.id}</dd>
                  </div>
                  <div>
                    <dt className="text-gray-400">Stage</dt>
                    <dd className="mt-0.5 text-gray-600">{job?.stage ?? '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-gray-400">Pages</dt>
                    <dd className="mt-0.5 text-gray-600">{job?.total_pages ?? doc.page_count ?? '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-gray-400">Source type</dt>
                    <dd className="mt-0.5 text-gray-600">Mixed (text + OCR)</dd>
                  </div>
                </dl>

                {doc.status === 'chunked' || doc.status === 'done' ? (
                  <ChunkStats docId={doc.id} />
                ) : null}
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
}
