import { useEffect, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Spinner } from '@/components/ui/spinner'
import { decide } from '@/lib/api'
import {
  CLIENT_OPTIONS,
  type DecideResponse,
  type FacilityCell,
  type PolicyDecision,
  TRAY_TYPES
} from '@/lib/types'
import { formatMinutes, formatNumber, formatPercent } from '@/lib/utils'

const POLICY_LABELS: Record<string, string> = {
  'variance-aware': 'Variance-aware',
  'mean-only': 'Mean-only',
  proximity: 'Proximity'
}

const badgeVariantFor = (id: string): 'boca' | 'lgb' | 'elm' | 'default' =>
  id === 'BOCA' ? 'boca' : id === 'LGB' ? 'lgb' : id === 'ELM' ? 'elm' : 'default'

export function Explorer() {
  const [trayTypeId, setTrayTypeId] = useState<string>(TRAY_TYPES[1].id)
  const [hour, setHour] = useState<number>(10)
  const [deadline, setDeadline] = useState<number>(220)
  const [clientId, setClientId] = useState<string>(CLIENT_OPTIONS[0].id)
  const [data, setData] = useState<DecideResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState<boolean>(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    decide({
      tray_type_id: trayTypeId,
      hour_of_pickup: hour,
      deadline_min: deadline,
      client_id: clientId
    })
      .then((response) => {
        if (!cancelled) setData(response)
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [trayTypeId, hour, deadline, clientId])

  return (
    <div className="p-8">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold">Routing policy explorer</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Set the pickup parameters below and watch the three routing policies make their decisions.
          Variance-aware uses the full completion-time distribution; mean-only just looks at the
          average; proximity uses a fixed client-to-facility map.
        </p>
      </header>

      <section className="mb-8">
        <Card>
          <CardHeader>
            <CardTitle>Pickup parameters</CardTitle>
            <CardDescription>
              Posterior loaded from the routing service. Sliders below requery on every change.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-2 text-sm">
              <span className="font-medium text-muted-foreground">Tray type</span>
              <select
                className="rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={trayTypeId}
                onChange={(e) => setTrayTypeId(e.target.value)}
              >
                {TRAY_TYPES.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-2 text-sm">
              <span className="font-medium text-muted-foreground">Client</span>
              <select
                className="rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
              >
                {CLIENT_OPTIONS.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-2 text-sm">
              <span className="font-medium text-muted-foreground">
                Hour of pickup:{' '}
                <span className="text-foreground">{hour.toString().padStart(2, '0')}:00</span>
              </span>
              <input
                type="range"
                min={0}
                max={23}
                value={hour}
                onChange={(e) => setHour(parseInt(e.target.value, 10))}
                className="accent-primary"
              />
            </label>

            <label className="flex flex-col gap-2 text-sm">
              <span className="font-medium text-muted-foreground">
                Deadline: <span className="text-foreground">{formatMinutes(deadline)}</span>
              </span>
              <input
                type="range"
                min={120}
                max={360}
                step={5}
                value={deadline}
                onChange={(e) => setDeadline(parseInt(e.target.value, 10))}
                className="accent-primary"
              />
            </label>
          </CardContent>
        </Card>
      </section>

      {error && (
        <section className="mb-8">
          <Card>
            <CardHeader>
              <CardTitle className="text-destructive">Routing API unreachable</CardTitle>
              <CardDescription>{error}</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Start the routing service:{' '}
                <code>uv run uvicorn routing.app:create_app --factory --port 8091</code>. You'll
                need a fitted model.npz; see <code>routing fit</code>.
              </p>
            </CardContent>
          </Card>
        </section>
      )}

      {loading && !data && (
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <Spinner size="sm" /> Sampling posterior...
        </div>
      )}

      {data && (
        <>
          <section className="grid grid-cols-1 gap-6 md:grid-cols-3">
            {data.facilities.map((f) => (
              <FacilityCard key={f.facility_id} facility={f} />
            ))}
          </section>

          <section className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-3">
            {data.policies.map((p) => (
              <PolicyCard key={p.policy_id} policy={p} />
            ))}
          </section>
        </>
      )}
    </div>
  )
}

function FacilityCard({ facility }: { facility: FacilityCell }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>{facility.name}</CardTitle>
          <Badge variant={badgeVariantFor(facility.facility_id)}>{facility.facility_id}</Badge>
        </div>
        <CardDescription>{facility.profile}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Stat label="Expected completion" value={formatMinutes(facility.expected_completion_min)} />
        <Stat label="P(on-time)" value={formatPercent(facility.p_on_time, 1)} />
      </CardContent>
    </Card>
  )
}

function PolicyCard({ policy }: { policy: PolicyDecision }) {
  const label = POLICY_LABELS[policy.policy_id] ?? policy.policy_id
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{label}</CardTitle>
        <CardDescription>
          Picks <Badge variant={badgeVariantFor(policy.facility_id)}>{policy.facility_id}</Badge>
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-1 text-xs">
        {Object.entries(policy.candidate_scores).map(([facilityId, score]) => (
          <div key={facilityId} className="flex justify-between tabular-nums">
            <span className="text-muted-foreground">{facilityId}</span>
            <span>{formatPolicyScore(policy.score_metric, score)}</span>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium tabular-nums">{value}</span>
    </div>
  )
}

function formatPolicyScore(metric: string | null, score: number): string {
  if (metric === 'p_on_time') return formatPercent(score, 1)
  if (metric === 'expected_completion_min') return formatMinutes(score)
  return formatNumber(score, 0)
}
