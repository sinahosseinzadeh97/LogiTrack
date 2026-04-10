import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { motion } from 'framer-motion'
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'
import { useSellerScorecard } from '@/hooks/useKPISummary'
import { SkeletonTable } from '@/components/shared/SkeletonCard'
import { EmptyState } from '@/components/shared/EmptyState'

type SortField = 'delay_rate' | 'avg_delay_days' | 'total_orders' | 'avg_cost'
type SortOrder = 'asc' | 'desc'

function SortIcon({ field, active, order }: { field: string; active: boolean; order: SortOrder }) {
  if (!active) return <ChevronsUpDown size={13} style={{ opacity: 0.3 }} />
  return active && order === 'asc' ? <ChevronUp size={13} /> : <ChevronDown size={13} />
}

function DelayRateBar({ rate }: { rate: number }) {
  const color = rate > 0.4 ? 'var(--danger)' : rate >= 0.2 ? 'var(--warn)' : 'var(--accent-green)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
      <div className="progress-bar" style={{ width: 80 }}>
        <div className="progress-fill" style={{ width: `${rate * 100}%`, background: color }} />
      </div>
      <span style={{ fontSize: '0.8rem', fontFamily: 'JetBrains Mono, monospace', color }}>
        {(rate * 100).toFixed(1)}%
      </span>
    </div>
  )
}

const PAGE_SIZE = 10

export function SellerTable() {
  const [page, setPage] = useState(1)
  const [sortBy, setSortBy] = useState<SortField>('total_orders')
  const [order, setOrder] = useState<SortOrder>('desc')
  const navigate = useNavigate()
  const { data: allRows, isLoading } = useSellerScorecard(1, sortBy, order)

  const handleSort = (field: SortField) => {
    if (sortBy === field) setOrder((o) => (o === 'asc' ? 'desc' : 'asc'))
    else { setSortBy(field); setOrder('desc') }
    setPage(1)
  }

  const cols: { key: SortField; label: string }[] = [
    { key: 'total_orders',       label: 'Orders'     },
    { key: 'delay_rate',         label: 'Delay Rate' },
    { key: 'avg_delay_days',     label: 'Avg Delay'  },
    { key: 'avg_cost',           label: 'Avg Freight'},
  ]

  // Client-side pagination since backend returns a flat list
  const rows = allRows ?? []
  const totalPages = Math.ceil(rows.length / PAGE_SIZE)
  const pageRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  return (
    <motion.div
      className="card"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.2 }}
      style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}
    >
      <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
        Seller Performance
      </div>

      {isLoading ? (
        <SkeletonTable rows={6} />
      ) : !rows.length ? (
        <EmptyState title="No sellers found" />
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Seller ID</th>
                <th>State</th>
                {cols.map(({ key, label }) => (
                  <th key={key} onClick={() => handleSort(key)} style={{ cursor: 'pointer', userSelect: 'none' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                      {label}
                      <SortIcon field={key} active={sortBy === key} order={order} />
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pageRows.map((s) => (
                <tr key={s.seller_id} onClick={() => navigate({ to: '/sellers/$sellerId', params: { sellerId: s.seller_id } })}>
                  <td style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.78rem' }}>
                    {s.seller_id.slice(0, 8)}…
                  </td>
                  <td>
                    <span className="badge badge-gray">{s.seller_state}</span>
                  </td>
                  <td style={{ fontFamily: 'JetBrains Mono, monospace' }}>{s.total_orders.toLocaleString()}</td>
                  <td><DelayRateBar rate={s.delay_rate} /></td>
                  <td style={{ fontFamily: 'JetBrains Mono, monospace' }}>{s.avg_delay_days.toFixed(1)}d</td>
                  <td style={{ fontFamily: 'JetBrains Mono, monospace' }}>R${s.avg_cost.toFixed(0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '0.5rem', borderTop: '1px solid var(--border)' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            Page {page} of {totalPages} · {rows.length} sellers
          </span>
          <div style={{ display: 'flex', gap: '0.375rem' }}>
            <button className="btn btn-ghost" style={{ padding: '0.3rem 0.6rem', fontSize: '0.78rem' }}
              disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Prev
            </button>
            <button className="btn btn-ghost" style={{ padding: '0.3rem 0.6rem', fontSize: '0.78rem' }}
              disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              Next
            </button>
          </div>
        </div>
      )}
    </motion.div>
  )
}
