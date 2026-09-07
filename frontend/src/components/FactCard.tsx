import React, { useState } from 'react'
import clsx from 'clsx'
import { ChevronDown, ChevronUp, ShieldCheck, ShieldAlert, Hash, Clock } from 'lucide-react'

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
}

const TYPE_COLORS: Record<string, string> = {
  numerical:  'bg-blue-100 text-blue-700',
  semantic:   'bg-purple-100 text-purple-700',
  relational: 'bg-amber-100 text-amber-700',
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 80 ? 'bg-green-500' : pct >= 60 ? 'bg-amber-500' : 'bg-red-400'
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-gray-200">
        <div className={clsx('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-500">{pct}%</span>
    </div>
  )
}

interface Props {
  fact: Fact
}

export function FactCard({ fact }: Props) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className={clsx(
      'rounded-xl border bg-white shadow-sm transition-all',
      fact.evidence_verified ? 'border-gray-200' : 'border-amber-200 bg-amber-50/30',
    )}>
      <button
        className="flex w-full items-start gap-3 p-4 text-left"
        onClick={() => setExpanded(v => !v)}
      >
        {/* Verified badge */}
        <div className="mt-0.5 shrink-0">
          {fact.evidence_verified
            ? <ShieldCheck className="h-5 w-5 text-green-500" />
            : <ShieldAlert className="h-5 w-5 text-amber-400" />}
        </div>

        <div className="min-w-0 flex-1">
          {/* Statement */}
          <p className="text-sm font-medium leading-snug text-gray-800">{fact.statement}</p>

          {/* Chips */}
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {fact.fact_type && (
              <span className={clsx('rounded-full px-2 py-0.5 text-xs font-medium', TYPE_COLORS[fact.fact_type] ?? 'bg-gray-100 text-gray-600')}>
                {fact.fact_type}
              </span>
            )}
            {fact.subject && (
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                {fact.subject}
              </span>
            )}
            {fact.value_raw && fact.unit_raw && (
              <span className="flex items-center gap-1 rounded-full bg-brand-50 px-2 py-0.5 text-xs font-mono text-brand-700">
                <Hash className="h-3 w-3" />
                {fact.value_raw} {fact.unit_raw}
              </span>
            )}
            {fact.time_period_raw && (
              <span className="flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                <Clock className="h-3 w-3" />
                {fact.time_period_raw}
              </span>
            )}
            <ConfidenceBar value={fact.confidence} />
          </div>
        </div>

        <div className="shrink-0 text-gray-400">
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </div>
      </button>

      {expanded && (
        <div className="border-t border-gray-100 px-4 pb-4 pt-3 space-y-3">
          {/* Evidence quote */}
          {fact.exact_quote && (
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-400">
                Source evidence {fact.evidence_verified ? '✓ verified' : '⚠ unverified'}
              </p>
              <blockquote className={clsx(
                'rounded-lg border-l-4 px-3 py-2 text-xs italic text-gray-600',
                fact.evidence_verified ? 'border-green-400 bg-green-50' : 'border-amber-400 bg-amber-50',
              )}>
                "{fact.exact_quote}"
              </blockquote>
            </div>
          )}

          {/* Normalized metadata */}
          <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs">
            {[
              ['Subject',    fact.subject],
              ['Predicate',  fact.predicate],
              ['Value',      fact.value_normalized != null ? `${fact.value_normalized}` : null],
              ['Unit',       fact.unit_canonical],
              ['Period',     fact.time_start ? `${fact.time_start} → ${fact.time_end}` : null],
              ['Scope',      fact.scope],
              ['Qualifier',  fact.qualifier],
            ].filter(([, v]) => v).map(([k, v]) => (
              <div key={String(k)}>
                <dt className="text-gray-400">{k}</dt>
                <dd className="font-medium text-gray-700">{v}</dd>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
