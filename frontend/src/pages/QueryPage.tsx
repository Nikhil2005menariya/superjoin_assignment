import React, { useState, useCallback, useRef, useEffect } from 'react'
import { ArrowUp, BookOpen, Layers, RotateCcw, ChevronDown, ChevronUp } from 'lucide-react'
import clsx from 'clsx'
import { api, Document } from '../api/client'
import { MarkdownCanvas } from '../components/MarkdownCanvas'

interface Props { documents: Document[] }

interface RetrievalMeta {
  hits: number
  md_files?: number
  chunks?: number
  method: string
}

interface SourceChunk {
  text: string
  page_num?: number
  doc_id?: string
  score?: number
  section_path?: string
}

interface QueryResult {
  answer: string
  source_facts: SourceChunk[]
  confidence: 'HIGH' | 'MEDIUM' | 'LOW'
  retrieval_meta: RetrievalMeta
  caveat: string | null
}

interface HistoryEntry {
  id: string
  question: string
  result: QueryResult
  docId: string
  ts: number
}

const CONFIDENCE_CONFIG = {
  HIGH:   { label: 'High confidence', dot: 'bg-deep-green', pill: 'bg-pale-green text-deep-green border-deep-green/25' },
  MEDIUM: { label: 'Medium confidence', dot: 'bg-amber-500', pill: 'bg-amber-50 text-amber-700 border-amber-200' },
  LOW:    { label: 'Low confidence',  dot: 'bg-muted',     pill: 'bg-stone text-slate border-hairline' },
}

const EXAMPLES = [
  'What was the total revenue for the last reported period?',
  'What are the top risk factors mentioned?',
  'Summarize the key financial metrics across all periods.',
  'Are there any contradictions across documents?',
  'What growth metrics are reported?',
]

function ConfidencePill({ level }: { level: 'HIGH' | 'MEDIUM' | 'LOW' }) {
  const cfg = CONFIDENCE_CONFIG[level]
  return (
    <span className={clsx('flex items-center gap-1.5 rounded-pill border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wider', cfg.pill)}>
      <span className={clsx('h-1.5 w-1.5 rounded-full', cfg.dot)} />
      {cfg.label}
    </span>
  )
}

function MetaChip({ label, value }: { label: string; value: string | number }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-xs border border-hairline bg-stone px-2 py-0.5 font-mono text-[10px] text-muted">
      <span className="text-muted/60">{label}</span>
      <span className="font-semibold text-slate">{value}</span>
    </span>
  )
}

function SourcePanel({ chunks, documents }: { chunks: SourceChunk[]; documents: Document[] }) {
  const [open, setOpen] = useState(false)
  if (!chunks?.length) return null

  const docMap = Object.fromEntries(documents.map(d => [d.id, d.filename]))

  return (
    <div className="rounded-sm border border-hairline overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-xs text-muted hover:bg-stone/40 transition-colors"
      >
        <span className="flex items-center gap-2 font-medium text-slate">
          <BookOpen className="h-3.5 w-3.5" />
          {chunks.length} source passage{chunks.length !== 1 ? 's' : ''} retrieved
        </span>
        {open ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
      </button>

      {open && (
        <div className="divide-y divide-hairline border-t border-hairline">
          {chunks.slice(0, 8).map((c, i) => (
            <div key={i} className="px-4 py-3 bg-stone/20">
              <div className="mb-1.5 flex items-center gap-2 flex-wrap">
                {c.doc_id && docMap[c.doc_id] && (
                  <span className="font-mono text-[10px] text-action-blue truncate max-w-[200px]">
                    {docMap[c.doc_id]}
                  </span>
                )}
                {c.page_num && (
                  <span className="rounded-xs bg-stone px-1.5 py-0.5 font-mono text-[9px] text-muted">
                    p.{c.page_num}
                  </span>
                )}
                {c.section_path && (
                  <span className="font-mono text-[9px] text-muted truncate">{c.section_path}</span>
                )}
                {c.score != null && (
                  <span className="ml-auto font-mono text-[9px] text-muted">
                    score {Number(c.score).toFixed(3)}
                  </span>
                )}
              </div>
              <p className="text-xs text-body-muted leading-relaxed line-clamp-4">{c.text ?? ''}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function AnswerCard({
  entry,
  documents,
}: {
  entry: HistoryEntry
  documents: Document[]
}) {
  const { question, result } = entry
  const meta = result.retrieval_meta

  return (
    <div className="space-y-3">
      {/* Question bubble */}
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-lg rounded-br-xs bg-ink px-4 py-3 text-sm text-canvas leading-relaxed shadow-sm">
          {question}
        </div>
      </div>

      {/* Answer card */}
      <div className="rounded-sm border border-hairline bg-canvas shadow-sm overflow-hidden">
        {/* Card header */}
        <div className="flex items-center justify-between gap-3 border-b border-hairline px-4 py-2.5 flex-wrap">
          <ConfidencePill level={result.confidence} />
          <div className="flex items-center gap-1.5 flex-wrap">
            {meta?.md_files !== undefined && (
              <MetaChip label="pages" value={meta.md_files} />
            )}
            {meta?.chunks !== undefined && (
              <MetaChip label="chunks" value={meta.chunks} />
            )}
            {meta?.method && (
              <MetaChip label="method" value={meta.method} />
            )}
          </div>
        </div>

        {/* Markdown answer */}
        <div className="px-5 py-4">
          <MarkdownCanvas content={result.answer} />
          {result.caveat && (
            <div className="mt-4 flex items-start gap-2 rounded-xs border border-amber-200 bg-amber-50 px-3 py-2.5">
              <span className="mt-0.5 text-amber-500 text-sm">⚠</span>
              <p className="text-xs text-amber-700 leading-relaxed">{result.caveat}</p>
            </div>
          )}
        </div>

        {/* Sources */}
        {result.source_facts?.length > 0 && (
          <div className="border-t border-hairline px-4 pb-4 pt-3">
            <SourcePanel chunks={result.source_facts as SourceChunk[]} documents={documents} />
          </div>
        )}
      </div>
    </div>
  )
}

export function QueryPage({ documents }: Props) {
  const [question, setQuestion]   = useState('')
  const [loading, setLoading]     = useState(false)
  const [filterDoc, setFilterDoc] = useState('')
  const [error, setError]         = useState<string | null>(null)
  const [history, setHistory]     = useState<HistoryEntry[]>([])
  const textareaRef               = useRef<HTMLTextAreaElement>(null)
  const bottomRef                 = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (history.length) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [history.length])

  // Auto-resize textarea
  const resizeTextarea = () => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
  }

  const submit = useCallback(async (q: string) => {
    const trimmed = q.trim()
    if (!trimmed || trimmed.length < 3 || loading) return
    setLoading(true)
    setError(null)
    setQuestion('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    try {
      const { data } = await api.post('/query', {
        question: trimmed,
        doc_id: filterDoc || undefined,
        limit: 10,
      })
      setHistory(prev => [...prev, {
        id: crypto.randomUUID(),
        question: trimmed,
        result: data,
        docId: filterDoc,
        ts: Date.now(),
      }])
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Query failed — please try again')
    } finally {
      setLoading(false)
    }
  }, [filterDoc, loading])

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit(question)
    }
  }

  return (
    <div className="flex flex-col" style={{ minHeight: 'calc(100vh - 130px)' }}>

      {/* Chat history */}
      <div className="flex-1 mx-auto w-full max-w-4xl px-4 pb-4">
        {history.length === 0 && !loading && (
          <div className="flex flex-col items-center justify-center py-20 gap-6">
            <div className="flex h-12 w-12 items-center justify-center rounded-sm bg-ink">
              <Layers className="h-6 w-6 text-canvas" />
            </div>
            <div className="text-center">
              <p className="text-base font-semibold text-ink mb-1">Ask anything about your documents</p>
              <p className="text-sm text-muted">Tables, numbers, summaries, comparisons — all rendered richly</p>
            </div>
            <div className="flex flex-wrap justify-center gap-2 max-w-lg">
              {EXAMPLES.map(ex => (
                <button
                  key={ex}
                  onClick={() => submit(ex)}
                  className="rounded-pill border border-hairline px-3.5 py-1.5 text-xs text-slate hover:border-slate hover:text-ink hover:bg-stone/40 transition-colors"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="space-y-8 pt-4">
          {history.map(entry => (
            <AnswerCard key={entry.id} entry={entry} documents={documents} />
          ))}

          {/* Loading state */}
          {loading && (
            <div className="space-y-3">
              <div className="flex justify-end">
                <div className="max-w-[80%] rounded-lg rounded-br-xs bg-ink px-4 py-3 text-sm text-canvas">
                  {/* Show the last submitted question */}
                </div>
              </div>
              <div className="rounded-sm border border-hairline bg-canvas p-5 shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="flex gap-1">
                    {[0, 1, 2].map(i => (
                      <div
                        key={i}
                        className="h-2 w-2 rounded-full bg-muted animate-bounce"
                        style={{ animationDelay: `${i * 120}ms` }}
                      />
                    ))}
                  </div>
                  <span className="text-xs text-muted">Searching knowledge graph…</span>
                </div>
                {/* Skeleton lines */}
                <div className="mt-4 space-y-2">
                  <div className="h-3 w-3/4 rounded-xs bg-stone animate-pulse" />
                  <div className="h-3 w-full rounded-xs bg-stone animate-pulse" />
                  <div className="h-3 w-5/6 rounded-xs bg-stone animate-pulse" />
                  <div className="mt-3 h-16 w-full rounded-xs bg-stone/60 animate-pulse" />
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="rounded-sm border border-error-red/30 bg-canvas px-4 py-3 shadow-sm">
              <p className="text-xs text-error-red">{error}</p>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Sticky input bar */}
      <div className="sticky bottom-0 bg-canvas border-t border-hairline">
        <div className="mx-auto max-w-4xl px-4 py-3">
          {history.length > 0 && (
            <div className="mb-2 flex items-center justify-between">
              <div className="flex flex-wrap gap-1.5">
                {EXAMPLES.slice(0, 3).map(ex => (
                  <button
                    key={ex}
                    onClick={() => submit(ex)}
                    disabled={loading}
                    className="rounded-pill border border-hairline px-2.5 py-1 text-[11px] text-slate hover:border-slate hover:text-ink hover:bg-stone/40 transition-colors disabled:opacity-40"
                  >
                    {ex}
                  </button>
                ))}
              </div>
              <button
                onClick={() => setHistory([])}
                className="flex items-center gap-1.5 text-[11px] text-muted hover:text-ink transition-colors"
              >
                <RotateCcw className="h-3 w-3" /> Clear
              </button>
            </div>
          )}

          <div className="flex items-end gap-2 rounded-sm border border-hairline bg-canvas shadow-sm focus-within:border-slate transition-colors">
            <div className="flex-1 px-3 pt-3 pb-2">
              <textarea
                ref={textareaRef}
                value={question}
                onChange={e => { setQuestion(e.target.value); resizeTextarea() }}
                onKeyDown={handleKey}
                placeholder="Ask a question… (Enter to send, Shift+Enter for new line)"
                rows={1}
                disabled={loading}
                className="w-full resize-none bg-transparent text-sm leading-relaxed text-ink placeholder:text-muted outline-none disabled:opacity-50"
                style={{ minHeight: '24px', maxHeight: '160px' }}
              />
            </div>

            <div className="flex items-end gap-2 pb-2.5 pr-2.5">
              <select
                value={filterDoc}
                onChange={e => setFilterDoc(e.target.value)}
                className="rounded-xs border border-hairline bg-stone px-2 py-1.5 text-[11px] text-muted outline-none focus:border-slate max-w-[140px] truncate"
              >
                <option value="">All docs</option>
                {documents.map(d => (
                  <option key={d.id} value={d.id}>{d.filename}</option>
                ))}
              </select>

              <button
                onClick={() => submit(question)}
                disabled={loading || question.trim().length < 3}
                className={clsx(
                  'flex h-8 w-8 items-center justify-center rounded-xs transition-colors',
                  loading || question.trim().length < 3
                    ? 'bg-stone text-muted cursor-not-allowed'
                    : 'bg-ink text-canvas hover:bg-ink/90',
                )}
              >
                {loading
                  ? <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-canvas/40 border-t-canvas" />
                  : <ArrowUp className="h-4 w-4" />
                }
              </button>
            </div>
          </div>
          <p className="mt-1.5 text-center font-mono text-[9px] text-muted/60 uppercase tracking-widest">
            Powered by Amazon Nova 2 Lite · Page Knowledge Graph · BM25 + Dense Hybrid Search
          </p>
        </div>
      </div>

    </div>
  )
}
