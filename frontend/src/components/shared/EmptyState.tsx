import { Package } from 'lucide-react'

interface EmptyStateProps {
  title?: string
  description?: string
  icon?: React.ReactNode
}

export function EmptyState({
  title = 'No data found',
  description = 'There is nothing to display here yet.',
  icon,
}: EmptyStateProps) {
  return (
    <div
      style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', padding: '3rem 1rem', gap: '0.75rem',
        color: 'var(--text-secondary)',
      }}
    >
      <div style={{ opacity: 0.3, marginBottom: '0.25rem' }}>
        {icon ?? <Package size={40} />}
      </div>
      <p style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.95rem' }}>{title}</p>
      <p style={{ fontSize: '0.85rem', textAlign: 'center', maxWidth: 320 }}>{description}</p>
    </div>
  )
}
