import { describe, expect, it } from 'vitest'

import { cn, formatMinutes, formatNumber, formatPercent } from './utils'

describe('cn', () => {
  it('merges class names', () => {
    expect(cn('a', 'b')).toBe('a b')
  })

  it('dedups conflicting tailwind classes via tailwind-merge', () => {
    expect(cn('p-2', 'p-4')).toBe('p-4')
  })
})

describe('formatNumber', () => {
  it('uses the configured digit count', () => {
    expect(formatNumber(1.2345, 2)).toBe('1.23')
  })

  it('defaults to one decimal', () => {
    expect(formatNumber(1.2345)).toBe('1.2')
  })
})

describe('formatPercent', () => {
  it('multiplies and appends a percent sign', () => {
    expect(formatPercent(0.529)).toBe('52.9%')
  })
})

describe('formatMinutes', () => {
  it('formats minutes below one hour', () => {
    expect(formatMinutes(45)).toBe('45m')
  })

  it('formats hours and minutes', () => {
    expect(formatMinutes(155)).toBe('2h 35m')
  })

  it('clamps negative values to zero', () => {
    expect(formatMinutes(-10)).toBe('0m')
  })
})
