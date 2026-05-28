# projector

Kafka consumer that projects events from the `events` topic into two Postgres tables:

- `tray` -- current state of each tray (one row per tray, upserted on every event).
- `journey` -- one row per finalized pickup-to-delivery cycle.

An intermediate `journey_open` table holds the in-flight state of each journey until DELIVERED arrives and the row can be finalized.

## Run

Requires the dev stack (`make dev-up`) plus a Postgres instance reachable via `PROJECTOR_POSTGRES_DSN`.

```bash
uv run projector run
```

Configuration via env vars (prefix `PROJECTOR_`):

- `PROJECTOR_KAFKA_BROKERS` (default `localhost:19092`)
- `PROJECTOR_SCHEMA_REGISTRY_URL` (default `http://localhost:18081`)
- `PROJECTOR_KAFKA_TOPIC` (default `events`)
- `PROJECTOR_KAFKA_GROUP_ID` (default `projector`)
- `PROJECTOR_POSTGRES_DSN` (default `postgresql://projector:projector@localhost:5432/projector`)
- `PROJECTOR_POLL_TIMEOUT_SEC` (default `1.0`)

## Test

```bash
# unit tests only
uv run pytest services/projector -m "not slow"

# full suite including integration (needs make dev-up and a running Postgres)
uv run pytest services/projector
```

100% line coverage is enforced.
