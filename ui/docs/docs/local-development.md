---
sidebar_position: 2
title: Local development
---

# Local development

The system is multi-process: Kafka (Redpanda), Postgres, the ingest service, the projector consumer, the routing API, and the React dashboard. The **full-stack demo** below brings every piece up in ~3 minutes and ends with you watching a tray's events propagate from `POST /events` all the way to the dashboard live. Underneath, each component has a "bring it up alone" recipe for service-focused work.

## Prerequisites

- [mise](https://mise.jdx.dev/) (manages Node 25, Python 3.12, uv)
- [Yarn 4](https://yarnpkg.com/) (bundled via Corepack)
- Docker with `docker compose`

One-time setup from a fresh clone:

```bash
mise install
corepack enable
yarn install
uv sync --all-groups
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

## Full-stack demo

End-to-end happy path. Five terminals + one for the live tracking script.

### 1. Bring up the dependency stack

```bash
make dev-up
```

This runs `docker compose up -d` and starts:

| Container          | Image                           | Purpose                                                                                | Host ports                                                     |
| ------------------ | ------------------------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `redpanda`         | `redpandadata/redpanda:v24.3.5` | Kafka broker + built-in Schema Registry                                                | `19092` (Kafka API), `18081` (Schema Registry), `9644` (admin) |
| `redpanda-init`    | (same)                          | One-shot sidecar: creates the `events` topic (6 partitions, 7-day retention) and exits | --                                                             |
| `redpanda-console` | `redpandadata/console:v2.8.0`   | Web UI for browsing topics, schemas, consumer groups                                   | `8080`                                                         |
| `postgres`         | `postgres:16-alpine`            | Projection store for the `projector`. Database, user, password all `projector`         | `5432`                                                         |

Wait for Postgres to be ready (a couple seconds):

```bash
docker compose exec postgres pg_isready -U projector -d projector
# expected: /var/run/postgresql:5432 - accepting connections
```

### 2. Start the projector consumer

**Terminal 1.** The projector subscribes to the `events` topic, creates the `tray` / `journey_open` / `journey` tables in Postgres on first run, and keeps running.

```bash
uv run projector run
# expected:
#   connecting to postgres at postgresql://projector:projector@localhost:5432/projector
#   subscribing to events as group projector
```

It will sit idle until events show up on the topic.

### 3. Start the ingest service

**Terminal 2.** Front door for events: validates payloads, derives the deterministic UUIDv5 `event_id`, publishes to the `events` topic.

```bash
uv run uvicorn ingest.app:create_app --factory --port 8000
```

### 4. Fit a model and start the routing API

**Terminal 3.** Generate synthetic journeys, fit the hierarchical Bayesian model, then leave the routing API running.

```bash
# One-time: generate training data + fit the model. Takes ~3 minutes.
uv run synth-events generate --n 5000 --out /tmp/journeys.parquet --seed 42 --days 30
uv run routing fit --in /tmp/journeys.parquet --out /tmp/routing-model.npz \
  --draws 500 --tune 500 --chains 2 --seed 42

# Long-running: serve the model and the operations endpoints.
ROUTING_MODEL_PATH=/tmp/routing-model.npz \
  uv run uvicorn routing.app:create_app --factory --port 8091
```

### 5. Start the dashboard

**Terminal 4.**

```bash
yarn workspace @isl/dashboard dev
# expected: server at http://localhost:3091
```

Open [http://localhost:3091](http://localhost:3091). The sidebar has five tabs; **Explorer**, **Operations**, **Backtest**, and **Model** are live; **Calibration** is the last placeholder pending its endpoint.

### 6. Backfill the dashboard with synthetic journeys

**Terminal 5.** Generate 200 realistic journeys, POST every event (10 per journey, 2000 total) through ingest. The projector reads them from Kafka and writes to Postgres; within a few seconds the dashboard's Operations tab fills.

```bash
uv run synth-events publish --n 200 --hours 24 --seed 1
# expected: "posted 2000 events from 200 journeys to http://localhost:8000"
```

Refresh [http://localhost:3091/operations](http://localhost:3091/operations). You should see 200 finalized journeys with a mix of on-time / late, and 200 trays in `DELIVERED` state.

### 7. Watch a live tray journey

**Terminal 6** (or reuse 5). Run the script below in a fresh terminal and keep the Operations tab open in your browser. The dashboard polls every 5 seconds; the script POSTs 10 events spaced 4 seconds apart, so you'll see the tray's stage update on each poll, then the row migrate from "Trays" to "Recent finalized journeys" once `DELIVERED` lands.

```bash
TRAY="TRAY-LIVE-$(date +%s)"
echo "watch the dashboard for tray $TRAY"

post() {
  local idx=$1 et=$2 fid=$3 ts=$4 payload=$5
  curl -sf -X POST http://localhost:8000/events \
    -H 'content-type: application/json' \
    -d "{
      \"source_system\": \"LIVE_DEMO\",
      \"source_event_id\": \"$TRAY-$idx\",
      \"tray_id\": \"$TRAY\",
      \"facility_id\": \"$fid\",
      \"event_type\": \"$et\",
      \"timestamp_event\": \"$ts\",
      \"payload\": $payload
    }" > /dev/null
  echo "$(date +%T) posted $et"
  sleep 4
}

post 00 PICKED_UP   HOSPITAL_A 2026-05-27T08:00:00Z '{"client_id":"HOSPITAL_A","tray_type_id":"TRAY-KNEE","required_by_ts":"2026-05-27T13:00:00Z"}'
post 01 CHECKED_IN  BOCA       2026-05-27T08:30:00Z '{}'
post 02 DECON_START BOCA       2026-05-27T08:45:00Z '{}'
post 03 DECON_END   BOCA       2026-05-27T09:05:00Z '{}'
post 04 INSPECTED   BOCA       2026-05-27T09:25:00Z '{}'
post 05 ASSEMBLED   BOCA       2026-05-27T09:50:00Z '{}'
post 06 STERILIZED  BOCA       2026-05-27T10:30:00Z '{}'
post 07 PACKED      BOCA       2026-05-27T10:45:00Z '{}'
post 08 LOADED      BOCA       2026-05-27T11:00:00Z '{}'
post 09 DELIVERED   HOSPITAL_A 2026-05-27T11:30:00Z '{}'
```

What to watch in the Operations tab:

- **After PICKED_UP**: the new tray appears at the top of the "Trays, most recently updated" table with `current_stage = PICKED_UP`.
- **Through CHECKED_IN -> LOADED**: the same row's `current_stage` column updates on each poll. The tray stays in the trays table because it hasn't completed a journey yet.
- **After DELIVERED**: `current_stage` becomes `DELIVERED` and a new row appears at the top of the "Recent finalized journeys" table with the per-stage dwells (20m decon, 20m inspection, ...) and an `on-time` badge.

That's the closed loop: the dashboard renders a projection of an event log whose source of truth is Kafka.

## Working on just the event spine

If you're iterating on the ingest service and don't need the projector/dashboard:

```bash
make dev-up                                            # Redpanda only is enough
uv run uvicorn ingest.app:create_app --factory --port 8000

# POST one event, see it on the topic
curl -X POST http://localhost:8000/events \
  -H 'content-type: application/json' \
  -d '{
    "source_system": "CENSITRAC_BOCA",
    "source_event_id": "abc-123",
    "tray_id": "TRAY-001",
    "facility_id": "BOCA",
    "event_type": "CHECKED_IN",
    "timestamp_event": "2026-05-27T14:30:00Z"
  }'
# expected: 202, body like {"event_id":"<uuid>"}

docker compose exec redpanda rpk topic consume events --num 1 --pretty-print
```

Replay the exact same POST -- the response carries the **same** `event_id` (deterministic UUIDv5 of `(source_system, source_event_id)`), the message lands on Kafka twice, the projector dedups it on `event_id`.

Or run the integration tests instead:

```bash
uv run pytest services/ingest -m slow -v
# expected: 3 passed
```

## Working on just the routing model + dashboard

If you only care about the DS demo and don't need ingest/projector running:

```bash
# (no make dev-up needed -- the routing API doesn't read Kafka)
uv run synth-events generate --n 5000 --out /tmp/journeys.parquet
uv run routing fit --in /tmp/journeys.parquet --out /tmp/routing-model.npz \
  --draws 500 --tune 500 --chains 2

ROUTING_MODEL_PATH=/tmp/routing-model.npz \
  uv run uvicorn routing.app:create_app --factory --port 8091
yarn workspace @isl/dashboard dev
```

The Explorer tab works against the model alone. The Operations tab will throw a 503 because the routing service can't reach Postgres -- bring up `make dev-up` to fix that.

If you want the headline backtest numbers without the UI:

```bash
uv run routing backtest --model /tmp/routing-model.npz --n 3000 --seed 100
# prints a per-policy table + bootstrap-CI lifts
```

## Browse the broker

- **Redpanda Console** -- [http://localhost:8080](http://localhost:8080). Topics, messages with full payloads, partitions, consumer groups, registered schemas. Click `events` to see your published messages.
- **Schema Registry over HTTP**:

  ```bash
  # List all subjects (should include "events-value" after first publish)
  curl http://localhost:18081/subjects

  # Show the latest schema
  curl http://localhost:18081/subjects/events-value/versions/latest
  ```

## Stop / reset / inspect

```bash
make dev-down    # stop containers, keep volumes (Postgres tables + Kafka log survive)
make dev-reset   # stop containers AND delete volumes (clean slate)
make dev-logs    # tail logs from all containers
```

For a partial wipe-and-replay -- drop just the projector's tables and let it rebuild from the Kafka log:

```bash
docker compose exec postgres psql -U projector -d projector \
  -c "TRUNCATE tray, journey_open, journey;"
# also reset the projector's consumer-group offsets so it re-reads from offset 0
docker compose exec redpanda rpk group seek projector --to start --topics events
# restart `projector run` -- it recreates tables on connect and replays the log
```

## Why 6 partitions

The `--partitions 6` flag in the `redpanda-init` container is an explicit choice, not a default. (Both Redpanda and vanilla Kafka would auto-create topics with **1 partition** otherwise, controlled by `default_topic_partitions` / `num.partitions`.)

A partition is Kafka's unit of **parallelism and ordering**. Two properties matter:

- **Per-partition order is guaranteed; cross-partition order is not.** We partition the `events` topic by `tray_id`, so every event for one tray lands on the same partition and downstream consumers read them in order. Events for different trays may interleave.
- **A consumer group can have at most N consumers for an N-partition topic.** Each partition is owned by exactly one consumer in the group at a time. With 6 partitions, the projector consumer group (and any other future group) can scale up to 6 replicas; a 7th replica would sit idle.

We picked 6 specifically because:

- At our peak (~120 events/sec) a single partition would handle the throughput. We are **not** partitioning for throughput -- we are partitioning for **consumer-side headroom** for the projector, the future preference-learner, and the future S3-sink consumer groups.
- 6 is small enough that per-partition metadata cost (open log files, segment indexes, controller bookkeeping) is negligible.
- 6 divides evenly by 1, 2, 3, and 6, so a consumer group scaled to any of those counts gets an even partition assignment. Compare to 5 (divisors 1, 5) which gives uneven assignment for most scale-out steps.

Tradeoffs at other counts:

| Pick | Tradeoff                                                                                                                            |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------- |
| 1    | No consumer parallelism. Every consumer group is a single point of failure with no horizontal scale option short of re-partitioning |
| 3    | Workable; each group scales to 3 replicas. Less headroom for later                                                                  |
| 6    | What we picked. Plenty of room for the planned consumers; cheap metadata cost                                                       |
| 24+  | Premature at our volume. More file handles, more metadata, more controller work, with no concrete consumer that benefits            |

### The catch with changing it later

You can **add** partitions to a topic (`rpk topic add-partitions events --num 4`) but you **cannot remove** them. Adding partitions also changes which partition a given `tray_id` hashes to, so in-flight events for the same tray can end up split across old and new partitions, temporarily breaking per-tray ordering until the old partition drains.

Practical implication: pick partition count up front with headroom. 6 covers our planned consumer roster (`projector`, preference-card learner, S3 sink) without a re-partitioning event. If we ever genuinely outgrow it, the migration is a documented one-time operation with a quiet window, not a casual config change.

## Troubleshooting

If `docker compose ps` shows anything other than the expected containers in healthy state:

```bash
docker compose ps
docker compose logs redpanda | tail -30
docker compose logs postgres | tail -30
```

Common situations:

- **Port 19092 / 18081 / 8080 / 5432 already in use** -- another local stack is bound. `docker ps -a` to find the offender, or change the host-side port in `docker-compose.yml`.
- **`redpanda-init` exited non-zero** -- topic creation failed. `docker compose logs redpanda-init` shows the error; usually a transient race with broker startup. `make dev-reset && make dev-up` reliably fixes it.
- **`projector run` fails with `psycopg.OperationalError`** -- Postgres isn't healthy yet, or its container isn't up. `docker compose ps postgres` should show `Up (healthy)`.
- **Dashboard Operations tab shows "Projector store unreachable"** -- the routing service can reach `/api/decide` but not Postgres. Verify `docker compose ps postgres`, then check `ROUTING_POSTGRES_DSN` if you changed it.
- **`uv run uvicorn ingest...` fails with a Kafka connection error** -- the broker isn't up yet, or you forgot `make dev-up`. Re-run after `docker compose ps` shows `redpanda` healthy.
- **`uvicorn routing.app:...` fails with `FileNotFoundError: model.npz`** -- skipped the model-fit step, or `ROUTING_MODEL_PATH` points somewhere stale. Re-run `routing fit` and pass the resulting path.
- **Dashboard shows "Routing API unreachable"** -- the routing process isn't running on `:8091`, or the Vite proxy in `ui/dashboard/vite.config.ts` is pointing somewhere else. Start the API and reload the page.
- **`pymc` import fails** -- usually a stale venv. `rm -rf .venv && uv sync` rebuilds against the pinned PyMC 5.19 / PyTensor 2.26 we need on macOS x86_64.
- **Port 3091 / 8091 already in use** -- another dashboard or another local API is bound. `lsof -i :3091` (or `:8091`) finds the offender.
