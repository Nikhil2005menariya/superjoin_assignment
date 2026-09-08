import React, { useState, useCallback, useRef } from 'react'
import { ArrowRight } from 'lucide-react'
import clsx from 'clsx'
import { api, Document } from '../api/client'

interface Props { documents: Document[] }

interface RetrievalMeta {
  hits: number
  md_files?: number
  chunks?: number
  method: string
}

interface QueryResult {
  answer: string
  source_facts: unknown[]
  confidence: 'HIGH' | 'MEDIUM' | 'LOW'
  retrieval_meta: RetrievalMeta
  caveat: string | null
}

const CONFIDENCE_STYLE = {
  HIGH:   'bg-pale-green text-deep-green border-deep-green/20',
  MEDIUM: 'bg-stone text-slate border-hairline',
  LOW:    'bg-stone text-muted border-hairline',
}

const EXAMPLES = [
  'What was the total revenue for the last reported period?',
  'Are there any contradictions across the uploaded documents?',
  'What growth metrics are reported across the documents?',
  'Which documents mention EBITDA or operating profit?',
  'Are there any facts about headcount or employee numbers?',
]

function MetaTag({ label, value }: { label: string; value: string | number }) {
  return (
    <span className="rounded-xs border border-hairline px-2 py-0.5 font-mono text-[10px] text-muted">
      {label}: {value}
    </span>
  )
}

export function QueryPage({ documents }: Props) {
  const [question, setQuestion] = useState('')
  const [loading, setLoading]   = useState(false)
  const [result, setResult]     = useState<QueryResult | null>(null)
  const [filterDoc, setFilterDoc] = useState('')
  const [error, setError]       = useState<string | null>(null)
  const textareaRef             = useRef<HTMLTextAreaElement>(null)

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
        limit: 10,
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

  const meta = result?.retrieval_meta

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
        <div className="space-y-4">

          {/* Answer */}
          <div className="rounded-sm border border-hairline bg-canvas">
            <div className="flex items-center justify-between border-b border-hairline px-4 py-2.5">
              <p className="font-mono text-[10px] uppercase tracking-widest text-muted">Answer</p>
              <div className="flex items-center gap-2 flex-wrap justify-end">
                <span className={clsx(
                  'rounded-xs border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider',
                  CONFIDENCE_STYLE[result.confidence],
                )}>
                  {result.confidence} confidence
                </span>
                {meta && (
                  <>
                    {meta.md_files !== undefined && (
                      <MetaTag label="pages read" value={meta.md_files} />
                    )}
                    {meta.chunks !== undefined && (
                      <MetaTag label="chunks" value={meta.chunks} />
                    )}
                    <MetaTag label="method" value={meta.method} />
                  </>
                )}
              </div>
            </div>
            <div className="px-4 py-4">
              <p className="text-sm leading-relaxed text-ink whitespace-pre-line">{result.answer}</p>
              {result.caveat && (
                <p className="mt-3 text-xs text-muted border-t border-hairline pt-3">{result.caveat}</p>
              )}
            </div>
          </div>

        </div>
      )}
    </div>
  )
}
