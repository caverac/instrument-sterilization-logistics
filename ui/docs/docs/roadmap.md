---
sidebar_position: 90
title: Roadmap
---

# Roadmap

What lands when, and what triggers each component we have not yet built. The discipline is to **not** add a component until the trigger fires -- every component built before it is needed is operational tax forever.

## Build order

- **M1 (now).** Event spine end-to-end for one pilot client and one facility.
  - Redpanda (Kafka + Schema Registry) running locally and in prod.
  - `ingest` service publishing validated events to topic `events`. **Done as of 2026-05-27.**
  - One facility adapter producing through ingest.
  - `projector` Kafka consumer building Postgres `tray` and `journey` projections.
  - Kafka Connect S3 sink writing the long-term archive.
  - Metabase SLA dashboard with row-level security on the projection store.
  - **Outcome:** "where is tray X" answered in `< 1s`; defensible SLA report for the pilot client.

- **M2.** Second facility + variance-aware routing.
  - Second facility adapter.
  - `routing` service (Kafka consumer + REST) with variance-aware scoring.
  - Backtest harness writing `actual_*` back to `routing_decisions`.
  - Dispatch console with override capability.
  - **Outcome:** automated facility selection for pickups, with a measurable on-time-rate lift over the round-robin / proximity baseline.

- **M3.** OR schedule + preference-card learning.
  - HL7 v2 SIU ingest via Mirth for the pilot client (this milestone is dominated by per-client integration work).
  - `case_schedule` and `case_result` flow through ingest as new event types on the same topic.
  - `preference-card-learner` Kafka consumer; "declared vs. observed" UI in the hospital portal.
  - Bottleneck attribution live on the dispatch console.
  - **Outcome:** demand forecast feeding routing; first client sees their preference cards being corrected by observed data.

## Out of scope, with triggers

| Not building                                   | Triggered by                                                                                            |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| OAuth2 / API keys on ingest                    | First external facility adapter outside our trust boundary                                              |
| Batch endpoint (`POST /events/bulk`)           | A vendor adapter that emits `>= 100 events/sec` sustained                                               |
| Direct scanner / RFID ingest                   | A pilot facility without an incumbent SPD system                                                        |
| Autoclave PLC streaming                        | A regulator or client requiring raw OPC-UA evidence rather than the facility's signed cycle record      |
| Avro or Protobuf encoding                      | A polyglot consumer (Go, Rust, ...) needing strict binary contracts. JSON Schema is good enough for now |
| Multiple topics / per-event-type topics        | A consumer that needs to subscribe to only one event type at high volume                                |
| Managed Kafka (Redpanda Cloud, MSK, Confluent) | Multi-tenant or multi-cluster needs, or we want out of broker ops                                       |
| Snowflake / Iceberg                            | Client BYO-warehouse demand, or PG analytical queries can't keep up                                     |
| TimescaleDB                                    | `station_metrics_1min` exceeds 100M rows or sub-second windowed queries that PG can't deliver           |
| Flink                                          | A stateful streaming windowed join we can't express as a Kafka consumer                                 |
| Driver app, floor tablet                       | A client requires it and the incumbent system can't supply the data                                     |
| ML add-on / cancellation model                 | `>= 6 months` of `case_schedule` + `case_result` data, plus a client willing to pay for the lift        |
| Individual-instrument UDI tracking             | A client mandates it, or a regulator does                                                               |
| FHIR adapter                                   | A pilot client speaks FHIR natively                                                                     |

## What changes about each service over time

### `ingest`

| When                         | Change                                                       | Reason                                                                       |
| ---------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| First polyglot consumer      | Add Avro or Protobuf encoding alongside JSON Schema          | JSON Schema is loose for non-Python consumers                                |
| Multi-tenant / multi-cluster | Promote to a managed broker (Redpanda Cloud, MSK, Confluent) | Self-hosted Redpanda is fine to a few hundred topics; beyond, pay to own it  |
| First adversarial caller     | Add OAuth2 client credentials                                | M1 assumes adapters are inside our trust boundary                            |
| Event volume `> 50k/sec`     | Add multiple ingest replicas behind a load balancer          | Single-instance Python can push ~5k/sec sustained; horizontally scale beyond |

(Other services land here as they are built.)
