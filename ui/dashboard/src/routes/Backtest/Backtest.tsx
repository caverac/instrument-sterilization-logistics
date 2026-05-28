import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function Backtest() {
  return (
    <div className="p-8">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold">Backtest</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Replay historical pickups through each routing policy and compare on-time rates, mean
          delay, and p95 delay. Bootstrap confidence intervals on the lift.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Needs a routing-service endpoint</CardTitle>
          <CardDescription>
            The backtest itself runs today via the CLI: <code>uv run routing backtest</code> prints
            per-policy on-time rates, mean delay, p95 delay, and bootstrap-CI lifts. This tab wires
            up once the routing service exposes <code>GET /backtest/summary</code>.
          </CardDescription>
        </CardHeader>
      </Card>
    </div>
  )
}
