import { useRouterState } from '@tanstack/react-router'

const TITLES: [string, string][] = [
  ['/overview', 'Overview'],
  ['/shipments', 'Orders'],
  ['/alerts', 'At-risk queue · backtest'],
  ['/sellers', 'Sellers'],
  ['/regions', 'Regions'],
  ['/model', 'Model card'],
]

export function TopBar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const title = TITLES.find(([prefix]) => pathname.startsWith(prefix))?.[1] ?? 'LogiTrack'
  return (
    <header style={{
      height: 56, flexShrink: 0, display: 'flex', alignItems: 'center', padding: '0 1.5rem',
      background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)',
    }}>
      <h1 style={{ fontWeight: 700, fontSize: '1rem' }}>{title}</h1>
    </header>
  )
}
