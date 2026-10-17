import type { Outcome } from '@/api/types'
import { riskTone } from '@/lib/format'

const STATUS: Record<string, string> = {
  delivered: 'badge-green', shipped: 'badge-blue', invoiced: 'badge-blue', processing: 'badge-blue',
  approved: 'badge-blue', created: 'badge-blue', canceled: 'badge-gray', unavailable: 'badge-gray',
}

export function StatusBadge({ status, isLate }: { status: string; isLate?: boolean | null }) {
  if (isLate) return <span className="badge badge-danger">Late</span>
  return <span className={`badge ${STATUS[status] ?? 'badge-gray'}`}>{status}</span>
}

const OUTCOME: Record<Outcome, [string, string]> = {
  late: ['Late', 'badge-danger'],
  on_time: ['On time', 'badge-green'],
  not_delivered: ['Never delivered', 'badge-warn'],
}

export function OutcomeBadge({ outcome }: { outcome: Outcome }) {
  const [label, cls] = OUTCOME[outcome]
  return <span className={`badge ${cls}`}>{label}</span>
}

const TONE_VAR = { green: 'var(--accent-green)', warn: 'var(--warn)', danger: 'var(--danger)' }

/** Probability bar coloured relative to the model's decision threshold. */
export function RiskBar({ probability, threshold, width = 64 }: { probability: number | null; threshold?: number; width?: number }) {
  if (probability == null) return <span className="text-muted">—</span>
  const color = TONE_VAR[riskTone(probability, threshold ?? 0.5)]
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
      <div className="progress-bar" style={{ width }} role="presentation">
        <div className="progress-fill" style={{ width: `${probability * 100}%`, background: color }} />
      </div>
      <span className="font-mono" style={{ fontSize: '0.75rem', color }}>{(probability * 100).toFixed(0)}%</span>
    </div>
  )
}
