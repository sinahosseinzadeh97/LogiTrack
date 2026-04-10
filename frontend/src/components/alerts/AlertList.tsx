import { Alert } from '@/api/alerts'
import { EmptyState } from '@/components/shared/EmptyState'
import { SkeletonTable } from '@/components/shared/SkeletonCard'
import { motion } from 'framer-motion'

interface AlertListProps {
  items: Alert[]
  loading: boolean
  onRowClick: (a: Alert) => void
}

function riskColor(prob: number) {
  return prob >= 0.8 ? 'var(--danger)' : 'var(--warn)'
}

export function AlertList({ items, loading, onRowClick }: AlertListProps) {
  if (loading) return <SkeletonTable rows={8} />
  if (!items.length) return <EmptyState title="No flagged shipments" description="All shipments are below risk threshold." />

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.25 }}>
      <div style={{ overflowX: 'auto' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Order ID</th>
              <th>Seller</th>
              <th>Route</th>
              <th>Category</th>
              <th>Distance</th>
              <th>Probability</th>
              <th>Days Left</th>
            </tr>
          </thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.order_id} onClick={() => onRowClick(a)}>
                <td style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.78rem' }}>
                  {a.order_id.slice(0, 12)}…
                </td>
                <td style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  {a.seller_id.slice(0, 8)}…
                </td>
                <td>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.82rem' }}>
                    <span className="badge badge-blue">{a.seller_state ?? '—'}</span>
                    <span style={{ color: 'var(--text-secondary)' }}>→</span>
                    <span className="badge badge-gray">{a.customer_state ?? '—'}</span>
                  </span>
                </td>
                <td style={{ fontSize: '0.8rem', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {a.category_name?.replace(/_/g, ' ') ?? '—'}
                </td>
                <td style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.82rem' }}>
                  {a.distance_km != null ? `${a.distance_km.toFixed(0)} km` : '—'}
                </td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <div className="progress-bar" style={{ width: 70 }}>
                      <div className="progress-fill" style={{
                        width: `${a.delay_probability * 100}%`,
                        background: riskColor(a.delay_probability),
                      }} />
                    </div>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.78rem', color: riskColor(a.delay_probability) }}>
                      {(a.delay_probability * 100).toFixed(0)}%
                    </span>
                  </div>
                </td>
                <td style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.82rem' }}>
                  {a.days_until_delivery != null ? `${a.days_until_delivery}d` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  )
}
