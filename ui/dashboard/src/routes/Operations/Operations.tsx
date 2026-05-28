import { useEffect, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Spinner } from '@/components/ui/spinner'
import { getRecentJourneys, getTrayStates } from '@/lib/api'
import type { Journey, TrayState } from '@/lib/types'
import { formatMinutes, formatNumber } from '@/lib/utils'

const POLL_INTERVAL_MS = 5000

const badgeVariantFor = (id: string): 'boca' | 'lgb' | 'elm' | 'default' =>
  id === 'BOCA' ? 'boca' : id === 'LGB' ? 'lgb' : id === 'ELM' ? 'elm' : 'default'

const formatTs = (iso: string): string => {
  const d = new Date(iso)
  return d.toLocaleString('en-US', {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

export function Operations() {
  const [trays, setTrays] = useState<TrayState[] | null>(null)
  const [journeys, setJourneys] = useState<Journey[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const [trayResp, journeyResp] = await Promise.all([getTrayStates(), getRecentJourneys()])
        if (cancelled) return
        setTrays(trayResp.trays)
        setJourneys(journeyResp.journeys)
        setError(null)
      } catch (e) {
        if (!cancelled) setError((e as Error).message)
      }
    }
    load()
    const id = window.setInterval(load, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [])

  return (
    <div className="p-8">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold">Operations</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          What the projector has captured from the event stream. Polls every 5 seconds. Tray
          current-state is sourced from the <code>tray</code> table; recent journeys from{' '}
          <code>journey</code>.
        </p>
      </header>

      {error && (
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="text-destructive">Projector store unreachable</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              The routing service couldn&apos;t reach the projector&apos;s Postgres. Verify the{' '}
              <code>projector</code> container is up (or <code>make dev-up</code>), then refresh.
            </p>
          </CardContent>
        </Card>
      )}

      <section className="mb-8">
        <Card>
          <CardHeader>
            <CardTitle>Trays, most recently updated</CardTitle>
            <CardDescription>
              {trays === null ? 'loading...' : `${trays.length} trays`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {trays === null ? (
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <Spinner size="sm" /> Loading...
              </div>
            ) : trays.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No trays projected yet. POST an event through the ingest service or run{' '}
                <code>uv run synth-events publish --n 200</code>.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-xs uppercase text-muted-foreground">
                    <tr className="border-b border-border">
                      <th className="py-2 pr-4 text-left font-medium">Tray</th>
                      <th className="py-2 pr-4 text-left font-medium">Stage</th>
                      <th className="py-2 pr-4 text-left font-medium">Facility</th>
                      <th className="py-2 text-left font-medium">Last event</th>
                    </tr>
                  </thead>
                  <tbody className="tabular-nums">
                    {trays.map((tray) => (
                      <tr key={tray.tray_id} className="border-b border-border last:border-0">
                        <td className="py-2 pr-4 font-mono text-xs">{tray.tray_id}</td>
                        <td className="py-2 pr-4">{tray.current_stage}</td>
                        <td className="py-2 pr-4">
                          <Badge variant={badgeVariantFor(tray.current_facility_id)}>
                            {tray.current_facility_id}
                          </Badge>
                        </td>
                        <td className="py-2 text-muted-foreground">
                          {formatTs(tray.last_event_ts)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      <section>
        <Card>
          <CardHeader>
            <CardTitle>Recent finalized journeys</CardTitle>
            <CardDescription>
              {journeys === null
                ? 'loading...'
                : `${journeys.length} journeys, ${journeys.filter((j) => j.on_time).length} on-time`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {journeys === null ? (
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <Spinner size="sm" /> Loading...
              </div>
            ) : journeys.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No finalized journeys yet. Each journey lands when its DELIVERED event arrives.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-xs uppercase text-muted-foreground">
                    <tr className="border-b border-border">
                      <th className="py-2 pr-4 text-left font-medium">Tray</th>
                      <th className="py-2 pr-4 text-left font-medium">Client</th>
                      <th className="py-2 pr-4 text-left font-medium">Facility</th>
                      <th className="py-2 pr-4 text-left font-medium">Type</th>
                      <th className="py-2 pr-4 text-right font-medium">Total time</th>
                      <th className="py-2 pr-4 text-right font-medium">Delay</th>
                      <th className="py-2 text-left font-medium">On-time</th>
                    </tr>
                  </thead>
                  <tbody className="tabular-nums">
                    {journeys.map((journey) => {
                      const total =
                        journey.decon_dwell_min +
                        journey.inspection_dwell_min +
                        journey.assembly_dwell_min +
                        journey.sterilization_dwell_min +
                        journey.packout_dwell_min +
                        journey.transport_min
                      return (
                        <tr
                          key={journey.journey_id}
                          className="border-b border-border last:border-0"
                        >
                          <td className="py-2 pr-4 font-mono text-xs">{journey.tray_id}</td>
                          <td className="py-2 pr-4">{journey.client_id}</td>
                          <td className="py-2 pr-4">
                            <Badge variant={badgeVariantFor(journey.facility_id)}>
                              {journey.facility_id}
                            </Badge>
                          </td>
                          <td className="py-2 pr-4 text-xs text-muted-foreground">
                            {journey.tray_type_id}
                          </td>
                          <td className="py-2 pr-4 text-right">{formatMinutes(total)}</td>
                          <td
                            className={
                              'py-2 pr-4 text-right ' +
                              (journey.on_time ? 'text-muted-foreground' : 'text-destructive')
                            }
                          >
                            {journey.delay_min >= 0 ? '+' : ''}
                            {formatNumber(journey.delay_min, 0)}m
                          </td>
                          <td className="py-2">
                            {journey.on_time ? (
                              <Badge variant="default">on-time</Badge>
                            ) : (
                              <Badge
                                variant="default"
                                className="bg-destructive text-destructive-foreground"
                              >
                                late
                              </Badge>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  )
}
