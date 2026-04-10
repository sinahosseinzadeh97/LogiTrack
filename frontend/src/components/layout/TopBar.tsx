import { useRouterState } from '@tanstack/react-router'
import { RefreshCw, Sun, Moon, Bell } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useSettingsStore } from '@/stores/settingsStore'
import { useAlertStats } from '@/hooks/useAlerts'

const PAGE_TITLES: Record<string, string> = {
  '/overview':    'Overview',
  '/shipments':   'Shipments',
  '/alerts':      'Flagged Alerts',
  '/sellers':     'Sellers',
  '/regions':     'Regions',
  '/prediction':  'Delay Prediction',
  '/reports':     'Reports',
  '/settings':    'Settings',
}

export function TopBar() {
  const { pathname } = useRouterState({ select: (s) => s.location })
  const { theme, setTheme } = useSettingsStore()
  const queryClient = useQueryClient()
  const { data: stats } = useAlertStats()

  const title = Object.entries(PAGE_TITLES).find(([k]) => pathname.startsWith(k))?.[1] ?? 'LogiTrack'

  const handleRefresh = () => {
    queryClient.invalidateQueries()
  }

  return (
    <header style={{
      height: 56,
      background: 'var(--bg-surface)',
      borderBottom: '1px solid var(--border)',
      display: 'flex', alignItems: 'center',
      padding: '0 1.25rem',
      gap: '1rem',
      position: 'sticky', top: 0, zIndex: 5,
      backdropFilter: 'blur(8px)',
    }}>
      <h1 style={{ fontWeight: 700, fontSize: '1rem', flex: 1 }}>{title}</h1>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        {/* Alert quick-view */}
        {(stats?.total_flagged ?? 0) > 0 && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '0.4rem',
            background: 'rgba(255,71,87,0.1)', border: '1px solid rgba(255,71,87,0.2)',
            borderRadius: 999, padding: '0.25rem 0.75rem',
            fontSize: '0.75rem', color: 'var(--danger)',
          }}>
            <Bell size={13} />
            <span style={{ fontWeight: 600 }}>{stats?.total_flagged} flagged</span>
          </div>
        )}

        {/* Refresh all */}
        <button
          onClick={handleRefresh}
          className="btn btn-ghost"
          style={{ padding: '0.4rem', borderRadius: '50%', width: 34, height: 34, justifyContent: 'center' }}
          title="Refresh all data"
        >
          <RefreshCw size={15} />
        </button>

        {/* Theme toggle */}
        <button
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          className="btn btn-ghost"
          style={{ padding: '0.4rem', borderRadius: '50%', width: 34, height: 34, justifyContent: 'center' }}
          title="Toggle theme"
        >
          {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
        </button>
      </div>
    </header>
  )
}
