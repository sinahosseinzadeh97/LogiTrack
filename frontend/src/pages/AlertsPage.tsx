import { useState } from 'react'
import { useBacktest, useBacktestWindow } from '@/api/queries'
import type { BacktestItem } from '@/api/types'
import { OutcomeBadge, RiskBar } from '@/components/shared/Badges'
import { KPICard } from '@/components/shared/KPICard'
import { QueryState } from '@/components/shared/QueryState'
import { Section } from '@/components/shared/Section'
import { ShipmentDrawer } from '@/components/shipments/ShipmentDrawer'
import { count, lift, pct, shortDate, shortId, titleCase } from '@/lib/format'

// Days worth replaying: the March 2018 backlog and the May 2018 truckers' strike.
const INTERESTING_DAYS = [
  { label: 'Mar 15 — backlog', date: '2018-03-15' },
  { label: 'May 24 — truckers’ strike', date: '2018-05-24' },
  { label: 'Jul 10 — quiet week', date: '2018-07-10' },
]

function QueueTable({ items, threshold, onSelect }: { items: BacktestItem[]; threshold: number; onSelect: (id: string) => void }) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="data-table">
        <thead>
          <tr><th>Order</th><th>Bought</th><th>Due in</th><th>To</th><th>Category</th><th>P(late)</th><th>What happened</th></tr>
        </thead>
        <tbody>
          {items.map((i) => (
            <tr key={i.order_id} onClick={() => onSelect(i.order_id)} tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && onSelect(i.order_id)}>
              <td className="font-mono" style={{ fontSize: '0.78rem' }}>{shortId(i.order_id, 10)}</td>
              <td className="text-muted">{shortDate(i.purchase_ts)}</td>
              <td className="font-mono">{i.days_to_promise} d</td>
              <td><span className="badge badge-gray">{i.customer_state ?? '?'}</span></td>
              <td style={{ maxWidth: 170, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{titleCase(i.category)}</td>
              <td><RiskBar probability={i.delay_probability} threshold={threshold} /></td>
              <td>
                <OutcomeBadge outcome={i.outcome} />
                {i.outcome === 'late' && <span className="font-mono text-muted" style={{ marginLeft: 6, fontSize: '0.75rem' }}>+{i.delay_days} d</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function AlertsPage() {
  const range = useBacktestWindow()
  const [picked, setPicked] = useState<string>()
  const asOf = picked ?? range.data?.default_as_of
  const backtest = useBacktest(asOf)
  const [selected, setSelected] = useState<string | null>(null)
  const s = backtest.data?.stats
  const threshold = range.data?.threshold ?? 0.5

  return (
    <div className="page">
      <div className="callout">
        The model was trained only on orders bought before <strong>{shortDate(range.data?.cutoff)}</strong>.
        Pick any later day to see the queue an operations team would have had that morning: orders
        in transit and not yet due, ranked by the late-delivery risk the model gave them at checkout.
        We know how each one ended, so the numbers below are what the alerts would really have achieved.
      </div>

      <QueryState isLoading={range.isLoading} error={range.error} loading={<div className="skeleton" style={{ height: 44 }} />}>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <label className="field">
            <span>Replay the morning of</span>
            <input className="input" type="date" value={asOf ?? ''} min={range.data?.min_date} max={range.data?.max_date}
              onChange={(e) => e.target.value && setPicked(e.target.value)} />
          </label>
          {INTERESTING_DAYS.map((d) => (
            <button key={d.date} className={`btn btn-sm ${asOf === d.date ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setPicked(d.date)}>
              {d.label}
            </button>
          ))}
        </div>
      </QueryState>

      <div className="grid-kpi">
        <KPICard loading={backtest.isLoading} title="In transit" value={s?.in_transit} decimals={0} tone="blue"
          hint={s ? `${count(s.overdue)} more were already overdue` : undefined} />
        <KPICard loading={backtest.isLoading} title="Flagged" value={s?.flagged} decimals={0} tone="warn"
          hint={s ? `${pct(s.in_transit ? s.flagged / s.in_transit : null)} of the queue, P(late) ≥ ${pct(threshold, 0)}` : undefined} />
        <KPICard loading={backtest.isLoading} title="Flagged that were late" value={s?.precision == null ? null : s.precision * 100}
          suffix="%" tone="danger" hint={s ? `${lift(s.precision, s.base_rate)} the ${pct(s.base_rate)} rate of the whole queue` : undefined} />
        <KPICard loading={backtest.isLoading} title="Late orders caught" value={s?.recall == null ? null : s.recall * 100}
          suffix="%" tone="green" hint="Share of the queue’s late orders that were flagged" />
      </div>

      <Section title={`Flagged orders on ${shortDate(asOf)}`} subtitle="Highest risk first. Click a row for the full order and the features the model saw.">
        <QueryState isLoading={backtest.isLoading} error={backtest.error} isEmpty={!backtest.data?.items.length}
          emptyTitle="No orders were flagged that day">
          <QueueTable items={backtest.data?.items ?? []} threshold={threshold} onSelect={setSelected} />
        </QueryState>
      </Section>

      <ShipmentDrawer orderId={selected} threshold={threshold} onClose={() => setSelected(null)} />
    </div>
  )
}
