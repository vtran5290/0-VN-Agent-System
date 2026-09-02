"""Diversity-weighted breadth portfolio constructor (Gate B research).

RESEARCH_ONLY — no execution modeling, no production signal path.

Universe: point-in-time top-N by median trailing 60d ADV (VN100 proxy; no PIT membership log).
Weights: w_i = mu_i^p / sum(mu_j^p) for p in {1.0, 0.5, 0.0}.
Returns: next-open to next-open across monthly rebalance (last trading day of month).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yaml

logger = logging.getLogger(__name__)

RESEARCH_ONLY_LABEL = "RESEARCH_ONLY_NOT_PRODUCTION"
DEFAULT_PANEL_PATH = Path("data/research/ema_cloud/ohlcv_panel_ext2012.parquet")
DEFAULT_LIVE_CONFIG = Path("config/live_trading.yaml")
DEFAULT_OUT_DIR = Path("data/research/diversity_breadth")
DEFAULT_TOP_N = 100
ADV_WINDOW = 60
MIN_UNIVERSE = 20
P_VALUES = (1.0, 0.5, 0.0)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_ex_vin_symbols(config_path: Path | None = None) -> list[str]:
    cfg_path = config_path or (_repo_root() / DEFAULT_LIVE_CONFIG)
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return list(cfg.get("ex_vin3_symbols") or ["VIC", "VHM", "VRE", "VPL"])


def _month_end_dates(dates: pd.DatetimeIndex) -> pd.DatetimeIndex:
    s = pd.Series(dates, index=dates)
    return pd.DatetimeIndex(s.groupby(s.dt.to_period("M")).max().values)


def _diversity_weights(mu: pd.Series, p: float) -> pd.Series:
    mu = mu.astype(float).clip(lower=0)
    if p == 0.0:
        return pd.Series(1.0 / len(mu), index=mu.index)
    powered = mu.pow(p)
    total = powered.sum()
    if total <= 0 or not np.isfinite(total):
        return pd.Series(np.nan, index=mu.index)
    return powered / total


def _select_universe(
    mu_row: pd.Series,
    *,
    top_n: int,
    exclude: Iterable[str] | None = None,
) -> pd.Series:
    ex = set(exclude or [])
    s = mu_row.dropna()
    s = s[s > 0]
    if ex:
        s = s[~s.index.isin(ex)]
    if s.empty:
        return s
    if len(s) >= top_n:
        return s.nlargest(top_n)
    return s.sort_values(ascending=False)


def _portfolio_open_return(
    weights: pd.Series,
    opens: pd.DataFrame,
    entry_date: pd.Timestamp,
    exit_date: pd.Timestamp,
) -> float | None:
    if weights.empty or entry_date not in opens.index or exit_date not in opens.index:
        return None
    entry = opens.loc[entry_date]
    exit_ = opens.loc[exit_date]
    valid = weights.index.intersection(entry.dropna().index).intersection(exit_.dropna().index)
    valid = valid[(entry[valid] > 0) & (exit_[valid] > 0)]
    if valid.empty:
        return None
    w = weights[valid].astype(float)
    w = w / w.sum()
    rets = exit_[valid].astype(float) / entry[valid].astype(float) - 1.0
    return float((w * rets).sum())


def build_diversity_portfolio_returns(
    panel_path: Path | None = None,
    *,
    top_n: int = DEFAULT_TOP_N,
    ex_vin_symbols: list[str] | None = None,
    adv_window: int = ADV_WINDOW,
) -> pd.DataFrame:
    """Build monthly diversity-weighted portfolio return series."""
    root = _repo_root()
    path = panel_path or (root / DEFAULT_PANEL_PATH)
    ex_vin = ex_vin_symbols if ex_vin_symbols is not None else load_ex_vin_symbols()

    panel = pd.read_parquet(path)
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    panel = panel.sort_values(["symbol", "date"])

    # `value` = close * volume * 1000 (VND turnover); raw close — document in summary.
    panel["adv_vnd"] = panel["value"].astype(float)
    panel["mu_adv"] = panel.groupby("symbol")["adv_vnd"].transform(
        lambda s: s.rolling(adv_window, min_periods=adv_window).median()
    )

    trading_dates = pd.DatetimeIndex(sorted(panel["date"].unique()))
    rebalance_dates = _month_end_dates(trading_dates)
    rebalance_dates = rebalance_dates[rebalance_dates >= trading_dates[min(adv_window, len(trading_dates) - 1)]]

    mu_wide = panel.pivot_table(index="date", columns="symbol", values="mu_adv", aggfunc="last")
    opens = panel.pivot_table(index="date", columns="symbol", values="open", aggfunc="last")

    rows: list[dict] = []
    for i, reb_date in enumerate(rebalance_dates[:-1]):
        next_reb = rebalance_dates[i + 1]
        entry_candidates = trading_dates[trading_dates > reb_date]
        exit_candidates = trading_dates[trading_dates > next_reb]
        if len(entry_candidates) == 0 or len(exit_candidates) == 0:
            continue
        entry_date = entry_candidates[0]
        exit_date = exit_candidates[0]

        if reb_date not in mu_wide.index:
            continue
        mu_row = mu_wide.loc[reb_date].dropna()
        mu_row = mu_row[mu_row > 0]
        if len(mu_row) < MIN_UNIVERSE:
            continue

        universe = _select_universe(mu_row, top_n=top_n, exclude=None)
        universe_ex = _select_universe(mu_row, top_n=top_n, exclude=ex_vin)
        if len(universe) < MIN_UNIVERSE:
            continue

        row: dict = {
            "date": pd.Timestamp(reb_date),
            "entry_date": pd.Timestamp(entry_date),
            "exit_date": pd.Timestamp(exit_date),
            "n_universe": len(universe),
            "n_universe_exvin": len(universe_ex),
            "research_label": RESEARCH_ONLY_LABEL,
        }

        for p in P_VALUES:
            tag = f"ret_p{int(p * 100):03d}"
            w = _diversity_weights(universe, p)
            row[tag] = _portfolio_open_return(w, opens, entry_date, exit_date)

            if len(universe_ex) >= MIN_UNIVERSE:
                w_ex = _diversity_weights(universe_ex, p)
                row[f"{tag}_exvin"] = _portfolio_open_return(w_ex, opens, entry_date, exit_date)
            else:
                row[f"{tag}_exvin"] = None

        if row.get("ret_p050") is not None and row.get("ret_p100") is not None:
            row["spread_p050_vs_p100"] = row["ret_p050"] - row["ret_p100"]
        else:
            row["spread_p050_vs_p100"] = np.nan

        if row.get("ret_p050_exvin") is not None and row.get("ret_p100_exvin") is not None:
            row["spread_p050_vs_p100_exvin"] = row["ret_p050_exvin"] - row["ret_p100_exvin"]
        else:
            row["spread_p050_vs_p100_exvin"] = np.nan

        rows.append(row)

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    col_order = [
        "date",
        "entry_date",
        "exit_date",
        "n_universe",
        "n_universe_exvin",
        "ret_p100",
        "ret_p050",
        "ret_p000",
        "ret_p100_exvin",
        "ret_p050_exvin",
        "ret_p000_exvin",
        "spread_p050_vs_p100",
        "spread_p050_vs_p100_exvin",
        "research_label",
    ]
    out = out[[c for c in col_order if c in out.columns]]
    return out


def save_diversity_series(df: pd.DataFrame, out_dir: Path | None = None) -> Path:
    root = _repo_root()
    dest = out_dir or (root / DEFAULT_OUT_DIR)
    dest.mkdir(parents=True, exist_ok=True)
    parquet_path = dest / "diversity_portfolio_returns.parquet"
    csv_path = dest / "diversity_portfolio_returns.csv"
    df.to_parquet(parquet_path, index=False)
    df.to_csv(csv_path, index=False)
    logger.info("Saved diversity series: %s (%d rows)", parquet_path, len(df))
    return parquet_path


def run_build(panel_path: Path | None = None, out_dir: Path | None = None) -> pd.DataFrame:
    df = build_diversity_portfolio_returns(panel_path=panel_path)
    if df.empty:
        raise RuntimeError("diversity portfolio build returned empty DataFrame")
    save_diversity_series(df, out_dir=out_dir)
    return df
