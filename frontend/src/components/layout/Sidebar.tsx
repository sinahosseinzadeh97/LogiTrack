import { Link, useRouterState } from '@tanstack/react-router'
import {
  LayoutDashboard, Package, Bell, Store, Map,
  Brain, FileText, Settings, LogOut, ChevronLeft, Truck,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuthStore } from '@/stores/authStore'
import { useSettingsStore } from '@/stores/settingsStore'
import { useAlertStats } from '@/hooks/useAlerts'

const NAV = [
  { to: '/overview',    label: 'Overview',    icon: LayoutDashboard },
  { to: '/shipments',  label: 'Shipments',   icon: Package },
  { to: '/alerts',     label: 'Alerts',      icon: Bell,    badge: true },
  { to: '/sellers',    label: 'Sellers',     icon: Store },
  { to: '/regions',    label: 'Regions',     icon: Map },
  { to: '/prediction', label: 'Prediction',  icon: Brain },
  { to: '/reports',    label: 'Reports',     icon: FileText },
  { to: '/settings',   label: 'Settings',    icon: Settings },
]

export function Sidebar() {
  const { pathname } = useRouterState({ select: (s) => s.location })
  const { user, logout } = useAuthStore()
  const { sidebarCollapsed, toggleSidebar } = useSettingsStore()
  const { data: stats } = useAlertStats()

  const w = sidebarCollapsed ? 64 : 220

  return (
    <motion.aside
      animate={{ width: w }}
      transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
      style={{
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column',
        overflow: 'hidden', flexShrink: 0,
        position: 'relative', zIndex: 10,
      }}
    >
      {/* Logo */}
      <div style={{
        padding: sidebarCollapsed ? '1.25rem 0' : '1.25rem 1rem',
        display: 'flex', alignItems: 'center',
        gap: '0.625rem', borderBottom: '1px solid var(--border)',
        justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
      }}>
        <div style={{
          width: 32, height: 32, borderRadius: 8, flexShrink: 0,
          background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-green))',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Truck size={16} color="#fff" strokeWidth={2.5} />
        </div>
        <AnimatePresence>
          {!sidebarCollapsed && (
            <motion.div
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.15 }}
            >
              <div style={{ fontWeight: 700, fontSize: '0.95rem', lineHeight: 1.1 }}>LogiTrack</div>
              <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                v5.0
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: '0.75rem 0.5rem', display: 'flex', flexDirection: 'column', gap: '0.25rem', overflowY: 'auto' }}>
        {NAV.map(({ to, label, icon: Icon, badge }) => {
          const active = pathname.startsWith(to)
          const alertCount = badge ? (stats?.total_flagged ?? 0) : 0
          return (
            <Link key={to} to={to}
              style={{ textDecoration: 'none' }}
            >
              <div
                className={`nav-item ${active ? 'active' : ''}`}
                style={{
                  justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
                  paddingLeft: sidebarCollapsed ? 0 : undefined,
                  paddingRight: sidebarCollapsed ? 0 : undefined,
                  position: 'relative',
                }}
                title={sidebarCollapsed ? label : undefined}
              >
                <Icon size={17} strokeWidth={1.8} style={{ flexShrink: 0 }} />
                <AnimatePresence>
                  {!sidebarCollapsed && (
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      style={{ flex: 1, fontSize: '0.875rem' }}
                    >
                      {label}
                    </motion.span>
                  )}
                </AnimatePresence>
                {badge && alertCount > 0 && (
                  <span style={{
                    position: sidebarCollapsed ? 'absolute' : 'static',
                    top: sidebarCollapsed ? 4 : undefined,
                    right: sidebarCollapsed ? 4 : undefined,
                    background: 'var(--danger)',
                    color: '#fff', borderRadius: 999,
                    fontSize: '0.6rem', fontWeight: 700,
                    padding: '1px 6px', lineHeight: 1.6,
                    minWidth: 18, textAlign: 'center',
                  }}>
                    {alertCount > 99 ? '99+' : alertCount}
                  </span>
                )}
              </div>
            </Link>
          )
        })}
      </nav>

      {/* User profile */}
      <div style={{
        borderTop: '1px solid var(--border)',
        padding: sidebarCollapsed ? '0.75rem 0.5rem' : '0.75rem',
        display: 'flex', flexDirection: 'column', gap: '0.5rem',
      }}>
        {!sidebarCollapsed && user && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', padding: '0.25rem 0' }}
          >
            <div style={{
              width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
              background: 'linear-gradient(135deg, var(--accent-blue), #7c3aed)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '0.75rem', fontWeight: 700, color: '#fff',
            }}>
              {user.full_name.charAt(0).toUpperCase()}
            </div>
            <div style={{ overflow: 'hidden', flex: 1 }}>
              <div style={{ fontSize: '0.825rem', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {user.full_name}
              </div>
              <span className={`badge ${user.role === 'admin' ? 'badge-danger' : user.role === 'analyst' ? 'badge-blue' : 'badge-gray'}`}
                style={{ fontSize: '0.6rem', padding: '1px 6px' }}>
                {user.role}
              </span>
            </div>
          </motion.div>
        )}
        <button
          onClick={logout}
          className="btn btn-ghost"
          style={{
            width: '100%', justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
            padding: sidebarCollapsed ? '0.5rem 0' : '0.5rem 0.75rem',
            fontSize: '0.8rem',
          }}
          title="Logout"
        >
          <LogOut size={15} />
          {!sidebarCollapsed && <span>Logout</span>}
        </button>
      </div>

      {/* Collapse toggle */}
      <button
        onClick={toggleSidebar}
        style={{
          position: 'absolute', top: '50%', right: -12,
          transform: 'translateY(-50%)',
          width: 24, height: 24, borderRadius: '50%',
          background: 'var(--bg-surface2)',
          border: '1px solid var(--border-strong)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer', zIndex: 20,
          color: 'var(--text-secondary)',
          transition: 'all var(--transition)',
        }}
        title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        <ChevronLeft
          size={13}
          style={{ transform: sidebarCollapsed ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}
        />
      </button>
    </motion.aside>
  )
}
