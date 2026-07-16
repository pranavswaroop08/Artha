"""Data lineage tracking for feature engineering and model training.

Rule C (train/serve parity) is enforced partly by the feature store, and
partly by being able to trace any feature or model output back to the exact
raw-data batch it was derived from. ``LineageTracker`` computes content
hashes of input/output frames and records each transformation step so the
record can be attached to a model registry entry / MLflow run.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

import pandas as pd

from ..common.context import get_logger

logger = get_logger(__name__)


def compute_dataframe_hash(df: pd.DataFrame) -> str:
    """Deterministic SHA256 hash of a DataFrame.

    Columns are sorted before hashing so the result is independent of column
    ordering. Row-level hashes come from ``pd.util.hash_pandas_object``.
    Note: this hashes *values*, not dtypes, so re-typing a column with
    identical values yields the same hash.
    """
    df_sorted = df.sort_index(axis=1)
    row_hashes = pd.util.hash_pandas_object(df_sorted, index=True).values
    return hashlib.sha256(row_hashes.tobytes()).hexdigest()


class LineageTracker:
    """Records data lineage through pipeline transformations."""

    def __init__(self) -> None:
        self.history: List[Dict[str, Any]] = []

    def log_input(
        self,
        name: str,
        df: pd.DataFrame,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log an input frame and return its content hash."""
        df_hash = compute_dataframe_hash(df)
        self.history.append(
            {
                "step": "input",
                "name": name,
                "hash": df_hash,
                "shape": list(df.shape),
                "metadata": metadata or {},
            }
        )
        logger.info("lineage.input", name=name, hash=df_hash, shape=list(df.shape))
        return df_hash

    def log_output(
        self,
        name: str,
        df: pd.DataFrame,
        step_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log a transformed/output frame and return its content hash."""
        df_hash = compute_dataframe_hash(df)
        self.history.append(
            {
                "step": "output",
                "name": name,
                "process": step_name,
                "hash": df_hash,
                "shape": list(df.shape),
                "metadata": metadata or {},
            }
        )
        logger.info(
            "lineage.output", name=name, process=step_name, hash=df_hash, shape=list(df.shape)
        )
        return df_hash

    def get_lineage_record(self) -> Dict[str, Any]:
        """Return the full lineage history for model registry / tracking."""
        return {
            "lineage_history": self.history,
            "final_hash": self.history[-1]["hash"] if self.history else None,
        }
