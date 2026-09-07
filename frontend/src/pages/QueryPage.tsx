import React, { useState, useCallback, useRef } from 'react'
import { ArrowRight, ChevronDown, ChevronUp } from 'lucide-react'
import clsx from 'clsx'
import { api, Document } from '../api/client'

interface Props { documents: Document[] }

interface SourceFact {
  id: string
  doc_id: string
  statement: string
  subject: string | null
  predicate: string | null
  value_raw: string | null
  unit_raw: string | null
  time_period_raw: string | null
  scope: string | null
  fact_type: string
  confidence: number
  exact_quote: string | null
  evidence_verified: boolean
}

interface QueryResult {
  answer: string
  source_facts: SourceFact[]
  confidence: 'HIGH' | 'MEDIUM' | 'LOW'
  retrieval_meta: { hits: number; used: number; method: string }
  caveat: string | null
}

const CONFIDENCE_STYLE = {
  HIGH:   'bg-pale-green text-deep-green border-deep-green/20',
  MEDIUM: 'bg-stone text-slate border-hairline',
  LOW:    'bg-stone text-muted border-hairline',
}

function SourceCard({ fact, docName }: { fact: SourceFact; docName: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="rounded-xs border border-hairline bg-canvas">
      <button
        className="flex w-full items-start gap-3 px-3 py-2.5 text-left"
        onClick={() => setOpen(v => !v)}
      >
        <div className={clsx(
          'mt-1 h-1.5 w-1.5 shrink-0 rounded-full',
          fact.evidence_verified ? 'bg-deep-green' : 'bg-muted',
        )} />
        <div className="min-w-0 flex-1">
          <p className="text-xs leading-snug text-ink">{fact.statement}</p>
          <div className="mt-1.5 flex flex-wrap gap-2">
            {fact.subject && <span className="text-[10px] text-muted">{fact.subject}</span>}
            {fact.value_raw && fact.unit_raw && (
              <span className="rounded-xs bg-stone px-1.5 py-px font-mono text-[10px] text-ink">
                {fact.value_raw} {fact.unit_raw}
              </span>
            )}
            {fact.time_period_raw && (
              <span className="text-[10px] text-muted">{fact.time_period_raw}</span>
            )}
            <span className="rounded-xs border border-hairline px-1.5 py-px font-mono text-[10px] text-muted">
              {docName}
            </span>
          </div>
        </div>
        <div className="shrink-0 text-muted">
          {open ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </div>
      </button>
      {open && fact.exact_quote && (
        <div className="border-t border-hairline px-3 pb-3 pt-2">
          <p className="mb-1 font-mono text-[9px] uppercase tracking-widest text-muted">
            Source evidence
          </p>
          <blockquote className="border-l-2 border-deep-green pl-2.5 text-[11px] italic leading-relaxed text-body-muted">
            {fact.exact_quote}
          </blockquote>
        </div>
      )}
    </div>
  )
}

const EXAMPLES = [
  'What was the total revenue last fiscal year?',
  'Are there any facts about profit margins?',
  'Which documents mention headcount or employee numbers?',
  'What growth metrics are reported across the documents?',
  'Are there any contradicting figures for the same metric?',
]

export function QueryPage({ documents }: Props) {
  const [question, setQuestion] = useState('')
  const [loading, setLoading]   = useState(false)
  const [result, setResult]     = useState<QueryResult | null>(null)
  const [filterDoc, setFilterDoc] = useState('')
  const [error, setError]       = useState<string | null>(null)
  const textareaRef             = useRef<HTMLTextAreaElement>(null)

  const docMap = Object.fromEntries(documents.map(d => [d.id, d.filename]))

  const submit = useCallback(async (q: string) => {
    const trimmed = q.trim()
    if (!trimmed || trimmed.length < 3) return
    setLoading(true)
    setResult(null)
    setError(null)
    try {
      const { data } = await api.post('/query', {
        question: trimmed,
        doc_id: filterDoc || undefined,
        limit: 12,
      })
      setResult(data)
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Query failed')
    } finally {
      setLoading(false)
    }
  }, [filterDoc])

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit(question)
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">

      {/* Input area */}
      <div className="rounded-sm border border-hairline bg-canvas">
        <div className="px-4 pt-4">
          <textarea
            ref={textareaRef}
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask a question about your uploaded documents…"
            rows={3}
            className="w-full resize-none bg-transparent text-sm leading-relaxed text-ink placeholder:text-muted outline-none"
          />
        </div>

        <div className="flex items-center justify-between border-t border-hairline px-4 py-2.5">
          <div className="flex items-center gap-2">
            <select
              value={filterDoc}
              onChange={e => setFilterDoc(e.target.value)}
              className="rounded-xs border border-hairline bg-canvas px-2 py-1 text-xs text-muted outline-none focus:border-slate"
            >
              <option value="">All documents</option>
              {documents.map(d => (
                <option key={d.id} value={d.id}>{d.filename}</option>
              ))}
            </select>
            <span className="text-xs text-muted">Cmd+Enter to submit</span>
          </div>

          <button
            onClick={() => submit(question)}
            disabled={loading || question.trim().length < 3}
            className={clsx(
              'flex items-center gap-1.5 rounded-pill px-4 py-1.5 text-xs font-medium transition-colors',
              loading || question.trim().length < 3
                ? 'bg-stone text-muted cursor-not-allowed'
                : 'bg-ink text-canvas hover:bg-ink/90',
            )}
          >
            {loading
              ? <><div className="h-3 w-3 animate-spin rounded-full border-2 border-canvas border-t-transparent" /> Thinking</>
              : <><ArrowRight className="h-3 w-3" /> Ask</>
            }
          </button>
        </div>
      </div>

      {/* Example queries */}
      {!result && !loading && (
        <div>
          <p className="mb-3 font-mono text-[10px] uppercase tracking-widest text-muted">Example questions</p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map(ex => (
              <button
                key={ex}
                onClick={() => { setQuestion(ex); submit(ex) }}
                className="rounded-pill border border-hairline px-3 py-1.5 text-xs text-slate hover:border-slate hover:text-ink transition-colors"
              >
                {ex}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-xs border border-error-red/30 bg-canvas px-4 py-3">
          <p className="text-xs text-error-red">{error}</p>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="space-y-6">

          {/* Answer */}
          <div className="rounded-sm border border-hairline bg-canvas">
            <div className="flex items-center justify-between border-b border-hairline px-4 py-2.5">
              <p className="font-mono text-[10px] uppercase tracking-widest text-muted">Answer</p>
              <div className="flex items-center gap-2">
                <span className={clsx(
                  'rounded-xs border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider',
                  CONFIDENCE_STYLE[result.confidence],
                )}>
                  {result.confidence} confidence
                </span>
                <span className="font-mono text-[10px] text-muted">
                  {result.retrieval_meta.used} facts · {result.retrieval_meta.method === 'colbert_hybrid' ? 'ColBERT' : 'Dense'}
                </span>
              </div>
            </div>
            <div className="px-4 py-4">
              <p className="text-sm leading-relaxed text-ink whitespace-pre-line">{result.answer}</p>
              {result.caveat && (
                <p className="mt-3 text-xs text-muted border-t border-hairline pt-3">{result.caveat}</p>
              )}
            </div>
          </div>

          {/* Source facts */}
          {result.source_facts.length > 0 && (
            <div>
              <p className="mb-3 font-mono text-[10px] uppercase tracking-widest text-muted">
                Source facts ({result.source_facts.length})
              </p>
              <div className="space-y-2">
                {result.source_facts.map(f => (
                  <SourceCard
                    key={f.id}
                    fact={f}
                    docName={docMap[f.doc_id] ?? f.doc_id.slice(0, 8)}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
