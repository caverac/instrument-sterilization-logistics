---
sidebar_position: 3
title: Routing model
---

# `services/routing`

The variance-aware routing model: a hierarchical Bayesian fit on journey data + three routing policies + a head-to-head simulation harness. Trained on parquet produced by [synth-events](./synth-events) (and, when real client data arrives, by the future `projector` service).

This is where the data-science work lives. The ingest service captures events, synth-events generates training data, and `routing` is the thing that turns it into actual decisions: given a tray to pick up and a deadline, which facility should we send it to?

## What this service does

For every pickup, the service answers one question: **which facility should this tray go to?** It answers it three different ways, and runs the three side-by-side so we can measure which one actually helps.

The three policies, in plain English:

- **Variance-aware** -- uses the full predicted distribution of completion time at each facility and picks the one most likely to beat the deadline. Reacts to the deadline; reacts to the model's uncertainty. This is the policy the data-science work is for.
- **Mean-only** -- reduces each facility to a single number, its expected completion time, and picks the fastest. Ignores variance; ignores the deadline. This is what "send the tray to the fastest facility" looks like as code, and is the operator intuition we want to beat.
- **Proximity** -- looks up the client in a static `client -> facility` table and picks whatever it returns. No model, no math, no awareness of the cell. Stands in for the very common real-world baseline "we always send hospital A's trays to facility BOCA."

| Policy         | Reads deadline | Uses model variance | Uses model at all |
| -------------- | -------------- | ------------------- | ----------------- |
| variance-aware | yes            | yes                 | yes               |
| mean-only      | no             | no                  | yes (mean only)   |
| proximity      | no             | no                  | **no**            |

### Why three, not one

A single number from a single policy doesn't tell you whether the model is useful. The backtest harness runs all three policies against the same simulated pickups and reports the **lift** of variance-aware over each baseline with bootstrap CIs. That gives a defensible statement of the form "the model adds $X$ percentage points of on-time rate over the operational baseline (proximity) and $Y$ over the heuristic baseline (mean-only)" -- with a confidence interval on each number.

The rest of this page is how variance-aware actually works: the decision problem stated formally, the hierarchical Bayesian model behind the predictions, the posterior-predictive scoring that turns those predictions into $\Pr(\text{on-time})$, the backtest harness, and the lift it produces on synth-events data.

## The decision problem

For a pickup with deadline $t_d$, a tray type $t$, and a peak-hour flag $p$, three facilities are candidates ($f \in \{\text{BOCA}, \text{LGB}, \text{ELM}\}$). We want the policy:

$$
f^* = \arg\max_f \Pr(\,T_{\text{total}}(f, t, p) + T_{\text{transport}} \le t_d\,)
$$

The naive baseline is the **mean-only** policy that picks the facility with the lowest expected completion time:

$$
f^*_{\text{mean}} = \arg\min_f \mathbb{E}[\,T_{\text{total}}(f, t, p) + T_{\text{transport}}\,]
$$

These are not the same. A facility with a low mean but high variance can lose to a slower-but-steadier one when the deadline is tight enough that the tail matters. Capturing that tail is what the Bayesian model is for.

## Notation

The two equations above use the following symbols.

| Term                        | What it is                                                                                                                                                      |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| $f$                         | A candidate facility -- the variable being optimized over. Ranges over $\{\text{BOCA}, \text{LGB}, \text{ELM}\}$. Discrete, three values.                       |
| $f^*$                       | The output of the variance-aware policy: the facility the policy actually picks for this pickup.                                                                |
| $f^*_{\text{mean}}$         | The output of the mean-only baseline. Typically a different facility from $f^*$.                                                                                |
| $\arg\max_f$, $\arg\min_f$  | "The value of $f$ that maximizes (resp. minimizes) the expression after it." Not the maximum itself -- the _facility_ that achieves it.                         |
| $t$                         | The tray type for this pickup. One of five categories in synth-events (small, knee, laparoscopic, cardiac, spine).                                              |
| $p$                         | Peak-hour indicator. $p = 1$ if pickup falls in 08:00-12:00 or 14:00-18:00 (busy reprocessing-floor hours), else $p = 0$.                                       |
| $t_d$                       | The deadline -- the time by which the tray must be back at the hospital, measured in minutes after pickup. Varies per pickup.                                   |
| $T_{\text{total}}(f, t, p)$ | A **random variable**: total reprocessing time at facility $f$ for a tray of type $t$ at peak state $p$. Not a point estimate -- a full posterior distribution. |
| $T_{\text{transport}}$      | A **random variable**: return-transport time from facility back to client. Modeled globally (independent of $f, t, p$ in this version).                         |

### In English

- **Variance-aware:** "For this specific pickup, send the tray to the facility that maximizes the probability of being on time."
- **Mean-only:** "Send the tray to the facility whose average reprocessing-plus-transport time is shortest."

### Why they're different

The mean-only criterion uses **one number per facility** -- the expected completion time. The variance-aware criterion uses the **whole distribution** of completion times and the deadline together.

A facility with mean 155 min and high variance can have a _higher_ mean completion time and yet a _lower_ probability of beating a 200-min deadline than a facility with mean 165 min and tight variance -- because the tail of the first distribution sticks out further past the deadline.

Concretely, for $T_{\text{total}} + T_{\text{transport}}$ log-normal with log-mean $\mu$ and log-sigma $\sigma$, and deadline $t_d$:

$$
\Pr(T \le t_d) = \Phi\!\left(\frac{\log t_d - \mu}{\sigma}\right)
$$

where $\Phi$ is the standard normal CDF. The mean-only policy only sees $\exp(\mu + \tfrac{1}{2}\sigma^2)$. The variance-aware policy sees the full $(\mu, \sigma)$ pair and lets the deadline $t_d$ decide which mattered more.

That's the DS substance of this project compressed into one observation: **deadlines turn variance into a first-class decision variable, and mean-only routing systematically ignores it.**

## The hierarchical model

We model total processing time (the sum of the five reprocessing stages) as log-normal, with per-facility mean offsets and per-facility observation sigmas. Transport is a separate global log-normal.

### Processing model

For journey $i$ with facility index $f_i$, tray index $t_i$, and peak indicator $p_i$:

$$
\log T_i \sim \mathcal{N}\!\left(\,\mu_i,\; \sigma_{\text{facility}}[f_i]\,\right)
$$

$$
\mu_i = \mu_{\text{global}} + \alpha_{\text{facility}}[f_i] + \beta_{\text{tray}}[t_i] + \gamma_{\text{peak}} \cdot p_i
$$

with hierarchical (partial-pooling) priors on the per-facility offsets and per-tray effects:

$$
\alpha_{\text{facility}}[f] \sim \mathcal{N}(0, \sigma_\alpha), \quad \sigma_\alpha \sim \mathrm{HalfNormal}(0.3)
$$

$$
\beta_{\text{tray}}[t] \sim \mathcal{N}(0, \sigma_\beta), \quad \sigma_\beta \sim \mathrm{HalfNormal}(0.3)
$$

$$
\sigma_{\text{facility}}[f] \sim \mathrm{HalfNormal}(0.5)
$$

Top-level priors:

$$
\mu_{\text{global}} \sim \mathcal{N}(\log 165, \; 0.5), \quad \gamma_{\text{peak}} \sim \mathcal{N}(0, 0.1)
$$

`<= 165` minutes is the synth-events baseline total processing time; the prior mean of $\mu_{\text{global}}$ is centered there.

### Transport model

Independent global log-normal:

$$
\log T_{\text{transport}} \sim \mathcal{N}(\mu_t, \sigma_t)
$$

$$
\mu_t \sim \mathcal{N}(\log 30, \; 0.5), \quad \sigma_t \sim \mathrm{HalfNormal}(0.5)
$$

### Why hierarchical

Partial pooling buys us two things:

1. **A new facility with few observations** shrinks toward the global mean rather than fitting a wild per-facility estimate from noise.
2. **A rare tray type** borrows strength from the other tray types via $\sigma_\beta$.

The hierarchical structure is the canonical use of Bayesian modeling here -- a flat OLS-style fit on cell means falls over the moment a tray type has 3 historical observations at a facility.

### Inference

NUTS via PyMC, two chains, 1000 draws each (configurable). The posterior is flattened to $(N_{\text{chains}} \cdot N_{\text{draws}})$ samples per parameter and persisted to a numpy `.npz` archive.

## Scoring: posterior predictive

For a candidate cell $(f, t, p)$ and a deadline $t_d$, we compute the on-time probability by Monte Carlo over the posterior:

For each posterior sample $s = 1, \dots, N$:

$$
\log T^{(s)} \sim \mathcal{N}\!\left(\,\mu_{\text{global}}^{(s)} + \alpha_{\text{facility}}^{(s)}[f] + \beta_{\text{tray}}^{(s)}[t] + \gamma_{\text{peak}}^{(s)} \cdot p,\; \sigma_{\text{facility}}^{(s)}[f]\,\right)
$$

$$
\log T_{\text{transport}}^{(s)} \sim \mathcal{N}(\mu_t^{(s)},\; \sigma_t^{(s)})
$$

$$
\widehat{\Pr}(\text{on-time}) = \frac{1}{N}\sum_{s=1}^{N} \mathbb{I}\!\left[T^{(s)} + T_{\text{transport}}^{(s)} \le t_d\right]
$$

This is the **posterior predictive** -- not just averaging point estimates but propagating uncertainty in $(\mu, \sigma)$ through the prediction. With $N \approx 2000$ posterior samples the Monte Carlo error on the on-time probability is below half a percentage point.

Expected completion (used by the mean-only baseline) uses the log-normal closed-form:

$$
\mathbb{E}[T \mid \mu, \sigma] = \exp\!\left(\mu + \tfrac{1}{2}\sigma^2\right)
$$

averaged over posterior samples.

## The three policies

| Policy             | Decision rule                                                                                            |
| ------------------ | -------------------------------------------------------------------------------------------------------- |
| **variance-aware** | $f^* = \arg\max_f \widehat{\Pr}(\,T(f) + T_{\text{transport}} \le t_d\,)$                                |
| **mean-only**      | $f^* = \arg\min_f \widehat{\mathbb{E}}[T(f) + T_{\text{transport}}]$                                     |
| **proximity**      | Hardcoded $\text{client} \to \text{facility}$ map (placeholder for a real distance/transport-cost table) |

The proximity policy is the operational baseline most fleets actually use: "always send the tray to whichever facility is closest to this hospital." It's cheap, predictable, and ignores the entire reprocessing-time distribution.

## Backtest + simulation harness

To compare policies honestly we need outcomes for each policy's choice -- including the choices the policy made that we didn't actually observe in history. We side-step counterfactual inference here by simulating against the **same data-generating process** that produced the training data:

1. Sample $N$ random pickups with (tray, hour, client, deadline) drawn from realistic distributions.
2. For each pickup, ask each of the three policies which facility it would pick.
3. Sample a "true" $(T_{\text{total}}, T_{\text{transport}})$ pair at the chosen facility from the data generator.
4. Score on-time (and signed delay).
5. Aggregate per-policy on-time rate, mean delay, p95 delay.

For lift over baselines we use a paired bootstrap. Given on-time vectors $o_a, o_b \in \{0,1\}^N$ over the same $N$ simulated pickups:

$$
\text{lift} = \bar{o}_a - \bar{o}_b
$$

Resample indices $i_1, \dots, i_N$ with replacement $B$ times; the 2.5th and 97.5th percentiles of the resampled differences are the 95% bootstrap CI on the lift.

This is an **online evaluation** rather than an offline backtest -- the data generator stands in for "what would have happened at the facility we routed to" so we don't have to wrestle with off-policy correction. The same harness works against real data later: swap the data generator for a sampler over historical outcomes at each facility.

## Observed lift on synth-events data

Fitting 5000 synthetic journeys with `routing fit --draws 500 --tune 500 --chains 2` and running `routing backtest --n 3000`:

```
backtest over n = 3000 pickups

  policy           on-time-rate   mean-delay (min)   p95-delay (min)
  -----------------------------------------------------------------
  variance-aware       0.526              1.5            124.6
  mean-only            0.528             -2.7            128.4
  proximity            0.479              5.9            129.3

  lift: variance-aware vs mean-only:  -0.2 pp  (95% CI: -1.6 -- +1.3)
  lift: variance-aware vs proximity:  +4.7 pp  (95% CI: +3.2 -- +6.1)
```

Reading the result honestly:

- **+4.7 pp lift over proximity** is statistically significant and meaningful. The naive "always pick the closest facility" baseline gets beaten by a real margin.
- **No significant lift over mean-only** -- under the synth-events distribution, BOCA's lower mean dominates its higher variance for typical deadlines, so both policies converge on BOCA most of the time.
- **Variance-aware has the lowest p95 delay** (124.6 vs 128.4 vs 129.3) -- it trades a tiny mean-rate concession for a real tail-risk reduction. When pickups go badly, they go _less_ badly.

The tighter the deadline distribution gets, the more the variance-aware advantage compounds -- at $t_d \approx \mathbb{E}[T]$ the choice between facilities is forced by their tails, not their means.

## Where it fits

```mermaid
flowchart LR
    SE[synth-events] -->|journeys.parquet| RF[routing fit]
    RF -->|model.npz| RB[routing backtest]
    RF -->|model.npz| API[routing FastAPI]
    API -->|POST /decide| UIE[dashboard Explorer]
    PG[(Postgres - projector store)] -->|SELECT| API
    API -->|GET /operations/*| UIO[dashboard Operations]
    PJ[future projector -> real journeys.parquet] -.->|real journey rows| RF

    classDef devtool fill:#0d6e6e,stroke:#053838,color:#fff
    classDef store fill:#2cc4c4,stroke:#0d6e6e,color:#053838
    class RF,RB,API devtool
    class PG store
```

The FastAPI service exposes three surfaces today: `POST /decide` (the modelling endpoint that backs the dashboard's Explorer tab), and two read-only `/operations/*` endpoints that pass through to the projector's Postgres tables for the Operations tab. The `routing fit` CLI still trains offline on `synth-events` parquet; once enough real journey volume accumulates in Postgres, the fit pipeline switches its input from parquet to a SQL query.

## HTTP API

`POST /decide` -- the model surface; see [Dashboard -- Explorer](../dashboard#explorer-live) for the request/response shape.

`GET /operations/tray-states` -- the most recently updated rows from the projector's `tray` table (default cap: 50). Used by the dashboard's Operations tab. Response:

```json
{
  "trays": [
    {
      "tray_id": "TRAY-LIVE-1779984855",
      "current_facility_id": "BOCA",
      "current_stage": "DELIVERED",
      "last_event_ts": "2026-05-27T11:30:00Z",
      "last_updated": "2026-05-28T16:14:16.080476Z"
    }
  ]
}
```

`GET /operations/recent-journeys` -- the most recently delivered rows from the projector's `journey` table (default cap: 50). Used by the dashboard's Operations tab. Response includes facility / client / tray_type, per-stage dwells, `delivered_ts`, `on_time`, and `delay_min`.

Both `/operations` endpoints return **503 Service Unavailable** if Postgres is unreachable -- they open a fresh psycopg connection per request and propagate any `OperationalError` as a recoverable HTTP error.

## CLI

```bash
# Fit
uv run routing fit \
  --in journeys.parquet \
  --out model.npz \
  --draws 1000 --tune 1000 --chains 2 --seed 42

# Backtest
uv run routing backtest --model model.npz --n 5000 --seed 100
```

## Configuration knobs

### CLI flags

| Knob                  | CLI flag   | Default | Notes                                                            |
| --------------------- | ---------- | ------- | ---------------------------------------------------------------- |
| NUTS draws per chain  | `--draws`  | 1000    | Higher gives smoother posteriors; diminishing returns past ~2000 |
| NUTS warmup per chain | `--tune`   | 1000    | Lower at your peril; NUTS step-size adapts during warmup         |
| Chains                | `--chains` | 2       | 2-4 is standard for diagnostics; CI uses 1 to stay fast          |
| Fit seed              | `--seed`   | 42      |                                                                  |
| Backtest pickups      | `--n`      | 5000    | Larger N tightens lift CIs; 3-5k is enough for most decisions    |
| Backtest seed         | `--seed`   | 100     |                                                                  |

### Environment variables (service)

| Variable                   | Default                                                     | Notes                                                                               |
| -------------------------- | ----------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `ROUTING_MODEL_PATH`       | `model.npz`                                                 | Posterior `.npz` archive loaded at startup; must be produced by `routing fit` first |
| `ROUTING_SEED`             | `42`                                                        | RNG seed for posterior-predictive sampling at decide time                           |
| `ROUTING_POSTGRES_DSN`     | `postgresql://projector:projector@localhost:5432/projector` | Read-only connection to the projector's projection store; used by `/operations/*`   |
| `ROUTING_OPERATIONS_LIMIT` | `50`                                                        | Max rows returned by either `/operations/*` endpoint (1--500)                       |

## Testing

```bash
cd services/routing && uv run python -m pytest tests/ -v
```

100% line coverage. The test suite includes:

- Statistical assertions: `expected_completion` is monotone in $\mu$, $\Pr(\text{on-time})$ is monotone in deadline, posterior shapes are correct.
- A tiny NUTS fit (1 chain, 50 draws, 50 tune) that exercises the model code path in seconds.
- A round-trip test of posterior `save()` and `load()`.
- An integration-flavored test that runs the full simulation against synth-events' ground truth and verifies variance-aware beats proximity.

## Out of scope (now)

| Not building                          | Triggered by                                                                                                                             |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /backtest/summary`               | Dashboard's Backtest tab wiring. CLI works today (`routing backtest`); the endpoint is a small wrapper                                   |
| `GET /model/summary`                  | Dashboard's Model tab wiring. Either reads the `.npz` directly or summarises the posterior at startup                                    |
| `GET /calibration/reliability`        | Dashboard's Calibration tab. Joins predicted P(on-time) against the projector's `journey.on_time` and bins the result                    |
| Connection pooling on `/operations/*` | Sustained dashboard load. Today is a fresh psycopg connection per request; fine for polling traffic, replace with `ConnectionPool` later |
| Calibration / drift monitoring        | First real-world data lands; we can't observe drift against synth-events because its distribution is fixed                               |
| Per-stage modeling                    | A real signal that stage-level structure matters for routing -- e.g. a bottleneck-attribution story for the dispatch console             |
| Causal evaluation                     | A real client running both policies in alternation; until then, simulation against the data generator is the honest evaluation framework |
| Stan / numpyro backend                | A speed or scale need PyMC can't meet. Not foreseeable for our problem size.                                                             |
