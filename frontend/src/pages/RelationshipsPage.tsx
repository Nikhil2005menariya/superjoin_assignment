import React, { useEffect, useState, useCallback, useMemo } from 'react'
import { RotateCcw } from 'lucide-react'
import clsx from 'clsx'
import { api, Document } from '../api/client'

interface Props { documents: Document[] }

interface PageInfo {
  page_num: number
  summary: string | null
  md_path: string | null
}

interface PageRel {
  id: string
  page_a_id: string
  page_b_id: string
  doc_a_id: string
  doc_b_id: string
  doc_a_filename: string
  doc_b_filename: string
  type: 'CORROBORATES' | 'CONTRADICTS' | 'RECONCILES' | 'RELATED'
  explanation: string
  confidence: number
  created_at: string
  page_a: PageInfo | null
  page_b: PageInfo | null
}

interface Stats {
  total: number
  corroborates: number
  contradicts: number
  reconciles: number
  related: number
  avg_confidence: number | null
}

const TYPE_CONFIG = {
  CORROBORATES: { label: 'Corroborates', dot: 'bg-deep-green',  text: 'text-deep-green' },
  CONTRADICTS:  { label: 'Contradicts',  dot: 'bg-error-red',   text: 'text-error-red'  },
  RECONCILES:   { label: 'Reconciles',   dot: 'bg-slate',       text: 'text-slate'      },
  RELATED:      { label: 'Related',      dot: 'bg-muted',       text: 'text-muted'      },
} as const

function TypeBadge({ type }: { type: string }) {
  const cfg = TYPE_CONFIG[type as keyof typeof TYPE_CONFIG]
  if (!cfg) return null
  return (
    <span className="inline-flex items-center gap-1.5 rounded-xs border border-hairline px-2 py-0.5 text-xs text-slate">
      <span className={clsx('h-1.5 w-1.5 rounded-full', cfg.dot)} />
      {cfg.label}
    </span>
  )
}

function PageCard({ page, docName }: { page: PageInfo | null; docName: string }) {
  if (!page) return <p className="text-xs text-muted italic">Page data unavailable</p>
  return (
    <div className="space-y-1">
      <p className="font-mono text-[10px] text-muted">
        {docName} · Page {page.page_num}
      </p>
      {page.summary && (
        <p className="text-xs leading-relaxed text-ink line-clamp-3">{page.summary}</p>
      )}
    </div>
  )
}

// ─── Document network graph ───────────────────────────────────────────────────

const EDGE_COLOR = {
  CORROBORATES: '#003c33',
  CONTRADICTS:  '#e53935',
  RECONCILES:   '#6b7280',
  RELATED:      '#d1d5db',
} as const

interface GraphNode { id: string; label: string; x: number; y: number }
interface GraphEdge { source: string; target: string; type: string }

function NetworkGraph({ rels, docMap }: { rels: PageRel[]; docMap: Record<string, string> }) {
  const W = 560, H = 240, R = 22

  const { nodes, edges } = useMemo(() => {
    const docIds = Array.from(new Set(
      rels.flatMap(r => [r.doc_a_id, r.doc_b_id].filter(Boolean))
    ))
    const n = docIds.length
    const nodes: GraphNode[] = docIds.map((id, i) => {
      const angle = (2 * Math.PI * i) / n - Math.PI / 2
      const cx = W / 2 + (n === 1 ? 0 : (W / 2 - 60)) * Math.cos(angle)
      const cy = H / 2 + (n === 1 ? 0 : (H / 2 - 36)) * Math.sin(angle)
      const label = (docMap[id] ?? id).replace(/\.[^.]+$/, '').slice(0, 16)
      return { id, label, x: cx, y: cy }
    })
    const seen = new Set<string>()
    const edges: GraphEdge[] = []
    for (const r of rels) {
      if (!r.doc_a_id || !r.doc_b_id || r.doc_a_id === r.doc_b_id) continue
      const key = [r.doc_a_id, r.doc_b_id].sort().join('|') + r.type
      if (seen.has(key)) continue
      seen.add(key)
      edges.push({ source: r.doc_a_id, target: r.doc_b_id, type: r.type })
    }
    return { nodes, edges }
  }, [rels, docMap])

  if (nodes.length < 2) return null

  const nMap = Object.fromEntries(nodes.map(n => [n.id, n]))

  return (
    <div className="rounded-sm border border-hairline bg-canvas">
      <div className="flex items-center gap-2 border-b border-hairline px-4 py-2.5">
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted">Document network</p>
        <div className="ml-auto flex items-center gap-4">
          {(['CORROBORATES', 'CONTRADICTS', 'RECONCILES'] as const).map(t => (
            <span key={t} className="flex items-center gap-1.5 text-[10px] text-muted">
              <span className="inline-block h-px w-4" style={{ backgroundColor: EDGE_COLOR[t] }} />
              {t.charAt(0) + t.slice(1).toLowerCase()}
            </span>
          ))}
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" className="block">
        <defs>
          {(Object.keys(EDGE_COLOR) as Array<keyof typeof EDGE_COLOR>).map(t => (
            <marker key={t} id={`arr-${t}`} markerWidth="6" markerHeight="6"
              refX="5" refY="3" orient="auto">
              <path d="M0,0 L0,6 L6,3 z" fill={EDGE_COLOR[t]} fillOpacity=".7" />
            </marker>
          ))}
        </defs>
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
              stroke={color} strokeWidth="1.5" strokeOpacity=".8"
              markerEnd={`url(#arr-${e.type})`} />
          )
        })}
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
  const [rels, setRels]           = useState<PageRel[]>([])
  const [stats, setStats]         = useState<Stats | null>(null)
  const [loading, setLoading]     = useState(false)
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
          <option value="RELATED">Related</option>
        </select>

        <button
          onClick={() => { setFilterDoc(''); setFilterType('') }}
          className="flex items-center gap-1.5 rounded-xs border border-hairline px-3 py-2 text-xs text-muted hover:text-ink transition-colors"
        >
          <RotateCcw className="h-3 w-3" />
          Reset
        </button>
      </div>

      <p className="text-sm text-muted">
        {loading ? 'Loading…' : `${rels.length} page-level relationships across documents`}
      </p>

      {loading ? (
        <div className="flex justify-center py-16">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-ink border-t-transparent" />
        </div>
      ) : rels.length === 0 ? (
        <div className="rounded-sm border border-dashed border-hairline p-16 text-center">
          <p className="text-sm text-muted">No cross-document relationships yet.</p>
          <p className="mt-1 text-xs text-muted">
            Upload two or more documents — cross-doc linking runs automatically after ingestion.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {rels.map(rel => (
            <article key={rel.id} className="rounded-sm border border-hairline bg-canvas">
              <div className="flex items-center justify-between border-b border-hairline px-4 py-2.5">
                <TypeBadge type={rel.type} />
                <span className="font-mono text-[10px] text-muted">
                  {Math.round(rel.confidence * 100)}% similarity
                </span>
              </div>

              <div className="grid gap-px bg-hairline sm:grid-cols-2">
                <div className="bg-canvas px-4 py-3">
                  <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted">Page A</p>
                  <PageCard
                    page={rel.page_a}
                    docName={rel.doc_a_filename ?? rel.doc_a_id?.slice(0, 8) ?? ''}
                  />
                </div>
                <div className="bg-canvas px-4 py-3">
                  <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted">Page B</p>
                  <PageCard
                    page={rel.page_b}
                    docName={rel.doc_b_filename ?? rel.doc_b_id?.slice(0, 8) ?? ''}
                  />
                </div>
              </div>

              <div className="border-t border-hairline px-4 py-3">
                <p className="text-xs leading-relaxed text-body-muted">{rel.explanation}</p>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
