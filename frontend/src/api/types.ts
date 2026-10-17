// Mirrors backend/app/schemas.py. Dates arrive as ISO strings.

export interface DateRange {
  start?: string
  end?: string
}

export interface KPISummary {
  total_orders: number
  delivered: number
  late: number
  on_time_rate: number | null
  fulfillment_rate: number | null
  avg_delay_days_late: number | null
  avg_delivery_days: number | null
  avg_freight: number | null
  first_order: string | null
  last_order: string | null
}

export interface TrendPoint {
  period: string
  orders: number
  on_time_rate: number
  avg_delivery_days: number | null
}

export interface CategoryRow {
  category: string
  orders: number
  late_rate: number
  avg_delay_days_late: number | null
}

export interface RegionRow {
  state: string
  orders: number
  on_time_rate: number | null
  avg_delivery_days: number | null
  avg_freight: number | null
  avg_distance_km: number | null
}

export interface SellerRow {
  seller_id: string
  seller_state: string | null
  orders: number
  delivered: number
  late_rate: number | null
  avg_delay_days_late: number | null
  avg_freight: number | null
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface SellerDetail extends SellerRow {
  trend: TrendPoint[]
}

export type SellerSort = 'orders' | 'late_rate' | 'avg_delay_days_late' | 'avg_freight'

export interface SellerQuery {
  sort: SellerSort
  order: 'asc' | 'desc'
  page: number
  min_orders?: number
}

export interface Shipment {
  order_id: string
  order_status: string
  seller_id: string | null
  seller_state: string | null
  customer_state: string | null
  category: string | null
  purchase_ts: string
  estimated_delivery: string | null
  delivered_ts: string | null
  price: number
  freight_value: number
  distance_km: number | null
  delay_days: number | null
  is_late: boolean | null
  delay_probability: number | null
}

export interface ShipmentDetail extends Shipment {
  customer_id: string
  approved_ts: string | null
  carrier_ts: string | null
  n_items: number
  weight_g: number | null
  review_score: number | null
  promised_days: number | null
  seller_prior_orders: number
  seller_prior_late_rate: number | null
  network_late_rate_14d: number | null
  network_orders_7d: number
  promise_gap_7d: number | null
}

export interface ShipmentQuery extends DateRange {
  page: number
  page_size?: number
  status?: string
  customer_state?: string
  seller_id?: string
  is_late?: boolean
  search?: string
  sort?: 'purchase_ts' | 'delay_probability' | 'delay_days'
}

export interface BacktestWindow {
  cutoff: string
  min_date: string
  max_date: string
  default_as_of: string
  threshold: number
}

export type Outcome = 'late' | 'on_time' | 'not_delivered'

export interface BacktestItem {
  order_id: string
  seller_id: string | null
  customer_state: string | null
  category: string | null
  purchase_ts: string
  estimated_delivery: string
  days_to_promise: number
  delay_probability: number
  risk: 'high' | 'medium'
  outcome: Outcome
  delay_days: number | null
}

export interface BacktestStats {
  in_transit: number
  overdue: number
  flagged: number
  flagged_late: number
  precision: number | null
  recall: number | null
  base_rate: number | null
}

export interface Backtest {
  as_of: string
  threshold: number
  stats: BacktestStats
  items: BacktestItem[]
}

export interface Metrics {
  roc_auc: number
  pr_auc: number
  base_rate: number
  precision: number
  recall: number
  f1: number
  alert_rate: number
  precision_top_10pct: number
}

export interface ModelCard {
  version: string
  trained_at: string
  algorithm: string
  cutoff: string
  train: { rows: number; from: string; to: string; late_rate: number }
  test: { rows: number; from: string; to: string; late_rate: number }
  feature_set: string
  cv_pr_auc: Record<string, number>
  threshold: number
  metrics: Metrics
  baselines: Record<string, { roc_auc: number; pr_auc: number }>
  monthly: { month: string; orders: number; late_rate: number; roc_auc: number | null; pr_auc: number | null }[]
  feature_importance: { feature: string; importance: number }[]
  features: string[]
  defaults: Record<string, number | string>
}

export type PredictInput = Partial<Record<string, number | string>>

export interface Prediction {
  delay_probability: number
  flagged: boolean
  threshold: number
  base_rate: number
  inputs: Record<string, number | string | null>
}
