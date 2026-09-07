import React, { useState } from 'react'
import { FileText, ChevronDown, ChevronUp } from 'lucide-react'
import clsx from 'clsx'
import { Document, Job, getChunks, Chunk } from '../api/client'

interface DocEntry { doc: Document; job?: Job }
interface Props { entries: DocEntry[] }

const STATUS_LABEL: Record<string, string> = {
  queued:     'Queued',
  processing: 'Parsing',
  chunked:    'Chunked',
  extracting: 'Extracting',
  embedding:  'Indexing',
  comparing:  'Comparing',
  done:       'Done',
  failed:     'Failed',
}

const STATUS_DOT: Record<string, string> = {
  queued:     'bg-muted',
  processing: 'bg-action-blue animate-pulse',
  chunked:    'bg-action-blue animate-pulse',
  extracting: 'bg-action-blue animate-pulse',
  embedding:  'bg-action-blue animate-pulse',
  comparing:  'bg-action-blue animate-pulse',
  done:       'bg-deep-green',
  failed:     'bg-error-red',
}

function StatusBadge({ status }: { status: string }) {
  const label = STATUS_LABEL[status] ?? status
  const dot   = STATUS_DOT[status] ?? 'bg-muted'
  return (
    <span className="inline-flex items-center gap-1.5 rounded-xs border border-hairline px-2 py-0.5 text-xs text-slate">
      <span className={clsx('h-1.5 w-1.5 rounded-full', dot)} />
      {label}
    </span>
  )
}

function ProgressBar({ value, active }: { value: number; active: boolean }) {
  return (
    <div className="mt-2 h-px w-full bg-hairline overflow-hidden">
      <div
        className={clsx('h-full bg-ink transition-all duration-500', active && 'progress-active')}
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
    try { setChunks(await getChunks(docId)) }
    finally { setLoading(false) }
  }

  const byLevel = chunks?.reduce<Record<string, number>>((acc, c) => {
    acc[c.level] = (acc[c.level] ?? 0) + 1; return acc
  }, {})

  return (
    <div className="mt-3">
      <button onClick={load} className="text-xs text-muted underline underline-offset-2 hover:text-ink">
        {loading ? 'Loading…' : byLevel ? 'Chunk breakdown' : 'Show chunks'}
      </button>
      {byLevel && (
        <div className="mt-2 flex flex-wrap gap-2">
          {Object.entries(byLevel).map(([level, count]) => (
            <span key={level} className="rounded-xs border border-hairline px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-muted">
              {level} · {count}
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
      <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-hairline p-12 text-center">
        <FileText className="h-8 w-8 text-hairline" strokeWidth={1} />
        <p className="text-sm text-muted">No documents — upload a PDF to begin</p>
      </div>
    )
  }

  return (
    <ul className="space-y-2">
      {entries.map(({ doc, job }) => {
        const isExpanded = expanded === doc.id
        const isActive   = job && !['done', 'failed'].includes(job.status ?? doc.status)

        return (
          <li key={doc.id} className="rounded-sm border border-hairline bg-canvas">
            <button
              className="flex w-full items-start gap-4 p-4 text-left"
              onClick={() => setExpanded(isExpanded ? null : doc.id)}
            >
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xs bg-stone">
                <FileText className="h-4 w-4 text-slate" strokeWidth={1.5} />
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="truncate text-sm font-medium text-ink">{doc.filename}</p>
                  <StatusBadge status={doc.status} />
                </div>

                <p className="mt-0.5 text-xs text-muted">
                  {[
                    doc.file_size && `${(doc.file_size / 1024 / 1024).toFixed(1)} MB`,
                    doc.page_count && `${doc.page_count} pages`,
                    new Date(doc.created_at).toLocaleString(),
                  ].filter(Boolean).join(' · ')}
                </p>

                {job && (
                  <div className="mt-2">
                    <div className="flex items-center justify-between text-xs text-muted">
                      <span>{job.message ?? job.stage}</span>
                      <span className="font-mono">{job.progress}%</span>
                    </div>
                    <ProgressBar value={job.progress} active={!!isActive} />
                  </div>
                )}

                {doc.error_msg && (
                  <p className="mt-1.5 text-xs text-error-red">{doc.error_msg}</p>
                )}
              </div>

              <div className="shrink-0 text-muted">
                {isExpanded
                  ? <ChevronUp className="h-4 w-4" />
                  : <ChevronDown className="h-4 w-4" />}
              </div>
            </button>

            {isExpanded && (
              <div className="border-t border-hairline px-4 pb-4 pt-3">
                <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
                  {[
                    ['Document ID', <span className="font-mono break-all">{doc.id}</span>],
                    ['Stage',       job?.stage ?? '—'],
                    ['Pages',       job?.total_pages ?? doc.page_count ?? '—'],
                    ['Source',      'Text + OCR fallback'],
                  ].map(([k, v]) => (
                    <div key={String(k)}>
                      <dt className="text-muted">{k}</dt>
                      <dd className="mt-0.5 text-ink">{v}</dd>
                    </div>
                  ))}
                </dl>
                {(doc.status === 'chunked' || doc.status === 'done') && (
                  <ChunkStats docId={doc.id} />
                )}
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
}
