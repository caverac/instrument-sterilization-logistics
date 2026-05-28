import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function Model() {
  return (
    <div className="p-8">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold">Model</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Posterior summary of the hierarchical log-normal dwell-time model: facility effects, stage
          sigmas, tray-type and hour-of-day coefficients. Posterior predictive checks and NUTS trace
          diagnostics live here.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>numpyro hierarchical fit</CardTitle>
          <CardDescription>
            Diagnostics surface once the first fit lands. R-hat, ESS per parameter, posterior
            predictive overlays.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Refit cadence: nightly. Rolling 90-day window with slow shrink toward all-time
            hyperparameters.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
