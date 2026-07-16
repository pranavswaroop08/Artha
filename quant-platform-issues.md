# Quantitative Platform - GitHub Issues Backlog (150)

Ordered by dependency. Each issue is scoped to 1-3h and independently completable given its prerequisites.

## Dependency key
- `Depends on`: issue IDs that must be merged first.
- `Est`: estimated effort (1-3h).
- `AC`: acceptance criteria. `Files`: required files. `Tests`: required tests. `Docs`: documentation.

## P0 - 18 issues

### ISS-001 · Init monorepo + pyproject.toml
- **Phase**: P0  |  **Est**: 1h  |  **Depends on**: -
- **Acceptance Criteria**
  - Repo scaffolds with src/, tests/, configs/, docs/ per architecture.
  - `pyproject.toml` declares deps (pandas, polars, sklearn, xgboost, lightgbm, catboost, pytorch, feast, mlflow, optuna, fastapi, structlog).
  - `make install` resolves a clean editable env.
- **Files**: pyproject.toml, Makefile, src/__init__.py, README.md
- **Tests**: tests/test_imports.py
- **Docs**: docs/README.md (repo layout)

### ISS-002 · Pre-commit: ruff, black, mypy
- **Phase**: P0  |  **Est**: 1h  |  **Depends on**: ISS-001
- **Acceptance Criteria**
  - `.pre-commit-config.yaml` runs ruff (lint+import sort), black, mypy on staged files.
  - `make lint` and `make type` pass locally on empty scaffold.
- **Files**: .pre-commit-config.yaml, .ruff.toml, Makefile
- **Tests**: -
- **Docs**: docs/STYLE.md

### ISS-003 · GitHub Actions CI skeleton
- **Phase**: P0  |  **Est**: 2h  |  **Depends on**: ISS-001, ISS-002
- **Acceptance Criteria**
  - Workflow runs on PR: lint -> type -> unit tests -> build.
  - Fails build on any stage error; artifacts uploaded.
  - Requires green CI before merge (branch protection).
- **Files**: .github/workflows/ci.yml, .github/pull_request_template.md
- **Tests**: -
- **Docs**: docs/CI.md

### ISS-004 · Hydra/OmegaConf config system
- **Phase**: P0  |  **Est**: 2h  |  **Depends on**: ISS-001
- **Acceptance Criteria**
  - `configs/` has base + env overlays (dev/staging/prod).
  - `load_config()` returns typed config; secrets resolved from env.
  - Example run prints merged config.
- **Files**: configs/config.yaml, configs/data/*.yaml, src/common/config.py
- **Tests**: tests/common/test_config.py
- **Docs**: docs/CONFIG.md

### ISS-005 · Structured logging + correlation IDs
- **Phase**: P0  |  **Est**: 2h  |  **Depends on**: ISS-001
- **Acceptance Criteria**
  - `structlog` JSON logs with ts, level, module, correlation_id.
  - Context var propagates correlation_id across calls.
  - Log to stdout + file; no secrets leaked.
- **Files**: src/logging/structured.py, src/common/context.py
- **Tests**: tests/logging/test_structured.py
- **Docs**: docs/LOGGING.md

### ISS-006 · Exception hierarchy + common utils
- **Phase**: P0  |  **Est**: 1h  |  **Depends on**: ISS-001
- **Acceptance Criteria**
  - Typed exceptions (DataError, ModelError, ConfigError, LeakageError).
  - Utils: safe_div, nan_guard, hash_payload.
- **Files**: src/common/exceptions.py, src/common/utils.py
- **Tests**: tests/common/test_utils.py
- **Docs**: -

### ISS-007 · Time utils: IST, trading calendar
- **Phase**: P0  |  **Est**: 2h  |  **Depends on**: ISS-001
- **Acceptance Criteria**
  - `to_ist()`, trading-day list for NSE/BSE (excl. holidays).
  - `is_trading_day()`, `next_expiry_thursday()`.
  - Handles weekly expiry + budget/election closures via config.
- **Files**: src/common/time_utils.py, configs/holidays.yaml
- **Tests**: tests/common/test_time_utils.py
- **Docs**: docs/CALENDAR.md

### ISS-008 · Object store client (S3/MinIO)
- **Phase**: P0  |  **Est**: 2h  |  **Depends on**: ISS-001, ISS-004
- **Acceptance Criteria**
  - `put_raw(bucket,key,payload)`, `get_raw`, `list_prefix` with idempotent write + content hash.
  - MinIO works locally via docker-compose.
- **Files**: src/data/raw_lake.py
- **Tests**: tests/data/test_raw_lake.py
- **Docs**: docs/STORAGE.md

### ISS-009 · Postgres schema + Alembic migrations
- **Phase**: P0  |  **Est**: 2h  |  **Depends on**: ISS-001
- **Acceptance Criteria**
  - Tables: symbols, corporate_actions, fundamentals_meta, runs.
  - `alembic upgrade head` creates schema in dev DB.
- **Files**: migrations/env.py, migrations/versions/*.py, src/data/db.py
- **Tests**: tests/data/test_db.py
- **Docs**: docs/SCHEMA.md

### ISS-010 · TimescaleDB hypertables
- **Phase**: P0  |  **Est**: 2h  |  **Depends on**: ISS-009
- **Acceptance Criteria**
  - Hypertables: prices_eod, prices_intraday, options_chain, vix.
  - Continuous aggregates for daily rollups.
  - Insert + range query <100ms for 1y.
- **Files**: migrations/versions/timescale.sql, src/data/tsdb.py
- **Tests**: tests/data/test_tsdb.py
- **Docs**: docs/SCHEMA.md

### ISS-011 · Redis cache client wrapper
- **Phase**: P0  |  **Est**: 1h  |  **Depends on**: ISS-001
- **Acceptance Criteria**
  - `get/set` with TTL, JSON serialization, namespacing.
  - Health check + reconnect on failure.
- **Files**: src/common/redis_client.py
- **Tests**: tests/common/test_redis.py
- **Docs**: -

### ISS-012 · Qdrant vector DB client
- **Phase**: P0  |  **Est**: 1h  |  **Depends on**: ISS-001
- **Acceptance Criteria**
  - `upsert(collection, vectors, payloads)`, `search`, collection create/recreate.
  - Local Qdrant via docker-compose.
- **Files**: src/nlp/vector_store.py
- **Tests**: tests/nlp/test_vector_store.py
- **Docs**: -

### ISS-013 · MLflow tracking + experiment registry
- **Phase**: P0  |  **Est**: 2h  |  **Depends on**: ISS-001
- **Acceptance Criteria**
  - `log_run(params,metrics,artifact)`; experiment per model family.
  - Model registry stages: None->Staging->Production.
- **Files**: src/models/registry.py, configs/mlflow.yaml
- **Tests**: tests/models/test_registry.py
- **Docs**: docs/EXPERIMENTS.md

### ISS-014 · Docker base images (python/ml/serve)
- **Phase**: P0  |  **Est**: 2h  |  **Depends on**: ISS-001
- **Acceptance Criteria**
  - 3 Dockerfiles: base (deps), ml (torch), serve (fastapi).
  - Build passes; image size reported.
- **Files**: docker/Dockerfile.base, docker/Dockerfile.ml, docker/Dockerfile.serve
- **Tests**: -
- **Docs**: docs/DOCKER.md

### ISS-015 · Docker-compose local stack
- **Phase**: P0  |  **Est**: 2h  |  **Depends on**: ISS-008, ISS-009, ISS-010, ISS-011, ISS-012
- **Acceptance Criteria**
  - Compose: postgres+timescale, redis, minio, qdrant, mlflow.
  - `make dev-up` brings stack up healthy.
- **Files**: docker-compose.yml, .env.example
- **Tests**: tests/integration/test_compose_health.py
- **Docs**: docs/LOCAL_DEV.md

### ISS-016 · Kubernetes base manifests / Helm skeleton
- **Phase**: P0  |  **Est**: 3h  |  **Depends on**: ISS-014
- **Acceptance Criteria**
  - Helm chart with deployable placeholders for ingest/train/serve.
  - `helm template` renders without errors.
- **Files**: k8s/Chart.yaml, k8s/templates/*.yaml
- **Tests**: -
- **Docs**: docs/K8S.md

### ISS-017 · Secrets management (Vault/env)
- **Phase**: P0  |  **Est**: 2h  |  **Depends on**: ISS-004, ISS-015
- **Acceptance Criteria**
  - Config loader resolves secrets from env or Vault agent.
  - No secret committed; `.env.example` documents keys.
- **Files**: src/common/secrets.py, configs/secrets.example.yaml
- **Tests**: tests/common/test_secrets.py
- **Docs**: docs/SECRETS.md

### ISS-018 · Makefile + dev bootstrap
- **Phase**: P0  |  **Est**: 1h  |  **Depends on**: ISS-003, ISS-015
- **Acceptance Criteria**
  - `make bootstrap` installs, starts stack, runs migrations.
  - Contributor can go from clone to green `make test` in one command.
- **Files**: Makefile, scripts/bootstrap.sh
- **Tests**: -
- **Docs**: README.md (Quickstart)

## P1 - 26 issues

### ISS-019 · Raw lake writer + immutable payload schema
- **Phase**: P1  |  **Est**: 2h  |  **Depends on**: ISS-008
- **Acceptance Criteria**
  - Every collector writes raw JSON/Parquet with `source, as_of_ts, event_ts, payload_hash`.
  - Writes are append-only + idempotent by natural key.
- **Files**: src/data/raw_lake.py, configs/data/raw.yaml
- **Tests**: tests/data/test_raw_lake_write.py
- **Docs**: docs/DATA_CONTRACTS.md

### ISS-020 · Symbol master + NSE/BSE/ISIN reconciliation
- **Phase**: P1  |  **Est**: 2h  |  **Depends on**: ISS-009
- **Acceptance Criteria**
  - Unified symbol table linking NSE ticker, BSE code, ISIN, industry, series.
  - Reconciliation handles re-listings/splits.
- **Files**: src/data/symbols.py, migrations/symbols.sql
- **Tests**: tests/data/test_symbols.py
- **Docs**: docs/SYMBOLS.md

### ISS-021 · NSE EOD collector (vendor)
- **Phase**: P1  |  **Est**: 2h  |  **Depends on**: ISS-019, ISS-020
- **Acceptance Criteria**
  - Pulls EOD + delivery % via configured vendor; writes raw + cleaned TS.
  - Handles pagination, rate limits, retries.
- **Files**: src/data/collectors/nse.py
- **Tests**: tests/data/collectors/test_nse.py
- **Docs**: docs/SOURCES.md#nse

### ISS-022 · BSE EOD collector
- **Phase**: P1  |  **Est**: 2h  |  **Depends on**: ISS-019, ISS-020
- **Acceptance Criteria**
  - Pulls BSE EOD; reconciles to symbol master; writes raw+cleaned.
- **Files**: src/data/collectors/bse.py
- **Tests**: tests/data/collectors/test_bse.py
- **Docs**: docs/SOURCES.md#bse

### ISS-023 · Yahoo Finance collector (backup)
- **Phase**: P1  |  **Est**: 2h  |  **Depends on**: ISS-019, ISS-020
- **Acceptance Criteria**
  - Pulls adj EOD + index + global proxies; flagged lower-trust.
  - Validation gate rejects on gaps before use as primary.
- **Files**: src/data/collectors/yfinance.py
- **Tests**: tests/data/collectors/test_yfinance.py
- **Docs**: docs/SOURCES.md#yahoo

### ISS-024 · Corporate actions + PIT adjustment engine
- **Phase**: P1  |  **Est**: 3h  |  **Depends on**: ISS-020, ISS-009
- **Acceptance Criteria**
  - Collects splits/bonus/dividends with ex-date.
  - Adjusts price/return series point-in-time so returns are total-return correct.
  - Reconciles adjusted vs raw within tolerance.
- **Files**: src/data/collectors/corporate_actions.py, src/data/adjustments.py
- **Tests**: tests/data/test_adjustments.py
- **Docs**: docs/CORP_ACTIONS.md

### ISS-025 · Financial statements collector
- **Phase**: P1  |  **Est**: 2h  |  **Depends on**: ISS-019, ISS-020
- **Acceptance Criteria**
  - Collects balance sheet / P&L / cash flow quarterly; normalized to standard schema.
  - Tags each filing with disclosure `as_of_ts`.
- **Files**: src/data/collectors/fundamentals.py
- **Tests**: tests/data/collectors/test_fundamentals.py
- **Docs**: docs/SOURCES.md#fundamentals

### ISS-026 · Quarterly earnings collector + event flags
- **Phase**: P1  |  **Est**: 2h  |  **Depends on**: ISS-025
- **Acceptance Criteria**
  - Captures earnings dates, results timestamps, guidance flags.
  - Emits earnings-event table used by NLP + features.
- **Files**: src/data/collectors/quarterly_earnings.py
- **Tests**: tests/data/collectors/test_earnings.py
- **Docs**: docs/SOURCES.md#earnings

### ISS-027 · Promoter holdings collector
- **Phase**: P1  |  **Est**: 2h  |  **Depends on**: ISS-019, ISS-020
- **Acceptance Criteria**
  - Collects promoter %, pledge %, changes; point-in-time.
- **Files**: src/data/collectors/promoter.py
- **Tests**: tests/data/collectors/test_promoter.py
- **Docs**: docs/SOURCES.md#promoter

### ISS-028 · FII/DII activity collector
- **Phase**: P1  |  **Est**: 2h  |  **Depends on**: ISS-019, ISS-020
- **Acceptance Criteria**
  - Daily FII/DII cash + F&O positioning by category; sector flow aggregation.
- **Files**: src/data/collectors/fii_dii.py
- **Tests**: tests/data/collectors/test_fii_dii.py
- **Docs**: docs/SOURCES.md#fii_dii

### ISS-029 · Mutual fund holdings collector
- **Phase**: P1  |  **Est**: 2h  |  **Depends on**: ISS-019, ISS-020
- **Acceptance Criteria**
  - Quarterly MF portfolios -> stake %, chg qoq; accumulation/distribution flags.
- **Files**: src/data/collectors/mf_holdings.py
- **Tests**: tests/data/collectors/test_mf.py
- **Docs**: docs/SOURCES.md#mf

### ISS-030 · Options chain collector (NSE F&O)
- **Phase**: P1  |  **Est**: 3h  |  **Depends on**: ISS-019, ISS-020
- **Acceptance Criteria**
  - Pulls full chain (calls/puts, OI, IV, volume) per expiry.
  - Computes PCR, max pain, IV skew at collection time.
- **Files**: src/data/collectors/options_chain.py
- **Tests**: tests/data/collectors/test_options.py
- **Docs**: docs/SOURCES.md#options

### ISS-031 · India VIX collector
- **Phase**: P1  |  **Est**: 1h  |  **Depends on**: ISS-019
- **Acceptance Criteria**
  - Daily India VIX series; intraday optional.
- **Files**: src/data/collectors/india_vix.py
- **Tests**: tests/data/collectors/test_vix.py
- **Docs**: docs/SOURCES.md#vix

### ISS-032 · USDINR collector
- **Phase**: P1  |  **Est**: 1h  |  **Depends on**: ISS-019
- **Acceptance Criteria**
  - Spot + forward USDINR daily.
- **Files**: src/data/collectors/usdinr.py
- **Tests**: tests/data/collectors/test_usdinr.py
- **Docs**: docs/SOURCES.md#usdinr

### ISS-033 · Gold + Crude Oil collector
- **Phase**: P1  |  **Est**: 2h  |  **Depends on**: ISS-019
- **Acceptance Criteria**
  - MCX gold + crude (or proxy) daily; INR-denominated.
- **Files**: src/data/collectors/commodities.py
- **Tests**: tests/data/collectors/test_commodities.py
- **Docs**: docs/SOURCES.md#commodities

### ISS-034 · RBI announcements collector + policy dummy
- **Phase**: P1  |  **Est**: 2h  |  **Depends on**: ISS-019
- **Acceptance Criteria**
  - Captures policy dates, repo changes, statements; emits policy-window + surprise dummy.
- **Files**: src/data/collectors/rbi.py
- **Tests**: tests/data/collectors/test_rbi.py
- **Docs**: docs/SOURCES.md#rbi

### ISS-035 · Inflation (CPI/IIP) collector
- **Phase**: P1  |  **Est**: 2h  |  **Depends on**: ISS-019
- **Acceptance Criteria**
  - Monthly CPI/IIP + consensus; inflation-surprise feature source.
- **Files**: src/data/collectors/macro.py
- **Tests**: tests/data/collectors/test_macro.py
- **Docs**: docs/SOURCES.md#macro

### ISS-036 · Interest rates / G-sec collector
- **Phase**: P1  |  **Est**: 1h  |  **Depends on**: ISS-019
- **Acceptance Criteria**
  - 10Y G-sec yield, repo, yield-curve points.
- **Files**: src/data/collectors/rates.py
- **Tests**: tests/data/collectors/test_rates.py
- **Docs**: docs/SOURCES.md#rates

### ISS-037 · GDP collector
- **Phase**: P1  |  **Est**: 1h  |  **Depends on**: ISS-019
- **Acceptance Criteria**
  - Quarterly real GDP + forecasts; slow regime factor.
- **Files**: src/data/collectors/gdp.py
- **Tests**: tests/data/collectors/test_gdp.py
- **Docs**: docs/SOURCES.md#gdp

### ISS-038 · Economic calendar collector
- **Phase**: P1  |  **Est**: 2h  |  **Depends on**: ISS-019
- **Acceptance Criteria**
  - Known events (RBI, CPI, GDP, elections, expiry) -> binary dummies + days-to-event.
- **Files**: src/data/collectors/economic_calendar.py
- **Tests**: tests/data/collectors/test_calendar.py
- **Docs**: docs/SOURCES.md#calendar

### ISS-039 · News collector (RSS + APIs)
- **Phase**: P1  |  **Est**: 3h  |  **Depends on**: ISS-019, ISS-020
- **Acceptance Criteria**
  - Pulls from RSS + vendor APIs; dedup; links to symbols via NER placeholder.
  - Stores raw articles with timestamps.
- **Files**: src/data/collectors/news/__init__.py, src/data/collectors/news/rss.py, src/data/collectors/news/api.py
- **Tests**: tests/data/collectors/news/test_news.py
- **Docs**: docs/SOURCES.md#news

### ISS-040 · Social sentiment collector
- **Phase**: P1  |  **Est**: 3h  |  **Depends on**: ISS-019, ISS-020
- **Acceptance Criteria**
  - Collects X/TradingView/forum posts; rate-limited; stores text + engagement.
- **Files**: src/data/collectors/social/__init__.py
- **Tests**: tests/data/collectors/social/test_social.py
- **Docs**: docs/SOURCES.md#social

### ISS-041 · Annual reports collector + ingest
- **Phase**: P1  |  **Est**: 2h  |  **Depends on**: ISS-019, ISS-020
- **Acceptance Criteria**
  - Downloads annual report PDFs/HTML; stores refs + metadata for NLP.
- **Files**: src/data/collectors/annual_reports.py
- **Tests**: tests/data/collectors/test_annual.py
- **Docs**: docs/SOURCES.md#annual

### ISS-042 · Data validation framework + contracts
- **Phase**: P1  |  **Est**: 3h  |  **Depends on**: ISS-019
- **Acceptance Criteria**
  - Pandera/Great Expectations schemas per source.
  - Reject on missing cols, stale ts, negative/zero price, dup keys, broken CA continuity.
- **Files**: src/data/validators.py, configs/data/contracts/*.yaml
- **Tests**: tests/data/test_validators.py
- **Docs**: docs/VALIDATION.md

### ISS-043 · Point-in-time lineage tracker
- **Phase**: P1  |  **Est**: 3h  |  **Depends on**: ISS-024, ISS-042
- **Acceptance Criteria**
  - Every fact carries `as_of_ts` (public) + `event_ts`; fundamentals/earnings invisible before disclosure.
  - Lineage log records transforms (OpenLineage-lite).
- **Files**: src/data/pit.py, src/data/lineage.py
- **Tests**: tests/data/test_pit.py
- **Docs**: docs/PIT.md

### ISS-044 · Orchestration DAGs (nightly ingest)
- **Phase**: P1  |  **Est**: 3h  |  **Depends on**: ISS-021, ISS-022, ISS-042
- **Acceptance Criteria**
  - Airflow/Prefect DAGs run collectors in dependency order with retries + alerts.
  - Manual backfill command per source.
- **Files**: airflow/dags/ingest_daily.py, airflow/plugins/
- **Tests**: tests/integration/test_dag_import.py
- **Docs**: docs/ORCHESTRATION.md

## P2 - 21 issues

### ISS-045 · Feature store setup (Feast)
- **Phase**: P2  |  **Est**: 3h  |  **Depends on**: ISS-010, ISS-011
- **Acceptance Criteria**
  - Feast repo connects offline (TS DB) + online (Redis).
  - `feast apply` creates infra; `get_historical_features` works.
- **Files**: feature_store/feature_store.yaml, feature_store/definitions.py
- **Tests**: tests/features/test_feast_smoke.py
- **Docs**: docs/FEATURE_STORE.md

### ISS-046 · Feature registry (catalog, 600+ defs)
- **Phase**: P2  |  **Est**: 3h  |  **Depends on**: ISS-045
- **Acceptance Criteria**
  - `features/registry.py` declares each feature: id, source, window, PIT rule, owner, transformer.
  - `list_features()` + metadata export to YAML.
- **Files**: src/features/registry.py, configs/features/registry.yaml
- **Tests**: tests/features/test_registry.py
- **Docs**: docs/FEATURES.md

### ISS-047 · Price / return features
- **Phase**: P2  |  **Est**: 2h  |  **Depends on**: ISS-046, ISS-024
- **Acceptance Criteria**
  - Log returns over [1,2,3,5,10,21,42,63,126,252]d; open/close, gap%, range%, VWAP-relative.
- **Files**: src/features/price.py
- **Tests**: tests/features/test_price.py
- **Docs**: docs/FEATURES.md#price

### ISS-048 · Volume features
- **Phase**: P2  |  **Est**: 2h  |  **Depends on**: ISS-046
- **Acceptance Criteria**
  - Vol/avg ratio, z-score, OBV, CMF, MFI, up/down vol, delivery%.
- **Files**: src/features/volume.py
- **Tests**: tests/features/test_volume.py
- **Docs**: docs/FEATURES.md#volume

### ISS-049 · Momentum features
- **Phase**: P2  |  **Est**: 2h  |  **Depends on**: ISS-047
- **Acceptance Criteria**
  - ROC multi-window, dual/triple momentum, cross-sectional rank, 12-1, short-term reversal.
- **Files**: src/features/momentum.py
- **Tests**: tests/features/test_momentum.py
- **Docs**: docs/FEATURES.md#momentum

### ISS-050 · Volatility features
- **Phase**: P2  |  **Est**: 2h  |  **Depends on**: ISS-047
- **Acceptance Criteria**
  - Rolling std, Parkinson, Garman-Klass, Yang-Zhang, ATR, vol-of-vol, skew/kurt, VIX corr.
- **Files**: src/features/volatility.py
- **Tests**: tests/features/test_volatility.py
- **Docs**: docs/FEATURES.md#volatility

### ISS-051 · Trend features
- **Phase**: P2  |  **Est**: 2h  |  **Depends on**: ISS-047
- **Acceptance Criteria**
  - SMA/EMA vs price, golden/death cross, ADX, DMI, SAR, Ichimoku, regression slope, Hurst.
- **Files**: src/features/trend.py
- **Tests**: tests/features/test_trend.py
- **Docs**: docs/FEATURES.md#trend

### ISS-052 · Market breadth features
- **Phase**: P2  |  **Est**: 2h  |  **Depends on**: ISS-021, ISS-022
- **Acceptance Criteria**
  - A/D line+ratio, McClellan, % above 50/200 DMA, new highs/lows, TRIN, breadth thrust.
- **Files**: src/features/breadth.py
- **Tests**: tests/features/test_breadth.py
- **Docs**: docs/FEATURES.md#breadth

### ISS-053 · Sector / industry strength
- **Phase**: P2  |  **Est**: 2h  |  **Depends on**: ISS-020, ISS-047
- **Acceptance Criteria**
  - Sector index momentum, RS vs Nifty, industry rank, peer median, sector flow.
- **Files**: src/features/sector.py
- **Tests**: tests/features/test_sector.py
- **Docs**: docs/FEATURES.md#sector

### ISS-054 · Correlation / coherence
- **Phase**: P2  |  **Est**: 2h  |  **Depends on**: ISS-047, ISS-031, ISS-032
- **Acceptance Criteria**
  - Rolling corr with Nifty/BankNifty/sector/USDINR/gold/crude; rolling beta; idiosyncratic vol.
- **Files**: src/features/correlation.py
- **Tests**: tests/features/test_correlation.py
- **Docs**: docs/FEATURES.md#correlation

### ISS-055 · Relative strength
- **Phase**: P2  |  **Est**: 1h  |  **Depends on**: ISS-047, ISS-053
- **Acceptance Criteria**
  - RS vs index/sector/peer median; percentile rank of price.
- **Files**: src/features/rs.py
- **Tests**: tests/features/test_rs.py
- **Docs**: docs/FEATURES.md#rs

### ISS-056 · Candlestick patterns
- **Phase**: P2  |  **Est**: 3h  |  **Depends on**: ISS-047
- **Acceptance Criteria**
  - ~30 patterns (doji, hammer, engulfing, harami, stars, soldiers, marubozu...) boolean + strength.
- **Files**: src/features/candlestick.py
- **Tests**: tests/features/test_candlestick.py
- **Docs**: docs/FEATURES.md#candles

### ISS-057 · Support / resistance
- **Phase**: P2  |  **Est**: 2h  |  **Depends on**: ISS-047
- **Acceptance Criteria**
  - Pivot/classic/Camarilla/Fib; local extrema; 52w hi/lo distance; VBP zones; breakout flags.
- **Files**: src/features/support_resistance.py
- **Tests**: tests/features/test_sr.py
- **Docs**: docs/FEATURES.md#sr

### ISS-058 · Options features
- **Phase**: P2  |  **Est**: 3h  |  **Depends on**: ISS-030
- **Acceptance Criteria**
  - PCR, max pain, IV skew (25d risk reversal), IV term, ATM IV%, gamma proxy, OI build-up, FII fut pos.
- **Files**: src/features/options.py
- **Tests**: tests/features/test_options_feat.py
- **Docs**: docs/FEATURES.md#options

### ISS-059 · Macro / cross-asset
- **Phase**: P2  |  **Est**: 2h  |  **Depends on**: ISS-031, ISS-032, ISS-033, ISS-034, ISS-035, ISS-036
- **Acceptance Criteria**
  - VIX level/chg, USDINR ret, G-sec yield, crude/gold ret, rate diff, CPI surprise, IIP, global (S&P/Nasdaq/DXY), monsoon, policy dummy.
- **Files**: src/features/macro.py
- **Tests**: tests/features/test_macro_feat.py
- **Docs**: docs/FEATURES.md#macro

### ISS-060 · Fundamental ratios (PIT)
- **Phase**: P2  |  **Est**: 3h  |  **Depends on**: ISS-025, ISS-043
- **Acceptance Criteria**
  - Valuation/growth/profitability/leverage/quality/earnings-surprise from filings, point-in-time.
- **Files**: src/features/fundamental.py
- **Tests**: tests/features/test_fundamental.py
- **Docs**: docs/FEATURES.md#fundamentals

### ISS-061 · Time / calendar
- **Phase**: P2  |  **Est**: 1h  |  **Depends on**: ISS-007, ISS-038
- **Acceptance Criteria**
  - DOW, month, quarter-end, expiry-week, pre/post earnings/budget/election, seasonality, festival dummies.
- **Files**: src/features/time.py
- **Tests**: tests/features/test_time.py
- **Docs**: docs/FEATURES.md#time

### ISS-062 · Rolling statistics
- **Phase**: P2  |  **Est**: 2h  |  **Depends on**: ISS-047, ISS-048
- **Acceptance Criteria**
  - Rolling mean/std/skew/kurt/min/max/quantile of returns/vol/spread; rolling Sharpe/Sortino/Calmar.
- **Files**: src/features/rolling.py
- **Tests**: tests/features/test_rolling.py
- **Docs**: docs/FEATURES.md#rolling

### ISS-063 · Lag / autoregressive
- **Phase**: P2  |  **Est**: 2h  |  **Depends on**: ISS-047
- **Acceptance Criteria**
  - Lagged returns/vol/volume (1..N), AR residuals, ACF/PACF features.
- **Files**: src/features/lags.py
- **Tests**: tests/features/test_lags.py
- **Docs**: docs/FEATURES.md#lags

### ISS-064 · Target / categorical encoding (OOF)
- **Phase**: P2  |  **Est**: 2h  |  **Depends on**: ISS-046
- **Acceptance Criteria**
  - Industry one-hot/hash, peer-cluster id, regime label, out-of-fold target encoding (leakage-safe).
- **Files**: src/features/target_encoding.py
- **Tests**: tests/features/test_encoding.py
- **Docs**: docs/FEATURES.md#encoding

### ISS-065 · Feature materialization job
- **Phase**: P2  |  **Est**: 2h  |  **Depends on**: ISS-045, ISS-047, ISS-064
- **Acceptance Criteria**
  - Batch job computes all registered features point-in-time -> offline store; backfill + incremental.
- **Files**: src/features/materialize.py
- **Tests**: tests/features/test_materialize.py
- **Docs**: docs/FEATURE_STORE.md

## P3 - 14 issues

### ISS-066 · Dataset builder (X,y, time split)
- **Phase**: P3  |  **Est**: 2h  |  **Depends on**: ISS-065
- **Acceptance Criteria**
  - Builds feature matrix + multi-target from feature store by symbol/date.
  - Honors PIT; no future rows in train.
- **Files**: src/models/dataset.py
- **Tests**: tests/models/test_dataset.py
- **Docs**: docs/TRAINING.md#dataset

### ISS-067 · Target definitions + horizons
- **Phase**: P3  |  **Est**: 2h  |  **Depends on**: ISS-066
- **Acceptance Criteria**
  - direction (sign fwd ret), return (reg), vol (reg) over H in {1,5,21,63}.
  - Handles delisting/illiquidity guards.
- **Files**: src/models/targets.py
- **Tests**: tests/models/test_targets.py
- **Docs**: docs/TRAINING.md#targets

### ISS-068 · Common trainer interface
- **Phase**: P3  |  **Est**: 2h  |  **Depends on**: ISS-066, ISS-067
- **Acceptance Criteria**
  - `Trainer.fit/predict` wrapping sklearn; uniform API; saves artifacts + metrics.
- **Files**: src/models/trainers.py
- **Tests**: tests/models/test_trainers.py
- **Docs**: docs/TRAINING.md#trainer

### ISS-069 · LightGBM baseline
- **Phase**: P3  |  **Est**: 2h  |  **Depends on**: ISS-068
- **Acceptance Criteria**
  - LightGBM for all 3 targets; categorical handling; baseline metrics logged.
- **Files**: src/models/ml/lgbm.py
- **Tests**: tests/models/ml/test_lgbm.py
- **Docs**: docs/MODELS.md#lgbm

### ISS-070 · CatBoost baseline
- **Phase**: P3  |  **Est**: 2h  |  **Depends on**: ISS-068
- **Acceptance Criteria**
  - CatBoost with native categoricals + ordered boosting; PIT-safe.
- **Files**: src/models/ml/catboost.py
- **Tests**: tests/models/ml/test_catboost.py
- **Docs**: docs/MODELS.md#catboost

### ISS-071 · XGBoost baseline
- **Phase**: P3  |  **Est**: 2h  |  **Depends on**: ISS-068
- **Acceptance Criteria**
  - XGBoost for all targets; strong tabular baseline.
- **Files**: src/models/ml/xgb.py
- **Tests**: tests/models/ml/test_xgb.py
- **Docs**: docs/MODELS.md#xgb

### ISS-072 · RandomForest baseline
- **Phase**: P3  |  **Est**: 1h  |  **Depends on**: ISS-068
- **Acceptance Criteria**
  - RF baseline + uncertainty estimate (tree variance).
- **Files**: src/models/ml/rf.py
- **Tests**: tests/models/ml/test_rf.py
- **Docs**: docs/MODELS.md#rf

### ISS-073 · HPO harness (Optuna)
- **Phase**: P3  |  **Est**: 3h  |  **Depends on**: ISS-069, ISS-070, ISS-071
- **Acceptance Criteria**
  - Multi-objective (IC + calibration) TPE with pruner; study persistence; parallel workers.
- **Files**: src/models/hpo.py
- **Tests**: tests/models/test_hpo.py
- **Docs**: docs/TRAINING.md#hpo

### ISS-074 · Probability calibration
- **Phase**: P3  |  **Est**: 2h  |  **Depends on**: ISS-069
- **Acceptance Criteria**
  - Isotonic/Platt on OOF preds; reliability curve + Brier reported.
- **Files**: src/models/calibration.py
- **Tests**: tests/models/test_calibration.py
- **Docs**: docs/TRAINING.md#calibration

### ISS-075 · Walk-forward validation engine
- **Phase**: P3  |  **Est**: 3h  |  **Depends on**: ISS-066, ISS-067
- **Acceptance Criteria**
  - Rolling train->val->test; aggregates OOS per fold; reproducible seeds.
- **Files**: src/training/walk_forward.py
- **Tests**: tests/training/test_walk_forward.py
- **Docs**: docs/TRAINING.md#walkforward

### ISS-076 · Purged K-fold CV + embargo
- **Phase**: P3  |  **Est**: 2h  |  **Depends on**: ISS-066
- **Acceptance Criteria**
  - Purged groups by time + embargo window; prevents cross-fold leakage.
- **Files**: src/training/ts_cv.py
- **Tests**: tests/training/test_ts_cv.py
- **Docs**: docs/TRAINING.md#cv

### ISS-077 · Leakage test harness (FutureLeak)
- **Phase**: P3  |  **Est**: 2h  |  **Depends on**: ISS-066, ISS-076
- **Acceptance Criteria**
  - Inject future feature -> assert model cannot learn it; CI gate.
- **Files**: src/training/leakage.py
- **Tests**: tests/training/test_leakage.py
- **Docs**: docs/TRAINING.md#leakage

### ISS-078 · Model evaluation metrics
- **Phase**: P3  |  **Est**: 2h  |  **Depends on**: ISS-067
- **Acceptance Criteria**
  - IC, rank-IC, AUC, Brier, ECE, regression MSE/R2; per-horizon + per-regime.
- **Files**: src/training/evaluate.py
- **Tests**: tests/training/test_evaluate.py
- **Docs**: docs/TRAINING.md#metrics

### ISS-079 · Model registry integration
- **Phase**: P3  |  **Est**: 2h  |  **Depends on**: ISS-013, ISS-069
- **Acceptance Criteria**
  - Trained models logged to MLflow; promotion Staging->Production gated.
- **Files**: src/models/registry.py
- **Tests**: tests/models/test_registry_integration.py
- **Docs**: docs/EXPERIMENTS.md

## P4 - 13 issues

### ISS-080 · Event-driven backtest core
- **Phase**: P4  |  **Est**: 3h  |  **Depends on**: ISS-066, ISS-067
- **Acceptance Criteria**
  - Bar-by-bar loop with portfolio state, cash, positions; deterministic given seed.
- **Files**: src/backtest/engine.py
- **Tests**: tests/backtest/test_engine_basic.py
- **Docs**: docs/BACKTEST.md

### ISS-081 · Indian cost model
- **Phase**: P4  |  **Est**: 3h  |  **Depends on**: ISS-080
- **Acceptance Criteria**
  - STT (0.025% intraday / 0.1% delivery), SEBI, exchange, stamp, GST 18%, DP, brokerage.
  - Unit-tested vs hand-computed examples.
- **Files**: src/backtest/costs.py
- **Tests**: tests/backtest/test_costs.py
- **Docs**: docs/BACKTEST.md#costs

### ISS-082 · Slippage model
- **Phase**: P4  |  **Est**: 2h  |  **Depends on**: ISS-080
- **Acceptance Criteria**
  - Volume-participation (Almgren-Chriss-lite) + spread proxy; expected + worst-case.
- **Files**: src/backtest/slippage.py
- **Tests**: tests/backtest/test_slippage.py
- **Docs**: docs/BACKTEST.md#slippage

### ISS-083 · Order types + partial fills
- **Phase**: P4  |  **Est**: 2h  |  **Depends on**: ISS-080
- **Acceptance Criteria**
  - MKT/LMT/SL/SL-M; partial fills; reject reasons logged.
- **Files**: src/backtest/orders.py
- **Tests**: tests/backtest/test_orders.py
- **Docs**: docs/BACKTEST.md#orders

### ISS-084 · Position sizing
- **Phase**: P4  |  **Est**: 2h  |  **Depends on**: ISS-080
- **Acceptance Criteria**
  - Fixed-fractional, fractional-Kelly (capped), vol-targeting; per-name cap.
- **Files**: src/backtest/positions.py
- **Tests**: tests/backtest/test_sizing.py
- **Docs**: docs/BACKTEST.md#sizing

### ISS-085 · Risk management
- **Phase**: P4  |  **Est**: 2h  |  **Depends on**: ISS-080, ISS-084
- **Acceptance Criteria**
  - Per-trade stop, trailing stop, max position%, sector cap, drawdown halt, vol circuit-breaker.
- **Files**: src/backtest/risk.py
- **Tests**: tests/backtest/test_risk.py
- **Docs**: docs/BACKTEST.md#risk

### ISS-086 · Portfolio optimization
- **Phase**: P4  |  **Est**: 3h  |  **Depends on**: ISS-080
- **Acceptance Criteria**
  - Markowitz mean-variance + Hierarchical Risk Parity (HRP default); weights constrained.
- **Files**: src/backtest/optimization.py
- **Tests**: tests/backtest/test_optimization.py
- **Docs**: docs/BACKTEST.md#optimization

### ISS-087 · Performance metrics
- **Phase**: P4  |  **Est**: 2h  |  **Depends on**: ISS-080
- **Acceptance Criteria**
  - Sharpe, Sortino, Calmar, MaxDD, ProfitFactor, CAGR, WinRate, expectancy, IR, alpha/beta.
- **Files**: src/backtest/metrics.py
- **Tests**: tests/backtest/test_metrics.py
- **Docs**: docs/BACKTEST.md#metrics

### ISS-088 · Deflated Sharpe ratio
- **Phase**: P4  |  **Est**: 1h  |  **Depends on**: ISS-087
- **Acceptance Criteria**
  - Bailey-Popelař deflated Sharpe + minimum track record length to reject luck.
- **Files**: src/backtest/deflated_sharpe.py
- **Tests**: tests/backtest/test_deflated_sharpe.py
- **Docs**: docs/BACKTEST.md#deflated

### ISS-089 · Backtest reporting (tearsheet)
- **Phase**: P4  |  **Est**: 2h  |  **Depends on**: ISS-087
- **Acceptance Criteria**
  - Equity curve, drawdown, monthly returns, trade blotter, plots -> HTML/PDF.
- **Files**: src/backtest/reports.py
- **Tests**: tests/backtest/test_reports.py
- **Docs**: docs/BACKTEST.md#reports

### ISS-090 · Multi-name portfolio runner
- **Phase**: P4  |  **Est**: 2h  |  **Depends on**: ISS-080, ISS-086
- **Acceptance Criteria**
  - Run signals across universe; aggregate portfolio; turnover/exposure tracked.
- **Files**: src/backtest/portfolio.py
- **Tests**: tests/backtest/test_portfolio.py
- **Docs**: docs/BACKTEST.md#portfolio

### ISS-091 · Walk-forward backtest integration
- **Phase**: P4  |  **Est**: 2h  |  **Depends on**: ISS-075, ISS-080
- **Acceptance Criteria**
  - Backtest over walk-forward folds; OOS aggregate vs in-sample guard.
- **Files**: src/backtest/walk_forward_run.py
- **Tests**: tests/backtest/test_wf_backtest.py
- **Docs**: docs/BACKTEST.md#walkforward

### ISS-092 · Cost model unit tests (golden)
- **Phase**: P4  |  **Est**: 2h  |  **Depends on**: ISS-081
- **Acceptance Criteria**
  - Hand-computed INR cost examples across trade types assert exact amounts.
- **Files**: tests/backtest/golden/test_costs_golden.py
- **Tests**: -
- **Docs**: docs/BACKTEST.md#costs

## P5 - 18 issues

### ISS-093 · PyTorch Lightning boilerplate
- **Phase**: P5  |  **Est**: 2h  |  **Depends on**: ISS-066
- **Acceptance Criteria**
  - Trainer wrapper: dataloaders (time-series sampler), logging, checkpoint, early-stop.
- **Files**: src/models/dl/base.py
- **Tests**: tests/models/dl/test_base.py
- **Docs**: docs/MODELS.md#dl

### ISS-094 · LSTM model
- **Phase**: P5  |  **Est**: 2h  |  **Depends on**: ISS-093
- **Acceptance Criteria**
  - Sequence model on raw series; multi-horizon + quantile heads.
- **Files**: src/models/dl/lstm.py
- **Tests**: tests/models/dl/test_lstm.py
- **Docs**: docs/MODELS.md#lstm

### ISS-095 · GRU model
- **Phase**: P5  |  **Est**: 2h  |  **Depends on**: ISS-093
- **Acceptance Criteria**
  - Lighter sequential model; same heads.
- **Files**: src/models/dl/gru.py
- **Tests**: tests/models/dl/test_gru.py
- **Docs**: docs/MODELS.md#gru

### ISS-096 · TFT model (primary deep)
- **Phase**: P5  |  **Est**: 3h  |  **Depends on**: ISS-093
- **Acceptance Criteria**
  - Temporal Fusion Transformer: static + known-future + observed-past; interpretable attention + variable selection.
- **Files**: src/models/dl/tft.py
- **Tests**: tests/models/dl/test_tft.py
- **Docs**: docs/MODELS.md#tft

### ISS-097 · N-BEATS model
- **Phase**: P5  |  **Est**: 2h  |  **Depends on**: ISS-093
- **Acceptance Criteria**
  - Univariate deep stack; benchmark/component.
- **Files**: src/models/dl/nbeats.py
- **Tests**: tests/models/dl/test_nbeats.py
- **Docs**: docs/MODELS.md#nbeats

### ISS-098 · PatchTST model
- **Phase**: P5  |  **Est**: 3h  |  **Depends on**: ISS-093
- **Acceptance Criteria**
  - Patch tokens + transformer encoder; long-series SOTA.
- **Files**: src/models/dl/patchtst.py
- **Tests**: tests/models/dl/test_patchtst.py
- **Docs**: docs/MODELS.md#patchtst

### ISS-099 · TimeMixer model
- **Phase**: P5  |  **Est**: 3h  |  **Depends on**: ISS-093
- **Acceptance Criteria**
  - Multi-scale past+future mixing; complements PatchTST.
- **Files**: src/models/dl/timemixer.py
- **Tests**: tests/models/dl/test_timemixer.py
- **Docs**: docs/MODELS.md#timemixer

### ISS-100 · TabNet model
- **Phase**: P5  |  **Est**: 2h  |  **Depends on**: ISS-093, ISS-066
- **Acceptance Criteria**
  - Attentive tabular DL for fundamental-heavy cross-section.
- **Files**: src/models/dl/tabnet.py
- **Tests**: tests/models/dl/test_tabnet.py
- **Docs**: docs/MODELS.md#tabnet

### ISS-101 · Transformer (encoder) model
- **Phase**: P5  |  **Est**: 3h  |  **Depends on**: ISS-093
- **Acceptance Criteria**
  - Feature-token + news-token cross-attention; optional research.
- **Files**: src/models/dl/transformer.py
- **Tests**: tests/models/dl/test_transformer.py
- **Docs**: docs/MODELS.md#transformer

### ISS-102 · DL quantile/multi-horizon heads
- **Phase**: P5  |  **Est**: 2h  |  **Depends on**: ISS-094
- **Acceptance Criteria**
  - Shared head producing mean + quantile forecasts for uncertainty.
- **Files**: src/models/dl/heads.py
- **Tests**: tests/models/dl/test_heads.py
- **Docs**: docs/MODELS.md#heads

### ISS-103 · NLP ingest + dedup
- **Phase**: P5  |  **Est**: 2h  |  **Depends on**: ISS-039, ISS-040
- **Acceptance Criteria**
  - Normalize news+social; dedup by hash; attach symbol candidates.
- **Files**: src/nlp/ingest_news.py, src/nlp/ingest_social.py
- **Tests**: tests/nlp/test_ingest.py
- **Docs**: docs/NLP.md#ingest

### ISS-104 · Entity linking (NER -> ISIN)
- **Phase**: P5  |  **Est**: 2h  |  **Depends on**: ISS-103, ISS-020
- **Acceptance Criteria**
  - Map article text to symbol(s) via NER + dictionary; confidence-scored.
- **Files**: src/nlp/entity_linking.py
- **Tests**: tests/nlp/test_entity_linking.py
- **Docs**: docs/NLP.md#ner

### ISS-105 · Sentiment scoring
- **Phase**: P5  |  **Est**: 2h  |  **Depends on**: ISS-103
- **Acceptance Criteria**
  - FinBERT + IndicBERT per-entity sentiment, volume, volatility-of-sentiment.
- **Files**: src/nlp/sentiment.py
- **Tests**: tests/nlp/test_sentiment.py
- **Docs**: docs/NLP.md#sentiment

### ISS-106 · Event extraction (LLM)
- **Phase**: P5  |  **Est**: 3h  |  **Depends on**: ISS-103, ISS-017
- **Acceptance Criteria**
  - Local LLM extracts typed events (earnings, M&A, reg, probe) + timestamps -> features + store.
- **Files**: src/nlp/event_extraction.py
- **Tests**: tests/nlp/test_event_extraction.py
- **Docs**: docs/NLP.md#events

### ISS-107 · Embeddings + Qdrant writes
- **Phase**: P5  |  **Est**: 2h  |  **Depends on**: ISS-103, ISS-012
- **Acceptance Criteria**
  - Sentence-transformers embeddings -> Qdrant with payload (symbol, ts, sentiment).
- **Files**: src/nlp/embeddings.py
- **Tests**: tests/nlp/test_embeddings.py
- **Docs**: docs/NLP.md#vectors

### ISS-108 · Transcript / annual tone scoring
- **Phase**: P5  |  **Est**: 2h  |  **Depends on**: ISS-026, ISS-041, ISS-105
- **Acceptance Criteria**
  - Earnings-call + annual-report tone/negativity/risk-section scoring via LLM.
- **Files**: src/nlp/tone.py
- **Tests**: tests/nlp/test_tone.py
- **Docs**: docs/NLP.md#tone

### ISS-109 · Summarizer (LLM)
- **Phase**: P5  |  **Est**: 2h  |  **Depends on**: ISS-106, ISS-108
- **Acceptance Criteria**
  - Condense last-N articles/events into 3-bullet briefing for explainability.
- **Files**: src/nlp/summarizer.py
- **Tests**: tests/nlp/test_summarizer.py
- **Docs**: docs/NLP.md#summary

### ISS-110 · NLP features -> feature store
- **Phase**: P5  |  **Est**: 2h  |  **Depends on**: ISS-045, ISS-105, ISS-107
- **Acceptance Criteria**
  - Persist sentiment/event/embedding features point-in-time into feature store.
- **Files**: src/nlp/nlp_features.py
- **Tests**: tests/nlp/test_nlp_features.py
- **Docs**: docs/NLP.md#features

## P6 - 10 issues

### ISS-111 · Level-1 ensemble runner
- **Phase**: P6  |  **Est**: 2h  |  **Depends on**: ISS-069, ISS-070, ISS-071, ISS-072, ISS-096, ISS-098, ISS-099
- **Acceptance Criteria**
  - Collects OOF predictions from all L1 models into a stacked dataset.
- **Files**: src/ensemble/level1.py
- **Tests**: tests/ensemble/test_level1.py
- **Docs**: docs/ENSEMBLE.md

### ISS-112 · Level-2 meta-learner
- **Phase**: P6  |  **Est**: 2h  |  **Depends on**: ISS-111
- **Acceptance Criteria**
  - LightGBM meta on OOF L1 preds + meta-features (regime, vol, disagreement, time-since-retrain).
- **Files**: src/ensemble/meta.py
- **Tests**: tests/ensemble/test_meta.py
- **Docs**: docs/ENSEMBLE.md#meta

### ISS-113 · Conformal prediction
- **Phase**: P6  |  **Est**: 2h  |  **Depends on**: ISS-112
- **Acceptance Criteria**
  - Exchangeable conformal bands for E[return]; valid coverage on holdout.
- **Files**: src/ensemble/conformal.py
- **Tests**: tests/ensemble/test_conformal.py
- **Docs**: docs/ENSEMBLE.md#conformal

### ISS-114 · Confidence estimation
- **Phase**: P6  |  **Est**: 2h  |  **Depends on**: ISS-111
- **Acceptance Criteria**
  - Disagreement (var/entropy) + epistemic estimate -> confidence in [0,1].
- **Files**: src/ensemble/confidence.py
- **Tests**: tests/ensemble/test_confidence.py
- **Docs**: docs/ENSEMBLE.md#confidence

### ISS-115 · Probability partition
- **Phase**: P6  |  **Est**: 1h  |  **Depends on**: ISS-112, ISS-074
- **Acceptance Criteria**
  - Final P(up)+P(down)+P(flat)=1 via softmax/calibration; E[return] separate head.
- **Files**: src/ensemble/weighting.py
- **Tests**: tests/ensemble/test_weighting.py
- **Docs**: docs/ENSEMBLE.md#probs

### ISS-116 · SHAP explainability
- **Phase**: P6  |  **Est**: 2h  |  **Depends on**: ISS-069, ISS-112
- **Acceptance Criteria**
  - Global+local SHAP; force plots; top-contributing-factors extractor.
- **Files**: src/serve/explain.py, src/ensemble/explain_shap.py
- **Tests**: tests/ensemble/test_shap.py
- **Docs**: docs/EXPLAIN.md

### ISS-117 · TFT attention explainability
- **Phase**: P6  |  **Est**: 2h  |  **Depends on**: ISS-096
- **Acceptance Criteria**
  - Expose variable-selection + attention weights per prediction.
- **Files**: src/models/dl/tft_explain.py
- **Tests**: tests/models/dl/test_tft_explain.py
- **Docs**: docs/EXPLAIN.md#tft

### ISS-118 · LLM narrative assembler
- **Phase**: P6  |  **Est**: 2h  |  **Depends on**: ISS-109, ISS-116, ISS-107
- **Acceptance Criteria**
  - Compose plain-English explanation from SHAP + similar-episode retrieval + news summary.
- **Files**: src/serve/narrative.py
- **Tests**: tests/serve/test_narrative.py
- **Docs**: docs/EXPLAIN.md#narrative

### ISS-119 · Prediction output schema + serializer
- **Phase**: P6  |  **Est**: 2h  |  **Depends on**: ISS-115, ISS-114, ISS-116
- **Acceptance Criteria**
  - Pydantic schema: prob_up/down/flat, E[return], CI, confidence, risk, stop/target, action, factors, explanation, model_version, regime.
- **Files**: src/serve/schema.py
- **Tests**: tests/serve/test_schema.py
- **Docs**: docs/SCHEMA.md

### ISS-120 · Ensemble E2E pipeline test
- **Phase**: P6  |  **Est**: 3h  |  **Depends on**: ISS-111, ISS-115, ISS-119
- **Acceptance Criteria**
  - Full L1->meta->calibrate->conformal->explain on a fixed window reproduces expected JSON.
- **Files**: tests/ensemble/test_e2e.py
- **Tests**: -
- **Docs**: docs/ENSEMBLE.md#e2e

## P7 - 6 issues

### ISS-121 · Simulated broker
- **Phase**: P7  |  **Est**: 3h  |  **Depends on**: ISS-080, ISS-083
- **Acceptance Criteria**
  - Order types, fills, partials, rejects; margin/SPAN-lite checks; matches backtest semantics.
- **Files**: src/trading/broker.py
- **Tests**: tests/trading/test_broker.py
- **Docs**: docs/TRADING.md#paper

### ISS-122 · Paper trade engine + decision loop
- **Phase**: P7  |  **Est**: 3h  |  **Depends on**: ISS-121, ISS-119
- **Acceptance Criteria**
  - Periodic signal -> ensemble -> decision -> simulated orders; portfolio P&L tracked.
- **Files**: src/trading/paper.py
- **Tests**: tests/trading/test_paper.py
- **Docs**: docs/TRADING.md#engine

### ISS-123 · Latency + implementation shortfall
- **Phase**: P7  |  **Est**: 2h  |  **Depends on**: ISS-122
- **Acceptance Criteria**
  - Simulate network/decision lag; measure implementation shortfall vs signal price.
- **Files**: src/trading/latency.py
- **Tests**: tests/trading/test_latency.py
- **Docs**: docs/TRADING.md#latency

### ISS-124 · Reconciliation vs replay
- **Phase**: P7  |  **Est**: 2h  |  **Depends on**: ISS-122, ISS-090
- **Acceptance Criteria**
  - Replay known window; assert paper P&L equals backtest within tolerance.
- **Files**: src/trading/reconcile.py
- **Tests**: tests/trading/test_reconcile.py
- **Docs**: docs/TRADING.md#reconcile

### ISS-125 · Paper trading dashboards
- **Phase**: P7  |  **Est**: 2h  |  **Depends on**: ISS-122
- **Acceptance Criteria**
  - Grafana panels: equity, exposure, fills, slippage vs expected.
- **Files**: k8s/grafana/paper.json
- **Tests**: -
- **Docs**: docs/TRADING.md#dash

### ISS-126 · Paper->live config flip
- **Phase**: P7  |  **Est**: 1h  |  **Depends on**: ISS-122
- **Acceptance Criteria**
  - Single config switch swaps simulated broker for live broker interface.
- **Files**: configs/trading/mode.yaml
- **Tests**: tests/trading/test_mode_switch.py
- **Docs**: docs/TRADING.md#flip

## P8 - 12 issues

### ISS-127 · Feature server (online) integration
- **Phase**: P8  |  **Est**: 2h  |  **Depends on**: ISS-045, ISS-065
- **Acceptance Criteria**
  - Feast online (Redis) serves point-in-time features sub-ms for inference.
- **Files**: src/serve/feature_server.py
- **Tests**: tests/serve/test_feature_server.py
- **Docs**: docs/SERVE.md#features

### ISS-128 · Model server + canary/shadow
- **Phase**: P8  |  **Est**: 3h  |  **Depends on**: ISS-079, ISS-115
- **Acceptance Criteria**
  - KServe/Seldon or FastAPI; canary + shadow deploy; health/readiness probes.
- **Files**: src/serve/model_server.py, docker/Dockerfile.serve
- **Tests**: tests/serve/test_model_server.py
- **Docs**: docs/SERVE.md#server

### ISS-129 · Ensemble runtime in serving
- **Phase**: P8  |  **Est**: 2h  |  **Depends on**: ISS-112, ISS-115, ISS-128
- **Acceptance Criteria**
  - Loads registered ensemble; runs L1->meta->calibrate->conformal per request.
- **Files**: src/serve/ensemble_runtime.py
- **Tests**: tests/serve/test_runtime.py
- **Docs**: docs/SERVE.md#runtime

### ISS-130 · Decision module + risk overlay
- **Phase**: P8  |  **Est**: 2h  |  **Depends on**: ISS-119, ISS-085
- **Acceptance Criteria**
  - Turns prob/conf/risk into action, size, stop, target; hard drawdown/circuit-breaker halt.
- **Files**: src/trading/risk_overlay.py
- **Tests**: tests/trading/test_risk_overlay.py
- **Docs**: docs/SERVE.md#decision

### ISS-131 · FastAPI prediction API
- **Phase**: P8  |  **Est**: 2h  |  **Depends on**: ISS-119, ISS-129, ISS-130
- **Acceptance Criteria**
  - `POST /predict` returns validated schema; auth; rate-limit; schema validation.
- **Files**: src/serve/api.py
- **Tests**: tests/serve/test_api.py
- **Docs**: docs/SERVE.md#api

### ISS-132 · Data drift monitor
- **Phase**: P8  |  **Est**: 2h  |  **Depends on**: ISS-127
- **Acceptance Criteria**
  - PSI/KS on input features per source; freshness/latency SLAs; alert on breach.
- **Files**: src/monitoring/data_drift.py
- **Tests**: tests/monitoring/test_data_drift.py
- **Docs**: docs/MONITORING.md#data

### ISS-133 · Model drift monitor
- **Phase**: P8  |  **Est**: 3h  |  **Depends on**: ISS-131
- **Acceptance Criteria**
  - Rolling IC, directional acc, calibration error (Brier/ECE), ADWIN/Page-Hinkley on residuals.
- **Files**: src/monitoring/model_drift.py
- **Tests**: tests/monitoring/test_model_drift.py
- **Docs**: docs/MONITORING.md#model

### ISS-134 · Serving metrics + Prometheus
- **Phase**: P8  |  **Est**: 2h  |  **Depends on**: ISS-131
- **Acceptance Criteria**
  - Latency/error/throughput/feature-missing metrics exposed; scrape config.
- **Files**: src/monitoring/latency.py, k8s/prometheus.yaml
- **Tests**: tests/monitoring/test_serving_metrics.py
- **Docs**: docs/MONITORING.md#serving

### ISS-135 · P&L / exposure monitoring
- **Phase**: P8  |  **Est**: 2h  |  **Depends on**: ISS-122, ISS-131
- **Acceptance Criteria**
  - Live P&L, gross/net exposure, drawdown, slippage-vs-expected, fill rate dashboards.
- **Files**: src/monitoring/pnl.py
- **Tests**: tests/monitoring/test_pnl.py
- **Docs**: docs/MONITORING.md#pnl

### ISS-136 · Tracing (OpenTelemetry)
- **Phase**: P8  |  **Est**: 2h  |  **Depends on**: ISS-005, ISS-131
- **Acceptance Criteria**
  - OTel spans across ingest->train->serve; correlation_id linkage.
- **Files**: src/monitoring/tracing.py
- **Tests**: tests/monitoring/test_tracing.py
- **Docs**: docs/MONITORING.md#tracing

### ISS-137 · Auto-retrain trigger DAG
- **Phase**: P8  |  **Est**: 2h  |  **Depends on**: ISS-133, ISS-044
- **Acceptance Criteria**
  - Drift/regime breach -> retrain DAG -> candidate -> shadow test -> promote gate.
- **Files**: airflow/dags/retrain.py
- **Tests**: tests/integration/test_retrain_dag.py
- **Docs**: docs/MONITORING.md#retrain

### ISS-138 · Alerting + runbooks
- **Phase**: P8  |  **Est**: 2h  |  **Depends on**: ISS-132, ISS-133, ISS-135
- **Acceptance Criteria**
  - Slack/PagerDuty severities; runbooks for drift, fill failure, drawdown halt.
- **Files**: src/monitoring/alerts.py, docs/runbooks/*.md
- **Tests**: tests/monitoring/test_alerts.py
- **Docs**: docs/MONITORING.md#alerts

## P9 - 12 issues

### ISS-139 · Feature unit test suite
- **Phase**: P9  |  **Est**: 2h  |  **Depends on**: ISS-047, ISS-064
- **Acceptance Criteria**
  - Known-input/known-output tests for every feature family (golden values).
- **Files**: tests/features/golden/test_features_golden.py
- **Tests**: -
- **Docs**: docs/FEATURES.md#tests

### ISS-140 · Integration: collector->lake->store
- **Phase**: P9  |  **Est**: 2h  |  **Depends on**: ISS-021, ISS-042, ISS-065
- **Acceptance Criteria**
  - End-to-end: one source collected -> validated -> features materialized.
- **Files**: tests/integration/test_collect_to_feature.py
- **Tests**: -
- **Docs**: docs/TESTING.md

### ISS-141 · Backtest determinism + replay consistency
- **Phase**: P9  |  **Est**: 2h  |  **Depends on**: ISS-080, ISS-127
- **Acceptance Criteria**
  - Fixed seed -> identical backtest; serve features == train features for same as_of_ts.
- **Files**: tests/integration/test_replay_consistency.py
- **Tests**: -
- **Docs**: docs/TESTING.md#consistency

### ISS-142 · E2E paper-trade known-window
- **Phase**: P9  |  **Est**: 3h  |  **Depends on**: ISS-124, ISS-120
- **Acceptance Criteria**
  - Run paper on a fixed historical window; assert P&L + schema + explainability outputs.
- **Files**: tests/e2e/test_paper_e2e.py
- **Tests**: -
- **Docs**: docs/TESTING.md#e2e

### ISS-143 · CI model-regression + backtest gate
- **Phase**: P9  |  **Est**: 3h  |  **Depends on**: ISS-077, ISS-088, ISS-142
- **Acceptance Criteria**
  - PR cannot promote model unless: no leakage, deflated-Sharpe beats baseline, calibration in tol, drift OK.
- **Files**: .github/workflows/model_gate.yml
- **Tests**: -
- **Docs**: docs/CI.md#gate

### ISS-144 · Chaos / resilience tests
- **Phase**: P9  |  **Est**: 2h  |  **Depends on**: ISS-044
- **Acceptance Criteria**
  - Kill a collector mid-run -> assert alert + backfill; degrade gracefully.
- **Files**: tests/integration/test_chaos.py
- **Tests**: -
- **Docs**: docs/TESTING.md#chaos

### ISS-145 · Universe expansion (50->100->250)
- **Phase**: P9  |  **Est**: 3h  |  **Depends on**: ISS-065, ISS-090
- **Acceptance Criteria**
  - Config-driven universe; liquidity/impact filters; batch materialization scales.
- **Files**: configs/universe/*.yaml, src/data/universe.py
- **Tests**: tests/data/test_universe.py
- **Docs**: docs/SCALE.md#universe

### ISS-146 · Multi-horizon support
- **Phase**: P9  |  **Est**: 2h  |  **Depends on**: ISS-067, ISS-112
- **Acceptance Criteria**
  - Pipeline trains/serves H in {1,5,21,63} with horizon-routed ensemble outputs.
- **Files**: src/models/horizons.py
- **Tests**: tests/models/test_horizons.py
- **Docs**: docs/SCALE.md#horizons

### ISS-147 · Options-strategy layer
- **Phase**: P9  |  **Est**: 3h  |  **Depends on**: ISS-030, ISS-058, ISS-080
- **Acceptance Criteria**
  - Vol/options trading strategies (not just directional equity) on top of signals.
- **Files**: src/trading/options_strategies.py
- **Tests**: tests/trading/test_options_strategies.py
- **Docs**: docs/SCALE.md#options

### ISS-148 · Documentation site (ADRs, runbooks)
- **Phase**: P9  |  **Est**: 3h  |  **Depends on**: ISS-138
- **Acceptance Criteria**
  - Architecture, ADRs (key decisions), runbooks, onboarding; built (mkdocs).
- **Files**: docs/index.md, mkdocs.yml
- **Tests**: -
- **Docs**: docs/README.md

### ISS-149 · On-prem LOQ dGPU training
- **Phase**: P9  |  **Est**: 2h  |  **Depends on**: ISS-093, ISS-013
- **Acceptance Criteria**
  - Run HPO/DL training on local Lenovo LOQ dGPU; artifacts sync to registry.
- **Files**: scripts/local_train.sh, configs/mlflow.yaml
- **Tests**: -
- **Docs**: docs/SCALE.md#onprem

### ISS-150 · Production rollout runbook + go-live checklist
- **Phase**: P9  |  **Est**: 2h  |  **Depends on**: ISS-131, ISS-138, ISS-143
- **Acceptance Criteria**
  - Small-capital live launch checklist: gates, monitoring, kill-switch, compliance.
- **Files**: docs/runbooks/go_live.md
- **Tests**: -
- **Docs**: docs/SCALE.md#golive
