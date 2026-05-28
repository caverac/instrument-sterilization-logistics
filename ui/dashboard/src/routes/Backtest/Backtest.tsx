import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Spinner } from '@/components/ui/spinner'
import { getBacktestSummary } from '@/lib/api'
import type { BacktestSummaryResponse, PolicyId } from '@/lib/types'
import { formatNumber, formatPercent } from '@/lib/utils'

const POLICY_LABEL: Record<PolicyId, string> = {
  'variance-aware': 'Variance-aware',
  'mean-only': 'Mean-only',
  proximity: 'Proximity'
}

const POLICY_COLOR: Record<PolicyId, string> = {
  'variance-aware': 'var(--color-primary)',
  'mean-only': 'var(--color-muted-foreground)',
  proximity: 'var(--color-muted-foreground)'
}

export function Backtest() {
  const [data, setData] = useState<BacktestSummaryResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getBacktestSummary()
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
        <h1 className="text-2xl font-semibold">Backtest</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {data === null
            ? 'Replays simulated pickups through each routing policy and reports the head-to-head lift with bootstrap confidence intervals. Result cached at routing-service startup; deterministic given posterior, seed, and N.'
            : `Replay over ${formatNumber(data.n, 0)} simulated pickups against synth-events' true distribution. Bootstrap CIs use 1000 paired resamples.`}
        </p>
      </header>

      {error && (
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="text-destructive">Backtest endpoint unreachable</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              The routing service couldn&apos;t serve <code>/backtest/summary</code>. Restart{' '}
              <code>uvicorn routing.app:create_app</code> and reload.
            </p>
          </CardContent>
        </Card>
      )}

      {!data && !error && (
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <Spinner size="sm" /> Loading backtest...
        </div>
      )}

      {data && (
        <>
          <section className="mb-8">
            <Card>
              <CardHeader>
                <CardTitle>On-time rate per policy</CardTitle>
                <CardDescription>
                  Higher is better. The point of the model is to beat the operational baseline
                  (proximity) by a defensible margin.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={data.per_policy.map((p) => ({
                        policy: POLICY_LABEL[p.policy_id],
                        rate: p.on_time_rate * 100,
                        id: p.policy_id
                      }))}
                      margin={{ top: 16, right: 16, bottom: 16, left: 16 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                      <XAxis dataKey="policy" stroke="var(--color-muted-foreground)" />
                      <YAxis
                        domain={[0, 100]}
                        tickFormatter={(v: number) => `${v.toFixed(0)}%`}
                        stroke="var(--color-muted-foreground)"
                      />
                      <Tooltip
                        formatter={(v: number) => [`${v.toFixed(1)}%`, 'On-time']}
                        cursor={{ fill: 'var(--color-muted)', opacity: 0.3 }}
                        contentStyle={{
                          backgroundColor: 'var(--color-card)',
                          border: '1px solid var(--color-border)',
                          borderRadius: '0.375rem',
                          color: 'var(--color-foreground)'
                        }}
                        labelStyle={{ color: 'var(--color-foreground)', fontWeight: 500 }}
                        itemStyle={{ color: 'var(--color-foreground)' }}
                      />
                      <Bar dataKey="rate">
                        {data.per_policy.map((p) => (
                          <Cell key={p.policy_id} fill={POLICY_COLOR[p.policy_id]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </section>

          <section className="mb-8">
            <Card>
              <CardHeader>
                <CardTitle>Per-policy aggregates</CardTitle>
                <CardDescription>
                  On-time rate, mean signed delay, and the 95th percentile delay (a tail-risk
                  proxy).
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-xs uppercase text-muted-foreground">
                      <tr className="border-b border-border">
                        <th className="py-2 pr-4 text-left font-medium">Policy</th>
                        <th className="py-2 pr-4 text-right font-medium">On-time rate</th>
                        <th className="py-2 pr-4 text-right font-medium">Mean delay (min)</th>
                        <th className="py-2 text-right font-medium">p95 delay (min)</th>
                      </tr>
                    </thead>
                    <tbody className="tabular-nums">
                      {data.per_policy.map((p) => (
                        <tr key={p.policy_id} className="border-b border-border last:border-0">
                          <td className="py-2 pr-4">{POLICY_LABEL[p.policy_id]}</td>
                          <td className="py-2 pr-4 text-right">
                            {formatPercent(p.on_time_rate, 1)}
                          </td>
                          <td className="py-2 pr-4 text-right">
                            {formatNumber(p.mean_delay_min, 1)}
                          </td>
                          <td className="py-2 text-right">{formatNumber(p.p95_delay_min, 1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </section>

          <section>
            <Card>
              <CardHeader>
                <CardTitle>Lift over baselines</CardTitle>
                <CardDescription>
                  Variance-aware vs each baseline, in on-time-rate percentage points. 95% CI from
                  1000 paired bootstrap resamples. A CI that excludes zero is the &quot;the model
                  helps&quot; signal.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-xs uppercase text-muted-foreground">
                      <tr className="border-b border-border">
                        <th className="py-2 pr-4 text-left font-medium">Comparison</th>
                        <th className="py-2 pr-4 text-right font-medium">Lift (pp)</th>
                        <th className="py-2 text-right font-medium">95% CI</th>
                      </tr>
                    </thead>
                    <tbody className="tabular-nums">
                      {data.lifts.map((lift) => {
                        const significant = lift.ci_95_lo_pp > 0 || lift.ci_95_hi_pp < 0
                        return (
                          <tr
                            key={`${lift.policy_id}-vs-${lift.vs}`}
                            className="border-b border-border last:border-0"
                          >
                            <td className="py-2 pr-4">
                              {POLICY_LABEL[lift.policy_id]} vs {POLICY_LABEL[lift.vs]}
                            </td>
                            <td className="py-2 pr-4 text-right">
                              {lift.point_pp >= 0 ? '+' : ''}
                              {formatNumber(lift.point_pp, 1)}
                            </td>
                            <td className="py-2 text-right">
                              [{formatNumber(lift.ci_95_lo_pp, 1)},{' '}
                              {formatNumber(lift.ci_95_hi_pp, 1)}]
                              {significant && (
                                <Badge variant="default" className="ml-2 align-middle">
                                  significant
                                </Badge>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </section>
        </>
      )}
    </div>
  )
}
