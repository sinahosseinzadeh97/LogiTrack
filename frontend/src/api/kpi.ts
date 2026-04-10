import apiClient from './client'

export interface KPISummary {
  otif_rate: number
  avg_delay_days: number
  fulfillment_rate: number
  avg_cost_per_shipment: number
  total_shipments: number
  late_shipments: number
  week_over_week_otif_delta: number | null
}

export interface OTIFPoint {
  week_start: string
  otif_rate: number | null
}

export interface DelayCategoryItem {
  category_name: string
  avg_delay_days: number | null
  order_count: number
}

export interface SellerScoreRow {
  seller_id: string
  seller_state: string
  total_orders: number
  delay_rate: number
  avg_delay_days: number
  avg_cost: number
}

export const kpiApi = {
  getSummary: () =>
    apiClient.get<KPISummary>('/api/v1/kpi/summary').then((r) => r.data),

  getOTIFTrend: (weeks = 8) =>
    apiClient.get<OTIFPoint[]>('/api/v1/kpi/otif-trend', { params: { weeks } }).then((r) => r.data),

  getDelayByCategory: () =>
    apiClient.get<DelayCategoryItem[]>('/api/v1/kpi/delay-by-category').then((r) => r.data),

  getSellerScorecard: (_page = 1, _page_size = 10, sort_by = 'delay_rate', order = 'desc') =>
    apiClient
      .get<SellerScoreRow[]>('/api/v1/kpi/seller-scorecard', { params: { sort_by, order, limit: 100 } })
      .then((r) => r.data),
}
