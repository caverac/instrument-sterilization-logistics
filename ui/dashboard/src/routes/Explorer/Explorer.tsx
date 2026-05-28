import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { FacilitySummary } from '@/lib/types'
import { formatMinutes, formatNumber, formatPercent } from '@/lib/utils'

// Placeholder data lifted from the synth-events distribution design.
// Replaced with live model output once the routing service lands (M2).
const FACILITIES: FacilitySummary[] = [
  {
    id: 'BOCA',
    name: 'Boca Raton',
    meanCompletionMin: 155,
    stdCompletionMin: 60,
    onTimeRate: 0.53,
    profile: 'Newest -- fast on average but unpredictable.'
  },
  {
    id: 'LGB',
    name: 'Long Beach',
    meanCompletionMin: 165,
    stdCompletionMin: 54,
    onTimeRate: 0.47,
    profile: 'Mature operation, consistent dwell times.'
  },
  {
    id: 'ELM',
    name: 'Elmhurst',
    meanCompletionMin: 185,
    stdCompletionMin: 51,
    onTimeRate: 0.36,
    profile: 'Constrained but very steady.'
  }
]

const badgeVariantFor = (id: FacilitySummary['id']) =>
  id === 'BOCA' ? 'boca' : id === 'LGB' ? 'lgb' : 'elm'

export function Explorer() {
  return (
    <div className="p-8">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold">Routing policy explorer</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Pick a deadline, a tray type, and a time of day -- compare the routing decision each
          policy would make. The variance-aware policy looks at the full completion-time
          distribution per facility; the mean-only baseline only looks at the average.
        </p>
      </header>

      <section className="grid grid-cols-1 gap-6 md:grid-cols-3">
        {FACILITIES.map((facility) => (
          <Card key={facility.id}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>{facility.name}</CardTitle>
                <Badge variant={badgeVariantFor(facility.id)}>{facility.id}</Badge>
              </div>
              <CardDescription>{facility.profile}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Stat label="Mean completion" value={formatMinutes(facility.meanCompletionMin)} />
              <Stat label="Std dev" value={`${formatNumber(facility.stdCompletionMin, 0)} min`} />
              <Stat label="On-time rate" value={formatPercent(facility.onTimeRate, 1)} />
            </CardContent>
          </Card>
        ))}
      </section>

      <section className="mt-8">
        <Card>
          <CardHeader>
            <CardTitle>Controls</CardTitle>
            <CardDescription>
              Wired up once the routing model is fit on synth-events data. See the{' '}
              <a className="underline" href="/model">
                Model tab
              </a>{' '}
              for the latest fit.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Sliders, distribution overlays, and Monte Carlo simulation land here.
            </p>
          </CardContent>
        </Card>
      </section>
    </div>
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
