import { useQuery } from '@tanstack/react-query'
import { kpiApi } from '@/api/kpi'

export function useKPISummary() {
  return useQuery({
    queryKey: ['kpi', 'summary'],
    queryFn: kpiApi.getSummary,
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  })
}

export function useOTIFTrend(weeks = 8) {
  return useQuery({
    queryKey: ['kpi', 'otif-trend', weeks],
    queryFn: () => kpiApi.getOTIFTrend(weeks),
    staleTime: 5 * 60 * 1000,
  })
}

export function useDelayByCategory() {
  return useQuery({
    queryKey: ['kpi', 'delay-by-category'],
    queryFn: kpiApi.getDelayByCategory,
    staleTime: 5 * 60 * 1000,
  })
}

export function useSellerScorecard(page: number, sortBy: string, order: string) {
  return useQuery({
    queryKey: ['kpi', 'seller-scorecard', page, sortBy, order],
    queryFn: () => kpiApi.getSellerScorecard(page, 10, sortBy, order),
    staleTime: 5 * 60 * 1000,
    placeholderData: (prev) => prev,
  })
}
