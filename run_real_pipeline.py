"""End-to-end REAL-data pipeline on RELIANCE.NS (2023-2026).

Ingest -> features -> target -> walk-forward LightGBM -> conformal -> backtest.
Maps EODBar (date) into the feature/target contract (event_ts=15:30 close,
symbol=RELIANCE) before feature engineering.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from src.data.collectors.yfinance import YFinanceCollector
from src.features.momentum import calculate_momentum_features
from src.features.volatility import calculate_volatility_features
from src.features.volume import calculate_volume_features
from src.data.targets import calculate_forward_returns
from src.training.walk_forward import WalkForwardCV
from src.models.ml.lightgbm_trainer import LightGBMTrainer
from src.backtest.engine import VectorizedBacktester

print("=== 1. INGEST REAL RELIANCE.NS (2023-2026) ===")
col = YFinanceCollector(provider="yfinance")
bars = list(col.collect_range("RELIANCE", dt.date(2023, 1, 1), dt.date(2026, 7, 1)))
df = pd.DataFrame([b.__dict__ for b in bars])
df["symbol"] = "RELIANCE"
# feature/target contract expects event_ts = close time (15:30 IST)
df["event_ts"] = pd.to_datetime(df["date"].astype(str)) + pd.Timedelta(hours=15, minutes=30)
df = df.sort_values("event_ts").reset_index(drop=True)
print(f"rows={len(df)} range={df['date'].min()}..{df['date'].max()}")

print("=== 2. FEATURES (PIT-safe) ===")
df = calculate_momentum_features(df)
df = calculate_volatility_features(df)
df = calculate_volume_features(df)
feat_cols = [c for c in df.columns if c.startswith("feat_")]
print(f"features({len(feat_cols)}): {feat_cols}")

print("=== 3. TARGET: 5d forward return ===")
df = calculate_forward_returns(df, horizons=[5])
print(f"target non-null: {df['target_fwd_ret_5d'].notna().sum()}")

print("=== 4. WALK-FORWARD LIGHTGBM (purged) ===")
cv = WalkForwardCV(n_splits=5, train_size_days=252, test_size_days=63, gap_days=5)
cv.validate_gap_for_horizon(5)
tr = LightGBMTrainer(target_col="target_fwd_ret_5d", feature_cols=feat_cols)
res = tr.train_and_evaluate(df, cv)
print("OOS:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in res.items()})

print("=== 5. CONFORMAL PREDICT (recent 63d) ===")
clean = df.dropna(subset=feat_cols + ["target_fwd_ret_5d"]).reset_index(drop=True)
recent = clean.iloc[-63:]
pts = tr.predict(recent)
ivs = tr.predict_interval(recent)
print(f"recent mean pred={pts.mean():.4f} ci_half={ivs[0].width/2:.4f}")

print("=== 6. BACKTEST NET OF COST (real prices) ===")
bt_df = clean.copy()
bt_df["prediction"] = tr.model.predict(bt_df[feat_cols])
bt = VectorizedBacktester(top_n=1)
brec = bt.run(bt_df[["symbol", "event_ts", "prediction", "close"]],
              prediction_col="prediction", price_col="close")
s = brec["summary"]
print("BACKTEST:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()})
print("DONE")
