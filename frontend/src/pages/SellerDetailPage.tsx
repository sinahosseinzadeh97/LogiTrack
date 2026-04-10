import { useParams } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { sellersApi } from '@/api/sellers'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { format, parseISO } from 'date-fns'
import { SkeletonChart } from '@/components/shared/SkeletonCard'
import { AnimatedNumber } from '@/components/shared/AnimatedNumber'
import { ArrowLeft } from 'lucide-react'
import { useNavigate } from '@tanstack/react-router'

export default function SellerDetailPage() {
  const { sellerId } = useParams({ from: '/protected/sellers/$sellerId' })
  const navigate = useNavigate()
  const { data, isLoading } = useQuery({
    queryKey: ['seller', sellerId],
    queryFn: () => sellersApi.getProfile(sellerId),
    staleTime: 5 * 60 * 1000,
  })

  const chartData = (data?.otif_trend ?? []).map((d) => ({
    week: format(parseISO(d.week_start), 'MMM dd'),
    otif: +(d.otif_rate * 100).toFixed(1),
  }))

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}
      style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

      <button className="btn btn-ghost" style={{ alignSelf: 'flex-start' }} onClick={() => navigate({ to: '/sellers' })}>
        <ArrowLeft size={14} /> Back to Sellers
      </button>

      {isLoading ? <SkeletonChart height={300} /> : data ? (
        <>
          {/* Profile header */}
          <div className="card" style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Seller ID</div>
              <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.82rem' }}>{data.seller_id}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>State</div>
              <span className="badge badge-blue">{data.seller_state}</span>
            </div>
            {[
              { label: 'Total Orders', value: data.total_orders, suffix: '', decimals: 0, color: 'var(--accent-blue)' },
              { label: 'Delay Rate',   value: data.delay_rate * 100, suffix: '%', decimals: 1, color: data.delay_rate > 0.4 ? 'var(--danger)' : 'var(--warn)' },
              { label: 'Avg Delay',    value: data.avg_delay_days, suffix: 'd', decimals: 1, color: 'var(--warn)' },
              { label: 'Avg Freight',  value: data.avg_freight_value, suffix: '', decimals: 0, color: 'var(--accent-green)', prefix: 'R$' },
            ].map(({ label, value, suffix, decimals, color, prefix }) => (
              <div key={label}>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
                <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '1.25rem', fontWeight: 700, color }}>
                  <AnimatedNumber value={value} decimals={decimals} suffix={suffix} prefix={prefix} />
                </div>
              </div>
            ))}
          </div>

          {/* OTIF trend */}
          <div className="card">
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '1rem' }}>
              8-Week OTIF Trend
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -24 }}>
                <defs>
                  <linearGradient id="sellerGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="var(--accent-green)" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="var(--accent-green)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                <XAxis dataKey="week" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v}%`} />
                <Tooltip
                  contentStyle={{ background: 'var(--bg-surface2)', border: '1px solid var(--border-strong)', borderRadius: 8, fontSize: '0.8rem' }}
                  labelStyle={{ color: 'var(--text-secondary)' }}
                  formatter={(v: any) => [`${(v as number).toFixed(1)}%`, 'OTIF']}
                />
                <ReferenceLine y={90} stroke="var(--accent-blue)" strokeDasharray="6 3" strokeWidth={1.5} />
                <Area type="monotone" dataKey="otif" stroke="var(--accent-green)" strokeWidth={2.5} fill="url(#sellerGrad)" dot={false} animationDuration={800} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </>
      ) : null}
    </motion.div>
  )
}
