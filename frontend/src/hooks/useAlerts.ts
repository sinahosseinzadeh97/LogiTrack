import { useQuery } from '@tanstack/react-query'
import { alertsApi } from '@/api/alerts'
import { useSettingsStore } from '@/stores/settingsStore'

export function useAlerts(params: { page?: number; page_size?: number; risk_level?: string } = {}) {
  const interval = useSettingsStore((s) => s.alertRefreshInterval)
  return useQuery({
    queryKey: ['alerts', params],
    queryFn: () => alertsApi.getList(params),
    staleTime: interval * 1000,
    refetchInterval: interval * 1000,
    placeholderData: (prev) => prev,
  })
}

export function useAlertStats() {
  const interval = useSettingsStore((s) => s.alertRefreshInterval)
  return useQuery({
    queryKey: ['alerts', 'stats'],
    queryFn: alertsApi.getStats,
    staleTime: interval * 1000,
    refetchInterval: interval * 1000,
  })
}
