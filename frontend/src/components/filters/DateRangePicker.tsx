import type { DateRange } from '@/api/types'

const PRESETS: { label: string; range: DateRange }[] = [
  { label: 'All time', range: {} },
  { label: '2017', range: { start: '2017-01-01', end: '2017-12-31' } },
  { label: '2018', range: { start: '2018-01-01', end: '2018-12-31' } },
]

interface DateRangePickerProps {
  value: DateRange
  onChange: (range: DateRange) => void
}

/** Filters by purchase date. Native date inputs, plus a few presets. */
export function DateRangePicker({ value, onChange }: DateRangePickerProps) {
  const isPreset = (r: DateRange) => r.start === value.start && r.end === value.end
  return (
    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
      {PRESETS.map(({ label, range }) => (
        <button key={label} className={`btn btn-sm ${isPreset(range) ? 'btn-primary' : 'btn-ghost'}`} onClick={() => onChange(range)}>
          {label}
        </button>
      ))}
      <label className="field">
        <span>From</span>
        <input className="input" type="date" value={value.start ?? ''} min="2016-09-01" max="2018-10-31"
          onChange={(e) => onChange({ ...value, start: e.target.value || undefined })} />
      </label>
      <label className="field">
        <span>To</span>
        <input className="input" type="date" value={value.end ?? ''} min="2016-09-01" max="2018-10-31"
          onChange={(e) => onChange({ ...value, end: e.target.value || undefined })} />
      </label>
    </div>
  )
}
