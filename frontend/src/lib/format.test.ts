import { describe, expect, it } from 'vitest'
import { brl, days, lift, pct, pctPoints, riskTone, shortDate, titleCase } from './format'

describe('format', () => {
  it('renders missing values as a dash', () => {
    for (const fn of [pct, pctPoints, days, brl]) expect(fn(null)).toBe('—')
    expect(shortDate(undefined)).toBe('—')
  })

  it('distinguishes 0–1 ratios from 0–100 rates', () => {
    expect(pct(0.0804)).toBe('8.0%')
    expect(pctPoints(93.23)).toBe('93.2%')
  })

  it('formats dates without shifting them across timezones', () => {
    expect(shortDate('2018-03-15')).toBe('Mar 15, 2018')
    expect(shortDate('2018-03-15T23:59:00')).toBe('Mar 15, 2018')
  })

  it('computes lift over the base rate', () => {
    expect(lift(0.74, 0.39)).toBe('1.9×')
    expect(lift(0.5, 0)).toBe('—')
  })

  it('colours risk relative to the threshold', () => {
    expect(riskTone(0.1, 0.26)).toBe('green')
    expect(riskTone(0.3, 0.26)).toBe('warn')
    expect(riskTone(0.6, 0.26)).toBe('danger')
  })

  it('turns slugs into labels', () => {
    expect(titleCase('bed_bath_table')).toBe('Bed Bath Table')
  })
})
