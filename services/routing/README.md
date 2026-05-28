# services/routing

Hierarchical Bayesian routing model + three routing policies + simulation harness.

Trained on journey parquet (typically produced by `services/synth-events`). The hierarchical structure is a log-normal observation model on total processing time with per-facility mean offsets (partial pooling), per-facility observation sigmas, tray-type fixed effects, and a peak-hour shift.

## What it produces

- A posterior over `(facility_mean, facility_sigma, tray_effects, peak_effect)` -- saved as numpy `.npz` for downstream use
- Three policies that consume the posterior to make routing decisions:
  - `variance-aware`: argmax P(complete + transport `<=` deadline)
  - `mean-only`: argmin expected completion time (the naive baseline)
  - `proximity`: a hardcoded client-to-facility distance map
- A simulation harness that scores all three policies against a held-out data generator and reports the lift in on-time rate with bootstrap confidence intervals

## Usage

```bash
# Fit a model on synth-events output (writes posterior to model.npz)
uv run routing fit --in journeys.parquet --out model.npz --seed 42

# Backtest the three policies against fresh synth-events pickups
uv run routing backtest --model model.npz --n 5000 --seed 100
```

Output of `backtest` is a comparison table:

```
policy           on-time-rate  mean-delay  p95-delay
variance-aware   0.612         -8.4 min    52.1 min
mean-only        0.487          3.2 min    71.8 min
proximity        0.458          7.5 min    79.4 min

lift vs proximity:  +15.4 pp (bootstrap 95% CI: 12.1 -- 18.8)
lift vs mean-only:  +12.5 pp (bootstrap 95% CI:  9.6 -- 15.5)
```

## Testing

```bash
cd services/routing && uv run python -m pytest tests/ -v
```

100% coverage enforced. NUTS sampling is exercised with small chain counts so tests stay fast.
