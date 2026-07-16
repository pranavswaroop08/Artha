"""Feast Feature Definitions for Artha.

Enforces Point-in-Time (PIT) discipline at the feature-retrieval layer:
the EOD feature view uses ``event_ts`` as the event timestamp (when the
market bar occurred) and ``as_of_ts`` as the created timestamp (when the
data became publicly knowable). Historical feature fetches therefore can
only return data knowable at the training/serving ``as_of`` time.

Offline store = parquet (file-based, CI-friendly). Online store = sqlite
(no Docker needed in dev; swap to Redis/Postgres in production).
"""
from __future__ import annotations

from datetime import timedelta

from feast import Entity, FeatureView, Field, FileSource
from feast.types import Float32, Int64
from feast.value_type import ValueType
from feast.data_format import ParquetFormat

# Core entity: a tradable symbol (e.g. RELIANCE.NS on Yahoo, 500325 on BSE).
symbol_entity = Entity(
    name="symbol",
    value_type=ValueType.STRING,
    description="Stock ticker symbol (e.g., RELIANCE.NS)",
)

# Parquet-backed offline source. `file_format` selects parquet; PIT columns
# are pinned so Feast's point-in-time join respects disclosure timing.
eod_parquet_source = FileSource(
    name="eod_parquet_source",
    path="data/offline/eod_data.parquet",
    file_format=ParquetFormat(),
    timestamp_field="event_ts",
    created_timestamp_column="as_of_ts",
)

eod_market_data_view = FeatureView(
    name="eod_market_data",
    entities=[symbol_entity],
    ttl=timedelta(days=3650),  # 10y lookback for training
    schema=[
        Field(name="open", dtype=Float32),
        Field(name="high", dtype=Float32),
        Field(name="low", dtype=Float32),
        Field(name="close", dtype=Float32),
        Field(name="volume", dtype=Int64),
    ],
    online=True,
    source=eod_parquet_source,
    tags={"domain": "market_data", "provider": "mock"},
)
