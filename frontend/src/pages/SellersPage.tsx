import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { useSellers } from '@/api/queries'
import type { SellerQuery, SellerSort } from '@/api/types'
import { Pagination } from '@/components/shared/Pagination'
import { QueryState } from '@/components/shared/QueryState'
import { Section } from '@/components/shared/Section'
import { brl, count, days, pct, shortId } from '@/lib/format'

const COLUMNS: { key: SellerSort; label: string }[] = [
  { key: 'orders', label: 'Orders' },
  { key: 'late_rate', label: 'Late rate' },
  { key: 'avg_delay_days_late', label: 'Late by' },
  { key: 'avg_freight', label: 'Avg freight' },
]
const MIN_ORDERS = [20, 50, 100, 500]

export default function SellersPage() {
  const [query, setQuery] = useState<SellerQuery>({ sort: 'late_rate', order: 'desc', page: 1, min_orders: 20 })
  const sellers = useSellers(query)
  const navigate = useNavigate()

  const sortBy = (key: SellerSort) =>
    setQuery({ ...query, page: 1, sort: key, order: query.sort === key && query.order === 'desc' ? 'asc' : 'desc' })

  const minOrdersPicker = (
    <label className="field">
      <span>Min. delivered orders</span>
      <select className="input" value={query.min_orders}
        onChange={(e) => setQuery({ ...query, page: 1, min_orders: Number(e.target.value) })}>
        {MIN_ORDERS.map((n) => <option key={n} value={n}>{n}</option>)}
      </select>
    </label>
  )

  return (
    <div className="page">
      <Section title="Seller scorecard" subtitle="Late rate is computed over delivered orders only." actions={minOrdersPicker}>
        <QueryState isLoading={sellers.isLoading} error={sellers.error} isEmpty={!sellers.data?.items.length}>
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Seller</th><th>State</th>
                  {COLUMNS.map(({ key, label }) => (
                    <th key={key} aria-sort={query.sort === key ? (query.order === 'asc' ? 'ascending' : 'descending') : 'none'}>
                      <button className="th-button" onClick={() => sortBy(key)}>
                        {label}
                        {query.sort === key && (query.order === 'asc' ? <ChevronUp size={13} /> : <ChevronDown size={13} />)}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sellers.data?.items.map((s) => (
                  <tr key={s.seller_id} tabIndex={0}
                    onClick={() => navigate({ to: '/sellers/$sellerId', params: { sellerId: s.seller_id } })}
                    onKeyDown={(e) => e.key === 'Enter' && navigate({ to: '/sellers/$sellerId', params: { sellerId: s.seller_id } })}>
                    <td className="font-mono" style={{ fontSize: '0.78rem' }}>{shortId(s.seller_id, 10)}</td>
                    <td><span className="badge badge-gray">{s.seller_state ?? '?'}</span></td>
                    <td className="font-mono">{count(s.orders)}</td>
                    <td className="font-mono" style={{ color: (s.late_rate ?? 0) > 0.15 ? 'var(--danger)' : undefined }}>{pct(s.late_rate)}</td>
                    <td className="font-mono">{days(s.avg_delay_days_late)}</td>
                    <td className="font-mono">{brl(s.avg_freight)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={query.page} pageSize={15} total={sellers.data?.total ?? 0} noun="sellers"
            onChange={(page) => setQuery({ ...query, page })} />
        </QueryState>
      </Section>
    </div>
  )
}
