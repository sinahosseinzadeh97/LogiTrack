import { motion } from 'framer-motion'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Cell, ResponsiveContainer,
} from 'recharts'
import { useDelayByCategory } from '@/hooks/useKPISummary'
import { SkeletonChart } from '@/components/shared/SkeletonCard'

function barColor(days: number) {
  if (days > 5) return 'var(--danger)'
  if (days >= 2) return 'var(--warn)'
  return 'var(--accent-green)'
}

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="chart-tooltip">
      <div style={{ color: 'var(--text-secondary)', fontSize: '0.72rem', marginBottom: 4, maxWidth: 160 }}>{d.category}</div>
      <div style={{ fontWeight: 700, fontFamily: 'JetBrains Mono, monospace' }}>
        {d.avg_delay_days.toFixed(1)} <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>days avg</span>
      </div>
      <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: 2 }}>{d.order_count} orders</div>
    </div>
  )
}

export function DelayCategoryChart() {
  const { data, isLoading } = useDelayByCategory()

  if (isLoading) return <SkeletonChart height={280} />

  const chartData = (data ?? [])
    .filter((d) => d.avg_delay_days != null)
    .slice(0, 10)
    .sort((a, b) => (b.avg_delay_days ?? 0) - (a.avg_delay_days ?? 0))
    .map((d) => ({
      category: (d.category_name ?? '').replace(/_/g, ' ').slice(0, 22),
      avg_delay_days: +(d.avg_delay_days ?? 0).toFixed(2),
      order_count: d.order_count,
    }))

  return (
    <motion.div
      className="card"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.15 }}
      style={{ height: '100%', minHeight: 300 }}
    >
      <div style={{ marginBottom: '1rem' }}>
        <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          Avg Delay by Category — Top 10
        </div>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 12, bottom: 0, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
          <XAxis type="number" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v}d`} />
          <YAxis dataKey="category" type="category" width={126} tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
          <Bar dataKey="avg_delay_days" radius={[0, 4, 4, 0]} maxBarSize={16} animationDuration={900}>
            {chartData.map((d, i) => (
              <Cell key={i} fill={barColor(d.avg_delay_days)} fillOpacity={0.85} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </motion.div>
  )
}
