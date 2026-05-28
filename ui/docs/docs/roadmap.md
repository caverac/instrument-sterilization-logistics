---
sidebar_position: 90
title: Roadmap
---

# Roadmap

What's built, what's next, and what we are deliberately **not** building until a specific trigger fires. Every component built before its trigger is operational tax forever -- so the discipline here is to keep the "not building yet" column long and explicit.

## Built today

What works end-to-end right now:

- **Redpanda** running via `docker compose up`; topic `events` (6 partitions, snappy compression, 7-day retention) created on first boot.
- **`services/ingest`** -- FastAPI service: `POST /events` validates with Pydantic (`extra="forbid"`), derives a deterministic UUIDv5 `event_id` from `(source_system, source_event_id)`, publishes to Kafka in Confluent JSON-Schema wire format. Schema registers under `events-value` on first publish. 100% test coverage, integration tests against the real broker.
- **`services/synth-events`** -- CLI + library that generates synthetic `journey` parquet rows shaped like the future `projector` output. Three facilities with deliberately different `(mean, variance)` profiles so variance-aware routing has something to find. Fully reproducible from a seed.
- **`services/routing`** -- the hierarchical Bayesian model (PyMC NUTS, partial pooling across facilities and tray types) + three policies (`variance-aware`, `mean-only`, `proximity`) + a backtest harness with paired-bootstrap lift CIs + a FastAPI service exposing `POST /decide`. The service also exposes `GET /backtest/summary` (head-to-head policy comparison, cached at startup), `GET /model/summary` (per-parameter posterior summaries, cached at startup), and read-only `GET /operations/tray-states` / `GET /operations/recent-journeys` that pass through to the projector's Postgres tables. CLI `routing fit` and `routing backtest` work standalone.
- **`services/projector`** -- Kafka consumer subscribed to `events`. Maintains `tray` (current state), `journey_open` (intermediate per-cycle state), and `journey` (finalized rows mirroring synth-events parquet). Postgres schema initialised idempotently at startup; commits Kafka offsets only after Postgres writes succeed. See [Projector](services/projector).
- **`synth-events publish`** -- CLI subcommand that POSTs N synthetic journeys (10 events each) through ingest, so the projector + dashboard have realistic data to work against before any real client onboards.
- **Postgres** -- in `docker-compose.yml` as the projector's projection store.
- **`ui/dashboard`** -- Vite + React 19 + Tailwind 4. **Explorer**, **Operations**, **Backtest**, and **Model** tabs are live (Operations renders the projector's `tray` and `journey` tables; Backtest renders the cached head-to-head policy comparison; Model renders per-parameter posterior summaries grouped by global / per-facility / per-tray-type). Calibration is the last placeholder (see [Dashboard](dashboard)).
- **`ui/docs`** -- this Docusaurus site, deployed to GitHub Pages via the release workflow.

## Next up

The immediate priorities, in rough order. None of these are blocked by external triggers -- they are the things that turn the existing pieces into a continuously-running pipeline.

1. **Last routing-service endpoint to unblock the dashboard.** `GET /calibration/reliability` for the Calibration tab -- read journey rows from Postgres, score each through the posterior, bin predicted P(on-time) vs observed on-time rate.
2. **Switch the routing fit pipeline's input from synth-events parquet to projector Postgres.** Once enough real journey volume accumulates, `routing fit` reads from the `journey` table instead of `--in journeys.parquet`. The bridge is in place; the model just needs the SQL loader.
3. **Kafka Connect S3 sink + MinIO in `docker-compose.yml`.** Day-partitioned object writes of the raw event log. Long-term immutable archive; backfill source for new consumers.
4. **Connection pool on `/operations/*`.** Today the routing service opens a fresh psycopg connection per request -- fine for polling traffic, replace with `psycopg.ConnectionPool` once the dashboard has multiple concurrent users.

## Not building yet, with triggers

Each row is a thing the design contemplated but we have not built. The trigger is the **specific external event** that flips the decision from "no" to "yes." Keep an eye on this column when client / scale conversations happen.

| Not building                                          | Triggered by                                                                                                                                |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Second facility adapter                               | Onboarding a real second facility (or a pilot client who serves two facilities). Until then, three synthetic facilities cover the modeling. |
| Dispatch console (operational UI, separate from this) | A real client routing real pickups. The current dashboard is a model-exploration surface, not an ops surface.                               |
| HL7 v2 SIU ingest via Mirth                           | A pilot hospital that needs OR-schedule capture. This work is dominated by per-client integration, not framework code.                      |
| `case_schedule` / `case_result` event types           | HL7 ingest landing -- they're the event types the SIU + ORU adapters publish.                                                               |
| Preference-card-learner consumer                      | `case_result` events flowing for `>=` a few months at one client. No earlier; the model needs observed-vs-declared data.                    |
| Bottleneck attribution on dispatch console            | Dispatch console exists, and the `projector` is producing journey rows. Both are dependencies, not the trigger itself.                      |
| Calibration tab wired                                 | Real `journey` rows from the projector. Synth-events is calibrated by construction, so reliability plots are uninteresting.                 |
| Demand forecast feeding routing                       | `case_schedule` events accumulating for `>=` 6 months at one client.                                                                        |
| OAuth2 / API keys on ingest                           | First external facility adapter outside our trust boundary.                                                                                 |
| Batch endpoint (`POST /events/bulk`)                  | A vendor adapter that emits `>= 100 events/sec` sustained.                                                                                  |
| Direct scanner / RFID ingest                          | A pilot facility without an incumbent SPD system.                                                                                           |
| Autoclave PLC streaming (OPC-UA)                      | A regulator or client requiring raw cycle telemetry rather than the facility's signed cycle record.                                         |
| Avro or Protobuf encoding                             | A polyglot consumer (Go, Rust, ...) needing strict binary contracts. JSON Schema is good enough for now.                                    |
| Multiple topics / per-event-type topics               | A consumer that needs to subscribe to only one event type at high volume.                                                                   |
| Managed Kafka (Redpanda Cloud, MSK, Confluent)        | Multi-tenant or multi-cluster needs, or we want out of broker ops.                                                                          |
| Snowflake / Iceberg                                   | Client BYO-warehouse demand, or PG analytical queries can't keep up.                                                                        |
| TimescaleDB                                           | `station_metrics_1min` exceeds 100M rows, or sub-second windowed queries that PG can't deliver.                                             |
| Flink                                                 | A stateful streaming windowed join we can't express as a Kafka consumer.                                                                    |
| Driver app, floor tablet                              | A client requires it and the incumbent system can't supply the data.                                                                        |
| ML add-on / cancellation model                        | `>= 6 months` of `case_schedule` + `case_result` data, plus a client willing to pay for the lift.                                           |
| Individual-instrument UDI tracking                    | A client mandates it, or a regulator does.                                                                                                  |
| FHIR adapter                                          | A pilot client speaks FHIR natively.                                                                                                        |

## What changes about each service over time

### `ingest`

| When                         | Change                                                       | Reason                                                                       |
| ---------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| First polyglot consumer      | Add Avro or Protobuf encoding alongside JSON Schema          | JSON Schema is loose for non-Python consumers                                |
| Multi-tenant / multi-cluster | Promote to a managed broker (Redpanda Cloud, MSK, Confluent) | Self-hosted Redpanda is fine to a few hundred topics; beyond, pay to own it  |
| First adversarial caller     | Add OAuth2 client credentials                                | Today assumes adapters are inside our trust boundary                         |
| Event volume `> 50k/sec`     | Add multiple ingest replicas behind a load balancer          | Single-instance Python can push ~5k/sec sustained; horizontally scale beyond |

### `routing`

| When                                        | Change                                                                                          | Reason                                                                                          |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Dashboard wiring for the Calibration tab    | Add `GET /calibration/reliability`                                                              | The endpoint doesn't exist yet; the tab is stubbed until it does                                |
| Sustained dashboard load on `/operations/*` | Replace per-request `psycopg.connect` with a `psycopg.ConnectionPool`                           | Per-request is fine for one-user polling; pool kicks in once concurrent users matter            |
| Real journey rows accumulate in `journey`   | Switch the fit pipeline's input from `journeys.parquet` to a Postgres query                     | Synth-events stays around for backtests against fixed distributions                             |
| First production deploy                     | Add a `routing-recalibrator` job that re-fits nightly on rolling-window data from the projector | Fitting at request time is too slow for a hot path; the model needs to track drift continuously |

### `projector`

| When                                       | Change                                                                      | Reason                                                                                                |
| ------------------------------------------ | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Throughput exceeds a single replica        | Run multiple replicas in the `projector` consumer group                     | Up to 6 (the partition count of `events`); per-tray ordering preserved by the `tray_id` partition key |
| Long-term operational state matters        | Graduate from `CREATE TABLE IF NOT EXISTS` at startup to Alembic migrations | The current setup assumes any schema change is paired with a wipe-and-replay; live data changes that  |
| Per-stage analytics become a routine query | Add covering indexes / a materialised view over `journey`                   | Today the `(facility_id, pickup_ts)` and `(tray_id)` indexes are enough for the dashboard             |

### `synth-events`

| When                                  | Change                                                             | Reason                                                                                |
| ------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------- |
| Real journey rows from the projector  | Demote `generate` to a backtest-only fixture; not the training set | Real data carries patterns we can't fully encode in the synthetic distribution        |
| Real per-tray-type complexity data    | Replace the hardcoded complexity multipliers with fits             | The synthetic multipliers are guesses; client data will give us empirical multipliers |
| First client adapter publishes events | Demote `publish` from primary backfill to a backtest-data fixture  | Once real events flow, the demo doesn't need synth-published ones                     |
