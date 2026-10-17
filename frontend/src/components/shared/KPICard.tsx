import { AnimatedNumber } from './AnimatedNumber'

type Tone = 'green' | 'blue' | 'warn' | 'danger'

interface KPICardProps {
  title: string
  value: number | null | undefined
  decimals?: number
  suffix?: string
  prefix?: string
  tone?: Tone
  hint?: string
  loading?: boolean
}

const TONE: Record<Tone, string> = {
  green: 'var(--accent-green)', blue: 'var(--accent-blue)', warn: 'var(--warn)', danger: 'var(--danger)',
}

export function KPICard({ title, value, decimals = 1, suffix = '', prefix = '', tone = 'blue', hint, loading }: KPICardProps) {
  if (loading) {
    return (
      <div className="card" style={{ minHeight: 128 }}>
        <div className="skeleton" style={{ height: '0.75rem', width: '40%', marginBottom: '1rem' }} />
        <div className="skeleton" style={{ height: '2.25rem', width: '60%' }} />
      </div>
    )
  }
  return (
    <div className="card" style={{ minHeight: 128, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: '0.5rem' }}>
      <div className="section-title">{title}</div>
      <div className="font-mono" style={{ fontSize: '2rem', fontWeight: 700, color: TONE[tone], lineHeight: 1 }}>
        {value == null ? '—' : <AnimatedNumber value={value} decimals={decimals} prefix={prefix} suffix={suffix} />}
      </div>
      {hint && <div className="text-muted" style={{ fontSize: '0.75rem' }}>{hint}</div>}
    </div>
  )
}
