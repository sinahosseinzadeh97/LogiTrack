import { useState } from 'react'
import { Search, Filter, X } from 'lucide-react'
import { ShipmentFilters } from '@/api/shipments'

const STATUSES = ['', 'delivered', 'in_transit', 'cancelled']
const BR_STATES = ['', 'SP', 'RJ', 'MG', 'RS', 'PR', 'SC', 'BA', 'GO', 'PE', 'CE', 'ES', 'AM', 'MT', 'MS', 'PA', 'DF', 'RN', 'PB', 'AL']

interface ShipmentFiltersProps {
  filters: ShipmentFilters
  onChange: (f: ShipmentFilters) => void
}

export function ShipmentFiltersBar({ filters, onChange }: ShipmentFiltersProps) {
  const [open, setOpen] = useState(false)

  const set = (key: keyof ShipmentFilters, val: any) =>
    onChange({ ...filters, [key]: val || undefined, page: 1 })

  const clear = () => onChange({ page: 1, page_size: 20 })
  const activeCount = [filters.status, filters.state, filters.is_late].filter(Boolean).length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {/* Search + filter toggle row */}
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <Search size={15} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)', pointerEvents: 'none' }} />
          <input
            className="input"
            style={{ paddingLeft: '2rem' }}
            placeholder="Search order ID, seller…"
            value={filters.search ?? ''}
            onChange={(e) => set('search', e.target.value)}
          />
        </div>
        <button className={`btn ${activeCount > 0 ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setOpen((o) => !o)}>
          <Filter size={14} />
          Filters {activeCount > 0 && `(${activeCount})`}
        </button>
        {activeCount > 0 && (
          <button className="btn btn-ghost" onClick={clear} title="Clear filters"><X size={14} /></button>
        )}
      </div>

      {/* Expanded filter row */}
      {open && (
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center', padding: '0.875rem', background: 'var(--bg-surface2)', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
            <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Status</label>
            <select className="input" style={{ width: 140 }} value={filters.status ?? ''} onChange={(e) => set('status', e.target.value)}>
              {STATUSES.map((s) => <option key={s} value={s}>{s || 'All'}</option>)}
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
            <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>State</label>
            <select className="input" style={{ width: 120 }} value={filters.state ?? ''} onChange={(e) => set('state', e.target.value)}>
              {BR_STATES.map((s) => <option key={s} value={s}>{s || 'All'}</option>)}
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
            <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Delayed Only</label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', height: 36 }}>
              <input type="checkbox" id="is_late" checked={!!filters.is_late} onChange={(e) => set('is_late', e.target.checked || undefined)} style={{ accentColor: 'var(--accent-blue)', width: 16, height: 16 }} />
              <label htmlFor="is_late" style={{ fontSize: '0.85rem', cursor: 'pointer' }}>Show late only</label>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
            <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>From</label>
            <input className="input" type="date" style={{ width: 150 }} value={filters.date_from ?? ''} onChange={(e) => set('date_from', e.target.value)} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
            <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>To</label>
            <input className="input" type="date" style={{ width: 150 }} value={filters.date_to ?? ''} onChange={(e) => set('date_to', e.target.value)} />
          </div>
        </div>
      )}
    </div>
  )
}
