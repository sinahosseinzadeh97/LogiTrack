import { type FormEvent, useState } from 'react'
import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { errorMessage } from '@/api/client'
import { useModelCard, usePredict } from '@/api/queries'
import type { ModelCard, PredictInput } from '@/api/types'
import { RiskBar } from '@/components/shared/Badges'
import { QueryState } from '@/components/shared/QueryState'
import { Section } from '@/components/shared/Section'
import { BR_STATES } from '@/lib/brazil'
import { count, pct, shortDate } from '@/lib/format'
import { hasRole, useAuthStore } from '@/stores/authStore'

const FEATURE_LABELS: Record<string, string> = {
  category: 'Product category', seller_state: 'Seller state', customer_state: 'Customer state',
  promised_days: 'Promised delivery window (days)', promise_gap_7d: 'Promise vs. last week’s typical (days)',
  distance_km: 'Seller → customer distance (km)', price: 'Order value (R$)', freight_value: 'Freight (R$)',
  weight_g: 'Weight (g)', n_items: 'Items in order', purchase_dow: 'Day of week (0 = Mon)',
  seller_prior_orders: 'Seller’s earlier orders due', seller_prior_late_rate: 'Seller’s earlier miss rate (0–1)',
  network_late_rate_14d: 'Network miss rate, last 14 days (0–1)', network_orders_7d: 'Orders in the previous 7 days',
}

function Metrics({ card }: { card: ModelCard }) {
  const rows = [
    { name: 'This model', ...card.metrics },
    ...Object.entries(card.baselines).map(([name, m]) => ({ name: `Baseline: ${name.replace('_', ' ')} only`, ...m })),
  ]
  return (
    <table className="data-table">
      <thead><tr><th>Score on the test period</th><th>ROC-AUC</th><th>PR-AUC</th></tr></thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.name} style={{ cursor: 'default' }}>
            <td>{r.name}</td>
            <td className="font-mono">{r.roc_auc.toFixed(3)}</td>
            <td className="font-mono">{r.pr_auc.toFixed(3)}</td>
          </tr>
        ))}
        <tr style={{ cursor: 'default' }}>
          <td className="text-muted">Random guessing</td>
          <td className="font-mono text-muted">0.500</td>
          <td className="font-mono text-muted">{card.metrics.base_rate.toFixed(3)}</td>
        </tr>
      </tbody>
    </table>
  )
}

function MonthlyChart({ card }: { card: ModelCard }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <ComposedChart data={card.monthly} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
        <XAxis dataKey="month" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis yAxisId="auc" domain={[0.3, 0.9]} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis yAxisId="rate" orientation="right" tickFormatter={(v: number) => pct(v, 0)}
          tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={{ background: 'var(--bg-surface2)', border: '1px solid var(--border-strong)', borderRadius: 10 }}
          formatter={(v, name) => (typeof v !== 'number' ? '—' : name === 'Late rate' ? pct(v) : v.toFixed(3))} />
        <Bar yAxisId="rate" dataKey="late_rate" name="Late rate" fill="var(--warn)" fillOpacity={0.35} maxBarSize={28} />
        <Line yAxisId="auc" dataKey="roc_auc" name="ROC-AUC" stroke="var(--accent-blue)" strokeWidth={2} dot isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

function Importance({ card }: { card: ModelCard }) {
  const max = Math.max(...card.feature_importance.map((f) => Math.abs(f.importance)), 1e-9)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
      {card.feature_importance.map((f) => (
        <div key={f.feature} style={{ display: 'grid', gridTemplateColumns: '220px 1fr 64px', alignItems: 'center', gap: '0.75rem', fontSize: '0.8rem' }}>
          <span className="text-muted">{FEATURE_LABELS[f.feature] ?? f.feature}</span>
          <div className="progress-bar">
            <div className="progress-fill" style={{
              width: `${(Math.abs(f.importance) / max) * 100}%`,
              background: f.importance < 0 ? 'var(--danger)' : 'var(--accent-blue)',
            }} />
          </div>
          <span className="font-mono" style={{ textAlign: 'right' }}>{f.importance.toFixed(3)}</span>
        </div>
      ))}
    </div>
  )
}

function WhatIf({ card }: { card: ModelCard }) {
  const [values, setValues] = useState<PredictInput>(card.defaults)
  const predict = usePredict()
  const set = (key: string, raw: string, numeric: boolean) =>
    setValues({ ...values, [key]: numeric ? Number(raw) : raw })
  const submit = (e: FormEvent) => { e.preventDefault(); predict.mutate(values) }

  return (
    <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))', gap: '0.75rem' }}>
        {card.features.map((f) => {
          const isState = f.endsWith('_state')
          const numeric = typeof card.defaults[f] === 'number'
          return (
            <label key={f} className="field">
              <span>{FEATURE_LABELS[f] ?? f}</span>
              {isState ? (
                <select className="input" value={String(values[f] ?? '')} onChange={(e) => set(f, e.target.value, false)}>
                  {BR_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              ) : (
                <input className="input" value={String(values[f] ?? '')} type={numeric ? 'number' : 'text'} step="any"
                  onChange={(e) => set(f, e.target.value, numeric)} />
              )}
            </label>
          )
        })}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
        <button className="btn btn-primary" type="submit" disabled={predict.isPending}>Score this order</button>
        <button className="btn btn-ghost" type="button" onClick={() => setValues(card.defaults)}>Reset to typical</button>
        {predict.data && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <RiskBar probability={predict.data.delay_probability} threshold={predict.data.threshold} width={160} />
            <span className={`badge ${predict.data.flagged ? 'badge-danger' : 'badge-green'}`}>
              {predict.data.flagged ? 'Would be flagged' : 'Below threshold'}
            </span>
          </div>
        )}
        {predict.error && <span className="badge badge-danger">{errorMessage(predict.error)}</span>}
      </div>
    </form>
  )
}

export default function ModelPage() {
  const card = useModelCard()
  const canPredict = hasRole(useAuthStore((s) => s.user), 'analyst')
  const c = card.data
  const weakMonths = (c?.monthly ?? []).filter((m) => m.roc_auc != null && m.roc_auc < 0.55).map((m) => m.month)
  const driftNote = weakMonths.length
    ? `Ranking quality collapses in ${weakMonths.join(', ')}: the world moved away from the training data, so a retrain is due.`
    : 'Ranking quality holds up across the whole test period.'

  return (
    <QueryState isLoading={card.isLoading} error={card.error}>
      {c && (
        <div className="page">
          <div className="callout">
            <strong>{c.algorithm}</strong> trained on {count(c.train.rows)} orders bought {shortDate(c.train.from)} – {shortDate(c.train.to)}
            {' '}({pct(c.train.late_rate)} late), evaluated once on {count(c.test.rows)} orders bought {shortDate(c.test.from)} – {shortDate(c.test.to)}
            {' '}({pct(c.test.late_rate)} late). Every input is known at checkout; the feature set ({c.feature_set}) and the
            decision threshold ({pct(c.threshold)}) were chosen inside the training window, never on the test set.
          </div>
          <div className="grid-2">
            <Section title="How good is it?" subtitle={`At the threshold it flags ${pct(c.metrics.alert_rate)} of orders; ${pct(c.metrics.precision)} of those are late and it catches ${pct(c.metrics.recall)} of all late orders.`}>
              <Metrics card={c} />
            </Section>
            <Section title="Month by month" subtitle={driftNote}>
              <MonthlyChart card={c} />
            </Section>
          </div>
          <Section title="What the model relies on" subtitle="Permutation importance: how much PR-AUC drops on the test set when a column is shuffled. Red means shuffling it helped.">
            <Importance card={c} />
          </Section>
          <Section title="What-if" subtitle="Change an order and score it. Starts from typical values of the test period.">
            {canPredict ? <WhatIf card={c} /> : <p className="text-muted">Scoring needs the analyst role. Sign in as analyst@logitrack.dev.</p>}
          </Section>
        </div>
      )}
    </QueryState>
  )
}
