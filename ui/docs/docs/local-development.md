---
sidebar_position: 2
title: Local development
---

# Local development

This page covers two independent local flows:

1. **Event spine** -- Redpanda + ingest service. Requires Docker. Demonstrates the event capture path.
2. **Routing model + dashboard** -- synth-events, the routing API, and the React dashboard. **No Docker required.** This is the DS demo: hierarchical Bayesian routing model fit on synthetic journeys, exposed via a FastAPI service, visualized in a Vite/React dashboard.

The two flows don't interact yet (the routing model trains on synth-events parquet, not on real ingested events). They'll meet up when the `projector` consumer lands -- see [Roadmap](roadmap).

## Prerequisites

- [mise](https://mise.jdx.dev/) (manages Node 25, Python 3.12, uv)
- [Yarn 4](https://yarnpkg.com/) (bundled via Corepack)
- Docker with `docker compose` -- only for the event-spine flow; skip if you're just running the routing model demo

One-time setup from a fresh clone:

```bash
mise install
corepack enable
yarn install
uv sync --all-groups
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

## Event spine: bring up the dev stack

> Skip this section if you only want the routing model + dashboard demo. The dev stack is just Kafka/Redpanda and is only used by the ingest service.

```bash
make dev-up
```

This runs `docker compose up -d` and starts three containers:

| Container          | Image                           | Purpose                                                                                | Host ports                                                     |
| ------------------ | ------------------------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `redpanda`         | `redpandadata/redpanda:v24.3.5` | Kafka broker + built-in Schema Registry                                                | `19092` (Kafka API), `18081` (Schema Registry), `9644` (admin) |
| `redpanda-init`    | (same)                          | One-shot sidecar: creates the `events` topic (6 partitions, 7-day retention) and exits | --                                                             |
| `redpanda-console` | `redpandadata/console:v2.8.0`   | Web UI for browsing topics, consumer groups, schemas                                   | `8080`                                                         |

Boot sequence: Redpanda starts, its healthcheck (`rpk cluster health`) passes, the init container fires `rpk topic create events` and exits, then the console comes up. Total time: roughly 5--10 seconds on a warm machine.

Postgres and MinIO are deliberately **not** part of the dev stack right now. They will be added back when the `projector` service and the Kafka Connect S3 sink land. See the [Roadmap](roadmap).

## Verify it came up cleanly

```bash
# All three containers should appear -- redpanda "Up (healthy)",
# redpanda-init "Exited (0)", redpanda-console "Up".
docker compose ps

# The `events` topic should exist alongside the internal `_schemas` topic.
make dev-topics
# expected:
#   NAME      PARTITIONS  REPLICAS
#   _schemas  1           1
#   events    6           1
```

## Why 6 partitions

The `--partitions 6` flag in the `redpanda-init` container is an explicit choice, not a default. (Both Redpanda and vanilla Kafka would auto-create topics with **1 partition** otherwise, controlled by `default_topic_partitions` / `num.partitions`.)

A partition is Kafka's unit of **parallelism and ordering**. Two properties matter:

- **Per-partition order is guaranteed; cross-partition order is not.** We partition the `events` topic by `tray_id`, so every event for one tray lands on the same partition and downstream consumers read them in order. Events for different trays may interleave.
- **A consumer group can have at most N consumers for an N-partition topic.** Each partition is owned by exactly one consumer in the group at a time. With 6 partitions, the projector consumer group (and any other future group) can scale up to 6 replicas; a 7th replica would sit idle.

We picked 6 specifically because:

- At our peak (~120 events/sec) a single partition would handle the throughput. We are **not** partitioning for throughput -- we are partitioning for **consumer-side headroom** for the planned projector, routing, preference-learner, and S3-sink consumer groups.
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

Practical implication: pick partition count up front with headroom. 6 covers our planned consumer roster (`projector`, routing, preference-card learner, S3 sink) without a re-partitioning event. If we ever genuinely outgrow it, the migration is a documented one-time operation with a quiet window, not a casual config change.

## Send an event end-to-end

In a second terminal, run the ingest service against the stack:

```bash
uv run uvicorn ingest.app:create_app --factory --reload --port 8000
```

In a third terminal, POST an event:

```bash
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
```

Confirm the message landed on the topic:

```bash
docker compose exec redpanda rpk topic consume events --num 1 --pretty-print
# expected: a JSON payload framed by the magic byte + schema ID
# (Confluent JSON-Schema wire format)
```

Replay the exact same POST. The response carries the **same** `event_id` (deterministic UUIDv5 of `(source_system, source_event_id)`), the message lands on Kafka a second time, and downstream consumers will dedup it on `event_id`:

```bash
curl -X POST http://localhost:8000/events -H 'content-type: application/json' -d '<same body>'
# expected: identical event_id in the response
```

Alternatively, run the integration tests, which exercise all of the above plus the Schema Registry round-trip:

```bash
uv run pytest services/ingest -m slow -v
# expected: 3 passed
```

## Routing model + dashboard demo

The DS demo: generate synthetic journey data, fit the hierarchical Bayesian routing model, serve it from FastAPI, and view it in the React dashboard. **No Docker, no Kafka** -- this whole flow is local processes.

### Step 1. Generate synthetic journeys

```bash
uv run synth-events generate --n 5000 --out /tmp/journeys.parquet --seed 42 --days 30
# expected: "wrote 5000 journeys to /tmp/journeys.parquet"
```

See [synth-events](./services/synth-events) for the distribution design -- BOCA is fast and unpredictable, LGB is balanced, ELM is slow and steady.

### Step 2. Fit the routing model

```bash
uv run routing fit \
  --in /tmp/journeys.parquet \
  --out /tmp/routing-model.npz \
  --draws 500 --tune 500 --chains 2 --seed 42
# expected: "wrote posterior (1000 samples) to /tmp/routing-model.npz"
# takes ~3 minutes on a warm machine
```

The NUTS sampler in PyMC produces a flattened posterior over the hierarchical model's parameters (per-facility mean offsets and sigmas, tray-type effects, peak-hour shift, transport time). See [routing](./services/routing) for the model math.

### Step 3. Start the routing API

In a second terminal:

```bash
ROUTING_MODEL_PATH=/tmp/routing-model.npz \
  uv run uvicorn routing.app:create_app --factory --reload --port 8091
```

Verify it's up:

```bash
curl http://localhost:8091/healthz
# expected: {"status":"ok"}

curl -X POST http://localhost:8091/decide \
  -H 'content-type: application/json' \
  -d '{
    "tray_type_id": "TRAY-KNEE",
    "hour_of_pickup": 10,
    "deadline_min": 220.0,
    "client_id": "HOSPITAL_A"
  }' | python3 -m json.tool
# expected: per-facility cells (expected_completion_min, p_on_time) and three policy choices
```

### Step 4. Start the dashboard

In a third terminal:

```bash
yarn workspace @isl/dashboard dev
# expected: server at http://localhost:3091
```

Open http://localhost:3091. The Explorer tab is wired to the routing API via Vite's `/api` proxy (configured in `ui/dashboard/vite.config.ts` to forward to `:8091`).

### What to look at

In the Explorer tab:

- **Move the deadline slider** down from 220 toward 150. Watch the variance-aware policy's P(on-time) numbers fall faster for BOCA (high variance) than for LGB / ELM. At tight deadlines variance-aware may pick a different facility than mean-only.
- **Move the hour slider** into 08-11 or 14-17. The peak-hour effect adds time across all facilities; you'll see the expected-completion numbers tick up.
- **Switch tray types**. Spine instrumentation has the highest complexity multiplier; small instrument trays are fastest.
- **Switch clients**. Only the proximity policy's choice changes (it consults a hardcoded client-to-facility map).

### Optional: just see the lift numbers without the UI

If you want the headline DS result without spinning up the API + dashboard, the CLI prints it directly:

```bash
uv run routing backtest --model /tmp/routing-model.npz --n 3000 --seed 100
# prints a per-policy table + bootstrap-CI lifts
```

## Browse it visually

- **Redpanda Console** -- http://localhost:8080. Topics, messages with full payloads, partitions, consumer groups, registered schemas. Click `events` to see your published messages.
- **Schema Registry over HTTP**:

  ```bash
  # List all subjects (should include "events-value" after first publish)
  curl http://localhost:18081/subjects

  # Show the latest schema
  curl http://localhost:18081/subjects/events-value/versions/latest
  ```

## Stop / reset / inspect

```bash
make dev-down    # stop containers, keep volumes (state survives a restart)
make dev-reset   # stop containers AND delete volumes (clean slate)
make dev-logs    # tail logs from all containers
```

## Troubleshooting

If `docker compose ps` shows anything other than the expected three containers in healthy / exited-0 state, the first two diagnostics are:

```bash
docker compose ps
docker compose logs redpanda | tail -30
```

Common situations:

- **Port 19092 / 18081 / 8080 already in use** -- another local stack is bound to one of them. `docker ps -a` to find the offender, or change the host-side port in `docker-compose.yml`.
- **`redpanda-init` exited non-zero** -- topic creation failed. `docker compose logs redpanda-init` shows the error; usually a transient race with broker startup. `make dev-reset && make dev-up` reliably fixes it.
- **`uv run uvicorn ingest...` fails with a Kafka connection error** -- the broker isn't up yet, or you forgot `make dev-up`. Re-run after `docker compose ps` shows `redpanda` healthy.

For the routing model + dashboard flow:

- **`uvicorn routing.app:...` fails with `FileNotFoundError: model.npz`** -- skipped Step 2, or `ROUTING_MODEL_PATH` is pointing somewhere stale. Re-run `routing fit` and pass the resulting path.
- **Dashboard shows "Routing API unreachable"** -- the routing process isn't running on `:8091`, or the Vite proxy in `ui/dashboard/vite.config.ts` is pointing somewhere else. Start the API and reload the page.
- **`pymc` import fails** -- usually a stale venv. `rm -rf .venv && uv sync` rebuilds against the pinned PyMC 5.19 / PyTensor 2.26 we need on macOS x86_64.
- **Port 3091 / 8091 already in use** -- another dashboard or another local API is bound. `lsof -i :3091` (or `:8091`) finds the offender.
