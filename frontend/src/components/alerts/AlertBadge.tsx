import { Bell } from 'lucide-react'

export function AlertBadge({ count }: { count: number }) {
  if (count === 0) return null
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '0.3rem',
      background: 'rgba(255,71,87,0.12)', color: 'var(--danger)',
      border: '1px solid rgba(255,71,87,0.25)', borderRadius: 999,
      padding: '0.2rem 0.6rem', fontSize: '0.72rem', fontWeight: 700,
    }}>
      <Bell size={11} />
      {count > 99 ? '99+' : count}
    </span>
  )
}
