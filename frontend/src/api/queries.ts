import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import apiClient from './client'
import type {
  Backtest, BacktestWindow, CategoryRow, DateRange, KPISummary, ModelCard, Page, PredictInput,
  Prediction, RegionRow, SellerDetail, SellerQuery, SellerRow, Shipment, ShipmentDetail,
  ShipmentQuery, TrendPoint,
} from './types'

// The dataset is historical, so nothing changes while you look at it.
const STATIC = { staleTime: Infinity }

const get = <T,>(url: string, params?: object) =>
  apiClient.get<T>(url, { params }).then((r) => r.data)

export const useKPISummary = (range: DateRange) =>
  useQuery({ queryKey: ['kpi', 'summary', range], queryFn: () => get<KPISummary>('/api/v1/kpi/summary', range), ...STATIC })

export const useTrend = (range: DateRange, granularity: 'week' | 'month' = 'week') =>
  useQuery({
    queryKey: ['kpi', 'trend', range, granularity],
    queryFn: () => get<TrendPoint[]>('/api/v1/kpi/trend', { ...range, granularity }),
    ...STATIC,
  })

export const useCategories = (range: DateRange) =>
  useQuery({ queryKey: ['kpi', 'categories', range], queryFn: () => get<CategoryRow[]>('/api/v1/kpi/categories', range), ...STATIC })

export const useRegions = (range: DateRange) =>
  useQuery({ queryKey: ['kpi', 'regions', range], queryFn: () => get<RegionRow[]>('/api/v1/kpi/regions', range), ...STATIC })

export const useSellers = (query: SellerQuery) =>
  useQuery({
    queryKey: ['sellers', query],
    queryFn: () => get<Page<SellerRow>>('/api/v1/sellers', { ...query, page_size: 15 }),
    placeholderData: keepPreviousData,
    ...STATIC,
  })

export const useSeller = (sellerId: string) =>
  useQuery({ queryKey: ['seller', sellerId], queryFn: () => get<SellerDetail>(`/api/v1/sellers/${sellerId}`), ...STATIC })

export const useShipments = (query: ShipmentQuery) =>
  useQuery({
    queryKey: ['shipments', query],
    queryFn: () => get<Page<Shipment>>('/api/v1/shipments', query),
    placeholderData: keepPreviousData,
    ...STATIC,
  })

export const useShipment = (orderId: string | null) =>
  useQuery({
    queryKey: ['shipment', orderId],
    queryFn: () => get<ShipmentDetail>(`/api/v1/shipments/${orderId}`),
    enabled: !!orderId,
    ...STATIC,
  })

export const exportShipments = (query: ShipmentQuery) =>
  apiClient.get<Blob>('/api/v1/shipments/export', { params: query, responseType: 'blob' }).then((r) => r.data)

export const useBacktestWindow = () =>
  useQuery({ queryKey: ['alerts', 'window'], queryFn: () => get<BacktestWindow>('/api/v1/alerts/window'), ...STATIC })

export const useBacktest = (asOf: string | undefined) =>
  useQuery({
    queryKey: ['alerts', asOf],
    queryFn: () => get<Backtest>('/api/v1/alerts', { as_of: asOf, limit: 200 }),
    enabled: !!asOf,
    placeholderData: keepPreviousData,
    ...STATIC,
  })

export const useModelCard = () =>
  useQuery({ queryKey: ['model'], queryFn: () => get<ModelCard>('/api/v1/ml/model'), ...STATIC, retry: false })

export const usePredict = () =>
  useMutation({
    mutationFn: (input: PredictInput) =>
      apiClient.post<Prediction>('/api/v1/ml/predict', input).then((r) => r.data),
  })
