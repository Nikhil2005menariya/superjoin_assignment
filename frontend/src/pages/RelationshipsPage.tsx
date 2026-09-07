import React, { useEffect, useState, useCallback, useMemo } from 'react'
import { RotateCcw } from 'lucide-react'
import clsx from 'clsx'
import { api, Document } from '../api/client'

interface Props { documents: Document[] }

interface RelFact {
  id: string
  statement: string
  subject: string | null
  predicate: string | null
  value_raw: string | null
  unit_raw: string | null
  time_period_raw: string | null
  doc_id: string
  fact_type: string
  confidence: number
}

interface Relationship {
  id: string
  fact_a_id: string
  fact_b_id: string
  type: 'CORROBORATES' | 'CONTRADICTS' | 'RECONCILES'
  explanation: string
  reconciliation_context: string | null
  confidence: number
  created_at: string
  fact_a: RelFact | null
  fact_b: RelFact | null
}

interface Stats {
  total: number
  corroborates: number
  contradicts: number
  reconciles: number
  avg_confidence: number | null
}

const TYPE_CONFIG = {
  CORROBORATES: { label: 'Corroborates', dot: 'bg-deep-green', text: 'text-deep-green' },
  CONTRADICTS:  { label: 'Contradicts',  dot: 'bg-error-red',  text: 'text-error-red'  },
  RECONCILES:   { label: 'Reconciles',   dot: 'bg-slate',      text: 'text-slate'       },
} as const

function RelTypeBadge({ type }: { type: string }) {
  const cfg = TYPE_CONFIG[type as keyof typeof TYPE_CONFIG]
  if (!cfg) return null
  return (
    <span className="inline-flex items-center gap-1.5 rounded-xs border border-hairline px-2 py-0.5 text-xs text-slate">
      <span className={clsx('h-1.5 w-1.5 rounded-full', cfg.dot)} />
      {cfg.label}
    </span>
  )
}

function FactSnippet({ fact, docName }: { fact: RelFact | null; docName: string }) {
  if (!fact) return <p className="text-xs text-muted italic">Fact unavailable</p>
  return (
    <div className="space-y-1">
      <p className="text-xs leading-relaxed text-ink">{fact.statement}</p>
      <div className="flex flex-wrap gap-2">
        {fact.subject && <span className="text-xs text-muted">{fact.subject}</span>}
        {fact.value_raw && fact.unit_raw && (
          <span className="rounded-xs bg-stone px-1.5 py-px font-mono text-[10px] text-ink">
            {fact.value_raw} {fact.unit_raw}
          </span>
        )}
        {fact.time_period_raw && <span className="text-xs text-muted">{fact.time_period_raw}</span>}
        <span className="rounded-xs border border-hairline px-1.5 py-px font-mono text-[10px] text-muted">{docName}</span>
      </div>
    </div>
  )
}

// ─── Network graph ────────────────────────────────────────────────────────────

const EDGE_COLOR = {
  CORROBORATES: '#003c33',
  CONTRADICTS:  '#e53935',
  RECONCILES:   '#6b7280',
} as const

interface GraphNode { id: string; label: string; x: number; y: number }
interface GraphEdge { source: string; target: string; type: string }

function NetworkGraph({ rels, docMap }: { rels: Relationship[]; docMap: Record<string, string> }) {
  const W = 560, H = 260, R = 22

  const { nodes, edges } = useMemo(() => {
    const docIds = Array.from(new Set(
      rels.flatMap(r => [r.fact_a?.doc_id, r.fact_b?.doc_id].filter(Boolean) as string[])
    ))
    const n = docIds.length
    const nodes: GraphNode[] = docIds.map((id, i) => {
      const angle = (2 * Math.PI * i) / n - Math.PI / 2
      const cx = W / 2 + (n === 1 ? 0 : (W / 2 - 50)) * Math.cos(angle)
      const cy = H / 2 + (n === 1 ? 0 : (H / 2 - 40)) * Math.sin(angle)
      return { id, label: (docMap[id] ?? id).replace(/\.[^.]+$/, '').slice(0, 18), x: cx, y: cy }
    })
    const seen = new Set<string>()
    const edges: GraphEdge[] = []
    for (const r of rels) {
      const a = r.fact_a?.doc_id, b = r.fact_b?.doc_id
      if (!a || !b || a === b) continue
      const key = [a, b].sort().join('|') + r.type
      if (seen.has(key)) continue
      seen.add(key)
      edges.push({ source: a, target: b, type: r.type })
    }
    return { nodes, edges }
  }, [rels, docMap])

  if (nodes.length < 2) return null

  const nMap = Object.fromEntries(nodes.map(n => [n.id, n]))

  return (
    <div className="rounded-sm border border-hairline bg-canvas">
      <div className="flex items-center gap-2 border-b border-hairline px-4 py-2.5">
        <svg className="h-3.5 w-3.5 text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="5" cy="5" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="12" cy="19" r="2"/>
          <line x1="5" y1="7" x2="12" y2="17"/><line x1="19" y1="7" x2="12" y2="17"/>
          <line x1="7" y1="5" x2="17" y2="5"/>
        </svg>
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted">Document network</p>
        <div className="ml-auto flex items-center gap-3">
          {Object.entries(EDGE_COLOR).map(([t, c]) => (
            <span key={t} className="flex items-center gap-1 text-[10px] text-muted">
              <span className="inline-block h-px w-4" style={{ backgroundColor: c }} />
              {t.charAt(0) + t.slice(1).toLowerCase()}
            </span>
          ))}
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" className="block">
        <defs>
          {Object.entries(EDGE_COLOR).map(([t, c]) => (
            <marker key={t} id={`arrow-${t}`} markerWidth="6" markerHeight="6"
              refX="5" refY="3" orient="auto">
              <path d="M0,0 L0,6 L6,3 z" fill={c} fillOpacity=".7" />
            </marker>
          ))}
        </defs>
        {/* Edges */}
        {edges.map((e, i) => {
          const s = nMap[e.source], t = nMap[e.target]
          if (!s || !t) return null
          const dx = t.x - s.x, dy = t.y - s.y
          const len = Math.sqrt(dx * dx + dy * dy) || 1
          const x1 = s.x + (dx / len) * R
          const y1 = s.y + (dy / len) * R
          const x2 = t.x - (dx / len) * (R + 4)
          const y2 = t.y - (dy / len) * (R + 4)
          const color = EDGE_COLOR[e.type as keyof typeof EDGE_COLOR] ?? '#999'
          return (
            <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
              stroke={color} strokeWidth="1.5" strokeOpacity=".7"
              markerEnd={`url(#arrow-${e.type})`} />
          )
        })}
        {/* Nodes */}
        {nodes.map(node => (
          <g key={node.id}>
            <circle cx={node.x} cy={node.y} r={R} fill="#17171c" />
            <text x={node.x} y={node.y + 1} textAnchor="middle" dominantBaseline="middle"
              fontSize="8" fill="white" fontFamily="monospace" fontWeight="600">
              {node.label.slice(0, 3).toUpperCase()}
            </text>
            <text x={node.x} y={node.y + R + 10} textAnchor="middle"
              fontSize="8" fill="#888" fontFamily="sans-serif">
              {node.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export function RelationshipsPage({ documents }: Props) {
  const [rels, setRels]       = useState<Relationship[]>([])
  const [stats, setStats]     = useState<Stats | null>(null)
  const [loading, setLoading] = useState(false)
  const [filterDoc, setFilterDoc] = useState('')
  const [filterType, setFilterType] = useState('')

  const docMap = Object.fromEntries(documents.map(d => [d.id, d.filename]))

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (filterDoc)  params.doc_id   = filterDoc
      if (filterType) params.rel_type = filterType

      const [rRes, sRes] = await Promise.all([
        api.get('/relationships', { params }),
        api.get('/relationships/stats/summary'),
      ])
      setRels(rRes.data)
      setStats(sRes.data)
    } finally {
      setLoading(false)
    }
  }, [filterDoc, filterType])

  useEffect(() => { load() }, [load])

  return (
    <div className="space-y-8">

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: 'Total relationships', value: stats.total },
            { label: 'Corroborates',        value: stats.corroborates ?? 0 },
            { label: 'Contradicts',         value: stats.contradicts  ?? 0 },
            { label: 'Reconciles',          value: stats.reconciles   ?? 0 },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-sm border border-hairline bg-canvas p-4">
              <p className="text-2xl font-semibold tracking-tight text-ink">{value}</p>
              <p className="mt-0.5 text-xs text-muted">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Network graph */}
      {rels.length > 0 && <NetworkGraph rels={rels} docMap={docMap} />}

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <select
          value={filterDoc}
          onChange={e => setFilterDoc(e.target.value)}
          className="rounded-xs border border-hairline bg-canvas px-3 py-2 text-xs text-ink focus:border-slate outline-none"
        >
          <option value="">All documents</option>
          {documents.map(d => <option key={d.id} value={d.id}>{d.filename}</option>)}
        </select>

        <select
          value={filterType}
          onChange={e => setFilterType(e.target.value)}
          className="rounded-xs border border-hairline bg-canvas px-3 py-2 text-xs text-ink focus:border-slate outline-none"
        >
          <option value="">All types</option>
          <option value="CORROBORATES">Corroborates</option>
          <option value="CONTRADICTS">Contradicts</option>
          <option value="RECONCILES">Reconciles</option>
        </select>

        <button
          onClick={() => { setFilterDoc(''); setFilterType('') }}
          className="flex items-center gap-1.5 rounded-xs border border-hairline px-3 py-2 text-xs text-muted hover:text-ink transition-colors"
        >
          <RotateCcw className="h-3 w-3" />
          Reset
        </button>
      </div>

      {/* Result header */}
      <p className="text-sm text-muted">
        {loading ? 'Loading…' : `${rels.length} relationships detected across documents`}
      </p>

      {/* Relationship list */}
      {loading ? (
        <div className="flex justify-center py-16">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-ink border-t-transparent" />
        </div>
      ) : rels.length === 0 ? (
        <div className="rounded-sm border border-dashed border-hairline p-16 text-center">
          <p className="text-sm text-muted">No relationships yet.</p>
          <p className="mt-1 text-xs text-muted">
            Upload two or more documents — cross-document comparison runs automatically.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {rels.map(rel => {
            const docAName = rel.fact_a ? (docMap[rel.fact_a.doc_id] ?? rel.fact_a.doc_id.slice(0, 8)) : '—'
            const docBName = rel.fact_b ? (docMap[rel.fact_b.doc_id] ?? rel.fact_b.doc_id.slice(0, 8)) : '—'
            return (
              <article key={rel.id} className="rounded-sm border border-hairline bg-canvas">
                {/* Header row */}
                <div className="flex items-center justify-between border-b border-hairline px-4 py-2.5">
                  <RelTypeBadge type={rel.type} />
                  <span className="font-mono text-[10px] text-muted">
                    {Math.round(rel.confidence * 100)}% confidence
                  </span>
                </div>

                {/* Two facts side by side */}
                <div className="grid gap-px bg-hairline sm:grid-cols-2">
                  <div className="bg-canvas px-4 py-3">
                    <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted">Fact A</p>
                    <FactSnippet fact={rel.fact_a} docName={docAName} />
                  </div>
                  <div className="bg-canvas px-4 py-3">
                    <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted">Fact B</p>
                    <FactSnippet fact={rel.fact_b} docName={docBName} />
                  </div>
                </div>

                {/* Explanation */}
                <div className="border-t border-hairline px-4 py-3">
                  <p className="text-xs leading-relaxed text-body-muted">{rel.explanation}</p>
                  {rel.reconciliation_context && (
                    <p className="mt-1 text-xs text-muted">
                      <span className="font-mono uppercase tracking-wider">Reconciliation: </span>
                      {rel.reconciliation_context}
                    </p>
                  )}
                </div>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}
