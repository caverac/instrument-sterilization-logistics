import { useEffect, useState } from 'react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Spinner } from '@/components/ui/spinner'
import { getModelSummary } from '@/lib/api'
import type { ModelSummaryResponse, ParameterSummary } from '@/lib/types'
import { formatNumber } from '@/lib/utils'

interface Section {
  title: string
  description: string
  params: ParameterSummary[]
}

const groupParameters = (params: ParameterSummary[]): Section[] => {
  const global = params.filter((p) => !p.name.includes('['))
  const alpha = params.filter((p) => p.name.startsWith('alpha['))
  const sigmaFacility = params.filter((p) => p.name.startsWith('sigma_facility['))
  const beta = params.filter((p) => p.name.startsWith('beta['))

  return [
    {
      title: 'Global',
      description:
        'Baseline log-mean, peak-hour shift, and transport-time parameters. mu_global sets the journey log-mean before facility / tray effects.',
      params: global
    },
    {
      title: 'Per-facility (alpha, sigma)',
      description:
        'Log-mean offset and observation sigma per facility. The tail of the on-time distribution is set by sigma_facility -- this is the variance the model exploits.',
      params: [...alpha, ...sigmaFacility]
    },
    {
      title: 'Per-tray-type (beta)',
      description:
        'Multiplicative complexity offset per tray type in log-space. Larger beta means the tray runs slower on average.',
      params: beta
    }
  ]
}

function ParameterTable({ params }: { params: ParameterSummary[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-xs uppercase text-muted-foreground">
          <tr className="border-b border-border">
            <th className="py-2 pr-4 text-left font-medium">Parameter</th>
            <th className="py-2 pr-4 text-right font-medium">Mean</th>
            <th className="py-2 pr-4 text-right font-medium">SD</th>
            <th className="py-2 text-right font-medium">90% CI</th>
          </tr>
        </thead>
        <tbody className="tabular-nums">
          {params.map((p) => (
            <tr key={p.name} className="border-b border-border last:border-0">
              <td className="py-2 pr-4 font-mono text-xs">{p.name}</td>
              <td className="py-2 pr-4 text-right">{formatNumber(p.mean, 3)}</td>
              <td className="py-2 pr-4 text-right text-muted-foreground">
                {formatNumber(p.sd, 3)}
              </td>
              <td className="py-2 text-right text-muted-foreground">
                [{formatNumber(p.p5, 3)}, {formatNumber(p.p95, 3)}]
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Model() {
  const [data, setData] = useState<ModelSummaryResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getModelSummary()
      .then((response) => {
        if (!cancelled) setData(response)
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="p-8">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold">Model</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {data === null
            ? 'Per-parameter posterior summaries for the loaded hierarchical model. Mean, SD, and 90% central credible interval (5th-95th percentile).'
            : `Posterior over ${formatNumber(data.n_samples, 0)} samples across the model's parameters. SD is the posterior SD (uncertainty in the parameter value); the 90% CI is the 5th-95th posterior percentile.`}
        </p>
      </header>

      {error && (
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="text-destructive">Model summary unreachable</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              The routing service couldn&apos;t serve <code>/model/summary</code>. Restart{' '}
              <code>uvicorn routing.app:create_app</code> and reload.
            </p>
          </CardContent>
        </Card>
      )}

      {!data && !error && (
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <Spinner size="sm" /> Loading posterior summary...
        </div>
      )}

      {data && (
        <div className="space-y-8">
          {groupParameters(data.parameters).map((section) => (
            <Card key={section.title}>
              <CardHeader>
                <CardTitle>{section.title}</CardTitle>
                <CardDescription>{section.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <ParameterTable params={section.params} />
              </CardContent>
            </Card>
          ))}

          <Card>
            <CardHeader>
              <CardTitle>What&apos;s not shown</CardTitle>
              <CardDescription>Diagnostics that need the original chain structure.</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                R-hat, effective sample size, and trace plots aren&apos;t available from this
                endpoint -- the routing service loads the flattened (chains x draws) posterior, so
                the chain structure is gone by the time we get here. To inspect convergence rerun{' '}
                <code>uv run routing fit</code> and check the NUTS warnings during sampling.
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
