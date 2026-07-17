# ADR-0002: Feast Offline Store Selection

## Status
Accepted (implemented 2026-07-17, `feature_store/feature_repo/`)

## Context
Feast does not natively support TimescaleDB as an offline store. The stack lists
both TimescaleDB and Feast, creating an integration gap. Options considered:
1. Custom `TimescaleOfflineStore` implementation
2. Postgres offline store (Feast-supported) with Timescale extensions
3. File (Parquet) offline store + SQLite online store (dev/CI) / Redis (prod)

## Decision
Use the **file (Parquet) offline store** + **SQLite online store** for dev/CI,
with a documented migration path to a **Redis online store** for production.

Rationale:
- The file/parquet offline store is the most stable, well-tested Feast backend.
- Avoids custom plugin maintenance burden.
- TimescaleDB remains the system-of-record for time-series queries outside Feast.
- SQLite avoids a Docker dependency in CI (tests must run without external services).
- Production can swap SQLite -> Redis in `feature_store.yaml` without code changes.

## Implementation notes (Feast 0.64)
- `offline_store.type: file` (NOT `parquet` — that is not a valid store type;
  parquet is the *source* format).
- The source is a `FileSource` with `file_format=ParquetFormat()` (an instance,
  not the string `"parquet"`).
- `feast apply` requires explicit objects passed in code in 0.64.
- The `symbol` Entity declares `value_type=ValueType.STRING`.

## Consequences
- Feature materialization writes Parquet to `data/offline/` (dev) or S3/MinIO (prod).
- Online serving uses SQLite (dev) or Redis (prod).
- All FeatureViews MUST set `timestamp_field=event_ts` (event) and
  `created_timestamp_column=as_of_ts` (disclosure) to enforce PIT discipline.

## Verification
`tests/unit/test_feature_store.py` — 2 tests: repo applies + entity/feature-view
registered; PIT timestamp columns (`event_ts`/`as_of_ts`) wired correctly.
