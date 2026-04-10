import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Package, MapPin, Calendar, AlertTriangle, TrendingUp } from 'lucide-react'
import { format, parseISO } from 'date-fns'
import { Shipment } from '@/api/shipments'
import { useShipment } from '@/hooks/useShipments'
import { StatusBadge } from '@/components/shared/StatusBadge'

interface ShipmentDrawerProps {
  orderId: string | null
  onClose: () => void
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.625rem 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>{label}</span>
      <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>{value}</span>
    </div>
  )
}

export function ShipmentDrawer({ orderId, onClose }: ShipmentDrawerProps) {
  const { data, isLoading } = useShipment(orderId ?? '')

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  const prob = data?.delay_probability ?? null
  const probColor = prob == null ? 'var(--text-secondary)'
    : prob > 0.8 ? 'var(--danger)'
    : prob > 0.65 ? 'var(--warn)'
    : 'var(--accent-green)'

  return (
    <AnimatePresence>
      {orderId && (
        <>
          <motion.div
            className="drawer-overlay"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            className="drawer-panel"
            initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 320, damping: 32 }}
          >
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border)', position: 'sticky', top: 0, background: 'var(--bg-surface)', zIndex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
                <Package size={18} color="var(--accent-blue)" />
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>Shipment Detail</div>
                  {data && <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{data.order_id.slice(0, 18)}…</div>}
                </div>
              </div>
              <button className="btn btn-ghost" style={{ padding: '0.4rem', borderRadius: '50%', width: 32, height: 32, justifyContent: 'center' }} onClick={onClose}>
                <X size={15} />
              </button>
            </div>

            <div style={{ padding: '1.5rem' }}>
              {isLoading ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {[...Array(8)].map((_, i) => <div key={i} className="skeleton" style={{ height: 40 }} />)}
                </div>
              ) : data ? (
                <>
                  {/* Risk gauge */}
                  {prob != null && (
                    <div style={{ marginBottom: '1.5rem', padding: '1rem', background: 'var(--bg-surface2)', borderRadius: 'var(--radius)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '1rem' }}>
                      <AlertTriangle size={20} color={probColor} />
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginBottom: 4, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Delay Risk</div>
                        <div className="progress-bar">
                          <div className="progress-fill" style={{ width: `${prob * 100}%`, background: probColor }} />
                        </div>
                      </div>
                      <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '1.5rem', fontWeight: 700, color: probColor }}>
                        {(prob * 100).toFixed(0)}%
                      </div>
                    </div>
                  )}

                  {/* Status */}
                  <div style={{ marginBottom: '1rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <StatusBadge status={data.status} />
                    {data.is_late && <StatusBadge status="late" />}
                  </div>

                  {/* Details */}
                  <section>
                    <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--accent-blue)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <MapPin size={12} /> Route
                    </div>
                    <Row label="Seller State" value={<span className="badge badge-blue">{data.seller_state}</span>} />
                    <Row label="Customer State" value={<span className="badge badge-gray">{data.customer_state}</span>} />
                    <Row label="Distance" value={<span style={{ fontFamily: 'JetBrains Mono, monospace' }}>{data.distance_km?.toFixed(0) ?? '—'} km</span>} />
                  </section>

                  <section style={{ marginTop: '1rem' }}>
                    <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--accent-green)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <Calendar size={12} /> Dates
                    </div>
                    <Row label="Purchase" value={format(parseISO(data.purchase_timestamp), 'MMM dd, yyyy HH:mm')} />
                    <Row label="Est. Delivery" value={format(parseISO(data.estimated_delivery_date), 'MMM dd, yyyy')} />
                    {data.actual_delivery_date && (
                      <Row label="Actual Delivery" value={format(parseISO(data.actual_delivery_date), 'MMM dd, yyyy')} />
                    )}
                    {data.delay_days != null && data.delay_days > 0 && (
                      <Row label="Delay" value={<span style={{ color: 'var(--danger)', fontFamily: 'JetBrains Mono, monospace', fontWeight: 600 }}>+{data.delay_days.toFixed(1)} days</span>} />
                    )}
                  </section>

                  <section style={{ marginTop: '1rem' }}>
                    <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--warn)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <TrendingUp size={12} /> Financials
                    </div>
                    <Row label="Price" value={<span style={{ fontFamily: 'JetBrains Mono, monospace' }}>R${data.price.toFixed(2)}</span>} />
                    <Row label="Freight Value" value={<span style={{ fontFamily: 'JetBrains Mono, monospace' }}>R${data.freight_value.toFixed(2)}</span>} />
                    <Row label="Category" value={<span style={{ fontSize: '0.8rem' }}>{data.product_category_name?.replace(/_/g, ' ') ?? '—'}</span>} />
                  </section>
                </>
              ) : null}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
