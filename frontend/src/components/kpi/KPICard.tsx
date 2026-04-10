import { motion } from 'framer-motion'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { AnimatedNumber } from '@/components/shared/AnimatedNumber'

interface KPICardProps {
  title: string
  value: number
  delta?: number
  decimals?: number
  suffix?: string
  prefix?: string
  color?: 'green' | 'blue' | 'warn' | 'danger'
  onClick?: () => void
  loading?: boolean
}

const COLOR_MAP = {
  green:  { var: 'var(--accent-green)', glow: 'card-glow-green', badge: 'badge-green' },
  blue:   { var: 'var(--accent-blue)',  glow: 'card-glow-blue',  badge: 'badge-blue' },
  warn:   { var: 'var(--warn)',          glow: '',                badge: 'badge-warn' },
  danger: { var: 'var(--danger)',        glow: 'card-glow-red',   badge: 'badge-danger' },
}

export function KPICard({
  title, value, delta, decimals = 1, suffix = '', prefix = '',
  color = 'blue', onClick, loading = false,
}: KPICardProps) {
  const c = COLOR_MAP[color]

  if (loading) {
    return (
      <div className="card" style={{ minHeight: 140 }}>
        <div className="skeleton" style={{ height: '0.75rem', width: '40%', marginBottom: '1rem' }} />
        <div className="skeleton" style={{ height: '2.5rem', width: '65%', marginBottom: '0.75rem' }} />
        <div className="skeleton" style={{ height: '0.7rem', width: '50%' }} />
      </div>
    )
  }

  const DeltaIcon = !delta || Math.abs(delta) < 0.001
    ? Minus
    : delta > 0 ? TrendingUp : TrendingDown
  const deltaColor = !delta || Math.abs(delta) < 0.001
    ? 'var(--text-secondary)'
    : delta > 0 ? 'var(--accent-green)' : 'var(--danger)'

  return (
    <motion.div
      className={`card ${c.glow}`}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
      onClick={onClick}
      style={{ cursor: onClick ? 'pointer' : 'default', minHeight: 140, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}
    >
      <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', letterSpacing: '0.07em', textTransform: 'uppercase' }}>
        {title}
      </div>

      <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '2.25rem', fontWeight: 700, color: c.var, lineHeight: 1 }}>
        <AnimatedNumber value={value} decimals={decimals} prefix={prefix} suffix={suffix} duration={800} />
      </div>

      {delta !== undefined && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', color: deltaColor, fontSize: '0.78rem', fontWeight: 500 }}>
          <DeltaIcon size={14} />
          <span>{Math.abs(delta).toFixed(1)}{suffix} vs last week</span>
        </div>
      )}
    </motion.div>
  )
}
