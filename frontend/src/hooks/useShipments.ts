import { useQuery } from '@tanstack/react-query'
import { shipmentsApi, ShipmentFilters } from '@/api/shipments'

export function useShipments(filters: ShipmentFilters) {
  return useQuery({
    queryKey: ['shipments', filters],
    queryFn: () => shipmentsApi.getList(filters),
    staleTime: 2 * 60 * 1000,
    placeholderData: (prev) => prev,
  })
}

export function useShipment(orderId: string) {
  return useQuery({
    queryKey: ['shipment', orderId],
    queryFn: () => shipmentsApi.getOne(orderId),
    staleTime: 5 * 60 * 1000,
    enabled: !!orderId,
  })
}
