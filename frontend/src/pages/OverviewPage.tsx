import { useNavigate } from '@tanstack/react-router'
import { motion } from 'framer-motion'
import { useKPISummary } from '@/hooks/useKPISummary'
import { useAlerts } from '@/hooks/useAlerts'
import { KPICard } from '@/components/kpi/KPICard'
import { OTIFTrendChart } from '@/components/kpi/OTIFTrendChart'
import { DelayCategoryChart } from '@/components/kpi/DelayCategoryChart'
import { SellerTable } from '@/components/kpi/SellerTable'
import { AlertList } from '@/components/alerts/AlertList'
import { ShipmentDrawer } from '@/components/shipments/ShipmentDrawer'
import { useState } from 'react'
import { Alert } from '@/api/alerts'

export default function OverviewPage() {
  const navigate = useNavigate()
  const { data: kpi, isLoading: kpiLoading } = useKPISummary()
  const { data: alertItems, isLoading: alertsLoading } = useAlerts({ page_size: 5 })
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null)

  const handleAlertClick = (a: Alert) => setSelectedOrderId(a.order_id)

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}
    >
      {/* Row 1 — KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
        <KPICard
          title="OTIF Rate"
          value={kpi?.otif_rate ?? 0}
          delta={kpi?.week_over_week_otif_delta ?? undefined}
          decimals={1} suffix="%" color="green" loading={kpiLoading}
        />
        <KPICard
          title="Avg Delay"
          value={kpi?.avg_delay_days ?? 0}
          decimals={1} suffix=" days"
          color={kpi && kpi.avg_delay_days > 2 ? 'warn' : 'blue'}
          loading={kpiLoading}
        />
        <KPICard
          title="Fulfillment Rate"
          value={kpi?.fulfillment_rate ?? 0}
          decimals={1} suffix="%" color="blue" loading={kpiLoading}
        />
        <KPICard
          title="Late Shipments"
          value={kpi?.late_shipments ?? 0}
          decimals={0}
          color={kpi && kpi.late_shipments > 0 ? 'danger' : 'green'}
          loading={kpiLoading}
          onClick={() => navigate({ to: '/alerts' })}
        />
      </div>

      {/* Row 2 — OTIF chart + Flagged list */}
      <div style={{ display: 'grid', gridTemplateColumns: '60% 40%', gap: '1rem' }}>
        <OTIFTrendChart />
        <motion.div
          className="card"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', overflow: 'hidden' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
              Recent Alerts
            </div>
            <button className="btn btn-ghost" style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
              onClick={() => navigate({ to: '/alerts' })}>
              View all →
            </button>
          </div>
          <div style={{ overflow: 'auto', flex: 1 }}>
            <AlertList items={alertItems ?? []} loading={alertsLoading} onRowClick={handleAlertClick} />
          </div>
        </motion.div>
      </div>

      {/* Row 3 — Delay chart + Seller table */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <DelayCategoryChart />
        <SellerTable />
      </div>

      <ShipmentDrawer orderId={selectedOrderId} onClose={() => setSelectedOrderId(null)} />
    </motion.div>
  )
}
