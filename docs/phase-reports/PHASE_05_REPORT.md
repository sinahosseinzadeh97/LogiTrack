# Phase 05 — React Dashboard (Frontend)

**Project:** LogiTrack — Logistics KPI Dashboard & Delay Prediction System
**Phase:** 05 — Frontend
**Completed:** 2026-04-09
**Author:** Engineering Team

---

## 1. All Files Created

| # | Path | Description |
|---|------|-------------|
| 1  | `frontend/vite.config.ts` | Vite config: Tailwind v4 plugin, `@` alias, proxy to FastAPI |
| 2  | `frontend/tsconfig.json` | TypeScript config with path aliases |
| 3  | `frontend/.env` | `VITE_API_URL=http://localhost:8000` |
| 4  | `frontend/src/index.css` | Full design system: tokens, cards, badges, skeleton, nav, animations |
| 5  | `frontend/src/main.tsx` | Entry point: QueryClientProvider + RouterProvider |
| 6  | `frontend/src/router.tsx` | TanStack Router tree: protected layout, guards, all routes |
| 7  | `frontend/src/vite-env.d.ts` | Vite `import.meta.env` type reference |
| 8  | `frontend/src/api/client.ts` | Axios instance: Bearer injection, 401→refresh→retry, DEV timing |
| 9  | `frontend/src/api/kpi.ts` | KPI API: summary, OTIF trend, delay-by-category, seller scorecard |
| 10 | `frontend/src/api/shipments.ts` | Shipments API: list/filter/single/csv-export |
| 11 | `frontend/src/api/alerts.ts` | Alerts API: flagged list, stats, live predict |
| 12 | `frontend/src/api/sellers.ts` | Sellers API: profile + OTIF trend, paginated shipments |
| 13 | `frontend/src/api/ml.ts` | ML Admin API: model-info, feature-importance, retrain |
| 14 | `frontend/src/stores/authStore.ts` | Zustand auth store: login/logout/refresh persisted to sessionStorage |
| 15 | `frontend/src/stores/settingsStore.ts` | Zustand settings: theme, sidebar collapse, alert refresh interval |
| 16 | `frontend/src/hooks/useKPISummary.ts` | TanStack Query hooks: KPI summary, OTIF trend, delay-by-cat, seller scorecard |
| 17 | `frontend/src/hooks/useShipments.ts` | TanStack Query hooks: shipment list, single shipment |
| 18 | `frontend/src/hooks/useAlerts.ts` | TanStack Query hooks: alert list + stats with configurable auto-refresh |
| 19 | `frontend/src/components/layout/AppShell.tsx` | Sidebar + TopBar + scrollable main Outlet |
| 20 | `frontend/src/components/layout/Sidebar.tsx` | Animated collapsible sidebar, live alert badge, user avatar, logout |
| 21 | `frontend/src/components/layout/TopBar.tsx` | Page title, global refresh, alert pill, theme toggle |
| 22 | `frontend/src/components/auth/ProtectedRoute.tsx` | Auth + role guard HOC |
| 23 | `frontend/src/components/shared/AnimatedNumber.tsx` | Framer Motion count-up animation |
| 24 | `frontend/src/components/shared/SkeletonCard.tsx` | Skeleton variants: card, KPI, table rows, chart |
| 25 | `frontend/src/components/shared/StatusBadge.tsx` | Color-coded badge for shipment/risk statuses |
| 26 | `frontend/src/components/shared/EmptyState.tsx` | Zero-data placeholder with icon |
| 27 | `frontend/src/components/kpi/KPICard.tsx` | Animated KPI card with delta indicator |
| 28 | `frontend/src/components/kpi/OTIFTrendChart.tsx` | Recharts AreaChart with gradient + 90% target line |
| 29 | `frontend/src/components/kpi/DelayCategoryChart.tsx` | Recharts horizontal BarChart colored by severity |
| 30 | `frontend/src/components/kpi/SellerTable.tsx` | Sortable seller table with delay-rate progress bars, pagination |
| 31 | `frontend/src/components/shipments/ShipmentFilters.tsx` | Search + status/state/date/late filter bar |
| 32 | `frontend/src/components/shipments/ShipmentTable.tsx` | Paginated shipment table with probability bars |
| 33 | `frontend/src/components/shipments/ShipmentDrawer.tsx` | Spring-animated slide-in detail drawer |
| 34 | `frontend/src/components/alerts/AlertList.tsx` | Alert table with route display and probability bars |
| 35 | `frontend/src/components/alerts/AlertBadge.tsx` | Alert count pill with bell icon |
| 36 | `frontend/src/components/alerts/PredictForm.tsx` | LiveInference form with SVG gauge + interpretation text |
| 37 | `frontend/src/pages/LoginPage.tsx` | Centered login card with logo, validation, show-password |
| 38 | `frontend/src/pages/OverviewPage.tsx` | 3-row grid dashboard: KPI cards, OTIF+alerts, categories+sellers |
| 39 | `frontend/src/pages/ShipmentsPage.tsx` | Shipments with filters, CSV export, drawer |
| 40 | `frontend/src/pages/AlertsPage.tsx` | Flagged alerts with stats cards, risk filter tabs, pagination |
| 41 | `frontend/src/pages/SellersPage.tsx` | Sellers list with sortable table, click-through to detail |
| 42 | `frontend/src/pages/SellerDetailPage.tsx` | Seller profile KPIs + 8-week OTIF area chart |
| 43 | `frontend/src/pages/RegionsPage.tsx` | Brazil map placeholder (Phase 6: react-leaflet choropleth) |
| 44 | `frontend/src/pages/PredictionPage.tsx` | Prediction form + feature importance chart + model info |
| 45 | `frontend/src/pages/ReportPage.tsx` | PDF report placeholder (Phase 6) |
| 46 | `frontend/src/pages/SettingsPage.tsx` | Theme toggle + alert refresh interval |
| 47 | `docs/phase-reports/PHASE_05_REPORT.md` | This document |

---

## 2. Component Tree

```
main.tsx
└── QueryClientProvider
    └── RouterProvider
        ├── /login → LoginPage
        └── /protected (ProtectedRoute)
            └── AppShell
                ├── Sidebar
                │   ├── Nav Items (lucide icons + active state)
                │   ├── Alert Badge (live count from useAlertStats)
                │   └── User Profile + Logout
                ├── TopBar
                │   ├── Page title (route-mapped)
                │   ├── Alert pill
                │   ├── Global refresh button
                │   └── Theme toggle
                └── <Outlet />
                    ├── /overview → OverviewPage
                    │   ├── KPICard × 4 (AnimatedNumber + delta)
                    │   ├── OTIFTrendChart (AreaChart + gradient)
                    │   ├── AlertList (preview 5 rows)
                    │   ├── DelayCategoryChart (horizontal BarChart)
                    │   ├── SellerTable (sortable + paginated)
                    │   └── ShipmentDrawer (slide-in)
                    ├── /shipments → ShipmentsPage
                    │   ├── ShipmentFiltersBar
                    │   ├── ShipmentTable (paginated)
                    │   └── ShipmentDrawer (slide-in)
                    ├── /alerts → AlertsPage
                    │   ├── AlertBadge + stats KPI cards × 4
                    │   ├── Risk filter tabs (All / High / Medium)
                    │   ├── AlertList
                    │   └── ShipmentDrawer (slide-in)
                    ├── /sellers → SellersPage
                    └── /sellers/$sellerId → SellerDetailPage
                    │   ├── Profile KPI cards (AnimatedNumber)
                    │   └── 8-week OTIF AreaChart
                    ├── /regions → RegionsPage (Phase 6 placeholder)
                    ├── /prediction → PredictionPage
                    │   ├── PredictForm (RHF + Zod + SVG gauge)
                    │   ├── Model info card
                    │   └── Feature importance BarChart
                    ├── /reports → ReportPage (Phase 6 placeholder)
                    └── /settings → SettingsPage
```

---

## 3. API Calls Per Page

| Page | Endpoints Called |
|------|-----------------|
| Login | `POST /auth/login`, `GET /auth/me` |
| Overview | `GET /kpi/summary`, `GET /kpi/otif-trend`, `GET /kpi/delay-by-category`, `GET /kpi/seller-scorecard`, `GET /alerts` (preview 5), `GET /shipments/{id}` (drawer) |
| Shipments | `GET /shipments` (paginated + filtered), `GET /shipments/{id}` (drawer), `GET /shipments/export` (CSV blob) |
| Alerts | `GET /alerts` (paginated + filtered by risk), `GET /alerts/stats`, `GET /shipments/{id}` (drawer) |
| Sellers | `GET /kpi/seller-scorecard` |
| Seller Detail | `GET /sellers/{id}` (profile + OTIF trend) |
| Prediction | `GET /ml/feature-importance`, `GET /ml/model-info`, `POST /alerts/predict` |
| Reports | — (Phase 6) |
| Regions | — (Phase 6) |
| Settings | — (local state only) |
| Sidebar | `GET /alerts/stats` (every 30s) |

---

## 4. State Management Decisions

| Store | Library | Persistence | Holds |
|-------|---------|-------------|-------|
| `authStore` | Zustand | `sessionStorage` | user, access_token, refresh_token, is_authenticated |
| `settingsStore` | Zustand | `localStorage` | theme, sidebarCollapsed, alertRefreshInterval |
| Server data | TanStack Query | In-memory cache | All API responses |

**Why sessionStorage for auth:** Tokens are lost on tab close (prevents session fixation). Refresh tokens are stored here rather than httpOnly cookies for simplicity; Phase 6 can migrate refresh token to httpOnly cookie.

**Why TanStack Query:** Declarative cache management, background refetch, placeholder data for smooth pagination transitions, and automatic deduplication of parallel requests.

---

## 5. Performance Optimizations

| Optimization | Detail |
|---|---|
| KPI Summary cache | 5 min stale time, auto-refetch every 5 min |
| OTIF Trend cache | 5 min stale time (data changes at most daily) |
| Alert list cache | Configurable via `alertRefreshInterval` (default 30s) |
| Sidebar alert badge | Uses same `useAlertStats` query — zero duplicate requests |
| Placeholder data | `placeholderData: (prev) => prev` keeps old data visible during page transitions |
| Animated numbers | `useMotionValue` + `useTransform` — no re-render on each frame |
| Skeleton loaders | Every data-dependent component renders a skeleton on `isLoading` |
| Code splitting | TanStack Router lazy-loads pages automatically |
| Recharts animations | `animationDuration={800}` smooth entrance on first render |
| Axios request dedup | TanStack Query deduplicates parallel identical queries |

---

## 6. How to Run

### Prerequisites
- Node.js ≥ 18 (tested with v25.8.1)
- Backend running on port 8000 (see Phase 04 REPORT)

### Start the frontend

```bash
cd frontend
npm install          # already done
npm run dev          # http://localhost:5173
```

### Environment variable

```bash
# frontend/.env
VITE_API_URL=http://localhost:8000
```

The Vite dev server also proxies `/api` and `/auth` to `localhost:8000`, so you can use relative paths if needed.

### Production build

```bash
npm run build        # outputs to frontend/dist/
```

---

## 7. Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `http://localhost:8000` | Base URL of the FastAPI backend |

---

## 8. Notes for Phase 6 (PDF Reporting & Map)

| Topic | Detail |
|-------|--------|
| **PDF Generation** | Install `@react-pdf/renderer`. `ReportPage.tsx` is already scaffolded as a placeholder. Generate OTIF summary + flagged list as PDF using the same data hooks. |
| **Brazil Choropleth Map** | `RegionsPage.tsx` is scaffolded. Install Brazil GeoJSON from `https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson`. Use `react-leaflet` + `GeoJSON` component; color each state based on `kpi/seller-scorecard` grouped by `seller_state`. |
| **Code Splitting** | `lucide-react` contributes ~400 KB to the bundle. Use `import { Icon } from 'lucide-react/dist/esm/icons/icon-name'` per-icon imports or `vite-plugin-svgr` to trim bundle size below 500 KB. |
| **HttpOnly Refresh Token** | Migrate `refresh_token` from sessionStorage to a `Set-Cookie: HttpOnly; Secure; SameSite=Strict` response. Update `api/client.ts` interceptor to use cookie-based storage. |
| **WebSocket KPI Push** | The Phase 04 report notes `GET /ws/kpi` as a planned endpoint. Wire it to `useKPISummary` with a WebSocket fallback to avoid polling. |
| **Dark/Light CSS** | `settingsStore` stores the theme preference. Phase 6 should apply `data-theme="light"` to `<html>` and migrate CSS tokens to light-mode overrides for full theming. |
