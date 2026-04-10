interface SkeletonCardProps {
  rows?: number
  height?: string
  className?: string
}

export function SkeletonCard({ rows = 3, height = '1rem', className = '' }: SkeletonCardProps) {
  return (
    <div className={`card ${className}`} style={{ gap: '0.75rem', display: 'flex', flexDirection: 'column' }}>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="skeleton"
          style={{
            height,
            width: i === rows - 1 ? '60%' : '100%',
            opacity: 1 - i * 0.15,
          }}
        />
      ))}
    </div>
  )
}

export function SkeletonKPICard() {
  return (
    <div className="card" style={{ minHeight: 140 }}>
      <div className="skeleton" style={{ height: '0.75rem', width: '40%', marginBottom: '1rem' }} />
      <div className="skeleton" style={{ height: '2.5rem', width: '65%', marginBottom: '0.75rem' }} />
      <div className="skeleton" style={{ height: '0.7rem', width: '50%' }} />
    </div>
  )
}

export function SkeletonTable({ rows = 8 }: { rows?: number }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', padding: '0.5rem 0' }}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height: '2.75rem', borderRadius: '6px' }} />
      ))}
    </div>
  )
}

export function SkeletonChart({ height = 260 }: { height?: number }) {
  return <div className="skeleton" style={{ height, borderRadius: 'var(--radius-lg)' }} />
}
