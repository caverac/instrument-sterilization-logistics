import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function Calibration() {
  return (
    <div className="p-8">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold">Calibration</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Predicted P(on-time) vs realized rate, decomposed by tray type, hour of day, and facility.
          The reliability diagram is the headline plot.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Reliability diagram and drift tracking</CardTitle>
          <CardDescription>
            Wired up after the first model fit. Drift alarms fire when the rolling window deviates
            from the diagonal by more than 5 percentage points.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Conformal-prediction wrapping is the recalibration path -- distribution-free,
            plug-and-play.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
