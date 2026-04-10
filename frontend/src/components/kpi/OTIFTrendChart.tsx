import { motion } from 'framer-motion'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer,
} from 'recharts'
import { format, parseISO } from 'date-fns'
import { useOTIFTrend } from '@/hooks/useKPISummary'
import { SkeletonChart } from '@/components/shared/SkeletonCard'

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tooltip">
      <div style={{ color: 'var(--text-secondary)', fontSize: '0.72rem', marginBottom: 4 }}>{label}</div>
      <div style={{ fontWeight: 700, color: 'var(--accent-blue)', fontFamily: 'JetBrains Mono, monospace', fontSize: '1rem' }}>
        {payload[0].value.toFixed(1)}%
      </div>
    </div>
  )
}

export function OTIFTrendChart() {
  const { data, isLoading } = useOTIFTrend(8)

  if (isLoading) return <SkeletonChart height={280} />

  const chartData = (data ?? []).map((d) => ({
    week: format(parseISO(d.week_start), 'MMM dd'),
    otif: +(d.otif_rate * 100).toFixed(1),
  }))

  return (
    <motion.div
      className="card"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.1 }}
      style={{ height: '100%', minHeight: 300 }}
    >
      <div style={{ marginBottom: '1rem' }}>
        <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          OTIF Trend — 8 Weeks
        </div>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -24 }}>
          <defs>
            <linearGradient id="otifGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="var(--accent-blue)" stopOpacity={0.25} />
              <stop offset="95%" stopColor="var(--accent-blue)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
          <XAxis dataKey="week" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis domain={[60, 100]} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v}%`} />
          <Tooltip content={<CustomTooltip />} cursor={{ stroke: 'rgba(255,255,255,0.08)', strokeWidth: 1 }} />
          <ReferenceLine y={90} stroke="var(--accent-green)" strokeDasharray="6 3" strokeWidth={1.5}
            label={{ value: '90% target', fill: 'var(--accent-green)', fontSize: 11, position: 'insideTopRight' }} />
          <Area
            type="monotone" dataKey="otif"
            stroke="var(--accent-blue)" strokeWidth={2.5}
            fill="url(#otifGrad)" dot={false}
            activeDot={{ r: 5, fill: 'var(--accent-blue)', stroke: 'var(--bg-base)', strokeWidth: 2 }}
            animationDuration={800}
          />
        </AreaChart>
      </ResponsiveContainer>
    </motion.div>
  )
}
