---
slug: /
sidebar_position: 1
---

# Instrument Sterilization Logistics

**Cross-facility coordination layer for offsite surgical-instrument reprocessing networks.**

## What this is

A network of N sterilization facilities reprocesses surgical trays for M client hospitals and <abbr title="Ambulatory Surgery Centers -- outpatient surgical facilities">ASCs</abbr>. Each tray must clear the pipeline (decon -> inspection -> assembly -> sterilization -> packout -> transport) and return by a deadline tied to the next <abbr title="Operating Room">OR</abbr> case.

This system is the **coordination layer** for that network. Specifically, it:

1. **Routes** each pickup to the facility most likely to hit the next <abbr title="Operating Room">OR</abbr>-case deadline -- variance-aware, not mean-aware.
2. **Reports** contractually defensible <abbr title="Service-Level Agreement">SLA</abbr> performance across all facilities for each client.
3. **Learns** the real composition of each tray type from observed reprocessing data, and uses that to forecast demand and pre-stage trays.
4. **Audits** the cross-facility journey of every tray with a regulatory-grade trail (<abbr title="U.S. Food and Drug Administration">FDA</abbr>, <abbr title="Association for the Advancement of Medical Instrumentation">AAMI</abbr> <abbr title="AAMI ST79 -- comprehensive guide to steam sterilization and sterility assurance">ST79</abbr>, Joint Commission, state licensing).

## What this is _not_

This is deliberately not a competitor to the single-facility <abbr title="Sterile Processing Department -- the hospital function that cleans, inspects, assembles, sterilizes, and packages surgical instruments">SPD</abbr> systems already deployed in the industry (CensiTrac, SPM, ...). Where a facility runs one of those, we integrate with it; we do not replace it. The wedge is in the **cross-facility** problems those systems are not designed to solve.

## How it's built

The system is event-sourced end to end. Every state change is an immutable event in a durable log; current state is a projection. This makes the system replayable, auditable, and easy to extend with new consumers without breaking existing ones.

The <abbr title="Milestone 1 -- the event spine + first client, end-to-end. See the Glossary for M1--M4+ definitions.">M1</abbr> stack is deliberately small: Postgres for state and journeys, S3 for the immutable event archive, FastAPI workers for ingest and projections, and Metabase for <abbr title="Service-Level Agreement">SLA</abbr> dashboards on a read replica. Kafka, Flink, Snowflake, and TimescaleDB are graduated _to_ only when a specific workload demands them -- not as up-front design choices.

## Where to go next

- **[Ingest service](services/ingest)** -- the front door for events. Owns durability, dedup, and fan-out.

(More services land here as the <abbr title="Milestones 1--3 in the build order -- event spine, second facility + routing, HL7 + preference-card learning">M1--M3</abbr> build order in the design doc progresses.)
