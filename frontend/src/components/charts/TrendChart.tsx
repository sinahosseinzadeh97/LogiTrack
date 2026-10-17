import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { TrendPoint } from '@/api/types'
import { count, pctPoints, shortDate } from '@/lib/format'

interface TooltipProps {
  active?: boolean
  payload?: { payload: TrendPoint }[]
}

function TrendTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="chart-tooltip">
      <div className="text-muted" style={{ fontSize: '0.72rem', marginBottom: 4 }}>{shortDate(p.period)}</div>
      <div className="font-mono" style={{ fontWeight: 700, color: 'var(--accent-blue)' }}>{pctPoints(p.on_time_rate)} on time</div>
      <div className="text-muted" style={{ fontSize: '0.72rem' }}>{count(p.orders)} delivered orders</div>
    </div>
  )
}

/** On-time rate per period. The y-axis follows the data instead of a fixed range. */
export function TrendChart({ data, height = 260 }: { data: TrendPoint[]; height?: number }) {
  const low = Math.min(...data.map((d) => d.on_time_rate))
  const floor = Math.max(0, Math.floor((low - 2) / 5) * 5)
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
        <defs>
          <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="var(--accent-blue)" stopOpacity={0.25} />
            <stop offset="95%" stopColor="var(--accent-blue)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
        <XAxis dataKey="period" tickFormatter={(v: string) => v.slice(0, 7)} minTickGap={32}
          tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis domain={[floor, 100]} tickFormatter={(v: number) => `${v}%`}
          tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} />
        <Tooltip content={<TrendTooltip />} cursor={{ stroke: 'rgba(255,255,255,0.08)' }} />
        <Area type="monotone" dataKey="on_time_rate" stroke="var(--accent-blue)" strokeWidth={2}
          fill="url(#trendFill)" dot={false} isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}
