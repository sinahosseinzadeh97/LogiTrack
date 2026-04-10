import apiClient from './client'
import type { SellerScoreRow } from './kpi'

export interface SellerProfile {
  seller_id: string
  seller_state: string
  total_orders: number
  delivered: number
  in_transit: number
  delay_rate: number
  avg_delay_days: number
  avg_freight_value: number
  otif_trend: Array<{ week_start: string; otif_rate: number }>
}

export const sellersApi = {
  getProfile: (sellerId: string) =>
    apiClient.get<SellerProfile>(`/api/v1/sellers/${sellerId}`).then((r) => r.data),

  getShipments: (sellerId: string, params: { page?: number; page_size?: number } = {}) =>
    apiClient
      .get(`/api/v1/sellers/${sellerId}/shipments`, { params })
      .then((r) => r.data),

  getScorecard: (sort_by = 'delay_rate', order = 'desc', limit = 100) =>
    apiClient
      .get<SellerScoreRow[]>('/api/v1/kpi/seller-scorecard', { params: { sort_by, order, limit } })
      .then((r) => r.data),
}
