---
sidebar_position: 4
title: Projector
---

# `services/projector`

The first real consumer of the `events` topic. It reads every event, upserts a current-state row in the `tray` table, and accumulates per-stage timestamps until a tray's pickup-to-delivery cycle is complete -- at which point it writes a finalized row to the `journey` table.

This is the bridge between the event spine and the modeling pipeline. With it in place, the [routing model](./routing) can fit on real ingested events rather than synth-events parquet.

## What it does, by event type

| Event                                                                   | `tray` projection                    | `journey_open` (intermediate)                                                | `journey` (finalized)                                 |
| ----------------------------------------------------------------------- | ------------------------------------ | ---------------------------------------------------------------------------- | ----------------------------------------------------- |
| `PICKED_UP`                                                             | upsert (current_stage = `PICKED_UP`) | open new row, pin `client_id`, `tray_type_id`, `required_by_ts` from payload | --                                                    |
| `CHECKED_IN`                                                            | upsert                               | --                                                                           | --                                                    |
| `DECON_START`                                                           | upsert                               | record timestamp, pin `facility_id`                                          | --                                                    |
| `DECON_END`, `INSPECTED`, `ASSEMBLED`, `STERILIZED`, `PACKED`, `LOADED` | upsert                               | record timestamp                                                             | --                                                    |
| `DELIVERED`                                                             | upsert                               | --                                                                           | insert finalized row, then delete from `journey_open` |
| `DEFECT_REPORTED`                                                       | upsert                               | --                                                                           | --                                                    |

Boundary cases are skipped silently rather than raised, so the consumer keeps making progress on the partition:

- **Malformed `PICKED_UP` payload** (missing `client_id` / `tray_type_id` / `required_by_ts`): tray is still updated, but no open journey starts.
- **Stage event for a tray with no open journey**: tray is updated, the stage timestamp is dropped.
- **`DELIVERED` for a tray with no open journey**: tray is updated, nothing else.
- **`DELIVERED` on an incomplete journey** (some intermediate stage timestamp is missing): the `journey_open` row is left in place. A separate cleanup process can deal with stale open journeys later.

## The schema

Three tables, all created on startup via idempotent `CREATE TABLE IF NOT EXISTS` (no Alembic for now).

### `tray`

```
tray_id              TEXT PRIMARY KEY
current_facility_id  TEXT NOT NULL
current_stage        TEXT NOT NULL
last_event_id        UUID NOT NULL
last_event_ts        TIMESTAMPTZ NOT NULL
last_updated         TIMESTAMPTZ NOT NULL DEFAULT NOW()
```

One row per tray. Last-write-wins by arrival order (Kafka per-partition ordering is preserved because events are partitioned on `tray_id`).

### `journey_open`

```
tray_id          TEXT PRIMARY KEY
pickup_event_id  UUID NOT NULL
client_id        TEXT NOT NULL
tray_type_id     TEXT NOT NULL
pickup_ts        TIMESTAMPTZ NOT NULL
required_by_ts   TIMESTAMPTZ NOT NULL
facility_id      TEXT
decon_start_ts   TIMESTAMPTZ
...
loaded_ts        TIMESTAMPTZ
```

Intermediate state. One row per in-flight journey; deleted when `DELIVERED` finalizes the journey.

### `journey`

```
journey_id              UUID PRIMARY KEY
tray_id                 TEXT NOT NULL
facility_id             TEXT NOT NULL
tray_type_id            TEXT NOT NULL
client_id               TEXT NOT NULL
pickup_ts               TIMESTAMPTZ NOT NULL
required_by_ts          TIMESTAMPTZ NOT NULL
decon_dwell_min         DOUBLE PRECISION NOT NULL
inspection_dwell_min    DOUBLE PRECISION NOT NULL
assembly_dwell_min      DOUBLE PRECISION NOT NULL
sterilization_dwell_min DOUBLE PRECISION NOT NULL
packout_dwell_min       DOUBLE PRECISION NOT NULL
transport_min           DOUBLE PRECISION NOT NULL
delivered_ts            TIMESTAMPTZ NOT NULL
on_time                 BOOLEAN NOT NULL
delay_min               DOUBLE PRECISION NOT NULL
hour_of_pickup          INTEGER NOT NULL
day_of_week             INTEGER NOT NULL
```

Schema mirrors [synth-events](./synth-events) parquet, so anything trained on synth-events output runs unchanged on the projector's tables. `journey_id` is `UUIDv5(JOURNEY_NAMESPACE, pickup_event_id)` so a journey has a stable, deterministic id derivable from its first event.

## Why per-stage timestamps and not a JSONB blob

Each stage gets its own typed `TIMESTAMPTZ` column rather than a single `stages JSONB` column. The dwells are first-class facts of the journey -- queries that filter by "inspection took more than 30 min" or "facility BOCA's sterilization is drifting" should be index-friendly and obvious in SQL, not require JSON-path expressions.

## The `PICKED_UP` payload contract

The projector needs three fields per journey -- `client_id`, `tray_type_id`, `required_by_ts` -- that are not first-class on the `Event` model. By convention, the hospital adapter places them in the `PICKED_UP` event's opaque `payload`:

```json
{
  "client_id": "HOSPITAL_A",
  "tray_type_id": "TRAY-KNEE",
  "required_by_ts": "2026-05-27T13:00:00+00:00"
}
```

The projector validates this via Pydantic; missing or malformed fields cause the journey to silently not start (the tray projection still updates). If vendor reliability becomes a problem, the right next step is a separate `tray_catalog` projection fed by a dedicated event stream.

## Replay and idempotency

The Kafka consumer commits its offset only after the Postgres write succeeds, so events are never marked consumed without their projection landing. Two properties follow:

- **Wipe-and-replay is safe.** Drop the three projection tables, reset the projector's consumer-group offsets, and re-consume from offset zero. The output is identical because:
  - `tray` upserts are LWW-by-arrival,
  - `journey_open` upserts are tray-keyed and contain the full open state, and
  - `journey` inserts use `ON CONFLICT (journey_id) DO NOTHING`.
- **Per-tray ordering is preserved.** The `events` topic is partitioned on `tray_id`, so a single consumer instance sees a tray's events in their original publish order. Adding replicas only splits work across partitions; per-tray order survives.

## Architecture

```mermaid
flowchart LR
    K(((Kafka topic 'events'))) -->|consumer group 'projector'| P[projector]
    P -->|UPSERT| T[(tray)]
    P -->|UPSERT| O[(journey_open)]
    P -->|INSERT| J[(journey)]

    classDef bus fill:#0d6e6e,stroke:#053838,color:#fff
    classDef store fill:#2cc4c4,stroke:#0d6e6e,color:#053838
    class K bus
    class T,O,J store
```

## Run

Requires Redpanda (via `make dev-up`) and Postgres (now also in `docker-compose.yml`).

```bash
uv run projector run
```

Stops cleanly on SIGINT / SIGTERM after finishing the in-flight message.

## Configuration

Env vars prefixed `PROJECTOR_`:

| Variable                        | Default                                                     | Notes                                    |
| ------------------------------- | ----------------------------------------------------------- | ---------------------------------------- |
| `PROJECTOR_KAFKA_BROKERS`       | `localhost:19092`                                           | Comma-separated bootstrap servers        |
| `PROJECTOR_SCHEMA_REGISTRY_URL` | `http://localhost:18081`                                    | Confluent-compatible Schema Registry URL |
| `PROJECTOR_KAFKA_TOPIC`         | `events`                                                    | Topic to consume                         |
| `PROJECTOR_KAFKA_GROUP_ID`      | `projector`                                                 | Consumer group; shared across replicas   |
| `PROJECTOR_POSTGRES_DSN`        | `postgresql://projector:projector@localhost:5432/projector` | Postgres connection string               |
| `PROJECTOR_POLL_TIMEOUT_SEC`    | `1.0`                                                       | Consumer poll timeout                    |

## Testing

```bash
# Unit tests only -- no Postgres or Kafka required.
uv run pytest services/projector -m "not slow"

# Full suite, including integration tests that exercise the real
# ingest -> Kafka -> projector -> Postgres path.
make dev-up
uv run pytest services/projector
```

100% line coverage is enforced. The integration test covers `pg_store.py` and the `cli.py` paths that depend on a live Postgres.
