# Generator for quant-platform GitHub issues backlog
issues = []
def mk(id, title, phase, deps, est, ac, files, tests, docs):
    issues.append(dict(id=id, title=title, phase=phase, deps=deps, est=est,
                       ac=ac, files=files, tests=tests, docs=docs))

# ========================= PHASE 0 — FOUNDATIONS =========================
mk("ISS-001","Init monorepo + pyproject.toml","P0",[],"1h",
   ["Repo scaffolds with src/, tests/, configs/, docs/ per architecture.","`pyproject.toml` declares deps (pandas, polars, sklearn, xgboost, lightgbm, catboost, pytorch, feast, mlflow, optuna, fastapi, structlog).","`make install` resolves a clean editable env."],
   ["pyproject.toml","Makefile","src/__init__.py","README.md"],
   ["tests/test_imports.py"],["docs/README.md (repo layout)"])
mk("ISS-002","Pre-commit: ruff, black, mypy","P0",["ISS-001"],"1h",
   ["`.pre-commit-config.yaml` runs ruff (lint+import sort), black, mypy on staged files.","`make lint` and `make type` pass locally on empty scaffold."],
   [".pre-commit-config.yaml",".ruff.toml","Makefile"],
   [],["docs/STYLE.md"])
mk("ISS-003","GitHub Actions CI skeleton","P0",["ISS-001","ISS-002"],"2h",
   ["Workflow runs on PR: lint -> type -> unit tests -> build.","Fails build on any stage error; artifacts uploaded.","Requires green CI before merge (branch protection)."],
   [".github/workflows/ci.yml",".github/pull_request_template.md"],
   [],["docs/CI.md"])
mk("ISS-004","Hydra/OmegaConf config system","P0",["ISS-001"],"2h",
   ["`configs/` has base + env overlays (dev/staging/prod).","`load_config()` returns typed config; secrets resolved from env.","Example run prints merged config."],
   ["configs/config.yaml","configs/data/*.yaml","src/common/config.py"],
   ["tests/common/test_config.py"],["docs/CONFIG.md"])
mk("ISS-005","Structured logging + correlation IDs","P0",["ISS-001"],"2h",
   ["`structlog` JSON logs with ts, level, module, correlation_id.","Context var propagates correlation_id across calls.","Log to stdout + file; no secrets leaked."],
   ["src/logging/structured.py","src/common/context.py"],
   ["tests/logging/test_structured.py"],["docs/LOGGING.md"])
mk("ISS-006","Exception hierarchy + common utils","P0",["ISS-001"],"1h",
   ["Typed exceptions (DataError, ModelError, ConfigError, LeakageError).","Utils: safe_div, nan_guard, hash_payload."],
   ["src/common/exceptions.py","src/common/utils.py"],
   ["tests/common/test_utils.py"],[])
mk("ISS-007","Time utils: IST, trading calendar","P0",["ISS-001"],"2h",
   ["`to_ist()`, trading-day list for NSE/BSE (excl. holidays).","`is_trading_day()`, `next_expiry_thursday()`.","Handles weekly expiry + budget/election closures via config."],
   ["src/common/time_utils.py","configs/holidays.yaml"],
   ["tests/common/test_time_utils.py"],["docs/CALENDAR.md"])
mk("ISS-008","Object store client (S3/MinIO)","P0",["ISS-001","ISS-004"],"2h",
   ["`put_raw(bucket,key,payload)`, `get_raw`, `list_prefix` with idempotent write + content hash.","MinIO works locally via docker-compose."],
   ["src/data/raw_lake.py"],
   ["tests/data/test_raw_lake.py"],["docs/STORAGE.md"])
mk("ISS-009","Postgres schema + Alembic migrations","P0",["ISS-001"],"2h",
   ["Tables: symbols, corporate_actions, fundamentals_meta, runs.","`alembic upgrade head` creates schema in dev DB."],
   ["migrations/env.py","migrations/versions/*.py","src/data/db.py"],
   ["tests/data/test_db.py"],["docs/SCHEMA.md"])
mk("ISS-010","TimescaleDB hypertables","P0",["ISS-009"],"2h",
   ["Hypertables: prices_eod, prices_intraday, options_chain, vix.","Continuous aggregates for daily rollups.","Insert + range query <100ms for 1y."],
   ["migrations/versions/timescale.sql","src/data/tsdb.py"],
   ["tests/data/test_tsdb.py"],["docs/SCHEMA.md"])
mk("ISS-011","Redis cache client wrapper","P0",["ISS-001"],"1h",
   ["`get/set` with TTL, JSON serialization, namespacing.","Health check + reconnect on failure."],
   ["src/common/redis_client.py"],
   ["tests/common/test_redis.py"],[])
mk("ISS-012","Qdrant vector DB client","P0",["ISS-001"],"1h",
   ["`upsert(collection, vectors, payloads)`, `search`, collection create/recreate.","Local Qdrant via docker-compose."],
   ["src/nlp/vector_store.py"],
   ["tests/nlp/test_vector_store.py"],[])
mk("ISS-013","MLflow tracking + experiment registry","P0",["ISS-001"],"2h",
   ["`log_run(params,metrics,artifact)`; experiment per model family.","Model registry stages: None->Staging->Production."],
   ["src/models/registry.py","configs/mlflow.yaml"],
   ["tests/models/test_registry.py"],["docs/EXPERIMENTS.md"])
mk("ISS-014","Docker base images (python/ml/serve)","P0",["ISS-001"],"2h",
   ["3 Dockerfiles: base (deps), ml (torch), serve (fastapi).","Build passes; image size reported."],
   ["docker/Dockerfile.base","docker/Dockerfile.ml","docker/Dockerfile.serve"],
   [],["docs/DOCKER.md"])
mk("ISS-015","Docker-compose local stack","P0",["ISS-008","ISS-009","ISS-010","ISS-011","ISS-012"],"2h",
   ["Compose: postgres+timescale, redis, minio, qdrant, mlflow.","`make dev-up` brings stack up healthy."],
   ["docker-compose.yml",".env.example"],
   ["tests/integration/test_compose_health.py"],["docs/LOCAL_DEV.md"])
mk("ISS-016","Kubernetes base manifests / Helm skeleton","P0",["ISS-014"],"3h",
   ["Helm chart with deployable placeholders for ingest/train/serve.","`helm template` renders without errors."],
   ["k8s/Chart.yaml","k8s/templates/*.yaml"],
   [],["docs/K8S.md"])
mk("ISS-017","Secrets management (Vault/env)","P0",["ISS-004","ISS-015"],"2h",
   ["Config loader resolves secrets from env or Vault agent.","No secret committed; `.env.example` documents keys."],
   ["src/common/secrets.py","configs/secrets.example.yaml"],
   ["tests/common/test_secrets.py"],["docs/SECRETS.md"])
mk("ISS-018","Makefile + dev bootstrap","P0",["ISS-003","ISS-015"],"1h",
   ["`make bootstrap` installs, starts stack, runs migrations.","Contributor can go from clone to green `make test` in one command."],
   ["Makefile","scripts/bootstrap.sh"],
   [],["README.md (Quickstart)"])

# ========================= PHASE 1 — DATA PIPELINE =========================
mk("ISS-019","Raw lake writer + immutable payload schema","P1",["ISS-008"],"2h",
   ["Every collector writes raw JSON/Parquet with `source, as_of_ts, event_ts, payload_hash`.","Writes are append-only + idempotent by natural key."],
   ["src/data/raw_lake.py","configs/data/raw.yaml"],
   ["tests/data/test_raw_lake_write.py"],["docs/DATA_CONTRACTS.md"])
mk("ISS-020","Symbol master + NSE/BSE/ISIN reconciliation","P1",["ISS-009"],"2h",
   ["Unified symbol table linking NSE ticker, BSE code, ISIN, industry, series.","Reconciliation handles re-listings/splits."],
   ["src/data/symbols.py","migrations/symbols.sql"],
   ["tests/data/test_symbols.py"],["docs/SYMBOLS.md"])
mk("ISS-021","NSE EOD collector (vendor)","P1",["ISS-019","ISS-020"],"2h",
   ["Pulls EOD + delivery % via configured vendor; writes raw + cleaned TS.","Handles pagination, rate limits, retries."],
   ["src/data/collectors/nse.py"],
   ["tests/data/collectors/test_nse.py"],["docs/SOURCES.md#nse"])
mk("ISS-022","BSE EOD collector","P1",["ISS-019","ISS-020"],"2h",
   ["Pulls BSE EOD; reconciles to symbol master; writes raw+cleaned."],
   ["src/data/collectors/bse.py"],
   ["tests/data/collectors/test_bse.py"],["docs/SOURCES.md#bse"])
mk("ISS-023","Yahoo Finance collector (backup)","P1",["ISS-019","ISS-020"],"2h",
   ["Pulls adj EOD + index + global proxies; flagged lower-trust.","Validation gate rejects on gaps before use as primary."],
   ["src/data/collectors/yfinance.py"],
   ["tests/data/collectors/test_yfinance.py"],["docs/SOURCES.md#yahoo"])
mk("ISS-024","Corporate actions + PIT adjustment engine","P1",["ISS-020","ISS-009"],"3h",
   ["Collects splits/bonus/dividends with ex-date.","Adjusts price/return series point-in-time so returns are total-return correct.","Reconciles adjusted vs raw within tolerance."],
   ["src/data/collectors/corporate_actions.py","src/data/adjustments.py"],
   ["tests/data/test_adjustments.py"],["docs/CORP_ACTIONS.md"])
mk("ISS-025","Financial statements collector","P1",["ISS-019","ISS-020"],"2h",
   ["Collects balance sheet / P&L / cash flow quarterly; normalized to standard schema.","Tags each filing with disclosure `as_of_ts`."],
   ["src/data/collectors/fundamentals.py"],
   ["tests/data/collectors/test_fundamentals.py"],["docs/SOURCES.md#fundamentals"])
mk("ISS-026","Quarterly earnings collector + event flags","P1",["ISS-025"],"2h",
   ["Captures earnings dates, results timestamps, guidance flags.","Emits earnings-event table used by NLP + features."],
   ["src/data/collectors/quarterly_earnings.py"],
   ["tests/data/collectors/test_earnings.py"],["docs/SOURCES.md#earnings"])
mk("ISS-027","Promoter holdings collector","P1",["ISS-019","ISS-020"],"2h",
   ["Collects promoter %, pledge %, changes; point-in-time."],
   ["src/data/collectors/promoter.py"],
   ["tests/data/collectors/test_promoter.py"],["docs/SOURCES.md#promoter"])
mk("ISS-028","FII/DII activity collector","P1",["ISS-019","ISS-020"],"2h",
   ["Daily FII/DII cash + F&O positioning by category; sector flow aggregation."],
   ["src/data/collectors/fii_dii.py"],
   ["tests/data/collectors/test_fii_dii.py"],["docs/SOURCES.md#fii_dii"])
mk("ISS-029","Mutual fund holdings collector","P1",["ISS-019","ISS-020"],"2h",
   ["Quarterly MF portfolios -> stake %, chg qoq; accumulation/distribution flags."],
   ["src/data/collectors/mf_holdings.py"],
   ["tests/data/collectors/test_mf.py"],["docs/SOURCES.md#mf"])
mk("ISS-030","Options chain collector (NSE F&O)","P1",["ISS-019","ISS-020"],"3h",
   ["Pulls full chain (calls/puts, OI, IV, volume) per expiry.","Computes PCR, max pain, IV skew at collection time."],
   ["src/data/collectors/options_chain.py"],
   ["tests/data/collectors/test_options.py"],["docs/SOURCES.md#options"])
mk("ISS-031","India VIX collector","P1",["ISS-019"],"1h",
   ["Daily India VIX series; intraday optional."],
   ["src/data/collectors/india_vix.py"],
   ["tests/data/collectors/test_vix.py"],["docs/SOURCES.md#vix"])
mk("ISS-032","USDINR collector","P1",["ISS-019"],"1h",
   ["Spot + forward USDINR daily."],
   ["src/data/collectors/usdinr.py"],
   ["tests/data/collectors/test_usdinr.py"],["docs/SOURCES.md#usdinr"])
mk("ISS-033","Gold + Crude Oil collector","P1",["ISS-019"],"2h",
   ["MCX gold + crude (or proxy) daily; INR-denominated."],
   ["src/data/collectors/commodities.py"],
   ["tests/data/collectors/test_commodities.py"],["docs/SOURCES.md#commodities"])
mk("ISS-034","RBI announcements collector + policy dummy","P1",["ISS-019"],"2h",
   ["Captures policy dates, repo changes, statements; emits policy-window + surprise dummy."],
   ["src/data/collectors/rbi.py"],
   ["tests/data/collectors/test_rbi.py"],["docs/SOURCES.md#rbi"])
mk("ISS-035","Inflation (CPI/IIP) collector","P1",["ISS-019"],"2h",
   ["Monthly CPI/IIP + consensus; inflation-surprise feature source."],
   ["src/data/collectors/macro.py"],
   ["tests/data/collectors/test_macro.py"],["docs/SOURCES.md#macro"])
mk("ISS-036","Interest rates / G-sec collector","P1",["ISS-019"],"1h",
   ["10Y G-sec yield, repo, yield-curve points."],
   ["src/data/collectors/rates.py"],
   ["tests/data/collectors/test_rates.py"],["docs/SOURCES.md#rates"])
mk("ISS-037","GDP collector","P1",["ISS-019"],"1h",
   ["Quarterly real GDP + forecasts; slow regime factor."],
   ["src/data/collectors/gdp.py"],
   ["tests/data/collectors/test_gdp.py"],["docs/SOURCES.md#gdp"])
mk("ISS-038","Economic calendar collector","P1",["ISS-019"],"2h",
   ["Known events (RBI, CPI, GDP, elections, expiry) -> binary dummies + days-to-event."],
   ["src/data/collectors/economic_calendar.py"],
   ["tests/data/collectors/test_calendar.py"],["docs/SOURCES.md#calendar"])
mk("ISS-039","News collector (RSS + APIs)","P1",["ISS-019","ISS-020"],"3h",
   ["Pulls from RSS + vendor APIs; dedup; links to symbols via NER placeholder.","Stores raw articles with timestamps."],
   ["src/data/collectors/news/__init__.py","src/data/collectors/news/rss.py","src/data/collectors/news/api.py"],
   ["tests/data/collectors/news/test_news.py"],["docs/SOURCES.md#news"])
mk("ISS-040","Social sentiment collector","P1",["ISS-019","ISS-020"],"3h",
   ["Collects X/TradingView/forum posts; rate-limited; stores text + engagement."],
   ["src/data/collectors/social/__init__.py"],
   ["tests/data/collectors/social/test_social.py"],["docs/SOURCES.md#social"])
mk("ISS-041","Annual reports collector + ingest","P1",["ISS-019","ISS-020"],"2h",
   ["Downloads annual report PDFs/HTML; stores refs + metadata for NLP."],
   ["src/data/collectors/annual_reports.py"],
   ["tests/data/collectors/test_annual.py"],["docs/SOURCES.md#annual"])
mk("ISS-042","Data validation framework + contracts","P1",["ISS-019"],"3h",
   ["Pandera/Great Expectations schemas per source.","Reject on missing cols, stale ts, negative/zero price, dup keys, broken CA continuity."],
   ["src/data/validators.py","configs/data/contracts/*.yaml"],
   ["tests/data/test_validators.py"],["docs/VALIDATION.md"])
mk("ISS-043","Point-in-time lineage tracker","P1",["ISS-024","ISS-042"],"3h",
   ["Every fact carries `as_of_ts` (public) + `event_ts`; fundamentals/earnings invisible before disclosure.","Lineage log records transforms (OpenLineage-lite)."],
   ["src/data/pit.py","src/data/lineage.py"],
   ["tests/data/test_pit.py"],["docs/PIT.md"])
mk("ISS-044","Orchestration DAGs (nightly ingest)","P1",["ISS-021","ISS-022","ISS-042"],"3h",
   ["Airflow/Prefect DAGs run collectors in dependency order with retries + alerts.","Manual backfill command per source."],
   ["airflow/dags/ingest_daily.py","airflow/plugins/"],
   ["tests/integration/test_dag_import.py"],["docs/ORCHESTRATION.md"])

# ========================= PHASE 2 — FEATURE STORE & FEATURES =========================
mk("ISS-045","Feature store setup (Feast)","P2",["ISS-010","ISS-011"],"3h",
   ["Feast repo connects offline (TS DB) + online (Redis).","`feast apply` creates infra; `get_historical_features` works."],
   ["feature_store/feature_store.yaml","feature_store/definitions.py"],
   ["tests/features/test_feast_smoke.py"],["docs/FEATURE_STORE.md"])
mk("ISS-046","Feature registry (catalog, 600+ defs)","P2",["ISS-045"],"3h",
   ["`features/registry.py` declares each feature: id, source, window, PIT rule, owner, transformer.","`list_features()` + metadata export to YAML."],
   ["src/features/registry.py","configs/features/registry.yaml"],
   ["tests/features/test_registry.py"],["docs/FEATURES.md"])
mk("ISS-047","Price / return features","P2",["ISS-046","ISS-024"],"2h",
   ["Log returns over [1,2,3,5,10,21,42,63,126,252]d; open/close, gap%, range%, VWAP-relative."],
   ["src/features/price.py"],
   ["tests/features/test_price.py"],["docs/FEATURES.md#price"])
mk("ISS-048","Volume features","P2",["ISS-046"],"2h",
   ["Vol/avg ratio, z-score, OBV, CMF, MFI, up/down vol, delivery%."],
   ["src/features/volume.py"],
   ["tests/features/test_volume.py"],["docs/FEATURES.md#volume"])
mk("ISS-049","Momentum features","P2",["ISS-047"],"2h",
   ["ROC multi-window, dual/triple momentum, cross-sectional rank, 12-1, short-term reversal."],
   ["src/features/momentum.py"],
   ["tests/features/test_momentum.py"],["docs/FEATURES.md#momentum"])
mk("ISS-050","Volatility features","P2",["ISS-047"],"2h",
   ["Rolling std, Parkinson, Garman-Klass, Yang-Zhang, ATR, vol-of-vol, skew/kurt, VIX corr."],
   ["src/features/volatility.py"],
   ["tests/features/test_volatility.py"],["docs/FEATURES.md#volatility"])
mk("ISS-051","Trend features","P2",["ISS-047"],"2h",
   ["SMA/EMA vs price, golden/death cross, ADX, DMI, SAR, Ichimoku, regression slope, Hurst."],
   ["src/features/trend.py"],
   ["tests/features/test_trend.py"],["docs/FEATURES.md#trend"])
mk("ISS-052","Market breadth features","P2",["ISS-021","ISS-022"],"2h",
   ["A/D line+ratio, McClellan, % above 50/200 DMA, new highs/lows, TRIN, breadth thrust."],
   ["src/features/breadth.py"],
   ["tests/features/test_breadth.py"],["docs/FEATURES.md#breadth"])
mk("ISS-053","Sector / industry strength","P2",["ISS-020","ISS-047"],"2h",
   ["Sector index momentum, RS vs Nifty, industry rank, peer median, sector flow."],
   ["src/features/sector.py"],
   ["tests/features/test_sector.py"],["docs/FEATURES.md#sector"])
mk("ISS-054","Correlation / coherence","P2",["ISS-047","ISS-031","ISS-032"],"2h",
   ["Rolling corr with Nifty/BankNifty/sector/USDINR/gold/crude; rolling beta; idiosyncratic vol."],
   ["src/features/correlation.py"],
   ["tests/features/test_correlation.py"],["docs/FEATURES.md#correlation"])
mk("ISS-055","Relative strength","P2",["ISS-047","ISS-053"],"1h",
   ["RS vs index/sector/peer median; percentile rank of price."],
   ["src/features/rs.py"],
   ["tests/features/test_rs.py"],["docs/FEATURES.md#rs"])
mk("ISS-056","Candlestick patterns","P2",["ISS-047"],"3h",
   ["~30 patterns (doji, hammer, engulfing, harami, stars, soldiers, marubozu...) boolean + strength."],
   ["src/features/candlestick.py"],
   ["tests/features/test_candlestick.py"],["docs/FEATURES.md#candles"])
mk("ISS-057","Support / resistance","P2",["ISS-047"],"2h",
   ["Pivot/classic/Camarilla/Fib; local extrema; 52w hi/lo distance; VBP zones; breakout flags."],
   ["src/features/support_resistance.py"],
   ["tests/features/test_sr.py"],["docs/FEATURES.md#sr"])
mk("ISS-058","Options features","P2",["ISS-030"],"3h",
   ["PCR, max pain, IV skew (25d risk reversal), IV term, ATM IV%, gamma proxy, OI build-up, FII fut pos."],
   ["src/features/options.py"],
   ["tests/features/test_options_feat.py"],["docs/FEATURES.md#options"])
mk("ISS-059","Macro / cross-asset","P2",["ISS-031","ISS-032","ISS-033","ISS-034","ISS-035","ISS-036"],"2h",
   ["VIX level/chg, USDINR ret, G-sec yield, crude/gold ret, rate diff, CPI surprise, IIP, global (S&P/Nasdaq/DXY), monsoon, policy dummy."],
   ["src/features/macro.py"],
   ["tests/features/test_macro_feat.py"],["docs/FEATURES.md#macro"])
mk("ISS-060","Fundamental ratios (PIT)","P2",["ISS-025","ISS-043"],"3h",
   ["Valuation/growth/profitability/leverage/quality/earnings-surprise from filings, point-in-time."],
   ["src/features/fundamental.py"],
   ["tests/features/test_fundamental.py"],["docs/FEATURES.md#fundamentals"])
mk("ISS-061","Time / calendar","P2",["ISS-007","ISS-038"],"1h",
   ["DOW, month, quarter-end, expiry-week, pre/post earnings/budget/election, seasonality, festival dummies."],
   ["src/features/time.py"],
   ["tests/features/test_time.py"],["docs/FEATURES.md#time"])
mk("ISS-062","Rolling statistics","P2",["ISS-047","ISS-048"],"2h",
   ["Rolling mean/std/skew/kurt/min/max/quantile of returns/vol/spread; rolling Sharpe/Sortino/Calmar."],
   ["src/features/rolling.py"],
   ["tests/features/test_rolling.py"],["docs/FEATURES.md#rolling"])
mk("ISS-063","Lag / autoregressive","P2",["ISS-047"],"2h",
   ["Lagged returns/vol/volume (1..N), AR residuals, ACF/PACF features."],
   ["src/features/lags.py"],
   ["tests/features/test_lags.py"],["docs/FEATURES.md#lags"])
mk("ISS-064","Target / categorical encoding (OOF)","P2",["ISS-046"],"2h",
   ["Industry one-hot/hash, peer-cluster id, regime label, out-of-fold target encoding (leakage-safe)."],
   ["src/features/target_encoding.py"],
   ["tests/features/test_encoding.py"],["docs/FEATURES.md#encoding"])
mk("ISS-065","Feature materialization job","P2",["ISS-045","ISS-047","ISS-064"],"2h",
   ["Batch job computes all registered features point-in-time -> offline store; backfill + incremental."],
   ["src/features/materialize.py"],
   ["tests/features/test_materialize.py"],["docs/FEATURE_STORE.md"])

# ========================= PHASE 3 — BASELINE ML =========================
mk("ISS-066","Dataset builder (X,y, time split)","P3",["ISS-065"],"2h",
   ["Builds feature matrix + multi-target from feature store by symbol/date.","Honors PIT; no future rows in train."],
   ["src/models/dataset.py"],
   ["tests/models/test_dataset.py"],["docs/TRAINING.md#dataset"])
mk("ISS-067","Target definitions + horizons","P3",["ISS-066"],"2h",
   ["direction (sign fwd ret), return (reg), vol (reg) over H in {1,5,21,63}.","Handles delisting/illiquidity guards."],
   ["src/models/targets.py"],
   ["tests/models/test_targets.py"],["docs/TRAINING.md#targets"])
mk("ISS-068","Common trainer interface","P3",["ISS-066","ISS-067"],"2h",
   ["`Trainer.fit/predict` wrapping sklearn; uniform API; saves artifacts + metrics."],
   ["src/models/trainers.py"],
   ["tests/models/test_trainers.py"],["docs/TRAINING.md#trainer"])
mk("ISS-069","LightGBM baseline","P3",["ISS-068"],"2h",
   ["LightGBM for all 3 targets; categorical handling; baseline metrics logged."],
   ["src/models/ml/lgbm.py"],
   ["tests/models/ml/test_lgbm.py"],["docs/MODELS.md#lgbm"])
mk("ISS-070","CatBoost baseline","P3",["ISS-068"],"2h",
   ["CatBoost with native categoricals + ordered boosting; PIT-safe."],
   ["src/models/ml/catboost.py"],
   ["tests/models/ml/test_catboost.py"],["docs/MODELS.md#catboost"])
mk("ISS-071","XGBoost baseline","P3",["ISS-068"],"2h",
   ["XGBoost for all targets; strong tabular baseline."],
   ["src/models/ml/xgb.py"],
   ["tests/models/ml/test_xgb.py"],["docs/MODELS.md#xgb"])
mk("ISS-072","RandomForest baseline","P3",["ISS-068"],"1h",
   ["RF baseline + uncertainty estimate (tree variance)."],
   ["src/models/ml/rf.py"],
   ["tests/models/ml/test_rf.py"],["docs/MODELS.md#rf"])
mk("ISS-073","HPO harness (Optuna)","P3",["ISS-069","ISS-070","ISS-071"],"3h",
   ["Multi-objective (IC + calibration) TPE with pruner; study persistence; parallel workers."],
   ["src/models/hpo.py"],
   ["tests/models/test_hpo.py"],["docs/TRAINING.md#hpo"])
mk("ISS-074","Probability calibration","P3",["ISS-069"],"2h",
   ["Isotonic/Platt on OOF preds; reliability curve + Brier reported."],
   ["src/models/calibration.py"],
   ["tests/models/test_calibration.py"],["docs/TRAINING.md#calibration"])
mk("ISS-075","Walk-forward validation engine","P3",["ISS-066","ISS-067"],"3h",
   ["Rolling train->val->test; aggregates OOS per fold; reproducible seeds."],
   ["src/training/walk_forward.py"],
   ["tests/training/test_walk_forward.py"],["docs/TRAINING.md#walkforward"])
mk("ISS-076","Purged K-fold CV + embargo","P3",["ISS-066"],"2h",
   ["Purged groups by time + embargo window; prevents cross-fold leakage."],
   ["src/training/ts_cv.py"],
   ["tests/training/test_ts_cv.py"],["docs/TRAINING.md#cv"])
mk("ISS-077","Leakage test harness (FutureLeak)","P3",["ISS-066","ISS-076"],"2h",
   ["Inject future feature -> assert model cannot learn it; CI gate."],
   ["src/training/leakage.py"],
   ["tests/training/test_leakage.py"],["docs/TRAINING.md#leakage"])
mk("ISS-078","Model evaluation metrics","P3",["ISS-067"],"2h",
   ["IC, rank-IC, AUC, Brier, ECE, regression MSE/R2; per-horizon + per-regime."],
   ["src/training/evaluate.py"],
   ["tests/training/test_evaluate.py"],["docs/TRAINING.md#metrics"])
mk("ISS-079","Model registry integration","P3",["ISS-013","ISS-069"],"2h",
   ["Trained models logged to MLflow; promotion Staging->Production gated."],
   ["src/models/registry.py"],
   ["tests/models/test_registry_integration.py"],["docs/EXPERIMENTS.md"])

# ========================= PHASE 4 — BACKTEST ENGINE =========================
mk("ISS-080","Event-driven backtest core","P4",["ISS-066","ISS-067"],"3h",
   ["Bar-by-bar loop with portfolio state, cash, positions; deterministic given seed."],
   ["src/backtest/engine.py"],
   ["tests/backtest/test_engine_basic.py"],["docs/BACKTEST.md"])
mk("ISS-081","Indian cost model","P4",["ISS-080"],"3h",
   ["STT (0.025% intraday / 0.1% delivery), SEBI, exchange, stamp, GST 18%, DP, brokerage.","Unit-tested vs hand-computed examples."],
   ["src/backtest/costs.py"],
   ["tests/backtest/test_costs.py"],["docs/BACKTEST.md#costs"])
mk("ISS-082","Slippage model","P4",["ISS-080"],"2h",
   ["Volume-participation (Almgren-Chriss-lite) + spread proxy; expected + worst-case."],
   ["src/backtest/slippage.py"],
   ["tests/backtest/test_slippage.py"],["docs/BACKTEST.md#slippage"])
mk("ISS-083","Order types + partial fills","P4",["ISS-080"],"2h",
   ["MKT/LMT/SL/SL-M; partial fills; reject reasons logged."],
   ["src/backtest/orders.py"],
   ["tests/backtest/test_orders.py"],["docs/BACKTEST.md#orders"])
mk("ISS-084","Position sizing","P4",["ISS-080"],"2h",
   ["Fixed-fractional, fractional-Kelly (capped), vol-targeting; per-name cap."],
   ["src/backtest/positions.py"],
   ["tests/backtest/test_sizing.py"],["docs/BACKTEST.md#sizing"])
mk("ISS-085","Risk management","P4",["ISS-080","ISS-084"],"2h",
   ["Per-trade stop, trailing stop, max position%, sector cap, drawdown halt, vol circuit-breaker."],
   ["src/backtest/risk.py"],
   ["tests/backtest/test_risk.py"],["docs/BACKTEST.md#risk"])
mk("ISS-086","Portfolio optimization","P4",["ISS-080"],"3h",
   ["Markowitz mean-variance + Hierarchical Risk Parity (HRP default); weights constrained."],
   ["src/backtest/optimization.py"],
   ["tests/backtest/test_optimization.py"],["docs/BACKTEST.md#optimization"])
mk("ISS-087","Performance metrics","P4",["ISS-080"],"2h",
   ["Sharpe, Sortino, Calmar, MaxDD, ProfitFactor, CAGR, WinRate, expectancy, IR, alpha/beta."],
   ["src/backtest/metrics.py"],
   ["tests/backtest/test_metrics.py"],["docs/BACKTEST.md#metrics"])
mk("ISS-088","Deflated Sharpe ratio","P4",["ISS-087"],"1h",
   ["Bailey-Popelař deflated Sharpe + minimum track record length to reject luck."],
   ["src/backtest/deflated_sharpe.py"],
   ["tests/backtest/test_deflated_sharpe.py"],["docs/BACKTEST.md#deflated"])
mk("ISS-089","Backtest reporting (tearsheet)","P4",["ISS-087"],"2h",
   ["Equity curve, drawdown, monthly returns, trade blotter, plots -> HTML/PDF."],
   ["src/backtest/reports.py"],
   ["tests/backtest/test_reports.py"],["docs/BACKTEST.md#reports"])
mk("ISS-090","Multi-name portfolio runner","P4",["ISS-080","ISS-086"],"2h",
   ["Run signals across universe; aggregate portfolio; turnover/exposure tracked."],
   ["src/backtest/portfolio.py"],
   ["tests/backtest/test_portfolio.py"],["docs/BACKTEST.md#portfolio"])
mk("ISS-091","Walk-forward backtest integration","P4",["ISS-075","ISS-080"],"2h",
   ["Backtest over walk-forward folds; OOS aggregate vs in-sample guard."],
   ["src/backtest/walk_forward_run.py"],
   ["tests/backtest/test_wf_backtest.py"],["docs/BACKTEST.md#walkforward"])
mk("ISS-092","Cost model unit tests (golden)","P4",["ISS-081"],"2h",
   ["Hand-computed INR cost examples across trade types assert exact amounts."],
   ["tests/backtest/golden/test_costs_golden.py"],
   [],["docs/BACKTEST.md#costs"])

# ========================= PHASE 5 — DL & NLP =========================
mk("ISS-093","PyTorch Lightning boilerplate","P5",["ISS-066"],"2h",
   ["Trainer wrapper: dataloaders (time-series sampler), logging, checkpoint, early-stop."],
   ["src/models/dl/base.py"],
   ["tests/models/dl/test_base.py"],["docs/MODELS.md#dl"])
mk("ISS-094","LSTM model","P5",["ISS-093"],"2h",
   ["Sequence model on raw series; multi-horizon + quantile heads."],
   ["src/models/dl/lstm.py"],
   ["tests/models/dl/test_lstm.py"],["docs/MODELS.md#lstm"])
mk("ISS-095","GRU model","P5",["ISS-093"],"2h",
   ["Lighter sequential model; same heads."],
   ["src/models/dl/gru.py"],
   ["tests/models/dl/test_gru.py"],["docs/MODELS.md#gru"])
mk("ISS-096","TFT model (primary deep)","P5",["ISS-093"],"3h",
   ["Temporal Fusion Transformer: static + known-future + observed-past; interpretable attention + variable selection."],
   ["src/models/dl/tft.py"],
   ["tests/models/dl/test_tft.py"],["docs/MODELS.md#tft"])
mk("ISS-097","N-BEATS model","P5",["ISS-093"],"2h",
   ["Univariate deep stack; benchmark/component."],
   ["src/models/dl/nbeats.py"],
   ["tests/models/dl/test_nbeats.py"],["docs/MODELS.md#nbeats"])
mk("ISS-098","PatchTST model","P5",["ISS-093"],"3h",
   ["Patch tokens + transformer encoder; long-series SOTA."],
   ["src/models/dl/patchtst.py"],
   ["tests/models/dl/test_patchtst.py"],["docs/MODELS.md#patchtst"])
mk("ISS-099","TimeMixer model","P5",["ISS-093"],"3h",
   ["Multi-scale past+future mixing; complements PatchTST."],
   ["src/models/dl/timemixer.py"],
   ["tests/models/dl/test_timemixer.py"],["docs/MODELS.md#timemixer"])
mk("ISS-100","TabNet model","P5",["ISS-093","ISS-066"],"2h",
   ["Attentive tabular DL for fundamental-heavy cross-section."],
   ["src/models/dl/tabnet.py"],
   ["tests/models/dl/test_tabnet.py"],["docs/MODELS.md#tabnet"])
mk("ISS-101","Transformer (encoder) model","P5",["ISS-093"],"3h",
   ["Feature-token + news-token cross-attention; optional research."],
   ["src/models/dl/transformer.py"],
   ["tests/models/dl/test_transformer.py"],["docs/MODELS.md#transformer"])
mk("ISS-102","DL quantile/multi-horizon heads","P5",["ISS-094"],"2h",
   ["Shared head producing mean + quantile forecasts for uncertainty."],
   ["src/models/dl/heads.py"],
   ["tests/models/dl/test_heads.py"],["docs/MODELS.md#heads"])
mk("ISS-103","NLP ingest + dedup","P5",["ISS-039","ISS-040"],"2h",
   ["Normalize news+social; dedup by hash; attach symbol candidates."],
   ["src/nlp/ingest_news.py","src/nlp/ingest_social.py"],
   ["tests/nlp/test_ingest.py"],["docs/NLP.md#ingest"])
mk("ISS-104","Entity linking (NER -> ISIN)","P5",["ISS-103","ISS-020"],"2h",
   ["Map article text to symbol(s) via NER + dictionary; confidence-scored."],
   ["src/nlp/entity_linking.py"],
   ["tests/nlp/test_entity_linking.py"],["docs/NLP.md#ner"])
mk("ISS-105","Sentiment scoring","P5",["ISS-103"],"2h",
   ["FinBERT + IndicBERT per-entity sentiment, volume, volatility-of-sentiment."],
   ["src/nlp/sentiment.py"],
   ["tests/nlp/test_sentiment.py"],["docs/NLP.md#sentiment"])
mk("ISS-106","Event extraction (LLM)","P5",["ISS-103","ISS-017"],"3h",
   ["Local LLM extracts typed events (earnings, M&A, reg, probe) + timestamps -> features + store."],
   ["src/nlp/event_extraction.py"],
   ["tests/nlp/test_event_extraction.py"],["docs/NLP.md#events"])
mk("ISS-107","Embeddings + Qdrant writes","P5",["ISS-103","ISS-012"],"2h",
   ["Sentence-transformers embeddings -> Qdrant with payload (symbol, ts, sentiment)."],
   ["src/nlp/embeddings.py"],
   ["tests/nlp/test_embeddings.py"],["docs/NLP.md#vectors"])
mk("ISS-108","Transcript / annual tone scoring","P5",["ISS-026","ISS-041","ISS-105"],"2h",
   ["Earnings-call + annual-report tone/negativity/risk-section scoring via LLM."],
   ["src/nlp/tone.py"],
   ["tests/nlp/test_tone.py"],["docs/NLP.md#tone"])
mk("ISS-109","Summarizer (LLM)","P5",["ISS-106","ISS-108"],"2h",
   ["Condense last-N articles/events into 3-bullet briefing for explainability."],
   ["src/nlp/summarizer.py"],
   ["tests/nlp/test_summarizer.py"],["docs/NLP.md#summary"])
mk("ISS-110","NLP features -> feature store","P5",["ISS-045","ISS-105","ISS-107"],"2h",
   ["Persist sentiment/event/embedding features point-in-time into feature store."],
   ["src/nlp/nlp_features.py"],
   ["tests/nlp/test_nlp_features.py"],["docs/NLP.md#features"])

# ========================= PHASE 6 — ENSEMBLE & EXPLAINABILITY =========================
mk("ISS-111","Level-1 ensemble runner","P6",["ISS-069","ISS-070","ISS-071","ISS-072","ISS-096","ISS-098","ISS-099"],"2h",
   ["Collects OOF predictions from all L1 models into a stacked dataset."],
   ["src/ensemble/level1.py"],
   ["tests/ensemble/test_level1.py"],["docs/ENSEMBLE.md"])
mk("ISS-112","Level-2 meta-learner","P6",["ISS-111"],"2h",
   ["LightGBM meta on OOF L1 preds + meta-features (regime, vol, disagreement, time-since-retrain)."],
   ["src/ensemble/meta.py"],
   ["tests/ensemble/test_meta.py"],["docs/ENSEMBLE.md#meta"])
mk("ISS-113","Conformal prediction","P6",["ISS-112"],"2h",
   ["Exchangeable conformal bands for E[return]; valid coverage on holdout."],
   ["src/ensemble/conformal.py"],
   ["tests/ensemble/test_conformal.py"],["docs/ENSEMBLE.md#conformal"])
mk("ISS-114","Confidence estimation","P6",["ISS-111"],"2h",
   ["Disagreement (var/entropy) + epistemic estimate -> confidence in [0,1]."],
   ["src/ensemble/confidence.py"],
   ["tests/ensemble/test_confidence.py"],["docs/ENSEMBLE.md#confidence"])
mk("ISS-115","Probability partition","P6",["ISS-112","ISS-074"],"1h",
   ["Final P(up)+P(down)+P(flat)=1 via softmax/calibration; E[return] separate head."],
   ["src/ensemble/weighting.py"],
   ["tests/ensemble/test_weighting.py"],["docs/ENSEMBLE.md#probs"])
mk("ISS-116","SHAP explainability","P6",["ISS-069","ISS-112"],"2h",
   ["Global+local SHAP; force plots; top-contributing-factors extractor."],
   ["src/serve/explain.py","src/ensemble/explain_shap.py"],
   ["tests/ensemble/test_shap.py"],["docs/EXPLAIN.md"])
mk("ISS-117","TFT attention explainability","P6",["ISS-096"],"2h",
   ["Expose variable-selection + attention weights per prediction."],
   ["src/models/dl/tft_explain.py"],
   ["tests/models/dl/test_tft_explain.py"],["docs/EXPLAIN.md#tft"])
mk("ISS-118","LLM narrative assembler","P6",["ISS-109","ISS-116","ISS-107"],"2h",
   ["Compose plain-English explanation from SHAP + similar-episode retrieval + news summary."],
   ["src/serve/narrative.py"],
   ["tests/serve/test_narrative.py"],["docs/EXPLAIN.md#narrative"])
mk("ISS-119","Prediction output schema + serializer","P6",["ISS-115","ISS-114","ISS-116"],"2h",
   ["Pydantic schema: prob_up/down/flat, E[return], CI, confidence, risk, stop/target, action, factors, explanation, model_version, regime."],
   ["src/serve/schema.py"],
   ["tests/serve/test_schema.py"],["docs/SCHEMA.md"])
mk("ISS-120","Ensemble E2E pipeline test","P6",["ISS-111","ISS-115","ISS-119"],"3h",
   ["Full L1->meta->calibrate->conformal->explain on a fixed window reproduces expected JSON."],
   ["tests/ensemble/test_e2e.py"],
   [],["docs/ENSEMBLE.md#e2e"])

# ========================= PHASE 7 — PAPER TRADING =========================
mk("ISS-121","Simulated broker","P7",["ISS-080","ISS-083"],"3h",
   ["Order types, fills, partials, rejects; margin/SPAN-lite checks; matches backtest semantics."],
   ["src/trading/broker.py"],
   ["tests/trading/test_broker.py"],["docs/TRADING.md#paper"])
mk("ISS-122","Paper trade engine + decision loop","P7",["ISS-121","ISS-119"],"3h",
   ["Periodic signal -> ensemble -> decision -> simulated orders; portfolio P&L tracked."],
   ["src/trading/paper.py"],
   ["tests/trading/test_paper.py"],["docs/TRADING.md#engine"])
mk("ISS-123","Latency + implementation shortfall","P7",["ISS-122"],"2h",
   ["Simulate network/decision lag; measure implementation shortfall vs signal price."],
   ["src/trading/latency.py"],
   ["tests/trading/test_latency.py"],["docs/TRADING.md#latency"])
mk("ISS-124","Reconciliation vs replay","P7",["ISS-122","ISS-090"],"2h",
   ["Replay known window; assert paper P&L equals backtest within tolerance."],
   ["src/trading/reconcile.py"],
   ["tests/trading/test_reconcile.py"],["docs/TRADING.md#reconcile"])
mk("ISS-125","Paper trading dashboards","P7",["ISS-122"],"2h",
   ["Grafana panels: equity, exposure, fills, slippage vs expected."],
   ["k8s/grafana/paper.json"],
   [],["docs/TRADING.md#dash"])
mk("ISS-126","Paper->live config flip","P7",["ISS-122"],"1h",
   ["Single config switch swaps simulated broker for live broker interface."],
   ["configs/trading/mode.yaml"],
   ["tests/trading/test_mode_switch.py"],["docs/TRADING.md#flip"])

# ========================= PHASE 8 — LIVE SERVING & MONITORING =========================
mk("ISS-127","Feature server (online) integration","P8",["ISS-045","ISS-065"],"2h",
   ["Feast online (Redis) serves point-in-time features sub-ms for inference."],
   ["src/serve/feature_server.py"],
   ["tests/serve/test_feature_server.py"],["docs/SERVE.md#features"])
mk("ISS-128","Model server + canary/shadow","P8",["ISS-079","ISS-115"],"3h",
   ["KServe/Seldon or FastAPI; canary + shadow deploy; health/readiness probes."],
   ["src/serve/model_server.py","docker/Dockerfile.serve"],
   ["tests/serve/test_model_server.py"],["docs/SERVE.md#server"])
mk("ISS-129","Ensemble runtime in serving","P8",["ISS-112","ISS-115","ISS-128"],"2h",
   ["Loads registered ensemble; runs L1->meta->calibrate->conformal per request."],
   ["src/serve/ensemble_runtime.py"],
   ["tests/serve/test_runtime.py"],["docs/SERVE.md#runtime"])
mk("ISS-130","Decision module + risk overlay","P8",["ISS-119","ISS-085"],"2h",
   ["Turns prob/conf/risk into action, size, stop, target; hard drawdown/circuit-breaker halt."],
   ["src/trading/risk_overlay.py"],
   ["tests/trading/test_risk_overlay.py"],["docs/SERVE.md#decision"])
mk("ISS-131","FastAPI prediction API","P8",["ISS-119","ISS-129","ISS-130"],"2h",
   ["`POST /predict` returns validated schema; auth; rate-limit; schema validation."],
   ["src/serve/api.py"],
   ["tests/serve/test_api.py"],["docs/SERVE.md#api"])
mk("ISS-132","Data drift monitor","P8",["ISS-127"],"2h",
   ["PSI/KS on input features per source; freshness/latency SLAs; alert on breach."],
   ["src/monitoring/data_drift.py"],
   ["tests/monitoring/test_data_drift.py"],["docs/MONITORING.md#data"])
mk("ISS-133","Model drift monitor","P8",["ISS-131"],"3h",
   ["Rolling IC, directional acc, calibration error (Brier/ECE), ADWIN/Page-Hinkley on residuals."],
   ["src/monitoring/model_drift.py"],
   ["tests/monitoring/test_model_drift.py"],["docs/MONITORING.md#model"])
mk("ISS-134","Serving metrics + Prometheus","P8",["ISS-131"],"2h",
   ["Latency/error/throughput/feature-missing metrics exposed; scrape config."],
   ["src/monitoring/latency.py","k8s/prometheus.yaml"],
   ["tests/monitoring/test_serving_metrics.py"],["docs/MONITORING.md#serving"])
mk("ISS-135","P&L / exposure monitoring","P8",["ISS-122","ISS-131"],"2h",
   ["Live P&L, gross/net exposure, drawdown, slippage-vs-expected, fill rate dashboards."],
   ["src/monitoring/pnl.py"],
   ["tests/monitoring/test_pnl.py"],["docs/MONITORING.md#pnl"])
mk("ISS-136","Tracing (OpenTelemetry)","P8",["ISS-005","ISS-131"],"2h",
   ["OTel spans across ingest->train->serve; correlation_id linkage."],
   ["src/monitoring/tracing.py"],
   ["tests/monitoring/test_tracing.py"],["docs/MONITORING.md#tracing"])
mk("ISS-137","Auto-retrain trigger DAG","P8",["ISS-133","ISS-044"],"2h",
   ["Drift/regime breach -> retrain DAG -> candidate -> shadow test -> promote gate."],
   ["airflow/dags/retrain.py"],
   ["tests/integration/test_retrain_dag.py"],["docs/MONITORING.md#retrain"])
mk("ISS-138","Alerting + runbooks","P8",["ISS-132","ISS-133","ISS-135"],"2h",
   ["Slack/PagerDuty severities; runbooks for drift, fill failure, drawdown halt."],
   ["src/monitoring/alerts.py","docs/runbooks/*.md"],
   ["tests/monitoring/test_alerts.py"],["docs/MONITORING.md#alerts"])

# ========================= PHASE 9 — SCALE, TESTING, DOCS =========================
mk("ISS-139","Feature unit test suite","P9",["ISS-047","ISS-064"],"2h",
   ["Known-input/known-output tests for every feature family (golden values)."],
   ["tests/features/golden/test_features_golden.py"],
   [],["docs/FEATURES.md#tests"])
mk("ISS-140","Integration: collector->lake->store","P9",["ISS-021","ISS-042","ISS-065"],"2h",
   ["End-to-end: one source collected -> validated -> features materialized."],
   ["tests/integration/test_collect_to_feature.py"],
   [],["docs/TESTING.md"])
mk("ISS-141","Backtest determinism + replay consistency","P9",["ISS-080","ISS-127"],"2h",
   ["Fixed seed -> identical backtest; serve features == train features for same as_of_ts."],
   ["tests/integration/test_replay_consistency.py"],
   [],["docs/TESTING.md#consistency"])
mk("ISS-142","E2E paper-trade known-window","P9",["ISS-124","ISS-120"],"3h",
   ["Run paper on a fixed historical window; assert P&L + schema + explainability outputs."],
   ["tests/e2e/test_paper_e2e.py"],
   [],["docs/TESTING.md#e2e"])
mk("ISS-143","CI model-regression + backtest gate","P9",["ISS-077","ISS-088","ISS-142"],"3h",
   ["PR cannot promote model unless: no leakage, deflated-Sharpe beats baseline, calibration in tol, drift OK."],
   [".github/workflows/model_gate.yml"],
   [],["docs/CI.md#gate"])
mk("ISS-144","Chaos / resilience tests","P9",["ISS-044"],"2h",
   ["Kill a collector mid-run -> assert alert + backfill; degrade gracefully."],
   ["tests/integration/test_chaos.py"],
   [],["docs/TESTING.md#chaos"])
mk("ISS-145","Universe expansion (50->100->250)","P9",["ISS-065","ISS-090"],"3h",
   ["Config-driven universe; liquidity/impact filters; batch materialization scales."],
   ["configs/universe/*.yaml","src/data/universe.py"],
   ["tests/data/test_universe.py"],["docs/SCALE.md#universe"])
mk("ISS-146","Multi-horizon support","P9",["ISS-067","ISS-112"],"2h",
   ["Pipeline trains/serves H in {1,5,21,63} with horizon-routed ensemble outputs."],
   ["src/models/horizons.py"],
   ["tests/models/test_horizons.py"],["docs/SCALE.md#horizons"])
mk("ISS-147","Options-strategy layer","P9",["ISS-030","ISS-058","ISS-080"],"3h",
   ["Vol/options trading strategies (not just directional equity) on top of signals."],
   ["src/trading/options_strategies.py"],
   ["tests/trading/test_options_strategies.py"],["docs/SCALE.md#options"])
mk("ISS-148","Documentation site (ADRs, runbooks)","P9",["ISS-138"],"3h",
   ["Architecture, ADRs (key decisions), runbooks, onboarding; built (mkdocs)."],
   ["docs/index.md","mkdocs.yml"],
   [],["docs/README.md"])
mk("ISS-149","On-prem LOQ dGPU training","P9",["ISS-093","ISS-013"],"2h",
   ["Run HPO/DL training on local Lenovo LOQ dGPU; artifacts sync to registry."],
   ["scripts/local_train.sh","configs/mlflow.yaml"],
   [],["docs/SCALE.md#onprem"])
mk("ISS-150","Production rollout runbook + go-live checklist","P9",["ISS-131","ISS-138","ISS-143"],"2h",
   ["Small-capital live launch checklist: gates, monitoring, kill-switch, compliance."],
   ["docs/runbooks/go_live.md"],
   [],["docs/SCALE.md#golive"])

# ========================= VALIDATION =========================
ids = {i["id"] for i in issues}
errors = []
for i in issues:
    for d in i["deps"]:
        if d not in ids:
            errors.append(f"{i['id']} depends on unknown {d}")
        if d == i["id"]:
            errors.append(f"{i['id']} self-depends")
        else:
            # dependency must be in an earlier-or-equal phase number
            pd = next(x for x in issues if x["id"] == d)["phase"]
            if pd > i["phase"]:
                errors.append(f"{i['id']} (P{i['phase'][1:]}) depends on {d} (P{pd[1:]}) - phase inversion")

if errors:
    print("DEPENDENCY ERRORS:")
    for e in errors:
        print("  -", e)
    raise SystemExit(1)
print("Dependency validation OK. Total issues:", len(issues))

# ----- Render markdown -----
phases = {}
for i in issues:
    phases.setdefault(i["phase"], []).append(i)

lines = []
lines.append("# Quantitative Platform - GitHub Issues Backlog (150)")
lines.append("")
lines.append("Ordered by dependency. Each issue is scoped to 1-3h and independently completable given its prerequisites.")
lines.append("")
lines.append("## Dependency key")
lines.append("- `Depends on`: issue IDs that must be merged first.")
lines.append("- `Est`: estimated effort (1-3h).")
lines.append("- `AC`: acceptance criteria. `Files`: required files. `Tests`: required tests. `Docs`: documentation.")
lines.append("")

for ph in sorted(phases):
    items = phases[ph]
    lines.append(f"## {ph} - {len(items)} issues")
    lines.append("")
    for it in items:
        lines.append(f"### {it['id']} · {it['title']}")
        dep = ", ".join(it["deps"]) if it["deps"] else "-"
        lines.append(f"- **Phase**: {it['phase']}  |  **Est**: {it['est']}  |  **Depends on**: {dep}")
        lines.append(f"- **Acceptance Criteria**")
        for a in it["ac"]:
            lines.append(f"  - {a}")
        lines.append(f"- **Files**: " + ", ".join(it["files"]))
        lines.append(f"- **Tests**: " + (", ".join(it["tests"]) if it["tests"] else "-"))
        lines.append(f"- **Docs**: " + (", ".join(it["docs"]) if it["docs"] else "-"))
        lines.append("")

report = "\n".join(lines)
out = r"C:\Users\prana\quant-platform-issues.md"
with open(out, "w", encoding="utf-8") as f:
    f.write(report)

# summary
print("Total issues:", len(issues))
for ph in sorted(phases):
    print(f"  {ph}: {len(phases[ph])}")
print("First 3:", [i['id'] for i in issues[:3]])
print("Last 3:", [i['id'] for i in issues[-3:]])
print("Bytes:", len(report))
