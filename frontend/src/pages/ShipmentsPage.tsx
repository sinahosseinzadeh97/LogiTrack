import { useState } from 'react'
import { motion } from 'framer-motion'
import { Download } from 'lucide-react'
import { useShipments } from '@/hooks/useShipments'
import { ShipmentFiltersBar } from '@/components/shipments/ShipmentFilters'
import { ShipmentTable } from '@/components/shipments/ShipmentTable'
import { ShipmentDrawer } from '@/components/shipments/ShipmentDrawer'
import { ShipmentFilters, Shipment, shipmentsApi } from '@/api/shipments'

export default function ShipmentsPage() {
  const [filters, setFilters] = useState<ShipmentFilters>({ page: 1, page_size: 20 })
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null)
  const { data, isLoading } = useShipments(filters)

  const handleExport = async () => {
    try {
      const blob = await shipmentsApi.exportCsv(filters)
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href = url; a.download = 'shipments_export.csv'; a.click()
      URL.revokeObjectURL(url)
    } catch {
      alert('Export failed — analyst role required.')
    }
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}
      style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            {data ? `${data.total.toLocaleString()} shipments` : 'Loading…'}
          </div>
        </div>
        <button className="btn btn-ghost" onClick={handleExport}>
          <Download size={14} /> Export CSV
        </button>
      </div>

      {/* Filters */}
      <ShipmentFiltersBar filters={filters} onChange={setFilters} />

      {/* Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <ShipmentTable
          items={data?.items ?? []}
          loading={isLoading}
          onRowClick={(s: Shipment) => setSelectedOrderId(s.order_id)}
          page={filters.page ?? 1}
          totalPages={data?.total_pages ?? 1}
          total={data?.total ?? 0}
          onPageChange={(p) => setFilters((f) => ({ ...f, page: p }))}
        />
      </div>

      <ShipmentDrawer orderId={selectedOrderId} onClose={() => setSelectedOrderId(null)} />
    </motion.div>
  )
}
