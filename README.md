# Artha — Institutional-Grade NSE/BSE Forecasting Platform

> **Codename:** *Artha* (Sanskrit for wealth / prosperity — one of the four Purushārthas).
> **Local folder:** `D:\project\quant-platform\` (singular `project`, NOT `projects`).
> **Repo:** `github.com/pranavswaroop08/Artha` (GitHub auto-capitalized the name).
> **Truth source:** this README + `quant-platform-design.md` + Obsidian vault `C:\Users\prana\Documents\Obsidian Vault\Quant Platform.md`.

This README is written **for AI agents** (and future sessions). It is the handoff document. If you are an agent dropped into this repo, read it top-to-bottom before writing code.

---

## 1. What this project is (and is NOT)

**Goal:** Build a production-grade AI platform that forecasts Indian equities (NSE + BSE) with the highest *realistically achievable* predictive performance.

**Every prediction outputs:**
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
    {"feature": "fii_net_buy_5d", "impact": 0.12, "direction": "up"},
    {"feature": "options_pcr", "impact": -0.06, "direction": "down"}
  ],
  "explanation": "FII inflows + positive news sentiment outweigh elevated put-call ratio.",
  "model_version": "ensemble-2026.07.01",
  "regime": "risk_on_trending"
}
```

**What it is NOT:**
- Not a "market predictor." There is no model that beats the market reliably. The realistic goal is a **small, repeatable, risk-adjusted edge** expressed as a *calibrated probability distribution*, not point forecasts.
- Not a trading bot yet. Phase 0 is foundation only. No production models exist.
- Not a get-rich-quick scheme. Capital protection is priority #1.

**Realistic internal targets (set expectations):**
- Cost-aware directional accuracy on liquid large-caps: **~55–62% OOS**. Anything claiming >70% sustained = leakage or overfit.
- Cross-sectional monthly Information Coefficient (IC): **0.03–0.08**.
- Edge compounds via **position sizing + risk overlays**, not per-trade accuracy.

---

## 2. The 3 load-bearing design rules (NEVER violate)

These are the difference between a real quant system and a lucky backtest. Any agent contributing code must respect them.

### Rule A — Point-in-Time (PIT) discipline is the #1 leakage defense
- Every fact carries `as_of_ts` (when it became *publicly knowable*) and `event_ts`.
- Fundamental/earnings data is **invisible to the model before its disclosure timestamp**.
- Feature code must be identical in training and serving (see Rule C).
- A `FutureLeak` harness (CI gate) injects future features and asserts the model cannot learn them.

### Rule B — Costs are first-class
Indian trading costs are modeled explicitly in every backtest and live decision:
- STT (0.025% intraday / 0.1% delivery), SEBI fees, exchange charges, stamp duty, **GST 18%** on charges, DP charges, brokerage, slippage (volume-participation / Almgren-Chriss-lite).
- **A signal that dies after costs is not a signal.** Never report raw returns without cost overlay.

### Rule C — Train/serve feature parity
- The exact same transformation code serves both training and inference via a **feature store (Feast)**. No divergent logic. No manual feature recomputation in notebooks that bypasses the store.

### Additional principles
- **Ensemble of heterogeneous learners** (tree models + deep models + NLP + meta-learner). No single model wins.
- **Drift is the enemy** → automatic retraining + drift surveillance mandatory.
- **Explainability is a risk control**, not marketing. If we can't explain a prediction, we don't trade it.

---

## 3. Architecture (condensed — full version in `quant-platform-design.md`)

Hybrid **batch + streaming + event-driven**. Three planes:

| Plane | Responsibility |
|---|---|
| **Data** | collectors → raw lake (immutable) → validation → feature store |
| **Model** | feature read → HPO → train → walk-forward eval → register → ensemble → calibrate |
| **Serving** | backtest → paper trade → live inference → execution → monitoring |

**Full subsystem list (18):** architecture · folder structure · data pipeline · data storage · feature engineering · ML pipeline · DL pipeline · NLP pipeline · ensemble pipeline · backtesting engine · paper trading engine · live prediction engine · explainability · monitoring · logging · CI/CD · testing · deployment · software architecture.

---

## 4. Tech stack (recommended / in use)

| Concern | Choice |
|---|---|
| Language | **Python** 3.10–3.12 (Rust/C++ reserved for hot loops later) |
| Dataframes | Polars (fast) + Pandas; DuckDB for ad-hoc |
| ML | scikit-learn, XGBoost, LightGBM, CatBoost, Optuna |
| DL | PyTorch, PyTorch Lightning, PyTorch Forecasting |
| NLP | HuggingFace Transformers (FinBERT), sentence-transformers, local LLM (Ollama) |
| Time-series DB | TimescaleDB (Postgres extension) |
| Relational | PostgreSQL |
| Cache / online features | Redis |
| Feature store | Feast (offline TS DB + online Redis) |
| Vector DB | Qdrant (news/social embeddings) |
| Experiment tracking | MLflow + Weights & Biases |
| Orchestration | Airflow / Prefect |
| Containerization | Docker |
| Deploy / orchestrate | Kubernetes + Helm |
| Model serving | KServe / Seldon / Triton |
| API | FastAPI |
| Monitoring | Prometheus + Grafana + Loki |
| CI/CD | GitHub Actions + Terraform |

**Models and where they fit:**
- **LightGBM / CatBoost** → cross-sectional tabular core (fast, robust baselines).
- **TFT (Temporal Fusion Transformer)** → **primary deep model** (multi-horizon, interpretable attention + variable selection).
- **PatchTST / TimeMixer** → temporal/long-series specialists (SOTA sample efficiency).
- **LSTM / GRU / N-BEATS / TabNet / Transformer** → supplementary / research.
- **Random Forest** → baseline + uncertainty estimate.
- **Ensemble:** L1 heterogeneous → L2 LightGBM meta on out-of-fold predictions + meta-features → isotonic calibration → **conformal prediction** bands → confidence from model disagreement.

---

## 5. Repository structure (what's BUILT vs PLANNED)

```
quant-platform/            ← this repo root
├── README.md            ← you are here (agent handoff)
├── quant-platform-design.md   ← full 18-subsystem design spec
├── quant-platform-issues.md   ← 150-issue dependency-ordered backlog
├── gen_issues.py        ← backlog generator + dependency validator (rerun to regenerate)
├── pyproject.toml      ← deps, ruff/black/mypy config
├── .pre-commit-config.yaml
├── Makefile             ← make install / bootstrap / dev-up / test / gen-issues
├── docker-compose.yml   ← pg/timescale, redis, minio, qdrant, mlflow
├── .env.example        ← copy to .env, fill secrets (NEVER commit .env)
├── alembic.ini
├── configs/            ← base + dev/staging/prod overlays (Hydra/OmegaConf)
│   ├── config.yaml
│   ├── config.dev.yaml / config.staging.yaml / config.prod.yaml
│   ├── data/contracts/   ← (planned) Pandera/Great-Expectations schemas
│   ├── features/         ← (planned) feature registry
│   ├── models/           ← (planned)
│   └── backtest/         ← (planned)
├── migrations/
│   └── versions/0001_baseline.py   ← Postgres + Timescale hypertables (DESIGNED, not runtime-tested)
├── src/
│   ├── common/         ← ✅ config, logging+correlation-id, exceptions
│   ├── data/
│   │   ├── raw_lake.py          ← ✅ immutable, content-hashed, idempotent
│   │   ├── symbols.py           ← ✅ symbol master (NSE/BSE/ISIN reconcile)
│   │   ├── validators.py        ← ✅ EOD schema/quality contracts
│   │   └── collectors/
│   │       └── nse.py          ← ✅ provider-agnostic NSE collector (mock + real interface)
│   ├── features/       ← (planned) registry + 20 feature families
│   ├── nlp/            ← (planned)
│   ├── models/          ← (planned) ml/ + dl/ trainers
│   ├── ensemble/        ← (planned)
│   ├── training/        ← (planned) walk-forward, purged CV, leakage
│   ├── backtest/        ← ✅ Indian cost model · (planned) event engine
│   ├── trading/         ← (planned) paper + live engines
│   ├── serve/           ← (planned) FastAPI, explainability
│   ├── monitoring/      ← (planned)
│   └── logging/         ← ✅ structured logging
├── tests/
│   ├── unit/            ← ✅ 50 tests across common, data, pit, targets, collectors, corp-actions, costs, features, feast
│   ├── leakage/         ← ✅ future-leak CI harness (4 tests)
│   ├── integration/      ← (planned)
│   ├── features/ nlp/ ensemble/ serve/ monitoring/  ← (planned)
│   └── e2e/            ← (planned)
├── feature_store/       ← ✅ Feast definitions (sqlite/parquet, PIT view)
├── docs/adr/            ← ✅ ADR-0001 targets · 0002 Feast store · 0003 MLflow-only
├── docker/ k8s/ airflow/ scripts/ docs/   ← (scaffold)
```

**Legend:** ✅ = implemented & tested · (planned) = designed, not built.

---

## 6. Current status (as of 2026-07-17)

| Milestone | Status |
|---|---|
| System design (18 subsystems) | ✅ done (`quant-platform-design.md`) |
| 150-issue backlog | ✅ done (`quant-platform-issues.md`) |
| **Phase 0 scaffold** | ✅ **done, pushed to `Artha`** |
| **Phase 1 (data pipeline + PIT + features)** | ✅ **done, 54 tests passing** |
| Phase 2+ (models, backtest, ensemble, serving) | ⬜ next |

**Phase 0 delivered:** config (Hydra), structured logging + correlation-id, raw lake, symbol master, provider-agnostic NSE collector, validation contracts, Alembic Timescale migration, docker-compose stack, pyproject/pre-commit/Makefile, README.

**Phase 1 delivered (all unit-tested, real `pytest` runs):**
- **PIT & lineage** — `pit.py` (get_pit_dataframe, assert_no_future_leakage), `lineage.py` (LineageTracker, content hashing), `validate_pit_row`.
- **Collectors** — provider-agnostic BSE + Yahoo Finance collectors (mock clients, `collect_range`), mirroring the NSE pattern.
- **Feast foundation** — `feature_store/feature_repo/` with sqlite online + file(parquet) offline store (no Docker needed); `eod_market_data` FeatureView with `event_ts`/`as_of_ts` PIT columns.
- **Targets** — `targets.py` `calculate_forward_returns` (per-symbol backward-shifted forward returns).
- **Corporate actions** — `corporate_actions.py` collector + `apply_adjustments` (splits & dividends, cumulative).
- **Indian cost model** — `backtest/costs.py` `IndianCostModel` (brokerage cap, STT, exchange, SEBI, stamp, GST, DP, ADV slippage).
- **Feature families** — `features/{momentum,volatility,volume}.py` (returns, RSI, rolling vol, ATR, volume MAs/ratio), strictly backward-looking.
- **Leakage CI harness** — `tests/leakage/test_future_leak.py` actively injects timestamp + shift(-1) leakage and asserts the PIT gate catches it.

**Test suite (real counts, `python -m pytest`): 54 passed.**

| File | Tests |
|---|---|
| tests/leakage/test_future_leak.py | 4 |
| tests/unit/test_collectors.py | 6 |
| tests/unit/test_common.py | 5 |
| tests/unit/test_corporate_actions.py | 5 |
| tests/unit/test_costs.py | 8 |
| tests/unit/test_data.py | 5 |
| tests/unit/test_feature_store.py | 2 |
| tests/unit/test_features.py | 4 |
| tests/unit/test_pit.py | 9 |
| tests/unit/test_targets.py | 6 |

**Known caveats (read before claiming "it works"):**
- **Docker is NOT installed in the dev environment.** `docker compose up` and `alembic upgrade head` against a live TimescaleDB have **not been runtime-tested**. Configs/migrations are written and syntactically valid, but unverified at execution.
- **No real market data flows yet.** All collectors (NSE/BSE/YF) and the corporate-actions client use deterministic **mock** providers so dev/tests run with **zero credentials**. This is intentional.
- **Cost model constants** approximate current discount-broker + regulatory rates; verify against live SEBI/exchange schedules before real PnL attribution.
- `gh` CLI is not installed; pushes done via `git` directly.

---

## 7. How to run (agent quickstart)

```bash
# 1. Install (editable + dev deps)
python -m pip install -e ".[dev]"     # or: uv pip install -e ".[dev]"
make install

# 2. Config
cp .env.example .env                     # fill secrets; dev needs NONE (provider=mock)

# 3. Start local stack (requires Docker — NOT available in base env)
make dev-up                             # pg/timescale, redis, minio, qdrant, mlflow
make migrate                            # alembic upgrade head  (needs the stack)

# 4. Tests (NO external services required — uses mock provider + tmp paths)
python -m pytest -q                    # → 54 passed

# 5. Run the first collector (no creds needed)
python -c "
from src.data.collectors.nse import NSECollector
from datetime import date
bar = NSECollector().collect('RELIANCE', date(2026, 7, 16))
print(bar)
"

# 6. Verify PIT filtering (no creds needed)  -> prints: Rows visible at T=Jan2: 1
python -c "
import pandas as pd
from src.data.pit import get_pit_dataframe
df = pd.DataFrame({'event_ts': pd.to_datetime(['2026-01-01','2026-01-02']),
                   'as_of_ts': pd.to_datetime(['2026-01-01','2026-01-03']),
                   'close': [100, 105]})
print('Rows visible at T=Jan2:', len(get_pit_dataframe(df, pd.Timestamp('2026-01-02'))))
"

# 7. Verify Indian cost model  -> prints: cost Rs52.55 (5.26 bps)
python -c "
from src.backtest.costs import IndianCostModel
c = IndianCostModel().calculate_costs(turnover_inr=100000, is_intraday=True, is_buy=False)
print(f'cost Rs{c.absolute_cost_inr:.2f} ({c.percentage_cost_bps:.2f} bps)')
"

# 8. Verify target construction  -> prints: 5d fwd ret Jan1: 0.25
python -c "
import pandas as pd
from src.data.targets import calculate_forward_returns
df = pd.DataFrame({'symbol': ['TEST']*6,
                   'event_ts': pd.to_datetime(['2026-01-01']*6) + pd.to_timedelta(range(6), 'D'),
                   'close': [100, 110, 105, 115, 120, 125]})
t = calculate_forward_returns(df, horizons=[5])
print('5d fwd ret Jan1:', t.iloc[0]['target_fwd_ret_5d'])
"
```

> All four snippets above were executed and their outputs verified (2026-07-17).

**Run the backlog generator:**
```bash
make gen-issues      # regenerates quant-platform-issues.md from gen_issues.py
```

---

## 8. How to contribute (for agents)

1. **Read the design doc first** (`quant-platform-design.md`) — especially Rules A/B/C in §0 and §2 of this README.
2. **Read the ADRs** (`docs/adr/`) before making architecture decisions — they capture locked-in choices (ADR-0001 targets, ADR-0002 Feast store, ADR-0003 MLflow-only).
3. **Pick an issue from `quant-platform-issues.md`** (or the GitHub Issues once synced). Issues are dependency-ordered; **do not start a child issue before its parents merge.**
4. **Each issue is scoped 1–3h** and specifies: acceptance criteria, required files, required tests, docs. Match them.
5. **Tests are mandatory.** Every feature/collector/model needs a unit test. The repo runs `pytest` with no external services (use `tmp_path`, mock providers, in-memory stores).
6. **Keep PIT discipline.** New features must declare their `as_of_ts` source and never peek at future rows. The leakage harness (`tests/leakage/`) runs on every PR.
7. **Never fake live data.** The mock provider is for dev only; clearly separate mock/dev paths from real-data paths.
8. **Commit convention:** imperative subject (`feat:`, `fix:`, `test:`, `docs:`). Branch from `main`; keep PRs small (one issue = one PR ideally).
9. **Regenerate the backlog** only via `make gen-issues` (edit `gen_issues.py`, never hand-edit the markdown).

**Next recommended work (Phase 2, unblocked):**
- `src/models/ml/lightgbm_trainer.py` — baseline LightGBM cross-sectional model
- `src/training/walk_forward.py` — walk-forward CV with purged gaps (gap > horizon)
- `src/backtest/engine.py` — event-driven backtest engine using `IndianCostModel`
- Feast materialization pipeline — `feast apply` + `feast materialize` against mock data
- Upgrade corporate-actions/collectors from mock to real vendor interfaces (needs creds)

---

## 9. Data sources (designed — most not yet collected)

NSE · BSE · Yahoo Finance (backup) · corporate actions · financial statements · quarterly earnings · promoter holdings · FII/DII activity · mutual fund holdings · options chain · India VIX · USDINR · gold · crude oil · RBI announcements · inflation (CPI/IIP) · interest rates / G-sec · GDP · economic calendar · news · social sentiment · annual reports.

**Critical:** NSE/BSE are **anti-bot**; production needs a **paid vendor** (TrueData / EODHistoricalData). The collector is provider-agnostic — implement `NSEClient` subclasses and wire them in `src/data/collectors/nse.py::_build_client` via the `NSE_PROVIDER` env var + token. Do NOT commit vendor tokens.

---

## 10. Critical footguns (avoid these)

- **Folder is `D:\project\quant-platform\`** (singular `project`). `D:\projects` (plural) does not exist.
- **`mock` provider is intentional** — don't "upgrade" it to return fake live-looking numbers. Keep mock clearly isolated.
- **Docker not in base env** — don't assume `make dev-up` works in CI; tests must run without it.
- **Leakage is the #1 trap** — when building features, ask "could the model see this before it was public?" If yes, it's a PIT violation.
- **Costs** — never report raw returns without the Indian cost model (see Rule B).
- **Secrets** — `.env` is gitignored; `.env.example` is committed. Tokens live in env vars only.

---

## 11. Where truth lives

- **This repo** — code, design doc, backlog, configs.
- **Obsidian vault** `C:\Users\prana\Documents\Obsidian Vault\Quant Platform.md` — project narrative, decisions, tasks, backlinks (the "external brain").
- **`Accomplishments.md`** in the vault — surfaces Artha to the portfolio site.

---

## 12. One-line summary for an agent

> *Build a hedge-fund-grade, explainable NSE/BSE forecasting platform that outputs calibrated up/down probabilities + expected return + risk, with point-in-time leakage discipline and Indian cost modeling as hard constraints. Phase 0 (foundation) and Phase 1 (PIT + lineage, BSE/YF collectors, Feast foundation, targets, corporate actions, Indian cost model, feature families, leakage CI harness) are complete and tested — 54 tests green. Phase 2 (model training, walk-forward CV, backtest engine, ensemble) is the next milestone.*
