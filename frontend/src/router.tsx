import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  redirect,
} from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import { ProtectedRoute } from '@/components/auth/ProtectedRoute'
import LoginPage from '@/pages/LoginPage'
import OverviewPage from '@/pages/OverviewPage'
import ShipmentsPage from '@/pages/ShipmentsPage'
import AlertsPage from '@/pages/AlertsPage'
import SellersPage from '@/pages/SellersPage'
import SellerDetailPage from '@/pages/SellerDetailPage'
import RegionsPage from '@/pages/RegionsPage'
import PredictionPage from '@/pages/PredictionPage'
import ReportPage from '@/pages/ReportPage'
import SettingsPage from '@/pages/SettingsPage'
import { useAuthStore } from '@/stores/authStore'

// ── Root ─────────────────────────────────────────────────────────────────
const rootRoute = createRootRoute({ component: Outlet })

// ── Public ───────────────────────────────────────────────────────────────
const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  component: LoginPage,
  beforeLoad: () => {
    if (useAuthStore.getState().is_authenticated) {
      throw redirect({ to: '/overview' })
    }
  },
})

// ── Protected shell ───────────────────────────────────────────────────────
const protectedLayout = createRoute({
  getParentRoute: () => rootRoute,
  id: 'protected',
  component: () => (
    <ProtectedRoute>
      <AppShell />
    </ProtectedRoute>
  ),
  beforeLoad: () => {
    if (!useAuthStore.getState().is_authenticated) {
      throw redirect({ to: '/login' })
    }
  },
})

// ── Index redirect ────────────────────────────────────────────────────────
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: () => { throw redirect({ to: '/overview' }) },
  component: () => null,
})

// ── App routes ────────────────────────────────────────────────────────────
const overviewRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: '/overview',
  component: OverviewPage,
})

const shipmentsRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: '/shipments',
  component: ShipmentsPage,
})

const alertsRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: '/alerts',
  component: AlertsPage,
})

const sellersRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: '/sellers',
  component: SellersPage,
})

const sellerDetailRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: '/sellers/$sellerId',
  component: SellerDetailPage,
})

const regionsRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: '/regions',
  component: RegionsPage,
})

const predictionRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: '/prediction',
  component: PredictionPage,
})

const reportsRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: '/reports',
  component: ReportPage,
})

const settingsRoute = createRoute({
  getParentRoute: () => protectedLayout,
  path: '/settings',
  component: SettingsPage,
})

// ── Route tree ────────────────────────────────────────────────────────────
const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  protectedLayout.addChildren([
    overviewRoute,
    shipmentsRoute,
    alertsRoute,
    sellersRoute,
    sellerDetailRoute,
    regionsRoute,
    predictionRoute,
    reportsRoute,
    settingsRoute,
  ]),
])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
