"""Typed exception hierarchy for the platform."""
from __future__ import annotations


class QuantError(Exception):
    """Base class for all platform errors."""


class ConfigError(QuantError):
    """Raised when configuration is missing or invalid."""


class DataError(QuantError):
    """Raised on data quality / collection failures."""


class ValidationError(DataError):
    """Raised when a data contract / schema check fails."""


class LeakageError(QuantError):
    """Raised when a future/point-in-time leakage is detected."""


class ModelError(QuantError):
    """Raised on model training / inference failures."""


class StorageError(QuantError):
    """Raised on raw-lake / DB / object-store failures."""


class TradingError(QuantError):
    """Raised on order / execution / risk violations."""
