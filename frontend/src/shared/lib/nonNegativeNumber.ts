import type { KeyboardEvent } from 'react'

const BLOCKED_NUMBER_KEYS = new Set(['-', '+', 'e', 'E'])

export function preventNegativeNumberInput(event: KeyboardEvent<HTMLInputElement>) {
  if (BLOCKED_NUMBER_KEYS.has(event.key)) {
    event.preventDefault()
  }
}

export function toNonNegativeInt(value: number | string | undefined, fallback: number): number {
  if (value === undefined) {
    return fallback
  }
  if (typeof value === 'string' && value.trim() === '') {
    return fallback
  }
  const parsed = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(parsed)) {
    return fallback
  }
  return Math.max(0, Math.trunc(parsed))
}

export function toNonNegativeNumber(value: string, fallback = 0): number {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) {
    return fallback
  }
  return Math.max(0, parsed)
}

export function toNonNegativeNumericString(value: string): string {
  if (!value.trim()) {
    return ''
  }
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) {
    return ''
  }
  return String(Math.max(0, parsed))
}
