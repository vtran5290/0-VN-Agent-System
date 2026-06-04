"""Research-only technical indicators (not used in production OMS)."""

from src.research.indicators.trend_speed_analyzer import compute_tsa_features

__all__ = ["compute_tsa_features"]
