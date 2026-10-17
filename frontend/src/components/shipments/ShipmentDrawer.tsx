import { useEffect, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { X } from 'lucide-react'
import { useShipment } from '@/api/queries'
import { StatusBadge, RiskBar } from '@/components/shared/Badges'
import { brl, count, days, pct, shortDate, titleCase } from '@/lib/format'

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', padding: '0.55rem 0', borderBottom: '1px solid var(--border)' }}>
      <span className="text-muted" style={{ fontSize: '0.8rem' }}>{label}</span>
      <span style={{ fontSize: '0.85rem', textAlign: 'right' }}>{children}</span>
    </div>
  )
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section style={{ marginTop: '1.25rem' }}>
      <h3 className="section-title" style={{ color: 'var(--accent-blue)', marginBottom: '0.25rem' }}>{title}</h3>
      {children}
    </section>
  )
}

interface ShipmentDrawerProps {
  orderId: string | null
  threshold?: number
  onClose: () => void
}

export function ShipmentDrawer({ orderId, threshold, onClose }: ShipmentDrawerProps) {
  const { data: s, isLoading } = useShipment(orderId)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <AnimatePresence>
      {orderId && (
        <>
          <motion.div className="drawer-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <motion.aside className="drawer-panel" role="dialog" aria-label="Order detail"
            initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }} transition={{ type: 'spring', stiffness: 320, damping: 32 }}>
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border)' }}>
              <div>
                <div style={{ fontWeight: 700 }}>Order detail</div>
                <div className="font-mono text-muted" style={{ fontSize: '0.72rem' }}>{orderId}</div>
              </div>
              <button className="btn btn-ghost" onClick={onClose} aria-label="Close"><X size={15} /></button>
            </header>
            <div style={{ padding: '0 1.5rem 1.5rem' }}>
              {isLoading || !s ? (
                <div className="skeleton" style={{ height: 320, marginTop: '1.25rem' }} />
              ) : (
                <>
                  <Group title="Outcome">
                    <Row label="Status"><StatusBadge status={s.order_status} isLate={s.is_late} /></Row>
                    <Row label="Promised for">{shortDate(s.estimated_delivery)}</Row>
                    <Row label="Delivered">{shortDate(s.delivered_ts)}</Row>
                    <Row label="Days vs promise">{s.delay_days == null ? '—' : `${s.delay_days > 0 ? '+' : ''}${s.delay_days}`}</Row>
                    <Row label="Review score">{s.review_score ?? '—'}</Row>
                  </Group>
                  <Group title="Model score (known at purchase)">
                    <Row label="P(late)"><RiskBar probability={s.delay_probability} threshold={threshold} width={120} /></Row>
                    <Row label="Promised window">{days(s.promised_days)}</Row>
                    <Row label="vs. last week's typical promise">{days(s.promise_gap_7d)}</Row>
                    <Row label="Seller's earlier orders due">{count(s.seller_prior_orders)}</Row>
                    <Row label="…of which missed (smoothed)">{pct(s.seller_prior_late_rate)}</Row>
                    <Row label="Network miss rate, last 14 days">{pct(s.network_late_rate_14d)}</Row>
                    <Row label="Orders in the previous 7 days">{count(s.network_orders_7d)}</Row>
                  </Group>
                  <Group title="Order">
                    <Row label="Bought">{shortDate(s.purchase_ts)}</Row>
                    <Row label="Route">{s.seller_state ?? '?'} → {s.customer_state ?? '?'} ({s.distance_km?.toFixed(0) ?? '—'} km)</Row>
                    <Row label="Category">{titleCase(s.category)}</Row>
                    <Row label="Items">{s.n_items}</Row>
                    <Row label="Price / freight">{brl(s.price)} / {brl(s.freight_value)}</Row>
                  </Group>
                </>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}
