import { useState } from 'react'
import { useRegions } from '@/api/queries'
import type { DateRange, RegionRow } from '@/api/types'
import { DateRangePicker } from '@/components/filters/DateRangePicker'
import { QueryState } from '@/components/shared/QueryState'
import { Section } from '@/components/shared/Section'
import { STATE_TILES } from '@/lib/brazil'
import { brl, count, days, pctPoints } from '@/lib/format'

/** Green at 97%+ on time, red at 80% or less, interpolated in between. */
function tileColor(onTime: number | null): string {
  if (onTime == null) return 'var(--bg-surface3)'
  const t = Math.min(1, Math.max(0, (onTime - 80) / 17))
  return `hsl(${Math.round(t * 140)} 70% ${38 + t * 6}%)`
}

function TileMap({ rows, selected, onSelect }: { rows: RegionRow[]; selected?: string; onSelect: (s: string) => void }) {
  const byState = new Map(rows.map((r) => [r.state, r]))
  return (
    <div role="list" aria-label="On-time rate by destination state"
      style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(0, 1fr))', gridTemplateRows: 'repeat(8, 52px)', gap: 6, maxWidth: 460 }}>
      {Object.entries(STATE_TILES).map(([state, [col, row]]) => {
        const r = byState.get(state)
        return (
          <button key={state} role="listitem" onClick={() => onSelect(state)}
            title={`${state}: ${pctPoints(r?.on_time_rate)} on time, ${count(r?.orders)} orders`}
            style={{
              gridColumn: col + 1, gridRow: row + 1, border: selected === state ? '2px solid #fff' : '1px solid var(--border)',
              borderRadius: 8, background: tileColor(r?.on_time_rate ?? null), color: '#fff', cursor: 'pointer',
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem',
            }}>
            <strong style={{ fontSize: '0.8rem' }}>{state}</strong>
            <span className="font-mono">{r?.on_time_rate == null ? '—' : `${r.on_time_rate.toFixed(0)}%`}</span>
          </button>
        )
      })}
    </div>
  )
}

export default function RegionsPage() {
  const [range, setRange] = useState<DateRange>({})
  const [selected, setSelected] = useState<string>()
  const regions = useRegions(range)
  const rows = [...(regions.data ?? [])].sort((a, b) => (a.on_time_rate ?? 0) - (b.on_time_rate ?? 0))

  return (
    <div className="page">
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}><DateRangePicker value={range} onChange={setRange} /></div>
      <QueryState isLoading={regions.isLoading} error={regions.error} isEmpty={!rows.length}>
        <div className="grid-2">
          <Section title="On-time rate by destination" subtitle="Each tile is a state, laid out roughly where it sits on the map">
            <TileMap rows={rows} selected={selected} onSelect={setSelected} />
          </Section>
          <Section title="All states" subtitle="Worst on-time rate first">
            <div style={{ overflow: 'auto', maxHeight: 470 }}>
              <table className="data-table">
                <thead><tr><th>State</th><th>Orders</th><th>On time</th><th>Delivery</th><th>Freight</th><th>Distance</th></tr></thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.state} onClick={() => setSelected(r.state)}
                      style={{ background: selected === r.state ? 'rgba(61,127,255,0.1)' : undefined }}>
                      <td><span className="badge badge-gray">{r.state}</span></td>
                      <td className="font-mono">{count(r.orders)}</td>
                      <td className="font-mono">{pctPoints(r.on_time_rate)}</td>
                      <td className="font-mono">{days(r.avg_delivery_days)}</td>
                      <td className="font-mono">{brl(r.avg_freight)}</td>
                      <td className="font-mono">{r.avg_distance_km == null ? '—' : `${count(Math.round(r.avg_distance_km))} km`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        </div>
      </QueryState>
    </div>
  )
}
