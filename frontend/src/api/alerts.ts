import apiClient from './client'

export interface Alert {
  order_id: string
  seller_id: string
  seller_state: string | null
  customer_state: string | null
  category_name: string | null
  distance_km: number | null
  delay_probability: number
  days_until_delivery: number | null
  estimated_delivery: string | null
}

export interface AlertStats {
  total_flagged: number
  high_risk: number
  medium_risk: number
  avg_probability: number
}

export interface PredictRequest {
  distance_km: number
  category_name: string
  seller_state: string
  day_of_week: number
  freight_value: number
  price: number
  month?: number
  seller_historical_delay_rate?: number
}

export interface PredictResponse {
  delay_probability: number
  predicted_late: boolean
  risk_level: 'high' | 'medium' | 'low'
}

export const alertsApi = {
  getList: (params: { page?: number; page_size?: number; risk_level?: string } = {}) =>
    apiClient.get<Alert[]>('/api/v1/alerts', { params }).then((r) => r.data),

  getStats: () =>
    apiClient.get<AlertStats>('/api/v1/alerts/stats').then((r) => r.data),

  predict: (payload: PredictRequest) =>
    apiClient.post<PredictResponse>('/api/v1/alerts/predict', payload).then((r) => r.data),
}
