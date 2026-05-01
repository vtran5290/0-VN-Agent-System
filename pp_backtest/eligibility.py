from __future__ import annotations

"""
pp_backtest/eligibility.py

Helpers to work with the monthly point-in-time eligibility map built by
`monthly_universe.py`.

Primary responsibilities:
- Load `monthly_universe_eligibility.csv`.
- For a given (symbol, date), answer:
  - is the symbol eligible in that month?
  - what are the trailing ADTV20 / ADTV50 estimates at month_start?
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

_PP = Path(__file__).resolve().parent


@dataclass
class EligibilityMap:
    df: pd.DataFrame

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "EligibilityMap":
        p = path or (_PP / "monthly_universe_eligibility.csv")
        if not p.exists():
            raise FileNotFoundError(f"Eligibility map not found: {p}")
        df = pd.read_csv(p)
        if "month_start" not in df.columns or "symbol" not in df.columns:
            raise ValueError("Eligibility CSV must contain 'symbol' and 'month_start' columns.")
        df["month_start"] = pd.to_datetime(df["month_start"])
        df["symbol"] = df["symbol"].astype(str).str.upper()
        return cls(df=df)

    def _lookup_row(self, symbol: str, date: pd.Timestamp) -> Optional[pd.Series]:
        sym = str(symbol).upper()
        d = pd.to_datetime(date).normalize()
        # Find latest month_start <= d
        sdf = self.df[self.df["symbol"] == sym]
        if sdf.empty:
            return None
        sdf = sdf[sdf["month_start"] <= d]
        if sdf.empty:
            return None
        row = sdf.sort_values("month_start").iloc[-1]
        return row

    def is_eligible(self, symbol: str, date: pd.Timestamp) -> bool:
        row = self._lookup_row(symbol, date)
        if row is None:
            return False
        return bool(row.get("eligible_flag", False))

    def adtv(self, symbol: str, date: pd.Timestamp) -> Tuple[Optional[float], Optional[float]]:
        row = self._lookup_row(symbol, date)
        if row is None:
            return None, None
        a20 = row.get("adtv20")
        a50 = row.get("adtv50")
        return (float(a20) if pd.notna(a20) else None, float(a50) if pd.notna(a50) else None)


@lru_cache(maxsize=1)
def get_global_eligibility() -> EligibilityMap:
    return EligibilityMap.load()

