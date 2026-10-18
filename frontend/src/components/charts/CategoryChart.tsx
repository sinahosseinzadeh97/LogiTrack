import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { CategoryRow } from '@/api/types'
import { count, days, pct, titleCase } from '@/lib/format'

interface TooltipProps {
  active?: boolean
  payload?: { payload: CategoryRow }[]
}

function CategoryTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length) return null
  const c = payload[0].payload
  return (
    <div className="chart-tooltip">
      <div className="text-muted" style={{ fontSize: '0.72rem', marginBottom: 4 }}>{titleCase(c.category)}</div>
      <div className="font-mono" style={{ fontWeight: 700 }}>{pct(c.late_rate)} late</div>
      <div className="text-muted" style={{ fontSize: '0.72rem' }}>
        {count(c.orders)} orders · late ones {days(c.avg_delay_days_late)} past promise
      </div>
    </div>
  )
}

/** Categories with the highest late-delivery rate, coloured against the overall rate. */
export function CategoryChart({ data, overallLateRate }: { data: CategoryRow[]; overallLateRate: number }) {
  const rows = data.map((c) => ({ ...c, label: titleCase(c.category).slice(0, 24) }))
  return (
    <ResponsiveContainer width="100%" height={Math.max(180, rows.length * 26)}>
      <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
        <XAxis type="number" tickFormatter={(v: number) => pct(v, 0)}
          tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis dataKey="label" type="category" width={150}
          tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} />
        <Tooltip content={<CategoryTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
        <Bar dataKey="late_rate" radius={[0, 4, 4, 0]} maxBarSize={16} isAnimationActive={false}>
          {rows.map((r) => (
            <Cell key={r.category} fill={r.late_rate > overallLateRate * 1.5 ? 'var(--danger)' : 'var(--warn)'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
