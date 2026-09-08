import React, { useState } from 'react'
import { FileText, ChevronDown, ChevronUp, MessageSquare, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import { Document, Job, getChunks, Chunk } from '../api/client'

interface DocEntry { doc: Document; job?: Job }
interface Props { entries: DocEntry[]; onAskNow?: () => void }

const STAGE_STEPS = ['processing', 'chunked', 'embedding', 'generating', 'linking', 'done']

const STAGE_LABEL: Record<string, string> = {
  queued:     'Queued',
  processing: 'Parsing pages',
  chunked:    'Chunked',
  embedding:  'Indexing vectors',
  generating: 'Building knowledge graph',
  linking:    'Cross-linking docs',
  done:       'Ready',
  failed:     'Failed',
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'done')   return <CheckCircle2 className="h-4 w-4 text-deep-green" />
  if (status === 'failed') return <AlertCircle className="h-4 w-4 text-error-red" />
  return <Loader2 className="h-4 w-4 text-action-blue animate-spin" />
}

function ProgressBar({ value, active }: { value: number; active: boolean }) {
  return (
    <div className="h-1 w-full overflow-hidden rounded-full bg-hairline">
      <div
        className={clsx(
          'h-full rounded-full bg-ink transition-all duration-700',
          active && 'progress-active',
        )}
        style={{ width: `${value}%` }}
      />
    </div>
  )
}

function StageTrack({ status, progress }: { status: string; progress?: number }) {
  const idx = STAGE_STEPS.indexOf(status)
  return (
    <div className="mt-3 space-y-1.5">
      <div className="flex items-center justify-between text-[10px] font-mono text-muted">
        <span>{STAGE_LABEL[status] ?? status}</span>
        {progress !== undefined && <span>{progress}%</span>}
      </div>
      <ProgressBar value={progress ?? (status === 'done' ? 100 : 0)} active={status !== 'done' && status !== 'failed'} />
      <div className="flex gap-1 pt-0.5">
        {STAGE_STEPS.slice(0, -1).map((s, i) => (
          <div
            key={s}
            className={clsx(
              'h-0.5 flex-1 rounded-full transition-colors duration-500',
              i < idx ? 'bg-ink' : i === idx ? 'bg-action-blue' : 'bg-hairline',
            )}
          />
        ))}
      </div>
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
    <div className="mt-3 border-t border-hairline pt-3">
      <button onClick={load} className="text-[11px] text-muted underline underline-offset-2 hover:text-ink transition-colors">
        {loading ? 'Loading…' : byLevel ? 'Chunk breakdown' : 'Show chunks'}
      </button>
      {byLevel && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {Object.entries(byLevel).map(([level, count]) => (
            <span key={level} className="rounded-xs border border-hairline bg-stone px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider text-slate">
              {level} · {count}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export function DocumentList({ entries, onAskNow }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null)

  if (!entries.length) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-sm border border-dashed border-hairline p-14 text-center">
        <FileText className="h-8 w-8 text-hairline" strokeWidth={1} />
        <div>
          <p className="text-sm font-medium text-ink">No documents yet</p>
          <p className="mt-0.5 text-xs text-muted">Upload a PDF to start ingestion</p>
        </div>
      </div>
    )
  }

  return (
    <ul className="space-y-2">
      {entries.map(({ doc, job }) => {
        const isExpanded = expanded === doc.id
        const status     = job?.status ?? doc.status
        const isDone     = status === 'done'
        const isFailed   = status === 'failed'
        const isActive   = !isDone && !isFailed

        return (
          <li key={doc.id} className={clsx(
            'rounded-sm border bg-canvas transition-colors',
            isDone   ? 'border-hairline' :
            isFailed ? 'border-error-red/30' :
                       'border-action-blue/20',
          )}>
            <div className="flex items-start gap-3 p-4">
              {/* File icon */}
              <div className={clsx(
                'flex h-10 w-10 shrink-0 items-center justify-center rounded-xs',
                isDone ? 'bg-pale-green' : isFailed ? 'bg-error-red/10' : 'bg-stone',
              )}>
                <FileText className={clsx(
                  'h-4.5 w-4.5',
                  isDone ? 'text-deep-green' : isFailed ? 'text-error-red' : 'text-slate',
                )} strokeWidth={1.5} />
              </div>

              {/* Main content */}
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-ink">{doc.filename}</p>
                    <p className="mt-0.5 text-[11px] text-muted">
                      {[
                        doc.file_size && `${(doc.file_size / 1024 / 1024).toFixed(1)} MB`,
                        doc.page_count && `${doc.page_count} pages`,
                        new Date(doc.created_at).toLocaleDateString(),
                      ].filter(Boolean).join(' · ')}
                    </p>
                  </div>

                  <div className="flex shrink-0 items-center gap-2">
                    <StatusIcon status={status} />
                    {isDone && onAskNow && (
                      <button
                        onClick={onAskNow}
                        className="flex items-center gap-1 rounded-xs border border-hairline bg-stone px-2.5 py-1 text-[11px] font-medium text-slate hover:border-ink hover:text-ink transition-colors"
                      >
                        <MessageSquare className="h-3 w-3" />
                        Ask
                      </button>
                    )}
                    <button
                      onClick={() => setExpanded(isExpanded ? null : doc.id)}
                      className="text-muted hover:text-ink transition-colors"
                    >
                      {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </button>
                  </div>
                </div>

                {/* Progress track */}
                {isActive && job && (
                  <StageTrack status={status} progress={job.progress} />
                )}

                {doc.error_msg && (
                  <p className="mt-2 text-xs text-error-red">{doc.error_msg}</p>
                )}
              </div>
            </div>

            {/* Expanded detail */}
            {isExpanded && (
              <div className="border-t border-hairline bg-stone/20 px-4 pb-4 pt-3">
                <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
                  {[
                    ['Document ID', <span className="font-mono text-[10px] break-all">{doc.id}</span>],
                    ['Stage',       STAGE_LABEL[status] ?? status],
                    ['Pages',       job?.total_pages ?? doc.page_count ?? '—'],
                    ['Method',      'Text + OCR + Vision'],
                  ].map(([k, v]) => (
                    <div key={String(k)}>
                      <dt className="text-muted">{k}</dt>
                      <dd className="mt-0.5 text-ink">{v as React.ReactNode}</dd>
                    </div>
                  ))}
                </dl>
                {(status === 'chunked' || isDone) && <ChunkStats docId={doc.id} />}
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
}
