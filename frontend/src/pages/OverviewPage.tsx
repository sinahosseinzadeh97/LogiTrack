import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { useCategories, useKPISummary, useModelCard, useRegions, useTrend } from '@/api/queries'
import type { DateRange } from '@/api/types'
import { CategoryChart } from '@/components/charts/CategoryChart'
import { TrendChart } from '@/components/charts/TrendChart'
import { DateRangePicker } from '@/components/filters/DateRangePicker'
import { KPICard } from '@/components/shared/KPICard'
import { QueryState } from '@/components/shared/QueryState'
import { Section } from '@/components/shared/Section'
import { SkeletonChart } from '@/components/shared/SkeletonCard'
import { count, days, pct, pctPoints, shortDate } from '@/lib/format'

function ModelTeaser() {
  const { data: card } = useModelCard()
  if (!card) return null
  const m = card.metrics
  return (
    <Section title="Late-delivery model" subtitle={`Trained on orders before ${shortDate(card.cutoff)}, scored on what came after`}>
      <div className="grid-2" style={{ gap: '0.75rem' }}>
        <div><div className="text-muted" style={{ fontSize: '0.75rem' }}>ROC-AUC (out-of-time)</div>
          <div className="font-mono" style={{ fontSize: '1.5rem', fontWeight: 700 }}>{m.roc_auc.toFixed(2)}</div></div>
        <div><div className="text-muted" style={{ fontSize: '0.75rem' }}>Late share of top-10% riskiest</div>
          <div className="font-mono" style={{ fontSize: '1.5rem', fontWeight: 700 }}>{pct(m.precision_top_10pct)}</div>
          <div className="text-muted" style={{ fontSize: '0.75rem' }}>vs {pct(m.base_rate)} overall</div></div>
      </div>
      <div className="callout">
        Replay the at-risk queue on any day of the test period and see how the alerts turned out.{' '}
        <Link to="/alerts" style={{ color: 'var(--accent-blue)' }}>Open the backtest →</Link>
      </div>
    </Section>
  )
}

export default function OverviewPage() {
  const [range, setRange] = useState<DateRange>({})
  const kpi = useKPISummary(range)
  const trend = useTrend(range)
  const categories = useCategories(range)
  const regions = useRegions(range)
  const k = kpi.data
  const lateRate = k && k.delivered ? k.late / k.delivered : 0
  const worstRegions = [...(regions.data ?? [])]
    .filter((r) => r.orders >= 200)
    .sort((a, b) => (a.on_time_rate ?? 100) - (b.on_time_rate ?? 100))
    .slice(0, 5)

  return (
    <div className="page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: '1rem', flexWrap: 'wrap' }}>
        <p className="text-muted" style={{ fontSize: '0.85rem', maxWidth: 560 }}>
          {k ? <>{count(k.total_orders)} Olist orders bought between {shortDate(k.first_order)} and {shortDate(k.last_order)}.</> : ' '}
          {' '}"On time" means delivered by the date promised at checkout.
        </p>
        <DateRangePicker value={range} onChange={setRange} />
      </div>

      <div className="grid-kpi">
        <KPICard loading={kpi.isLoading} title="On-time rate" value={k?.on_time_rate} suffix="%" tone="green"
          hint={k ? `${count(k.late)} of ${count(k.delivered)} delivered orders were late` : undefined} />
        <KPICard loading={kpi.isLoading} title="Fulfillment rate" value={k?.fulfillment_rate} suffix="%" tone="blue"
          hint="Orders that were delivered at all" />
        <KPICard loading={kpi.isLoading} title="Avg delivery time" value={k?.avg_delivery_days} suffix=" d" tone="blue"
          hint="Purchase to doorstep" />
        <KPICard loading={kpi.isLoading} title="Late by, on average" value={k?.avg_delay_days_late} suffix=" d" tone="danger"
          hint="Days past the promise, late orders only" />
      </div>

      <div className="grid-wide-left">
        <Section title="On-time rate by week" subtitle="Dips line up with Black Friday 2017 and the Feb–Mar 2018 backlog">
          <QueryState isLoading={trend.isLoading} error={trend.error} isEmpty={!trend.data?.length} loading={<SkeletonChart />}>
            <TrendChart data={trend.data ?? []} />
          </QueryState>
        </Section>
        <ModelTeaser />
      </div>

      <div className="grid-2">
        <Section title="Categories most often late" subtitle={`Red: over 1.5× the overall late rate (${pct(lateRate)})`}>
          <QueryState isLoading={categories.isLoading} error={categories.error} isEmpty={!categories.data?.length} loading={<SkeletonChart />}>
            <CategoryChart data={categories.data ?? []} overallLateRate={lateRate} />
          </QueryState>
        </Section>
        <Section title="Hardest destinations" subtitle="States with 200+ orders, lowest on-time rate first"
          actions={<Link to="/regions" className="btn btn-ghost btn-sm">All states</Link>}>
          <QueryState isLoading={regions.isLoading} error={regions.error} isEmpty={!worstRegions.length}>
            <table className="data-table">
              <thead><tr><th>State</th><th>Orders</th><th>On time</th><th>Avg delivery</th><th>Avg distance</th></tr></thead>
              <tbody>
                {worstRegions.map((r) => (
                  <tr key={r.state} style={{ cursor: 'default' }}>
                    <td><span className="badge badge-gray">{r.state}</span></td>
                    <td className="font-mono">{count(r.orders)}</td>
                    <td className="font-mono">{pctPoints(r.on_time_rate)}</td>
                    <td className="font-mono">{days(r.avg_delivery_days)}</td>
                    <td className="font-mono">{r.avg_distance_km == null ? '—' : `${count(Math.round(r.avg_distance_km))} km`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </QueryState>
        </Section>
      </div>
    </div>
  )
}
