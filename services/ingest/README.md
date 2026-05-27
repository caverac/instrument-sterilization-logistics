# services/ingest

FastAPI service that ingests facility events: validates, archives to S3, then upserts into Postgres (with `pg_notify` for downstream projectors).

See [section 7.1 of the design doc](../../notebooks/notes/logs/20260525-idea.md).

## Endpoints

| Method | Path       | Purpose                                                         |
| ------ | ---------- | --------------------------------------------------------------- |
| GET    | `/healthz` | Liveness probe                                                  |
| POST   | `/events`  | Submit one event. Dedups on `(source_system, source_event_id)`. |

## Local development

From the repo root:

```bash
# 1. Bring up Postgres + MinIO
make dev-up

# 2. Run the ingest service
uv run uvicorn ingest.app:create_app --factory --reload --port 8000

# 3. Send a sample event
curl -X POST http://localhost:8000/events \
  -H 'content-type: application/json' \
  -d '{
    "source_system": "CENSITRAC_BOCA",
    "source_event_id": "abc-123",
    "tray_id": "TRAY-001",
    "facility_id": "BOCA",
    "event_type": "CHECKED_IN",
    "timestamp_event": "2026-05-25T14:30:00Z"
  }'

# 4. Verify in Postgres
docker compose exec postgres psql -U isl -d isl -c "SELECT event_id, source_system, event_type FROM events;"

# 5. Verify in MinIO console at http://localhost:9001  (minio / minio12345)
```

## Testing

```bash
# Unit tests only (100% coverage enforced)
uv run pytest services/ingest -m "not slow"

# Integration tests (require `make dev-up`)
uv run pytest services/ingest -m slow
```

## Configuration

All settings are environment variables prefixed `INGEST_`:

| Var                      | Default                                   |
| ------------------------ | ----------------------------------------- |
| `INGEST_DATABASE_URL`    | `postgresql://isl:isl@localhost:5432/isl` |
| `INGEST_S3_ENDPOINT_URL` | `http://localhost:9000`                   |
| `INGEST_S3_BUCKET`       | `isl-events`                              |
| `INGEST_S3_ACCESS_KEY`   | `minio`                                   |
| `INGEST_S3_SECRET_KEY`   | `minio12345`                              |
| `INGEST_S3_REGION`       | `us-east-1`                               |
