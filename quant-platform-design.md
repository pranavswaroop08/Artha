# Institutional-Grade Indian Equity Forecast Platform — System Design

**Role:** Principal Quantitative Engineer / AI Systems Architect
**Scope:** NSE + BSE directional & return forecasting platform (probabilistic, multi-horizon, explainable, production-grade)
**Version:** 1.0 (Design Phase — no implementation code)

---

## 0. Design Philosophy & Honest Constraints

Before architecture, the single most important thing a real quant lead tells the investment committee:

> **There is no model that "predicts the market."** Indian equities are a semi-strong efficient, partly retail-driven, heavily event-driven market. The realistic goal is a *small, repeatable, risk-adjusted edge* — a probability distribution that is (a) better than the prior, (b) stable enough to size positions against, and (c) honest about its uncertainty. Everything below is built to **protect capital first** and extract that edge second.

Core principles:

1. **Point-in-time correctness is the only thing that matters.** 90% of "great backtests" are leakage. We build a strict point-in-time (PIT) data lineage so the model at time *t* only sees what was actually knowable at *t*.
2. **Probabilities, not point forecasts.** Output is a calibrated distribution: P(up), P(down), E[return], confidence, risk.
3. **Ensemble of heterogeneous learners.** No single model wins. Tree models capture tabular cross-sectional structure; deep models capture temporal/sequential structure; NLP captures text; meta-learner fuses.
4. **Costs are first-class.** STT, exchange txn charges, GST, SEBI fees, stamp duty, DP charges, slippage, and funding cost are baked into every backtest and live decision. A signal that dies after costs is not a signal.
5. **Drift is the enemy.** Regimes (2018, COVID, 2020 recovery, 2022 rate shock, 2024 election, 2025–26 macro) kill static models. Automatic retraining + drift surveillance is mandatory.
6. **Explainability is a risk control**, not a marketing feature. If we can't explain a prediction, we don't trade it.

**Realistic performance framing (set expectations internally):**
- Top-decile directional accuracy on liquid large-caps: target ~55–62% (out-of-sample, cost-aware). Anything claiming >70% sustained is leakage or overfit.
- Information Coefficient (IC) targets: 0.03–0.08 cross-sectional monthly IC.
- The edge compounds via position sizing + risk overlays, not via huge per-trade accuracy.

---

## 1. Overall Architecture

Hybrid **batch + streaming + event-driven** system. Three planes:

- **Data Plane** — ingestion, validation, feature computation, storage.
- **Model Plane** — training, HPO, evaluation, registration, ensemble, calibration.
- **Serving Plane** — backtest, paper trade, live inference, execution, monitoring.

```
                          ┌─────────────────────────────────────────────┐
                          │                 ORCHESTRATION                 │
                          │   Airflow / Prefect  (DAGs: ingest→feat→train)│
                          └───────────────┬───────────────┬──────────────┘
                                          │               │
        ┌─────────────────────────────────┴──┐         ┌──┴─────────────────────────────────┐
        │            DATA / INGESTION          │         │            TRAINING / RESEARCH      │
        │  collectors (NSE,BSE,YF,macro,news)  │         │  feature store read → HPO → train  │
        │  raw lake (S3/MinIO)                 │         │  walk-forward → evaluate → register │
        │  validation (Great Expectations)     │         │  MLflow / W&B experiment tracking   │
        │  feature store (Feast + TS DB)       │         │  model registry (versioned)        │
        └───────────────┬─────────────────────┘         └───────────────┬─────────────────────┘
                        │                                            │
                        └───────────────┬────────────────────────────┘
                                        │
                          ┌─────────────▼──────────────┐
                          │      SERVING / INFERENCE    │
                          │  Feature server (online)    │
                          │  Model server (KServe/Seldon)│
                          │  Ensemble runtime           │
                          │  Explainability (SHAP)      │
                          └───────┬──────────────┬──────┘
                                  │              │
                    ┌─────────────▼──┐    ┌──────▼─────────────┐
                    │  BACKTEST ENGINE│    │ PAPER / LIVE ENGINE│
                    │  event-driven   │    │  order simulation  │
                    │  cost models    │    │  risk overlays     │
                    └─────────────────┘    └────────────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │   MONITORING / LOGGING      │
                    │  Prometheus/Grafana         │
                    │  drift (PSI/KS/ADWIN)       │
                    │  Loki/ELK structured logs   │
                    │  alerting (Slack/PagerDuty) │
                    └─────────────────────────────┘
```

**Key design choices:**
- **Online + offline feature parity** via a feature store (Feast). The exact same transformation code serves both training and inference → kills train/serve skew.
- **Immutable raw lake** + **reproducible feature versions** → every prediction is auditable to the byte.
- **Model registry as a gate**: nothing reaches serving without passing backtest + calibration + drift gates in CI.

---

## 2. Folder Structure

```
quant-platform/
├── Makefile
├── pyproject.toml
├── README.md
├── docker/                      # Dockerfiles (ingest, train, serve, backtest)
├── k8s/                         # Helm charts, manifests
├── airflow/  (or prefect/)      # DAG definitions
│   ├── dags/
│   └── plugins/
├── configs/                     # Hydra / OmegaConf YAMLs
│   ├── data/
│   ├── features/
│   ├── models/
│   └── backtest/
├── src/
│   ├── common/                  # logging, time utils, io, exceptions
│   ├── data/                    # ── DATA PIPELINE ──
│   │   ├── collectors/          # one module per source
│   │   │   ├── nse.py  bse.py  yfinance.py
│   │   │   ├── corporate_actions.py  fundamentals.py
│   │   │   ├── fii_dii.py  mf_holdings.py  promoter.py
│   │   │   ├── options_chain.py  india_vix.py
│   │   │   ├── macro.py (usdinr, gold, crude, rbi, cpi, gdp)
│   │   │   ├── economic_calendar.py
│   │   │   └── news/  (rss, scraping, api)  social/  (x, forums)
│   │   ├── raw_lake.py          # write raw to object store
│   │   ├── validators.py        # schema + PIT validation
│   │   └── loaders.py
│   ├── features/                # ── FEATURE ENGINEERING ──
│   │   ├── price.py  volume.py  momentum.py  volatility.py
│   │   ├── trend.py  breadth.py  sector.py  correlation.py
│   │   ├── rs.py  candlestick.py  support_resistance.py
│   │   ├── options.py  macro.py  fundamental.py  sentiment.py
│   │   ├── cross_asset.py  time.py  rolling.py  lags.py
│   │   ├── target_encoding.py
│   │   └── registry.py          # feature catalog (500–1000 defs)
│   ├── nlp/                     # ── NLP PIPELINE ──
│   │   ├── ingest_news.py  ingest_social.py
│   │   ├── embeddings.py        # FinBERT / sentence-transformers / LLM
│   │   ├── sentiment.py  event_extraction.py  summarizer.py
│   │   └── vector_store.py      # Qdrant writes
│   ├── models/                  # ── ML / DL ──
│   │   ├── ml/  (xgb, lgbm, catboost, rf)
│   │   ├── dl/  (lstm, gru, tft, nbeats, patchtst, timemixer, tabnet, transformer)
│   │   ├── trainers.py  hpo.py  calibration.py
│   │   └── registry.py
│   ├── ensemble/                # ── ENSEMBLE ──
│   │   ├── level1.py  meta.py  stacking.py
│   │   ├── confidence.py  conformal.py
│   │   └── weighting.py
│   ├── training/                # ── TRAINING OPS ──
│   │   ├── walk_forward.py  ts_cv.py  leakage.py
│   │   ├── drift.py  retrain.py  feature_selection.py
│   │   └── evaluate.py
│   ├── backtest/                # ── BACKTESTING ──
│   │   ├── engine.py  (event-driven)
│   │   ├── costs.py  slippage.py  positions.py
│   │   ├── portfolio.py  optimization.py
│   │   ├── risk.py  metrics.py
│   │   └── reports.py
│   ├── trading/                 # ── PAPER / LIVE ──
│   │   ├── paper.py  live.py  broker.py
│   │   ├── risk_overlay.py  order_manager.py
│   │   └── scheduler.py
│   ├── serve/                   # ── INFERENCE SERVING ──
│   │   ├── api.py (FastAPI)  ensemble_runtime.py
│   │   ├── feature_server.py  predictor.py
│   │   └── explain.py (SHAP/LIME/attention)
│   ├── monitoring/              # ── MONITORING ──
│   │   ├── data_drift.py  model_drift.py
│   │   ├── perf_monitor.py  latency.py  pnl.py
│   │   └── alerts.py
│   └── logging/                 # ── LOGGING ──
│       ├── structured.py  audit.py  tracing.py
├── tests/                       # ── TESTING ──
│   ├── unit/  integration/  data/  model/  backtest/
│   └── e2e/
├── notebooks/                   # research (not production)
├── experiments/                 # MLflow artifacts, W&B runs
├── docs/                        # architecture, runbooks, ADRs
└── scripts/                     # one-off ops scripts
```

---

## 3. Data Pipeline

**Paradigm:** Lambda-ish hybrid — *batch* for slow/cheap data (fundamentals, holdings, macro), *near-real-time streaming* for prices/options/news.

**Stages:**

1. **Collect** — scheduled collectors per source. Each writes *raw, immutable* payloads (JSON/Parquet) to object store with timestamp + source hash. Idempotent (dedupe by natural key).
2. **Validate** — Great Expectations / Pandera schema contracts. Reject on: missing columns, stale timestamp, out-of-range prices (negative, zero), duplicate keys, broken corporate-action continuity.
3. **Normalize** — symbol mapping (NSE/BSE/ISIN reconciliation), timezone (IST), currency (INR), corporate-action adjustments (splits, bonuses, dividends) applied *point-in-time* so returns are total-return-adjusted.
4. **Store** — raw → lake; cleaned → time-series DB; derived → feature store.
5. **Publish** — feature store materialization triggers; downstream DAGs subscribe.

**Point-in-time discipline:** every fact carries an `as_of_ts` (when it became public) and `event_ts`. Fundamental/earnings data is only "visible" after its official disclosure timestamp, never before. This is the #1 leakage defense.

**Lineage:** OpenLineage / custom event log records every transformation → full audit trail for any prediction.

---

## 4. Data Storage

| Data type | Store | Rationale |
|---|---|---|
| Raw immutable payloads | **S3 / MinIO** (object store) | Cheap, versioned, replayable |
| Tick / 1-min / EOD prices, options | **TimescaleDB** (Postgres+ts) or **ClickHouse** | Fast time-range + rollup queries |
| Cleaned reference (symbols, corp actions) | **PostgreSQL** | ACID, relational integrity |
| Features (offline + online) | **Feast** on top of TS DB + **Redis** (online) | Train/serve parity, low-latency online reads |
| News / social embeddings | **Qdrant** (vector DB) | Semantic search, similarity, clustering |
| Model artifacts / metrics | **MLflow** registry + **S3** | Versioning, reproducibility |
| Experiments | **Weights & Biases** | Tracking, comparison |
| Hot cache (quotes, computed features) | **Redis** | Sub-ms reads for live engine |
| Logs / traces | **Loki** (or ELK) | Centralized structured logging |

---

## 5. Feature Engineering (target: 500–1000 features)

Organized by family. Each is computed point-in-time and versioned in the feature registry.

### 5.1 Price / Return features
- Log returns over [1,2,3,5,10,21,42,63,126,252] days
- Open-to-close, close-to-close, high-low range %, gap %
- Realized return vs sector index, vs Nifty50, vs factor
- Intraday return distribution moments
- Close relative to day's VWAP, relative to prior session range

### 5.2 Volume features
- Volume / 20d avg volume (ratio), volume z-score
- Volume-weighted price, OBV, CMF (Chaikin), MFI
- Up/down volume ratio, volume at price buckets
- Abnormal volume flag (>> 3σ)
- Delivery percentage (NSE exchange data — strong Indian signal)

### 5.3 Momentum
- ROC(10/21/63/126/252), dual/triple momentum, time-series momentum
- Cross-sectional momentum rank within sector/industry
- 12-1 momentum (Jegadeesh-Titman adapted to India)
- Short-term reversal (1–5d)

### 5.4 Volatility
- Rolling std of returns (20/60/120d), Parkinson, Garman-Klass, Yang-Zhang
- ATR, realized vol vs implied vol (options), vol-of-vol
- Downside deviation, skew, kurtosis
- Rolling correlation of returns with VIX

### 5.5 Trend
- SMA/EMA (5/10/20/50/100/200) + price vs each; golden/death cross
- ADX, DMI, parabolic SAR, Ichimoku cloud position
- Linear regression slope over N days (trend strength)
- Hurst exponent (mean-reversion vs trending regime)

### 5.6 Market breadth
- Advance-Decline line, A/D ratio, McClellan oscillator
- % stocks above 50/200 DMA, new highs-lows
- Breadth thrust, TRIN (Arms index)
- Sector rotation score

### 5.7 Sector / industry strength
- Sector index momentum, relative strength vs Nifty
- Industry group rank, peer median return
- Sector flow (FII/DII into sector)

### 5.8 Correlation / coherence
- Rolling correlation with Nifty, BankNifty, sector, USDINR, gold, crude
- Beta to index (rolling 60/120d), systematic vs idiosyncratic vol
- Copula tail dependence with peers

### 5.9 Relative strength
- RS vs index, vs sector, vs peer median
- Percentile rank of price over trailing window

### 5.10 Candlestick patterns
- ~30 patterns: doji, hammer, engulfing, harami, morning/evening star, three soldiers, shooting star, spinning top, marubozu, etc. (boolean + strength)

### 5.11 Support / resistance
- Pivot points (classic/Camarilla/Fibonacci), rolling local maxima/minima
- Distance to 52w high/low, distance to recent support/resistance zones
- Volume-by-price support zones, breakout/breakdown flags

### 5.12 Options features
- PCR (put-call ratio), max pain, IV skew (25d risk reversal), IV term structure
- ATM IV, IV percentile, gamma exposure proxy, OI change by strike
- Open interest buildup (long/short build-up), FII long/short in index futures
- Implied vs realized vol spread

### 5.13 Macro / cross-asset
- India VIX level & change, USDINR returns, 10Y G-sec yield, crude returns, gold returns
- Rate diff (repo), inflation surprise (CPI vs consensus), IIP growth
- Global: S&P500 / Nasdaq overnight, DXY, VIX (US), emerging-market FX index
- Monsoon/agri index (rural-demand proxy for FMCG/auto)
- RBI policy window dummy, policy surprise

### 5.14 Fundamental ratios (point-in-time, from filings)
- Valuation: P/E, P/B, EV/EBITDA, PEG, P/S, dividend yield
- Growth: revenue/earnings YoY & QoQ, 5y CAGR
- Profitability: ROE, ROCE, ROIC, EBITDA margin, net margin
- Leverage: D/E, interest coverage, current ratio, quick ratio
- Quality: accruals ratio, cash conversion, FCF yield, earnings stability
- Earnings surprise vs consensus, guidance revision
- Surprise percentile, revision momentum

### 5.15 Sentiment / NLP
- News sentiment score (FinBERT), article volume, sentiment volatility
- Social sentiment (X/TradingView/Moneycontrol), buzz volume, retail fear/greed
- Earnings-call transcript tone, Q&A aggression, guidance language (LLM-scored)
- Annual-report risk-section length/negativity, topic embeddings
- Entity-specific embedding similarity to historical events

### 5.16 Cross-asset relationships
- Gold-crude ratio, USDINR-gold correlation, equity-bond yield spread
- INR carry proxy, commodity basket factor exposure

### 5.17 Time / calendar
- Day-of-week, month, quarter-end, expiry-week dummy (NSE weekly expiry Thursdays)
- Pre/post earnings window, pre/post budget, election-period dummy
- Seasonality (SAD, January effect adapted), festival-period dummies

### 5.18 Rolling statistics
- Rolling mean/std/skew/kurt/min/max/quantile of returns, volume, spread
- Rolling Sharpe/Sortino/Calmar over windows

### 5.19 Lag / autoregressive
- Lagged returns/vol/volume (1..N), AR(1..p) residuals, ACF/PACF features

### 5.20 Target / categorical encoding
- Industry one-hot/hashing, peer-cluster id, regime label encoding
- Out-of-fold target encoding for slow fundamentals (leakage-safe)

**Total:** comfortably 600–1000 after cross-multiplication of windows/transformations. Catalog lives in `features/registry.py` with metadata (source, window, PIT rule, owner).

---

## 6. ML Pipeline (Tabular / Gradient-Boosted)

**Stack:** scikit-learn + **XGBoost, LightGBM, CatBoost, RandomForest** orchestrated via a common `Trainer` interface.

- **Target design:** multi-target
  - `direction` = sign of forward return over horizon H (classification)
  - `return` = forward return (regression)
  - `vol` = forward realized vol (regression, for risk)
- **Training:** each model trained with time-series-aware CV, class weighting, quantile loss option.
- **HPO:** Optuna (TPE) per model, budgeted.
- **Calibration:** isotonic/Platt on out-of-fold predictions → calibrated probabilities.
- **Why these fit:** handle heterogeneous tabular features, missingness, categoricals (CatBoost native), fast iteration, strong baselines. They dominate cross-sectional signal in practice.

---

## 7. Deep Learning Pipeline (Sequential / Temporal)

**Stack:** PyTorch + PyTorch Lightning + PyTorch Forecasting; optional JAX for speed.

Models and fit:

- **LSTM / GRU** — sequence modeling of raw price/volume/options time series; capture non-linear temporal dependencies; strong for single-asset sequential priors.
- **Temporal Fusion Transformer (TFT)** — best-in-class for multi-horizon, interpretable (attention + variable selection); handles static (fundamentals), known future (macro calendar), observed past. **Primary deep workhorse.**
- **N-BEATS** — pure deep stack for univariate trend/seasonality; good as a benchmark / component.
- **PatchTST** — patches time series into tokens, transformer encoder; SOTA sample-efficiency on long series; great for high-frequency/long-window features.
- **TimeMixer** — multi-scale mixing (past & future), strong recent SOTA for long-horizon; complements PatchTST.
- **TabNet** — attentive tabular DL; bridges tabular + deep; useful for fundamental-heavy cross-section.
- **Transformer (custom, encoder-only)** — for cross-asset/attention over feature tokens and news tokens; optional.

Each outputs distributional forecasts (mean + quantile heads) for uncertainty.

---

## 8. NLP Pipeline

**Inputs:** news (RSS, Moneycontrol, Economic Times, Reuters/PTI), social (X/Twitter, TradingView ideas, forums), earnings transcripts, annual reports, RBI statements, economic calendar text.

**Components:**
- **Ingest + dedup + entity linking** (map to ISIN/symbol via NER).
- **Embeddings:** FinBERT (finance-tuned), multilingual + IndicBERT for Hindi/regional business news, sentence-transformers for clustering, **LLM (local Mixtral/Llama via Ollama or API) for structured event extraction & summarization**.
- **Sentiment:** per-entity sentiment score + confidence + volume + volatility-of-sentiment.
- **Event extraction:** earnings dates, guidance changes, acquisitions, regulation, probes — typed events with timestamps → fed as features & to vector store.
- **Vector store (Qdrant):** store embeddings; enable "similar historical episodes" retrieval for explainability ("last time this pattern + sentiment occurred, stock did X").
- **Summarizer:** condense a company's last-N articles into a 3-bullet briefing for the explainability layer.

---

## 9. Ensemble Pipeline (Multi-Stage Stacking)

**Level 1 (base learners)** — heterogeneous, trained independently:
- Tabular: XGBoost, LightGBM, CatBoost, RF, TabNet
- Sequential: LSTM, GRU, TFT, N-BEATS, PatchTST, TimeMixer

**Level 2 (meta-learner)** — trained on **out-of-fold** Level-1 predictions (strict temporal split, no leakage):
- Inputs: each base model's P(up), P(down), E[return], per-horizon; plus meta-features (regime, volatility, liquidity, time-since-last-retrain, disagreement/entropy among Level-1).
- Model: **LightGBM / Gradient-boosted meta** (robust, fast) or shallow neural net.
- Output: final calibrated P(up), P(down), E[return], and an explicit **uncertainty / disagreement** estimate.

**Confidence estimation:**
- Model **disagreement** (variance/entropy across Level-1).
- **Conformal prediction** bands (exchangeable, distribution-free) → valid prediction intervals for E[return].
- **Aleatoric + epistemic** decomposition where models provide it.

**Calibration:** isotonic regression / temperature scaling on the meta output using a rolling holdout; continuously monitored via reliability diagrams + Brier score.

**Probability outputs:** P(up) + P(down) + P(flat) partition sums to 1; E[return] independent regression head; confidence in [0,1].

---

## 10. Backtesting Engine

**Two modes:**
- **Vectorized** (fast sweeps, signal research).
- **Event-driven** (realistic: bar-by-bar, portfolio state, orders, fills) — the source of truth for go/no-go.

**Costs (Indian-specific, all modeled):**
- Brokerage (flat or %), **STT** (0.025% intraday equity sell / 0.1% delivery), exchange txn charges, **SEBI charges**, **stamp duty** (state-wise), **GST** 18% on charges, **DP charges** on delivery sell, funding/margin interest.
- **Slippage:** volume-participation model (Almgren-Chriss style) + spread proxy from bid-ask/options; worst-case + expected.

**Position sizing:** fixed-fractional, **Kelly (fractional, capped)**, volatility-targeting, risk-parity; per-name + portfolio caps.

**Risk management:** per-trade stop, trailing stop, max position %, sector cap, max gross/net exposure, drawdown halt, volatility circuit-breaker.

**Portfolio optimization:** mean-variance (Markowitz), **Hierarchical Risk Parity (HRP)** (robust to estimation error — recommended default), risk parity, Black-Litterman with views from model.

**Metrics:** Sharpe, **Sortino**, Calmar, **Max Drawdown**, **Profit Factor**, **CAGR**, **Win Rate**, turnover, hit/miss by regime, information ratio, alpha/beta vs Nifty, expectancy, exposure, tail ratio. Plus **deflated Sharpe ratio** (Bailey-Pópelař) to reject lucky backtests.

---

## 11. Paper Trading Engine

- **Simulated broker** with realistic order types (MKT, LMT, SL, SL-M), partial fills, reject reasons.
- **Intraday & delivery** modes; margin/SPAN-like checks approximated.
- **Latency simulation** (network + decision lag) to stress-test the live path.
- **Reconciliation** vs actual market by replay — measures implementation shortfall.
- Emits the same prediction/decision schema as live, so paper→live is a config flip.

---

## 12. Live Prediction Engine

- **Feature server** (Feast online / Redis) serves point-in-time features sub-ms.
- **Model server** (KServe/Seldon or Triton) loads registered ensemble; canary + shadow deployments.
- **Ensemble runtime** fuses Level-1 → meta → calibration → conformal.
- **Decision module** turns probability + confidence + risk into action (size, stop, target) via risk overlay.
- **Latency budget:** pre-open & intraday signals within seconds of bar close; event-driven news signals within minutes.
- **Consistency guard:** asserts train/serve feature parity; rejects inference if feature schema drift.

---

## 13. Explainability

- **Global:** SHAP feature importance (permutation + TreeSHAP), feature interaction (SHAP interaction), PDP/ICE.
- **Local (per prediction):** SHAP force plots → top contributing factors; attention weights from TFT; counterfactual "what if VIX were lower."
- **Narrative:** LLM-generated plain-English explanation assembled from: top SHAP factors, retrieved similar historical episodes (vector store), latest news summary, options-sentiment context.
- **Output includes** "Top contributing factors" so every trade is justifiable to risk/PM.

---

## 14. Monitoring

- **Data drift:** PSI, KS test, population drift on input features; freshness/latency SLAs per source.
- **Model drift:** rolling IC, directional accuracy, calibration error (Brier/ECE), P&L decay; concept-drift detectors (ADWIN, Page-Hinkley).
- **Serving:** latency, error rate, throughput, GPU/CPU, feature-missing rate.
- **Business:** live P&L, exposure, drawdown, slippage-vs-expected, fill rate.
- **Dashboards (Grafana)** + alerting (Slack/PagerDuty) with severity tiers and auto-rollback hooks.

---

## 15. Logging

- **Structured JSON logs** (structlog) with correlation IDs across ingest→train→serve.
- **Audit trail:** every prediction, its feature snapshot, model version, decision, and outcome stored immutably → post-mortem & regulatory readiness.
- **Tracing:** OpenTelemetry spans for pipeline performance.
- **PII/compliance:** minimal, access-controlled; SEBI/audit-friendly retention.

---

## 16. CI/CD

- **Git + GitHub Actions** (or GitLab CI).
- **Stages:** lint (ruff), type-check (mypy), unit → integration → data-validation → model-regression → backtest-gate → build images → deploy (staging) → canary (prod).
- **Model validation gate:** a PR/merge cannot promote a model unless it passes: no leakage test, backtest beat baseline on deflated Sharpe, calibration within tolerance, drift thresholds OK.
- **Infrastructure as code:** Terraform for cloud; Helm for k8s.
- **Artifact promotion:** MLflow model stage transition (Staging→Production) only via passing gate.

---

## 17. Testing Strategy

- **Unit:** feature transforms (known-input/known-output), cost/slippage math, metric formulas.
- **Integration:** collector→lake→feature store round trips; train→register→serve path.
- **Data validation:** schema + PIT + corporate-action continuity tests on golden datasets.
- **Leakage tests:** assert no future feature correlates with target beyond noise; "FutureLeak" harness.
- **Model regression:** new model must not degrade baseline metrics (CI-enforced).
- **Backtest determinism:** fixed seeds → identical results; cost model unit tests vs hand-computed examples.
- **Replay/consistency:** serve features == train features for same `as_of_ts`.
- **Chaos / resilience:** kill a collector, assert alert + backfill; degrade gracefully.
- **E2E:** paper-trade a known window, reconcile P&L vs expected.

---

## 18. Deployment Strategy

- **Containerization:** Docker per service; **Kubernetes** for orchestration (HPA by load).
- **Workflow orchestration:** Airflow/Prefect for batch DAGs (ingest→feature→retrain).
- **Serving:** KServe/Seldon (or Triton for DL) with canary + shadow; FastAPI for the prediction API.
- **Environments:** dev → staging (paper) → prod (live, initially small capital).
- **Auto-retrain:** drift/performance triggers a retrain DAG; new model shadow-tests before promotion.
- **Secrets/config:** Vault / cloud secret manager; Hydra for config.
- **On-prem note:** heavy DL/HPO can run on the Lenovo LOQ dGPU for research; production scales to cloud GPU.

---

## DATA SOURCES — How Each Is Used

| Source | Primary use | Notes |
|---|---|---|
| **NSE / BSE** | EOD + intraday prices, volumes, corporate actions, F&O, breadth, delivery %, OI | Official; NSE anti-bot → use vendor (TrueData, NSEPy, EODHistoricalData) + cache |
| **Yahoo Finance** | Free EOD/adj prices, index, macro proxies, global indices | Backup/breadth; less reliable → validation gate |
| **Corporate actions** | Total-return adjustment (splits/bonus/dividends) PIT | Critical for clean returns |
| **Financial statements** | Fundamental ratios, quality/growth/value factors | Quarterly; PIT by filing date |
| **Quarterly earnings** | Earnings surprise, revision momentum, transcript NLP | Event features + NLP |
| **Promoter holdings** | Governance/confidence signal, pledging risk | Slow factor |
| **FII/DII activity** | Flow-driven momentum, sector flow, index-future positioning | Strong short-term Indian signal |
| **Mutual fund holdings** | Sticky domestic flow, accumulation/distribution | Confirms trends |
| **Options chain** | PCR, IV skew, max pain, OI build-up, gamma proxy | Powerful 0DTE/weekly-expiry signal |
| **India VIX** | Regime/vol state, fear gauge, vol targeting | Direct feature + risk overlay |
| **USDINR** | Cross-asset risk-off, IT/pharma vs import sectors | Macro factor |
| **Gold** | Safe-haven, correlation, rural wealth proxy | Cross-asset |
| **Crude Oil** | OMC/aviation/inflation passthrough | Sector-specific macro |
| **RBI announcements** | Policy-window dummy, rate-surprise, liquidity | Event risk overlay |
| **Inflation (CPI/IIP)** | Macro regime, rate-expectation, consumption | Slow factor |
| **Interest rates (G-sec)** | Yield curve, discount rate, bond-equity spread | Cross-asset |
| **GDP** | Macro trend, sector demand | Slow factor |
| **Economic calendar** | Known-event dummies, avoid trading into binary events | Risk control |
| **News** | Sentiment, event extraction, embeddings, explainability | NLP core |
| **Social sentiment** | Retail positioning, fear/greed, buzz | Contrast vs FII for contrarian |
| **Annual reports** | Risk-section tone, long-doc embeddings, governance | Deep NLP |

---

## MODELS — Comparison & Recommendation

| Model | Strength | Weakness | Fit here |
|---|---|---|---|
| **XGBoost** | Fast, robust, strong tabular baseline | Less native categoricals | Cross-sectional core |
| **LightGBM** | Faster, handles categoricals, GOSS | Slightly less stable | Default meta-learner + core |
| **CatBoost** | Native categoricals, low leakage, ordered boosting | Slower | Fundamental/categorical-heavy |
| **Random Forest** | Stable, low variance baseline, interpretable | Weaker accuracy | Baseline / uncertainty |
| **LSTM** | Sequential nonlinear deps | Hard to tune, less interpretable | Single-asset temporal prior |
| **GRU** | Lighter than LSTM | Similar limits | Lightweight temporal |
| **TFT** | Multi-horizon, interpretable, multi-type inputs | Heavier | **Primary deep model** |
| **N-BEATS** | Strong univariate forecast | Univariate only | Benchmark/component |
| **PatchTST** | SOTA long-series sample efficiency | Transformer cost | Long-window features |
| **TimeMixer** | SOTA multi-scale long-horizon | Newer, less battle-tested | Complement to PatchTST |
| **TabNet** | Attentive tabular DL | Needs more data | Fundamental cross-section |
| **Transformer (enc)** | Cross-asset/feature attention | Data-hungry, cost | Optional research |

**Recommendation:** Tree models (LightGBM/CatBoost) as the reliable cross-sectional base; **TFT as the deep backbone**; PatchTST/TimeMixer as temporal specialists; all stacked. Don't bet on one.

---

## TRAINING

- **Walk-forward validation:** rolling window (train → validate → test forward), repeated; reports per-fold + aggregated OOS.
- **Time-series CV:** Purged K-fold + **embargo** (no leakage across fold boundary); group by regime.
- **HPO:** Optuna (multi-objective: IC + calibration), pruner, study persistence.
- **Concept drift detection:** PSI/KS on features, ADWIN on residuals; trigger retrain.
- **Automatic retraining:** scheduled (weekly/monthly) + event-triggered (drift/regime change); register candidate, shadow-test, promote on gate.
- **Feature selection:** SHAP/importance pruning, Boruta, stability selection; keep interpretable core.
- **Data leakage prevention:** PIT lineage, purged CV, no forward-looking macros, OOF target encoding, "FutureLeak" harness in CI.

---

## OUTPUT SCHEMA (every prediction)

```json
{
  "symbol": "RELIANCE",
  "as_of_ts": "2026-07-16T15:30:00+05:30",
  "horizon_days": 5,
  "prob_up": 0.58,
  "prob_down": 0.34,
  "prob_flat": 0.08,
  "expected_return": 0.021,
  "return_ci_low": -0.014,
  "return_ci_high": 0.057,
  "confidence": 0.71,
  "risk_score": 0.42,
  "suggested_stop_loss_pct": -0.045,
  "suggested_take_profit_pct": 0.062,
  "recommended_action": "LONG_PARTIAL",
  "position_size_pct": 1.8,
  "top_contributing_factors": [
    {"feature": "fii_net_buy_5d", "impact": +0.12, "direction": "up"},
    {"feature": "options_pcr", "impact": -0.06, "direction": "down"},
    {"feature": "news_sentiment_3d", "impact": +0.05, "direction": "up"}
  ],
  "explanation": "Model is mildly bullish: strong FII inflows over 5 days and positive 3-day news sentiment outweigh a slightly elevated put-call ratio. Confidence moderate; similar episodes historically returned +2.1% over 5d (62% up).",
  "model_version": "ensemble-2026.07.01",
  "regime": "risk_on_trending"
}
```

---

## SOFTWARE ARCHITECTURE — Recommendations

| Concern | Recommendation |
|---|---|
| Language | **Python** (research/ML/serve) + **Rust/C++** for hot loops (matching, cost sim) |
| Dataframes | **Polars** (fast) + **Pandas**; **DuckDB** for ad-hoc |
| ML | scikit-learn, XGBoost, LightGBM, CatBoost, Optuna |
| DL | PyTorch, PyTorch Lightning, PyTorch Forecasting |
| NLP | HuggingFace Transformers (FinBERT), sentence-transformers, Ollama (local LLM) |
| DB | TimescaleDB / ClickHouse + Postgres |
| Vector DB | **Qdrant** |
| Cache | Redis |
| Task queue | Celery + Redis (or Arq) |
| Orchestration | Airflow / Prefect |
| Experiment tracking | MLflow + Weights & Biases |
| Containerization | Docker |
| Deploy/orchestrate | Kubernetes + Helm |
| Model serving | KServe / Seldon / Triton |
| API | FastAPI |
| Monitoring | Prometheus + Grafana + Loki |
| CI/CD | GitHub Actions + Terraform |
| Config | Hydra / OmegaConf |

---

## DEVELOPMENT ROADMAP & MILESTONES

**Phase 0 — Foundations (4–6 wks):** repo, CI, storage, object store, logging, config, data contracts.
**Phase 1 — Data (6–8 wks):** all collectors + validation + PIT corporate-action adjustment + feature store skeleton.
**Phase 2 — Features (4 wks):** implement feature registry to ~600 features; unit tests.
**Phase 3 — Baseline models (4 wks):** LightGBM/CatBoost baselines + walk-forward + leakage harness.
**Phase 4 — Backtest engine (4–6 wks):** event-driven + Indian cost model + metrics + deflated Sharpe.
**Phase 5 — Deep + NLP (6–8 wks):** TFT/PatchTST/TimeMixer + NLP/sentiment + vector store.
**Phase 6 — Ensemble + calibration (4 wks):** stacking, conformal, confidence, explainability.
**Phase 7 — Paper trading (4 wks):** simulated broker, reconciliation, dashboards.
**Phase 8 — Live (small capital) + monitoring (ongoing):** canary, drift, auto-retrain.
**Phase 9 — Scale:** more names, more horizons, options-strategy layer, factor book.

---

## RISKS

- **Leakage** → false edge (mitigated by PIT + CI harness).
- **Overfitting** → use deflated Sharpe, purged CV, shrinkage.
- **Regime change** → drift detection + auto-retrain + risk overlays.
- **Data quality/vendor failure** → multi-source + validation + backfill + alerts.
- **Cost/slippage erosion** → cost model first-class; only trade liquid names.
- **Regulatory (SEBI)** → audit trail, compliant execution, algo-registration if needed.
- **Latency** → separate research vs live paths; cache; feature parity guard.
- **Liquidity/impact** → position caps, participation limits, focus on liquid large/mid-caps.
- **Capital-at-risk** → live starts tiny; risk overlays hard-stop drawdowns.

---

## FUTURE IMPROVEMENTS

- Options/volatility trading strategies (not just directional equity).
- Reinforcement-learning execution (optimal slicing, slippage minimization).
- Cross-asset global macro layer (US rates, EM flows).
- LLM agent for autonomous research + hypothesis generation.
- Alternative data (satellite, credit-card, app downloads) for select names.
- Factor-investing book + smart-beta products on top of signals.
- On-chain/stablecoin FX liquidity as an INR pressure gauge.
- Auto-ML + neural architecture search for the DL specialists.

---

*End of design v1.0. Next step (on your go-ahead): scaffold Phase 0 repo + storage + CI, then build collectors. No production code has been written.*
