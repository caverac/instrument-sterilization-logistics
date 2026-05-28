# services/synth-events

Synthetic journey generator. Produces parquet rows that look like what the `projector` service would emit if it were running against a real event stream. Used as the input data set for the variance-aware routing model and other modeling work before real client data exists.

## What it generates

One row per **journey** -- a single tray's pickup through return cycle. Columns:

```
journey_id              uuid
facility_id             one of {BOCA, LGB, ELM}
tray_id                 synthesized identifier
tray_type_id            one of 5 tray types of varying complexity
client_id               hospital identifier
pickup_ts               when the tray was picked up at the hospital
required_by_ts          deadline (next OR-case start)
decon_dwell_min         per-stage dwell times, sampled from
inspection_dwell_min      per-facility log-normal distributions
assembly_dwell_min
sterilization_dwell_min
packout_dwell_min
transport_min           return trip from facility back to hospital
delivered_ts            pickup_ts + sum of stage dwells + transport
on_time                 delivered_ts <= required_by_ts
delay_min               (delivered_ts - required_by_ts) in minutes (signed)
hour_of_pickup          0-23, in pickup local time
day_of_week             0=Monday ... 6=Sunday
```

## Distribution design

Three facilities with different reliability profiles. **The variance ranking is deliberate** -- it is what makes variance-aware routing actually win against mean-only routing in the backtest:

| Facility | Mean total time | Variance multiplier | Story                                  |
| -------- | --------------- | ------------------- | -------------------------------------- |
| `BOCA`   | ~155 min        | 1.5x                | Newest, fast on average, unpredictable |
| `LGB`    | ~165 min        | 1.0x                | Mature operation, consistent           |
| `ELM`    | ~185 min        | 0.5x                | Constrained but very steady            |

A mean-only router always picks BOCA. A variance-aware router picks LGB for tight deadlines, BOCA for slack ones.

## Usage

```bash
# Generate 10,000 journeys, seed for reproducibility
uv run synth-events generate --n 10000 --out journeys.parquet --seed 42

# Quick peek
uv run python -c "import pyarrow.parquet as pq; t = pq.read_table('journeys.parquet'); print(t.schema); print(t.to_pandas().head())"
```

## Testing

```bash
cd services/synth-events && uv run python -m pytest tests/ -v
```

100% coverage is enforced.
