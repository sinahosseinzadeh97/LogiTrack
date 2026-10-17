interface PaginationProps {
  page: number
  pageSize: number
  total: number
  noun: string
  onChange: (page: number) => void
}

export function Pagination({ page, pageSize, total, noun, onChange }: PaginationProps) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '0.75rem', borderTop: '1px solid var(--border)' }}>
      <span className="text-muted" style={{ fontSize: '0.75rem' }}>
        Page {page} of {pages} · {total.toLocaleString('en-US')} {noun}
      </span>
      <div style={{ display: 'flex', gap: '0.375rem' }}>
        <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>Prev</button>
        <button className="btn btn-ghost btn-sm" disabled={page >= pages} onClick={() => onChange(page + 1)}>Next</button>
      </div>
    </div>
  )
}
