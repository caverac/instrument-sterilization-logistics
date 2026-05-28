import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Merge Tailwind CSS classes with clsx semantics. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

/** Format a number with a fixed digit count, e.g. 162.5. */
export function formatNumber(value: number, digits = 1): string {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  })
}

/** Format a value as a percentage with the given decimal digits. */
export function formatPercent(value: number, digits = 1): string {
  return `${(value * 100).toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  })}%`
}

/** Format a duration in minutes as e.g. "2h 35m". */
export function formatMinutes(value: number): string {
  const total = Math.max(0, Math.round(value))
  const hours = Math.floor(total / 60)
  const minutes = total % 60
  if (hours === 0) return `${minutes}m`
  return `${hours}h ${minutes}m`
}
