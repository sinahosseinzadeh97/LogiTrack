import { useState } from 'react'
import { Download } from 'lucide-react'
import { errorMessage } from '@/api/client'
import { exportShipments, useModelCard, useShipments } from '@/api/queries'
import type { ShipmentQuery } from '@/api/types'
import { Pagination } from '@/components/shared/Pagination'
import { QueryState } from '@/components/shared/QueryState'
import { Section } from '@/components/shared/Section'
import { ShipmentDrawer } from '@/components/shipments/ShipmentDrawer'
import { ShipmentFilters } from '@/components/shipments/ShipmentFilters'
import { ShipmentTable } from '@/components/shipments/ShipmentTable'
import { hasRole, useAuthStore } from '@/stores/authStore'

const PAGE_SIZE = 25

export default function ShipmentsPage() {
  const [query, setQuery] = useState<ShipmentQuery>({ page: 1 })
  const [selected, setSelected] = useState<string | null>(null)
  const [exportError, setExportError] = useState('')
  const shipments = useShipments({ ...query, page_size: PAGE_SIZE })
  const threshold = useModelCard().data?.threshold
  const canExport = hasRole(useAuthStore((s) => s.user), 'analyst')

  const handleExport = async () => {
    setExportError('')
    try {
      const url = URL.createObjectURL(await exportShipments({ ...query, page: 1 }))
      const link = Object.assign(document.createElement('a'), { href: url, download: 'shipments.csv' })
      link.click()
      URL.revokeObjectURL(url)
    } catch (error) {
      setExportError(errorMessage(error))
    }
  }

  const exportButton = canExport ? (
    <button className="btn btn-ghost btn-sm" onClick={handleExport}><Download size={14} /> Export CSV</button>
  ) : (
    <span className="text-muted" style={{ fontSize: '0.75rem' }}>CSV export needs the analyst role</span>
  )

  return (
    <div className="page">
      <Section title="Orders" subtitle="Every order in the dataset, any status." actions={exportButton}>
        <ShipmentFilters query={query} onChange={setQuery} />
        {exportError && <div className="badge badge-danger">{exportError}</div>}
        <QueryState isLoading={shipments.isLoading} error={shipments.error} isEmpty={!shipments.data?.items.length}
          emptyTitle="No orders match">
          <ShipmentTable items={shipments.data?.items ?? []} threshold={threshold} onSelect={setSelected} />
          <Pagination page={query.page} pageSize={PAGE_SIZE} total={shipments.data?.total ?? 0} noun="orders"
            onChange={(page) => setQuery({ ...query, page })} />
        </QueryState>
      </Section>
      <ShipmentDrawer orderId={selected} threshold={threshold} onClose={() => setSelected(null)} />
    </div>
  )
}
