import type { CSSProperties, ReactNode } from 'react'

interface SectionProps {
  title: string
  subtitle?: string
  actions?: ReactNode
  children: ReactNode
  style?: CSSProperties
}

/** A titled card: the building block of every page. */
export function Section({ title, subtitle, actions, children, style }: SectionProps) {
  return (
    <section className="card" style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem', minWidth: 0, ...style }}>
      <header style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem' }}>
        <div>
          <h2 className="section-title">{title}</h2>
          {subtitle && <p className="text-muted" style={{ fontSize: '0.8rem', marginTop: 4 }}>{subtitle}</p>}
        </div>
        {actions}
      </header>
      {children}
    </section>
  )
}
