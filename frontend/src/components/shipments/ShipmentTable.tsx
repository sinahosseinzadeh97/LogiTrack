import { format, parseISO } from 'date-fns'
import { motion } from 'framer-motion'
import { Shipment } from '@/api/shipments'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { SkeletonTable } from '@/components/shared/SkeletonCard'
import { EmptyState } from '@/components/shared/EmptyState'

interface ShipmentTableProps {
  items: Shipment[]
  loading: boolean
  onRowClick: (s: Shipment) => void
  page: number
  totalPages: number
  total: number
  onPageChange: (p: number) => void
}

export function ShipmentTable({ items, loading, onRowClick, page, totalPages, total, onPageChange }: ShipmentTableProps) {
  if (loading) return <SkeletonTable rows={10} />
  if (!items.length) return <EmptyState title="No shipments found" description="Try adjusting your filters." />

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.25 }}>
      <div style={{ overflowX: 'auto' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Order ID</th>
              <th>Date</th>
              <th>Seller State</th>
              <th>Customer State</th>
              <th>Category</th>
              <th>Distance</th>
              <th>Status</th>
              <th>Delay Risk</th>
            </tr>
          </thead>
          <tbody>
            {items.map((s) => (
              <tr key={s.order_id} onClick={() => onRowClick(s)}>
                <td style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.78rem' }}>
                  {s.order_id.slice(0, 12)}…
                </td>
                <td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                  {format(parseISO(s.purchase_timestamp), 'MMM dd, yyyy')}
                </td>
                <td><span className="badge badge-gray">{s.seller_state}</span></td>
                <td><span className="badge badge-gray">{s.customer_state}</span></td>
                <td style={{ fontSize: '0.82rem', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {s.product_category_name?.replace(/_/g, ' ') ?? '—'}
                </td>
                <td style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.82rem' }}>
                  {s.distance_km ? `${s.distance_km.toFixed(0)} km` : '—'}
                </td>
                <td>
                  {s.is_late
                    ? <StatusBadge status="late" />
                    : <StatusBadge status={s.status} />}
                </td>
                <td>
                  {s.delay_probability != null ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <div className="progress-bar" style={{ width: 60 }}>
                        <div className="progress-fill" style={{
                          width: `${s.delay_probability * 100}%`,
                          background: s.delay_probability > 0.8 ? 'var(--danger)' : s.delay_probability > 0.65 ? 'var(--warn)' : 'var(--accent-green)',
                        }} />
                      </div>
                      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                        {(s.delay_probability * 100).toFixed(0)}%
                      </span>
                    </div>
                  ) : <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '1rem', borderTop: '1px solid var(--border)', marginTop: '0.5rem' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            Page {page} of {totalPages} · {total.toLocaleString()} shipments
          </span>
          <div style={{ display: 'flex', gap: '0.375rem' }}>
            {[...Array(Math.min(totalPages, 7))].map((_, i) => {
              const p = i + 1
              return (
                <button key={p} className={`btn ${p === page ? 'btn-primary' : 'btn-ghost'}`}
                  style={{ padding: '0.3rem 0.6rem', minWidth: 34, fontSize: '0.8rem' }}
                  onClick={() => onPageChange(p)}>
                  {p}
                </button>
              )
            })}
            {totalPages > 7 && page < totalPages && (
              <button className="btn btn-ghost" style={{ padding: '0.3rem 0.6rem', fontSize: '0.8rem' }} onClick={() => onPageChange(totalPages)}>
                {totalPages}
              </button>
            )}
          </div>
        </div>
      )}
    </motion.div>
  )
}
