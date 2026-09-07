import React, { useEffect, useState, useCallback } from 'react'
import { Search, Filter, RefreshCw } from 'lucide-react'
import clsx from 'clsx'
import { api, Document } from '../api/client'
import { FactCard, Fact } from '../components/FactCard'

interface Props {
  documents: Document[]
}

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

  // Filters
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
    } finally {
      setLoading(false)
    }
  }, [filterDoc, filterVerified, filterType])

  const searchFacts = useCallback(async () => {
    if (!query.trim() || query.length < 3) return
    setSearching(true)
    try {
      const { data } = await api.get('/facts/search/semantic', { params: { q: query } })
      // Fetch full facts for the returned IDs
      const ids: string[] = data.map((h: any) => h.fact_id).filter(Boolean)
      if (!ids.length) { setFacts([]); return }
      const full = await Promise.all(ids.map((id: string) => api.get(`/facts/${id}`).then(r => r.data).catch(() => null)))
      setFacts(full.filter(Boolean))
    } finally {
      setSearching(false)
    }
  }, [query])

  useEffect(() => {
    loadFacts()
  }, [loadFacts])

  const verifiedCount = facts.filter(f => f.evidence_verified).length

  return (
    <div className="space-y-6">
      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: 'Total Facts',  value: stats.total },
            { label: 'Verified',     value: stats.verified },
            { label: 'Subjects',     value: stats.subjects },
            { label: 'Avg Confidence', value: stats.avg_confidence != null ? `${Math.round(stats.avg_confidence * 100)}%` : '—' },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-xl border border-gray-200 bg-white p-4">
              <p className="text-2xl font-bold text-gray-900">{value}</p>
              <p className="text-xs text-gray-500">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Search + filters */}
      <div className="flex flex-wrap gap-3">
        {/* Semantic search */}
        <div className="flex flex-1 min-w-[260px] items-center gap-2 rounded-xl border border-gray-300 bg-white px-3 py-2">
          <Search className="h-4 w-4 shrink-0 text-gray-400" />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && searchFacts()}
            placeholder="Semantic search (press Enter)…"
            className="flex-1 text-sm outline-none placeholder:text-gray-400"
          />
          {searching && <div className="h-4 w-4 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />}
        </div>

        {/* Document filter */}
        <select
          value={filterDoc}
          onChange={e => { setFilterDoc(e.target.value); setQuery('') }}
          className="rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700"
        >
          <option value="">All documents</option>
          {documents.map(d => (
            <option key={d.id} value={d.id}>{d.filename}</option>
          ))}
        </select>

        {/* Verified filter */}
        <select
          value={filterVerified}
          onChange={e => setFilterVerified(e.target.value as any)}
          className="rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700"
        >
          <option value="">All facts</option>
          <option value="true">Verified only</option>
          <option value="false">Unverified only</option>
        </select>

        {/* Type filter */}
        <select
          value={filterType}
          onChange={e => setFilterType(e.target.value)}
          className="rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700"
        >
          <option value="">All types</option>
          <option value="numerical">Numerical</option>
          <option value="semantic">Semantic</option>
          <option value="relational">Relational</option>
        </select>

        <button
          onClick={() => { setQuery(''); loadFacts() }}
          className="flex items-center gap-1.5 rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm text-gray-600 hover:bg-gray-50"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {/* Results header */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          {loading ? 'Loading…' : `${facts.length} facts — ${verifiedCount} evidence-verified`}
        </p>
        {query && (
          <button onClick={() => { setQuery(''); loadFacts() }} className="text-xs text-brand-600 hover:underline">
            Clear search
          </button>
        )}
      </div>

      {/* Fact list */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-brand-500 border-t-transparent" />
        </div>
      ) : facts.length === 0 ? (
        <div className="rounded-xl border-2 border-dashed border-gray-200 p-12 text-center">
          <p className="text-sm text-gray-500">
            No facts yet — upload and process a PDF to extract facts.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {facts.map(fact => <FactCard key={fact.id} fact={fact} />)}
        </div>
      )}
    </div>
  )
}
