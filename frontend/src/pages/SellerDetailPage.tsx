import { useState } from 'react'
import { Link, useParams } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { useModelCard, useSeller, useShipments } from '@/api/queries'
import { TrendChart } from '@/components/charts/TrendChart'
import { KPICard } from '@/components/shared/KPICard'
import { Pagination } from '@/components/shared/Pagination'
import { QueryState } from '@/components/shared/QueryState'
import { Section } from '@/components/shared/Section'
import { SkeletonChart } from '@/components/shared/SkeletonCard'
import { ShipmentDrawer } from '@/components/shipments/ShipmentDrawer'
import { ShipmentTable } from '@/components/shipments/ShipmentTable'

export default function SellerDetailPage() {
  const { sellerId } = useParams({ from: '/protected/sellers/$sellerId' })
  const seller = useSeller(sellerId)
  const [page, setPage] = useState(1)
  const shipments = useShipments({ seller_id: sellerId, page, page_size: 10 })
  const threshold = useModelCard().data?.threshold
  const [selected, setSelected] = useState<string | null>(null)
  const s = seller.data

  return (
    <div className="page">
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <Link to="/sellers" className="btn btn-ghost btn-sm"><ArrowLeft size={14} /> Sellers</Link>
        <span className="font-mono text-muted" style={{ fontSize: '0.8rem' }}>{sellerId}</span>
        {s?.seller_state && <span className="badge badge-gray">{s.seller_state}</span>}
      </div>

      <QueryState isLoading={false} error={seller.error}>
        <div className="grid-kpi">
          <KPICard loading={seller.isLoading} title="Orders" value={s?.orders} decimals={0} />
          <KPICard loading={seller.isLoading} title="Late rate" value={s?.late_rate == null ? null : s.late_rate * 100} suffix="%" tone="danger"
            hint={s ? `over ${s.delivered} delivered orders` : undefined} />
          <KPICard loading={seller.isLoading} title="Late by, on average" value={s?.avg_delay_days_late} suffix=" d" tone="warn" />
          <KPICard loading={seller.isLoading} title="Avg freight" value={s?.avg_freight} prefix="R$ " decimals={2} tone="green" />
        </div>

        <Section title="On-time rate by month">
          {seller.isLoading ? <SkeletonChart /> : <TrendChart data={s?.trend ?? []} height={220} />}
        </Section>
      </QueryState>

      <Section title="Orders">
        <QueryState isLoading={shipments.isLoading} error={shipments.error} isEmpty={!shipments.data?.items.length}>
          <ShipmentTable items={shipments.data?.items ?? []} threshold={threshold} onSelect={setSelected} />
          <Pagination page={page} pageSize={10} total={shipments.data?.total ?? 0} noun="orders" onChange={setPage} />
        </QueryState>
      </Section>
      <ShipmentDrawer orderId={selected} threshold={threshold} onClose={() => setSelected(null)} />
    </div>
  )
}
