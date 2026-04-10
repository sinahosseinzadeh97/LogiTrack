import { useNavigate } from '@tanstack/react-router'
import { motion } from 'framer-motion'
import { useSellerScorecard } from '@/hooks/useKPISummary'
import { SkeletonTable } from '@/components/shared/SkeletonCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { useState } from 'react'

const PAGE_SIZE = 20

export default function SellersPage() {
  const [page, setPage] = useState(1)
  const navigate = useNavigate()
  const { data, isLoading } = useSellerScorecard(1, 'delay_rate', 'desc')

  console.log('sellers response:', data)

  // API returns a plain SellerScoreRow[] — no .items or .data wrapper
  const rows = Array.isArray(data) ? data : []
  const totalPages = Math.ceil(rows.length / PAGE_SIZE)
  const pageRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}
      style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

      <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
        {data ? `${rows.length.toLocaleString()} sellers` : 'Loading…'}
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {isLoading ? <div style={{ padding: '1rem' }}><SkeletonTable rows={10} /></div> :
         !pageRows.length ? <EmptyState title="No sellers" /> : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Seller ID</th>
                <th>State</th>
                <th>Orders</th>
                <th>Delay Rate</th>
                <th>Avg Delay</th>
                <th>Avg Freight</th>
              </tr>
            </thead>
            <tbody>
              {pageRows.map((s) => {
                const color = s.delay_rate > 0.4 ? 'var(--danger)' : s.delay_rate >= 0.2 ? 'var(--warn)' : 'var(--accent-green)'
                return (
                  <tr key={s.seller_id} onClick={() => navigate({ to: '/sellers/$sellerId', params: { sellerId: s.seller_id } })}>
                    <td style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.78rem' }}>{s.seller_id.slice(0, 12)}…</td>
                    <td><span className="badge badge-gray">{s.seller_state}</span></td>
                    <td style={{ fontFamily: 'JetBrains Mono, monospace' }}>{s.total_orders.toLocaleString()}</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <div className="progress-bar" style={{ width: 80 }}>
                          <div className="progress-fill" style={{ width: `${s.delay_rate * 100}%`, background: color }} />
                        </div>
                        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.78rem', color }}>{(s.delay_rate * 100).toFixed(1)}%</span>
                      </div>
                    </td>
                    <td style={{ fontFamily: 'JetBrains Mono, monospace' }}>{s.avg_delay_days.toFixed(1)}d</td>
                    <td style={{ fontFamily: 'JetBrains Mono, monospace' }}>R${s.avg_cost.toFixed(0)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {totalPages > 1 && (
        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center', alignItems: 'center' }}>
          <button className="btn btn-ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Prev</button>
          <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>Page {page} / {totalPages}</span>
          <button className="btn btn-ghost" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</button>
        </div>
      )}
    </motion.div>
  )
}
