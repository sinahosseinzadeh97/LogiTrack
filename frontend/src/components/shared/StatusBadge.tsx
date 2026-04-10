type Status = 'delivered' | 'in_transit' | 'cancelled' | 'late' | 'on_time' | 'HIGH' | 'MEDIUM' | 'LOW'

const MAP: Record<Status, { label: string; cls: string }> = {
  delivered:  { label: 'Delivered',  cls: 'badge-green' },
  in_transit: { label: 'In Transit', cls: 'badge-blue'  },
  cancelled:  { label: 'Cancelled',  cls: 'badge-gray'  },
  late:       { label: 'Late',       cls: 'badge-danger' },
  on_time:    { label: 'On Time',    cls: 'badge-green'  },
  HIGH:       { label: 'High Risk',  cls: 'badge-danger' },
  MEDIUM:     { label: 'Med Risk',   cls: 'badge-warn'   },
  LOW:        { label: 'Low Risk',   cls: 'badge-green'  },
}

export function StatusBadge({ status }: { status: Status }) {
  const cfg = MAP[status] ?? { label: status, cls: 'badge-gray' }
  return <span className={`badge ${cfg.cls}`}>{cfg.label}</span>
}
