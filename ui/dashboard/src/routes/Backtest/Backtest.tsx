import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

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
          <CardTitle>Coming with the routing model (M2)</CardTitle>
          <CardDescription>
            Implementation lands once the hierarchical model is fit and the replay harness exists.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            See the Roadmap in the docs site for the full milestone breakdown.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
