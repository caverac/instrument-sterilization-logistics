/**
 * Typed client for the routing HTTP API. All calls go through Vite's `/api`
 * proxy, which forwards to the routing service on :8091 in dev.
 */

import type { DecideRequest, DecideResponse } from './types'

const API_BASE = '/api'

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers
    }
  })
  if (!response.ok) {
    throw new Error(`routing API ${path} returned ${response.status} ${response.statusText}`)
  }
  return (await response.json()) as T
}

export async function getHealth(): Promise<{ status: string }> {
  return fetchJson('/healthz')
}

export async function decide(request: DecideRequest): Promise<DecideResponse> {
  return fetchJson('/decide', { method: 'POST', body: JSON.stringify(request) })
}
