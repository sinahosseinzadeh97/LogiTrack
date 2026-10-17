import { Search, X } from 'lucide-react'
import type { ShipmentQuery } from '@/api/types'
import { BR_STATES } from '@/lib/brazil'

const STATUSES = ['delivered', 'shipped', 'canceled', 'unavailable', 'invoiced', 'processing']

interface ShipmentFiltersProps {
  query: ShipmentQuery
  onChange: (query: ShipmentQuery) => void
}

export function ShipmentFilters({ query, onChange }: ShipmentFiltersProps) {
  const set = (patch: Partial<ShipmentQuery>) => onChange({ ...query, ...patch, page: 1 })
  const active = [query.status, query.customer_state, query.is_late, query.start, query.end, query.search]
    .some((v) => v !== undefined && v !== '')

  return (
    <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
      <label className="field" style={{ flex: '1 1 220px' }}>
        <span>Order ID</span>
        <div style={{ position: 'relative' }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
          <input className="input" style={{ paddingLeft: '2rem' }} placeholder="Starts with…" value={query.search ?? ''}
            onChange={(e) => set({ search: e.target.value || undefined })} />
        </div>
      </label>
      <label className="field">
        <span>Status</span>
        <select className="input" value={query.status ?? ''} onChange={(e) => set({ status: e.target.value || undefined })}>
          <option value="">All</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </label>
      <label className="field">
        <span>Customer state</span>
        <select className="input" value={query.customer_state ?? ''} onChange={(e) => set({ customer_state: e.target.value || undefined })}>
          <option value="">All</option>
          {BR_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </label>
      <label className="field">
        <span>Outcome</span>
        <select className="input" value={query.is_late === undefined ? '' : String(query.is_late)}
          onChange={(e) => set({ is_late: e.target.value === '' ? undefined : e.target.value === 'true' })}>
          <option value="">Any</option>
          <option value="true">Late</option>
          <option value="false">On time</option>
        </select>
      </label>
      <label className="field">
        <span>From</span>
        <input className="input" type="date" value={query.start ?? ''} onChange={(e) => set({ start: e.target.value || undefined })} />
      </label>
      <label className="field">
        <span>To</span>
        <input className="input" type="date" value={query.end ?? ''} onChange={(e) => set({ end: e.target.value || undefined })} />
      </label>
      <label className="field">
        <span>Sort by</span>
        <select className="input" value={query.sort ?? 'purchase_ts'}
          onChange={(e) => set({ sort: e.target.value as ShipmentQuery['sort'] })}>
          <option value="purchase_ts">Newest</option>
          <option value="delay_probability">Highest risk</option>
          <option value="delay_days">Most delayed</option>
        </select>
      </label>
      {active && (
        <button className="btn btn-ghost" onClick={() => onChange({ page: 1 })} aria-label="Clear filters">
          <X size={14} /> Clear
        </button>
      )}
    </div>
  )
}
