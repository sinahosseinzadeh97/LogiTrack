import { Navigate } from '@tanstack/react-router'
import { useAuthStore, UserRole } from '@/stores/authStore'

interface ProtectedRouteProps {
  children: React.ReactNode
  requiredRole?: UserRole
}

const ROLE_LEVEL: Record<UserRole, number> = { viewer: 1, analyst: 2, admin: 3 }

export function ProtectedRoute({ children, requiredRole }: ProtectedRouteProps) {
  const { is_authenticated, user } = useAuthStore()

  if (!is_authenticated) return <Navigate to="/login" />

  if (requiredRole && user) {
    const userLevel = ROLE_LEVEL[user.role]
    const requiredLevel = ROLE_LEVEL[requiredRole]
    if (userLevel < requiredLevel) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '60vh', gap: '1rem', textAlign: 'center' }}>
          <div style={{ fontSize: '3rem' }}>🔒</div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>Access Denied</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Your role (<strong>{user.role}</strong>) does not have permission to view this page.
            <br />This page requires <strong>{requiredRole}</strong> or higher.
          </p>
        </div>
      )
    }
  }

  return <>{children}</>
}
