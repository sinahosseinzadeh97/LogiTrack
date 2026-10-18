import { Link, useRouterState } from '@tanstack/react-router'
import { Bell, Brain, LayoutDashboard, LogOut, Map, Package, Store, Truck } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'

const NAV = [
  { to: '/overview', label: 'Overview', icon: LayoutDashboard },
  { to: '/alerts', label: 'At-risk queue', icon: Bell },
  { to: '/shipments', label: 'Orders', icon: Package },
  { to: '/sellers', label: 'Sellers', icon: Store },
  { to: '/regions', label: 'Regions', icon: Map },
  { to: '/model', label: 'Model', icon: Brain },
] as const

const ROLE_BADGE = { admin: 'badge-danger', analyst: 'badge-blue', viewer: 'badge-gray' } as const

export function Sidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const { user, logout } = useAuthStore()

  const handleLogout = () => {
    logout()
    window.location.assign('/login')
  }

  return (
    <aside className="sidebar">
      <div style={{ padding: '1.25rem 1rem', display: 'flex', alignItems: 'center', gap: '0.625rem', borderBottom: '1px solid var(--border)' }}>
        <div style={{
          width: 32, height: 32, borderRadius: 8, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-green))',
        }}>
          <Truck size={16} color="#fff" strokeWidth={2.5} />
        </div>
        <div className="sidebar-label">
          <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>LogiTrack</div>
          <div className="text-muted" style={{ fontSize: '0.65rem' }}>Olist delivery analytics</div>
        </div>
      </div>

      <nav aria-label="Main navigation" style={{ flex: 1, padding: '0.75rem 0.5rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        {NAV.map(({ to, label, icon: Icon }) => (
          <Link key={to} to={to} className={`nav-item ${pathname.startsWith(to) ? 'active' : ''}`} title={label}>
            <Icon size={17} strokeWidth={1.8} style={{ flexShrink: 0 }} />
            <span className="sidebar-label">{label}</span>
          </Link>
        ))}
      </nav>

      <div style={{ borderTop: '1px solid var(--border)', padding: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {user && (
          <div className="sidebar-label" style={{ overflow: 'hidden' }}>
            <div style={{ fontSize: '0.825rem', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.full_name}</div>
            <span className={`badge ${ROLE_BADGE[user.role]}`} style={{ fontSize: '0.6rem' }}>{user.role}</span>
          </div>
        )}
        <button onClick={handleLogout} className="btn btn-ghost btn-sm" title="Sign out">
          <LogOut size={15} /> <span className="sidebar-label">Sign out</span>
        </button>
      </div>
    </aside>
  )
}
