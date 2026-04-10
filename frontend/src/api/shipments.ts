import apiClient from './client'

export interface Shipment {
  order_id: string
  seller_id: string
  seller_state: string
  customer_state: string
  product_category_name: string
  purchase_timestamp: string
  estimated_delivery_date: string
  actual_delivery_date: string | null
  carrier_arrival_date: string | null
  freight_value: number
  price: number
  distance_km: number
  is_late: boolean
  delay_days: number | null
  delay_probability: number | null
  status: 'delivered' | 'in_transit' | 'cancelled'
}

export interface ShipmentListResponse {
  items: Shipment[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface ShipmentFilters {
  page?: number
  page_size?: number
  status?: string
  state?: string
  category?: string
  is_late?: boolean
  date_from?: string
  date_to?: string
  search?: string
}

export const shipmentsApi = {
  getList: (filters: ShipmentFilters = {}) =>
    apiClient.get<ShipmentListResponse>('/api/v1/shipments', { params: filters }).then((r) => r.data),

  getOne: (orderId: string) =>
    apiClient.get<Shipment>(`/api/v1/shipments/${orderId}`).then((r) => r.data),

  exportCsv: (filters: ShipmentFilters = {}) =>
    apiClient
      .get('/api/v1/shipments/export', { params: filters, responseType: 'blob' })
      .then((r) => r.data as Blob),
}
