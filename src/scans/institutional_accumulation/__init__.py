"""
Institutional Accumulation Scan — hybrid Smart Money context + OHLCV money flow.

Research/ranking layer only. Does not emit orders or final_action.
"""

from .pipeline import run_institutional_accumulation_scan

__all__ = ["run_institutional_accumulation_scan"]
