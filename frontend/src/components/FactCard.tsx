import React, { useState } from 'react'
import clsx from 'clsx'
import { ChevronDown, ChevronUp } from 'lucide-react'

export interface Fact {
  id: string
  doc_id: string
  statement: string
  subject: string | null
  predicate: string | null
  value_raw: string | null
  value_normalized: number | null
  unit_raw: string | null
  unit_canonical: string | null
  time_period_raw: string | null
  time_start: string | null
  time_end: string | null
  scope: string | null
  qualifier: string | null
  fact_type: string
  confidence: number
  evidence_verified: boolean
  exact_quote: string | null
  created_at: string
  relationship_count?: number
}

const TYPE_COLOR: Record<string, string> = {
  numerical:  'text-action-blue border-action-blue/30',
  semantic:   'text-slate border-hairline',
  relational: 'text-coral border-coral/30',
}

function ConfidencePip({ value }: { value: number }) {
  const pct  = Math.round(value * 100)
  const fill = pct >= 80 ? 'bg-deep-green' : pct >= 60 ? 'bg-slate' : 'bg-error-red'
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1 w-12 overflow-hidden rounded-full bg-stone">
        <div className={clsx('h-full rounded-full', fill)} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-[10px] text-muted">{pct}%</span>
    </div>
  )
}

interface Props { fact: Fact }

export function FactCard({ fact }: Props) {
  const [expanded, setExpanded] = useState(false)

  return (
    <article className={clsx(
      'rounded-sm border bg-canvas transition-colors',
      fact.evidence_verified ? 'border-hairline' : 'border-hairline bg-stone/30',
    )}>
      <button
        className="flex w-full items-start gap-3 px-4 py-3 text-left"
        onClick={() => setExpanded(v => !v)}
      >
        {/* Verification indicator */}
        <div className={clsx(
          'mt-1 h-2 w-2 shrink-0 rounded-full',
          fact.evidence_verified ? 'bg-deep-green' : 'bg-muted',
        )} />

        <div className="min-w-0 flex-1">
          <p className="text-sm leading-snug text-ink">{fact.statement}</p>

          <div className="mt-2 flex flex-wrap items-center gap-2">
            {fact.fact_type && (
              <span className={clsx(
                'rounded-xs border px-1.5 py-px font-mono text-[10px] uppercase tracking-wider',
                TYPE_COLOR[fact.fact_type] ?? 'text-muted border-hairline',
              )}>
                {fact.fact_type}
              </span>
            )}
            {fact.subject && (
              <span className="text-xs text-slate">{fact.subject}</span>
            )}
            {fact.value_raw && fact.unit_raw && (
              <span className="rounded-xs bg-stone px-1.5 py-px font-mono text-[11px] text-ink">
                {fact.value_raw} {fact.unit_raw}
              </span>
            )}
            {fact.time_period_raw && (
              <span className="text-xs text-muted">{fact.time_period_raw}</span>
            )}
            <ConfidencePip value={fact.confidence} />
            {(fact.relationship_count ?? 0) > 0 && (
              <span className="rounded-xs border border-hairline px-1.5 py-px font-mono text-[10px] text-slate">
                {fact.relationship_count} linked
              </span>
            )}
          </div>
        </div>

        <div className="shrink-0 text-muted">
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-hairline px-4 pb-4 pt-3 space-y-4">

          {/* Evidence */}
          {fact.exact_quote && (
            <div>
              <p className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-muted">
                Source evidence — {fact.evidence_verified ? 'verified' : 'unverified'}
              </p>
              <blockquote className={clsx(
                'border-l-2 pl-3 text-xs italic leading-relaxed text-body-muted',
                fact.evidence_verified ? 'border-deep-green' : 'border-muted',
              )}>
                {fact.exact_quote}
              </blockquote>
            </div>
          )}

          {/* Normalized metadata */}
          <div>
            <p className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-muted">Normalized</p>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs">
              {([
                ['Subject',   fact.subject],
                ['Predicate', fact.predicate],
                ['Value',     fact.value_normalized != null ? String(fact.value_normalized) : null],
                ['Unit',      fact.unit_canonical],
                ['Period',    fact.time_start ? `${fact.time_start} → ${fact.time_end}` : null],
                ['Scope',     fact.scope],
                ['Qualifier', fact.qualifier],
              ] as [string, string | null][]).filter(([, v]) => v).map(([k, v]) => (
                <div key={k}>
                  <dt className="text-muted">{k}</dt>
                  <dd className="mt-0.5 font-medium text-ink">{v}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      )}
    </article>
  )
}
