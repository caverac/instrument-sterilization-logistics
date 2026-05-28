import { afterEach, describe, expect, it, vi } from 'vitest'

import { decide, getHealth } from './api'
import type { DecideResponse } from './types'

const realFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = realFetch
  vi.restoreAllMocks()
})

describe('getHealth', () => {
  it('GETs /api/healthz and parses JSON', async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve(new Response(JSON.stringify({ status: 'ok' }), { status: 200 }))
    ) as unknown as typeof fetch
    const result = await getHealth()
    expect(result).toEqual({ status: 'ok' })
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/healthz',
      expect.objectContaining({
        headers: expect.objectContaining({ 'Content-Type': 'application/json' })
      })
    )
  })
})

describe('decide', () => {
  const sample: DecideResponse = {
    facilities: [],
    policies: []
  }

  it('POSTs the request body to /api/decide and returns the response', async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve(new Response(JSON.stringify(sample), { status: 200 }))
    ) as unknown as typeof fetch
    const result = await decide({
      tray_type_id: 'TRAY-KNEE',
      hour_of_pickup: 10,
      deadline_min: 220,
      client_id: 'HOSPITAL_A'
    })
    expect(result).toEqual(sample)
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/decide',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          tray_type_id: 'TRAY-KNEE',
          hour_of_pickup: 10,
          deadline_min: 220,
          client_id: 'HOSPITAL_A'
        })
      })
    )
  })

  it('throws on a non-2xx response', async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve(new Response('boom', { status: 500, statusText: 'Internal Server Error' }))
    ) as unknown as typeof fetch
    await expect(
      decide({ tray_type_id: 't', hour_of_pickup: 0, deadline_min: 1, client_id: 'c' })
    ).rejects.toThrow(/500/)
  })
})
