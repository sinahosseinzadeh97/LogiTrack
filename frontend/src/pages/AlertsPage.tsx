import { useState } from 'react'
import { motion } from 'framer-motion'
import { RefreshCw } from 'lucide-react'
import { useAlerts, useAlertStats } from '@/hooks/useAlerts'
import { AlertList } from '@/components/alerts/AlertList'
import { AlertBadge } from '@/components/alerts/AlertBadge'
import { ShipmentDrawer } from '@/components/shipments/ShipmentDrawer'
import { AnimatedNumber } from '@/components/shared/AnimatedNumber'
import { Alert } from '@/api/alerts'
import { useQueryClient } from '@tanstack/react-query'

type Filter = 'all' | 'high' | 'medium'

export default function AlertsPage() {
  const [filter, setFilter] = useState<Filter>('all')
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null)
  const qc = useQueryClient()

  const risk_level = filter === 'high' ? 'HIGH' : filter === 'medium' ? 'MEDIUM' : undefined
  const { data, isLoading } = useAlerts({ risk_level })
  const { data: stats } = useAlertStats()

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}
      style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <AlertBadge count={stats?.total_flagged ?? 0} />
        <button className="btn btn-ghost" onClick={() => qc.invalidateQueries({ queryKey: ['alerts'] })}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
        {[
          { label: 'Total Flagged', value: stats?.total_flagged ?? 0, color: 'var(--danger)', decimals: 0 },
          { label: 'High Risk',     value: stats?.high_risk ?? 0,     color: 'var(--danger)', decimals: 0 },
          { label: 'Medium Risk',   value: stats?.medium_risk ?? 0,   color: 'var(--warn)',   decimals: 0 },
          { label: 'Avg Probability', value: (stats?.avg_probability ?? 0) * 100, color: 'var(--accent-blue)', decimals: 1 },
        ].map(({ label, value, color, decimals }) => (
          <motion.div
            key={label} className="card"
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '0.5rem' }}>{label}</div>
            <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '1.75rem', fontWeight: 700, color }}>
              <AnimatedNumber value={value} decimals={decimals} suffix={label === 'Avg Probability' ? '%' : ''} />
            </div>
          </motion.div>
        ))}
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        {(['all', 'high', 'medium'] as Filter[]).map((f) => (
          <button key={f} className={`btn ${filter === f ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => { setFilter(f); setPage(1) }}>
            {f === 'all' ? 'All' : f === 'high' ? 'High Risk (>80%)' : 'Medium Risk (65–80%)'}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <AlertList
          items={data ?? []}
          loading={isLoading}
          onRowClick={(a: Alert) => setSelectedOrderId(a.order_id)}
        />
      </div>

      <ShipmentDrawer orderId={selectedOrderId} onClose={() => setSelectedOrderId(null)} />
    </motion.div>
  )
}
