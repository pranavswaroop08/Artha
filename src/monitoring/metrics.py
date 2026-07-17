"""Prometheus metrics for the Artha serving API.

Uses a dedicated CollectorRegistry so tests (and multiple app instances) don't
collide on the global default registry.
"""
from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram

REGISTRY = CollectorRegistry()

PREDICT_REQUESTS = Counter(
    "artha_predict_requests_total",
    "Total number of predictions made",
    ["recommended_action"],
    registry=REGISTRY,
)

PREDICT_LATENCY = Histogram(
    "artha_predict_latency_seconds",
    "Latency of the /predict endpoint in seconds",
    registry=REGISTRY,
)

PREDICTION_CONFIDENCE = Histogram(
    "artha_prediction_confidence",
    "Distribution of model confidence scores",
    buckets=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
    registry=REGISTRY,
)
