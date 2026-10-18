import type { Shipment } from '@/api/types'
import { StatusBadge, RiskBar } from '@/components/shared/Badges'
import { shortDate, shortId, titleCase } from '@/lib/format'

interface ShipmentTableProps {
  items: Shipment[]
  threshold?: number
  onSelect: (orderId: string) => void
}

export function ShipmentTable({ items, threshold, onSelect }: ShipmentTableProps) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="data-table">
        <thead>
          <tr>
            <th>Order</th><th>Bought</th><th>Route</th><th>Category</th>
            <th>Promised</th><th>Status</th><th>Delay</th><th>P(late) at purchase</th>
          </tr>
        </thead>
        <tbody>
          {items.map((s) => (
            <tr key={s.order_id} onClick={() => onSelect(s.order_id)} tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && onSelect(s.order_id)}>
              <td className="font-mono" style={{ fontSize: '0.78rem' }}>{shortId(s.order_id, 10)}</td>
              <td className="text-muted">{shortDate(s.purchase_ts)}</td>
              <td><span className="badge badge-gray">{s.seller_state ?? '?'} → {s.customer_state ?? '?'}</span></td>
              <td style={{ maxWidth: 170, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {titleCase(s.category)}
              </td>
              <td className="text-muted">{shortDate(s.estimated_delivery)}</td>
              <td><StatusBadge status={s.order_status} isLate={s.is_late} /></td>
              <td className="font-mono" style={{ color: (s.delay_days ?? 0) > 0 ? 'var(--danger)' : 'var(--text-secondary)' }}>
                {s.delay_days == null ? '—' : s.delay_days > 0 ? `+${s.delay_days} d` : `${s.delay_days} d`}
              </td>
              <td><RiskBar probability={s.delay_probability} threshold={threshold} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
