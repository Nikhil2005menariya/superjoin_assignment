import React, { useEffect, useState, useCallback } from 'react'
import { Search, SlidersHorizontal, RotateCcw } from 'lucide-react'
import clsx from 'clsx'
import { api, Document } from '../api/client'
import { FactCard, Fact } from '../components/FactCard'

interface Props { documents: Document[] }

interface Stats {
  total: number
  verified: number
  documents: number
  subjects: number
  avg_confidence: number | null
  numerical: number
  semantic: number
  relational: number
}

export function FactsPage({ documents }: Props) {
  const [facts, setFacts]         = useState<Fact[]>([])
  const [stats, setStats]         = useState<Stats | null>(null)
  const [loading, setLoading]     = useState(false)
  const [query, setQuery]         = useState('')
  const [searching, setSearching] = useState(false)
  const [searchMeta, setSearchMeta] = useState<string | null>(null)

  const [filterDoc,      setFilterDoc]      = useState('')
  const [filterVerified, setFilterVerified] = useState<'' | 'true' | 'false'>('')
  const [filterType,     setFilterType]     = useState('')

  const loadFacts = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (filterDoc)      params.doc_id   = filterDoc
      if (filterVerified) params.verified  = filterVerified
      if (filterType)     params.fact_type = filterType

      const [factsRes, statsRes] = await Promise.all([
        api.get('/facts', { params }),
        api.get('/facts/stats/summary'),
      ])
      setFacts(factsRes.data)
      setStats(statsRes.data)
      setSearchMeta(null)
    } finally {
      setLoading(false)
    }
  }, [filterDoc, filterVerified, filterType])

  const searchFacts = useCallback(async () => {
    if (!query.trim() || query.length < 3) return
    setSearching(true)
    setSearchMeta(null)
    try {
      const { data } = await api.get('/facts/search/semantic', { params: { q: query } })
      const hits: any[] = data
      const ids = hits.map((h: any) => h.fact_id).filter(Boolean)
      if (!ids.length) { setFacts([]); return }
      const full = await Promise.all(ids.map((id: string) =>
        api.get(`/facts/${id}`).then(r => r.data).catch(() => null)
      ))
      setFacts(full.filter(Boolean))
      setSearchMeta(hits[0]?.retrieval ?? null)
    } finally {
      setSearching(false)
    }
  }, [query])

  useEffect(() => { loadFacts() }, [loadFacts])

  const clearSearch = () => { setQuery(''); setSearchMeta(null); loadFacts() }
  const verifiedCount = facts.filter(f => f.evidence_verified).length

  return (
    <div className="space-y-8">

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: 'Total facts',      value: stats.total },
            { label: 'Verified',         value: stats.verified },
            { label: 'Unique subjects',  value: stats.subjects },
            { label: 'Avg confidence',   value: stats.avg_confidence != null ? `${Math.round(stats.avg_confidence * 100)}%` : '—' },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-sm border border-hairline bg-canvas p-4">
              <p className="text-2xl font-semibold tracking-tight text-ink">{value}</p>
              <p className="mt-0.5 text-xs text-muted">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Search + filters */}
      <div className="flex flex-wrap gap-2">
        <div className="flex flex-1 min-w-[240px] items-center gap-2 rounded-xs border border-hairline bg-canvas px-3 py-2 focus-within:border-slate transition-colors">
          <Search className="h-3.5 w-3.5 shrink-0 text-muted" strokeWidth={1.5} />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && searchFacts()}
            placeholder="Semantic search — press Enter"
            className="flex-1 bg-transparent text-sm text-ink placeholder:text-muted outline-none"
          />
          {searching && (
            <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-ink border-t-transparent" />
          )}
        </div>

        <Select value={filterDoc} onChange={v => { setFilterDoc(v); setQuery('') }}>
          <option value="">All documents</option>
          {documents.map(d => <option key={d.id} value={d.id}>{d.filename}</option>)}
        </Select>

        <Select value={filterVerified} onChange={v => setFilterVerified(v as any)}>
          <option value="">All facts</option>
          <option value="true">Verified only</option>
          <option value="false">Unverified only</option>
        </Select>

        <Select value={filterType} onChange={setFilterType}>
          <option value="">All types</option>
          <option value="numerical">Numerical</option>
          <option value="semantic">Semantic</option>
          <option value="relational">Relational</option>
        </Select>

        <button
          onClick={clearSearch}
          className="flex items-center gap-1.5 rounded-xs border border-hairline px-3 py-2 text-xs text-muted hover:text-ink transition-colors"
        >
          <RotateCcw className="h-3 w-3" />
          Reset
        </button>
      </div>

      {/* Result meta */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <p className="text-sm text-muted">
            {loading ? 'Loading…' : `${facts.length} facts · ${verifiedCount} verified`}
          </p>
          {searchMeta && (
            <span className="rounded-xs border border-hairline px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-slate">
              {searchMeta === 'colbert_hybrid' ? 'ColBERT hybrid' : 'Dense ANN'}
            </span>
          )}
        </div>
        {query && (
          <button onClick={clearSearch} className="text-xs text-muted underline underline-offset-2 hover:text-ink">
            Clear search
          </button>
        )}
      </div>

      {/* Fact list */}
      {loading ? (
        <div className="flex justify-center py-16">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-ink border-t-transparent" />
        </div>
      ) : facts.length === 0 ? (
        <div className="rounded-sm border border-dashed border-hairline p-16 text-center">
          <p className="text-sm text-muted">No facts — upload and process a PDF to extract facts.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {facts.map(fact => <FactCard key={fact.id} fact={fact} />)}
        </div>
      )}
    </div>
  )
}

function Select({ value, onChange, children }: {
  value: string
  onChange: (v: string) => void
  children: React.ReactNode
}) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className="rounded-xs border border-hairline bg-canvas px-3 py-2 text-xs text-ink focus:border-slate outline-none"
    >
      {children}
    </select>
  )
}
