// Display helpers. Every one renders missing values as an em dash.

const DASH = '—'

/** `ratio` is a 0–1 fraction. */
export const pct = (ratio: number | null | undefined, digits = 1): string =>
  ratio == null ? DASH : `${(ratio * 100).toFixed(digits)}%`

/** `value` is already on a 0–100 scale (on_time_rate, fulfillment_rate). */
export const pctPoints = (value: number | null | undefined, digits = 1): string =>
  value == null ? DASH : `${value.toFixed(digits)}%`

export const days = (value: number | null | undefined, digits = 1): string =>
  value == null ? DASH : `${value.toFixed(digits)} d`

export const brl = (value: number | null | undefined, digits = 2): string =>
  value == null ? DASH : `R$ ${value.toFixed(digits)}`

export const count = (value: number | null | undefined): string =>
  value == null ? DASH : value.toLocaleString('en-US')

export const shortId = (id: string | null | undefined, length = 8): string =>
  id ? `${id.slice(0, length)}…` : DASH

export const titleCase = (slug: string | null | undefined): string =>
  slug ? slug.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) : DASH

/** "2018-03-15" or "2018-03-15T10:00:00" -> "Mar 15, 2018" (no timezone shifting). */
export function shortDate(iso: string | null | undefined): string {
  if (!iso) return DASH
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC',
  })
}

/** How much more often a flagged order is late than a random one. */
export const lift = (precision: number | null, baseRate: number | null): string =>
  precision == null || !baseRate ? DASH : `${(precision / baseRate).toFixed(1)}×`

export type Tone = 'green' | 'warn' | 'danger'

/** Colour for a late-delivery probability relative to the model's threshold. */
export function riskTone(probability: number, threshold: number): Tone {
  if (probability >= Math.max(0.5, threshold)) return 'danger'
  if (probability >= threshold) return 'warn'
  return 'green'
}
