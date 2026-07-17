# ADR-0003: MLflow-Only Experiment Tracking

## Status
Accepted

## Context
Early planning mentioned both MLflow and Weights & Biases (W&B) for experiment
tracking. Running both creates a dual source of truth for model metadata,
inconsistent lineage between training and deployment, and redundant infra.

## Decision
Use **MLflow only** for experiment tracking and model registry.

Rationale:
- MLflow has a native model registry (W&B needs Artifacts + an external registry).
- Rule C (train/serve parity) needs tight coupling of training metadata and
  deployment lineage.
- MLflow is open-source and self-hostable (no SaaS dependency).
- W&B is stronger for visual exploration, but the platform prioritizes
  reproducibility over exploration.

## Current state
- `pyproject.toml` already lists **`mlflow`** and does **NOT** list `wandb`
  (verified 2026-07-17) — so no dependency removal is required; this ADR records
  the decision so W&B is not reintroduced.

## Consequences
- All training runs log to an MLflow tracking server (local in dev, dedicated in prod).
- Model registry uses the MLflow Model Registry for versioning + stage transitions.
- Optuna hyperparameter search logs directly to MLflow.
- Do not add `wandb` to dependencies.
