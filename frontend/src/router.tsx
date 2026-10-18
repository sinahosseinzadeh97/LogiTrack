import {
  createRootRoute, createRoute, createRouter, lazyRouteComponent, Outlet, redirect,
} from '@tanstack/react-router'
import { AppShell } from '@/components/layout/AppShell'
import LoginPage from '@/pages/LoginPage'
import { isAuthenticated } from '@/stores/authStore'

const rootRoute = createRootRoute({ component: Outlet })

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  component: LoginPage,
  beforeLoad: () => {
    if (isAuthenticated()) throw redirect({ to: '/overview' })
  },
})

// Every app page sits under this layout route, which requires a signed-in user.
const protectedLayout = createRoute({
  getParentRoute: () => rootRoute,
  id: 'protected',
  component: AppShell,
  beforeLoad: () => {
    if (!isAuthenticated()) throw redirect({ to: '/login' })
  },
})

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: () => {
    throw redirect({ to: '/overview' })
  },
})

// Written out one by one so TanStack Router keeps each literal path type.
// Pages load lazily: the login screen doesn't pay for the charting library.
const overview = createRoute({ getParentRoute: () => protectedLayout, path: '/overview', component: lazyRouteComponent(() => import('@/pages/OverviewPage')) })
const shipments = createRoute({ getParentRoute: () => protectedLayout, path: '/shipments', component: lazyRouteComponent(() => import('@/pages/ShipmentsPage')) })
const alerts = createRoute({ getParentRoute: () => protectedLayout, path: '/alerts', component: lazyRouteComponent(() => import('@/pages/AlertsPage')) })
const sellers = createRoute({ getParentRoute: () => protectedLayout, path: '/sellers', component: lazyRouteComponent(() => import('@/pages/SellersPage')) })
const seller = createRoute({ getParentRoute: () => protectedLayout, path: '/sellers/$sellerId', component: lazyRouteComponent(() => import('@/pages/SellerDetailPage')) })
const regions = createRoute({ getParentRoute: () => protectedLayout, path: '/regions', component: lazyRouteComponent(() => import('@/pages/RegionsPage')) })
const model = createRoute({ getParentRoute: () => protectedLayout, path: '/model', component: lazyRouteComponent(() => import('@/pages/ModelPage')) })

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  protectedLayout.addChildren([overview, shipments, alerts, sellers, seller, regions, model]),
])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
