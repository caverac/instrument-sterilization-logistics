---
sidebar_position: 99
title: Glossary
---

# Glossary

Acronyms and domain-specific terms used throughout the documentation. The same terms appear inline in the docs with hover tooltips -- this page is the canonical reference.

---

**AAMI** -- _Association for the Advancement of Medical Instrumentation._ U.S. standards body whose publications govern medical-device reprocessing.

**API** -- _Application Programming Interface._

**ASC** -- _Ambulatory Surgery Center._ Outpatient surgical facility, smaller than a hospital and a common client of offsite reprocessing networks.

**BI / CI** -- _Biological Indicator / Chemical Indicator._ Test devices placed in each sterilization load to prove the cycle achieved sterility. The BI/CI result is part of the regulatory record per AAMI ST79.

**BYO-warehouse** -- _Bring-Your-Own warehouse._ Pattern where a customer reads our analytics data into their own data warehouse (e.g. their Snowflake account) rather than ours.

**CensiTrac** -- Commercial single-facility SPD tracking system. Not an acronym; included here because it appears throughout as the incumbent we integrate with rather than replace.

**Confluent wire format** -- The on-the-wire encoding used by Confluent serializers (and compatible with Redpanda's Schema Registry): one magic byte (`0x00`) + a 4-byte schema ID + the serialized payload. Consumers read the schema ID, fetch the schema from Schema Registry if not cached, then deserialize.

**Consumer group** -- A set of Kafka consumers that cooperate to read a topic: each partition is assigned to exactly one consumer in the group at a time. Lets you scale consumers horizontally without coordination code.

**DR** -- _Disaster Recovery._

**DSN** -- _Data Source Name._ Connection string for a database, e.g. `postgresql://user:pass@host:5432/db`.

**EHR** -- _Electronic Health Record._ The hospital's clinical system of record; the source for OR schedules and (sometimes) post-case instrument usage.

**FDA** -- U.S. _Food and Drug Administration._ Regulator whose [21 CFR Part 820](https://www.fda.gov) governs medical-device records, including reprocessing.

**FHIR** -- _Fast Healthcare Interoperability Resources._ Modern REST/JSON healthcare interop standard. Cleaner than HL7 v2 but less commonly deployed in OR-scheduling contexts as of 2026.

**HL7** -- _Health Level Seven._ Both a standards body and a family of healthcare messaging standards. HL7 v2 is the pipe-delimited legacy format still dominant in hospital integrations; HL7 v3 / FHIR are newer.

**IAM** -- _Identity and Access Management._ AWS service for credentials and permissions.

**IRSA** -- _IAM Roles for Service Accounts._ The AWS-recommended way to grant Kubernetes pods AWS permissions without static credentials.

**ISL** -- _Instrument Sterilization Logistics._ This project.

**Idempotent producer** -- A Kafka producer mode where the broker dedups messages by `(producer_id, sequence_number)` during retries. Combined with our deterministic `event_id`, gives us at-most-once landing per `(source_system, source_event_id)` even under network turbulence.

**Joint Commission** -- Independent U.S. healthcare accreditation body. Not an acronym; included because their standards are referenced alongside FDA and AAMI for compliance scope.

**JSON Schema** -- JSON-based schema language for describing the shape of JSON documents. Used as our event-payload contract on Kafka, registered to Schema Registry, enforced at serialize/deserialize time.

**jsonb** -- Postgres binary-JSON column type. Indexed and queryable, unlike `text`-serialized JSON.

**Kafka** -- Distributed durable log used as the project's event bus and source of truth. We run a Kafka-compatible broker called Redpanda (see below).

**Kafka Connect** -- Pluggable framework for moving data between Kafka and external systems (S3, Postgres, Snowflake, ...) without writing application code. We plan to use the S3 sink connector for the long-term event archive.

**KMS** -- _Key Management Service._ AWS service for managing cryptographic keys.

**MinIO** -- Open-source S3-compatible object store. Used in local dev as a drop-in for AWS S3 when the S3 sink connector and projector land.

**MQTT** -- _Message Queuing Telemetry Transport._ Lightweight pub/sub protocol common for IoT/edge devices (e.g. handheld scanners).

**OAuth2** -- _Open Authorization 2.0._ Token-based authorization standard.

**OPC-UA** -- _OPC Unified Architecture._ Industrial machine-to-machine communication protocol. Autoclave PLCs typically expose cycle telemetry over OPC-UA.

**Partition** -- Kafka unit of parallelism within a topic. We partition the `events` topic by `tray_id` (6 partitions in dev) so all events for a given tray land on the same partition and consume in order.

**OR** -- _Operating Room._ The downstream consumer of every tray we reprocess.

**ORU** -- HL7 v2 _Observation Result Unsolicited._ The message type a hospital EHR uses to report case results (e.g. instruments used per case).

**PHI** -- _Protected Health Information._ Patient-identifying data subject to HIPAA and equivalent state law. Tokenized at ingest in this system.

**PLC** -- _Programmable Logic Controller._ The industrial computer that runs an autoclave (or other reprocessing equipment).

**pg_notify** -- Postgres function for publishing notifications to listeners on a named channel. The earlier ingest design used this for fan-out; we replaced it with Kafka.

**Redpanda** -- Kafka-API-compatible broker, written in C++, single binary, no Zookeeper or KRaft co-process. We use it as the local-dev broker; same API as managed Kafka services if we ever migrate.

**RFID** -- _Radio-Frequency Identification._ Wireless tag-and-reader technology; an alternative to barcodes for tray and instrument tracking.

**RPO** -- _Recovery Point Objective._ The maximum acceptable data loss measured in time. ISL's RPO target is 5 minutes.

**RTO** -- _Recovery Time Objective._ The maximum acceptable downtime after an incident. ISL's RTO target is 4 hours.

**SCD-2** -- _Slowly Changing Dimension type 2._ A warehouse-modeling pattern that tracks changes to dimension records by appending new rows with validity windows rather than updating in place.

**Schema Registry** -- Service (built into Redpanda) that stores versioned schemas keyed by subject (typically `<topic>-value`). Producers and consumers fetch schemas from it; enforces forward/backward compatibility on registration.

**SIU** -- HL7 v2 _Scheduling Information Unsolicited._ The message type a hospital EHR uses to push OR-schedule events (new case, reschedule, cancel).

**SLA** -- _Service-Level Agreement._ Contractual on-time-return promise we make to client hospitals.

**SPD** -- _Sterile Processing Department._ The hospital function that cleans, inspects, assembles, sterilizes, and packages surgical instruments. The pipeline this whole project orchestrates.

**SPM** -- Commercial single-facility SPD tracking system (vendor name; not strictly an acronym). One of the incumbents alongside CensiTrac.

**ST79** -- AAMI's _ST79: Comprehensive guide to steam sterilization and sterility assurance._ The procedural standard reprocessing facilities are audited against.

**UDI** -- _Unique Device Identification._ FDA-mandated identifier system for medical devices, including (for some classes) individual surgical instruments.

**UUID / UUIDv4 / UUIDv5 / UUIDv7** -- _Universally Unique Identifier._ v4 is random; v5 is deterministic from a namespace + name (we use this for `event_id`); v7 embeds a timestamp prefix so IDs sort chronologically.

**WIP** -- _Work In Progress._ In a queueing context, the number of items currently between two stations.
