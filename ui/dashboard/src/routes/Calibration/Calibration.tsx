import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

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
          <CardTitle>Gates on real outcome data</CardTitle>
          <CardDescription>
            Calibration is uninformative against synth-events -- the data generator and the model
            agree by construction, so reliability is near-perfect by definition. This tab wires up
            once the <code>projector</code> consumer is producing real journey rows we can score the
            model against.
          </CardDescription>
        </CardHeader>
      </Card>
    </div>
  )
}
