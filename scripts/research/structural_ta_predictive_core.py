"""Structural TA predictive-score core (RESEARCH ONLY).

ChatGPT REDIRECT 2026-08-28: PIT ADV50, date-level IC, canonical WF folds,
missing-score-as-null, F5/F6 seal, hash-pinned feature panel.

Does not modify vn_ta_fireant_cli scoring or OMS paths.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from scripts.wf.wf_fold_utils import get_fold_config, load_fold_config

REPO_ROOT = Path(__file__).resolve().parents[2]
PANEL_PATH = REPO_ROOT / "data" / "fireant_ssot" / "ta_ohlcv_panel.parquet"
FOLDS_YAML = REPO_ROOT / "data" / "config" / "walkforward_folds.yaml"
EX_VIN = frozenset({"VIC", "VHM", "VRE"})
VPL = "VPL"
BUCKET_KEYS = (
    "ma_confluence",
    "horizontal_pivot",
    "role_reversal",
    "prior_base_origin_markup",
    "volume_absorption",
    "momentum_invalidation",
)
DEFAULT_BOOTSTRAP_SEED = 20260828
CONFIRMATION_FOLDS = frozenset({"F5", "F6"})
DEVELOPMENT_FOLDS = ("F1", "F2", "F3", "F4")
ETF_RE = re.compile(r"^(E1|FUE|FUC)", re.IGNORECASE)
CW_RE = re.compile(r"^C[A-Z]{3}\d{2,}", re.IGNORECASE)


def is_non_equity_ticker(symbol: str) -> bool:
    s = str(symbol).upper()
    return bool(ETF_RE.match(s) or CW_RE.match(s))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def spec_hash(spec: Dict[str, Any]) -> str:
    blob = json.dumps(spec, sort_keys=True, separators=(",", ":"), default=str).encode()
    return sha256_bytes(blob)


def git_identifier() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except Exception:
        return "UNKNOWN"


def normalize_panel(panel: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Uppercase symbols, parse dates, drop duplicate (symbol, date)."""
    flags: Dict[str, Any] = {"n_dup_symbol_date": 0, "n_zero_close": 0, "n_zero_value": 0}
    df = panel.copy()
    df.columns = [str(c).lower() for c in df.columns]
    if "symbol" not in df.columns and "ticker" in df.columns:
        df = df.rename(columns={"ticker": "symbol"})
    df["symbol"] = df["symbol"].astype(str).str.upper()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    n0 = len(df)
    df = df.sort_values(["symbol", "date"]).drop_duplicates(["symbol", "date"], keep="last")
    flags["n_dup_symbol_date"] = int(n0 - len(df))
    if "close" in df.columns:
        flags["n_zero_close"] = int((pd.to_numeric(df["close"], errors="coerce").fillna(0) <= 0).sum())
    if "value" in df.columns:
        flags["n_zero_value"] = int((pd.to_numeric(df["value"], errors="coerce").fillna(0) <= 0).sum())
    flags["n_rows"] = int(len(df))
    flags["n_symbols"] = int(df["symbol"].nunique())
    flags["date_min"] = df["date"].min().strftime("%Y-%m-%d") if len(df) else None
    flags["date_max"] = df["date"].max().strftime("%Y-%m-%d") if len(df) else None
    return df.reset_index(drop=True), flags


def composite_score(
    breakdown: Optional[Dict[str, Any]],
    spec: Dict[str, Any],
    cli_total: Any = None,
) -> Optional[float]:
    """Research composite. Missing/unevaluated → None. Never coerce missing to 0."""
    if not breakdown or not isinstance(breakdown, dict):
        return None
    if cli_total is None or (isinstance(cli_total, float) and math.isnan(cli_total)):
        return None
    caps = spec["caps"]
    mult = spec.get("multipliers") or {}
    enabled = spec.get("enabled") or {}
    total = 0.0
    for key, cap in caps.items():
        if not enabled.get(key, True):
            continue
        if key not in breakdown:
            return None
        raw = breakdown[key]
        if raw is None or (isinstance(raw, float) and math.isnan(raw)):
            return None
        total += min(float(raw), float(cap)) * float(mult.get(key, 1.0))
    return float(total)


def validate_search_space(spec: Dict[str, Any]) -> None:
    space = spec.get("search_space") or {}
    allowed = set(space.get("allowed_multiplier_keys") or BUCKET_KEYS)
    lo = float(space.get("multiplier_min", 0.0))
    hi = float(space.get("multiplier_max", 3.0))
    for key, val in (spec.get("multipliers") or {}).items():
        if key not in allowed:
            raise ValueError(f"multiplier key outside frozen search space: {key}")
        v = float(val)
        if v < lo or v > hi:
            raise ValueError(f"multiplier {key}={v} outside [{lo}, {hi}]")
    for key, on in (spec.get("enabled") or {}).items():
        if key not in allowed:
            raise ValueError(f"enabled key outside frozen search space: {key}")
        if not on and not space.get("may_disable_buckets", True):
            raise ValueError("disabling buckets is not allowed by frozen search space")


def fold_oos_end(fold: Dict[str, Any], panel_end: date) -> date:
    raw = fold.get("oos_end")
    if raw in (None, "null"):
        return panel_end
    return pd.Timestamp(raw).date()


def load_canonical_folds(panel_end: date) -> Dict[str, Dict[str, Any]]:
    cfg = load_fold_config(FOLDS_YAML)
    if str(cfg.get("version")) != "1.1":
        raise ValueError(f"walkforward_folds.yaml version must be 1.1, got {cfg.get('version')}")
    out: Dict[str, Dict[str, Any]] = {}
    for fold in cfg["folds"]:
        fid = fold["id"]
        out[fid] = {
            "id": fid,
            "oos_start": pd.Timestamp(fold["oos_start"]).date(),
            "oos_end": fold_oos_end(fold, panel_end),
            "oos_regime": fold.get("oos_regime"),
            "sealed": fid in CONFIRMATION_FOLDS,
        }
    return out


def assign_dev_fold(asof: date, folds: Dict[str, Dict[str, Any]]) -> Optional[str]:
    for fid in DEVELOPMENT_FOLDS:
        f = folds[fid]
        if f["oos_start"] <= asof <= f["oos_end"]:
            return fid
    return None


def assign_confirm_fold(asof: date, folds: Dict[str, Dict[str, Any]]) -> Optional[str]:
    for fid in ("F5", "F6"):
        f = folds[fid]
        if f["oos_start"] <= asof <= f["oos_end"]:
            return fid
    return None


def weekly_fridays(sessions: Sequence[pd.Timestamp], start: date, end: date, step: int = 1) -> List[date]:
    s = pd.to_datetime(pd.Index(sessions)).normalize()
    wk = pd.Series(s).dt.to_period("W-FRI").dt.to_timestamp(how="end")
    wk = pd.to_datetime(wk).dt.normalize().unique()
    wk = pd.to_datetime(sorted(wk))
    mask = (wk.date >= start) & (wk.date <= end)
    fridays = [d.date() for d in wk[mask]]
    if step > 1:
        fridays = fridays[::step]
    return fridays


def staggered_week_offsets(sessions: Sequence[pd.Timestamp], start: date, end: date) -> Dict[int, List[date]]:
    base = weekly_fridays(sessions, start, end, step=1)
    return {off: base[off::4] for off in range(4)}


def pit_adv50_matrices(panel: pd.DataFrame) -> Tuple[pd.DatetimeIndex, pd.DataFrame, pd.DataFrame]:
    """Session-indexed ADV50 mean (50) and active flag (any value>0 in last 10)."""
    work = panel[["symbol", "date", "value"]].copy()
    work["value"] = pd.to_numeric(work["value"], errors="coerce")
    sessions = pd.DatetimeIndex(np.sort(work["date"].unique())).normalize()
    piv = (
        work.pivot_table(index="date", columns="symbol", values="value", aggfunc="sum")
        .reindex(sessions)
        .fillna(0.0)
        .sort_index()
    )
    adv50 = piv.rolling(50, min_periods=50).mean()
    active10 = piv.rolling(10, min_periods=1).max().gt(0.0)
    return sessions, adv50, active10


def last_session_on_or_before(sessions: pd.DatetimeIndex, asof: date) -> Optional[pd.Timestamp]:
    ts = pd.Timestamp(asof)
    loc = sessions.searchsorted(ts, side="right") - 1
    if loc < 0:
        return None
    return sessions[loc]


def pit_membership_at_asof(
    asof: date,
    sessions: pd.DatetimeIndex,
    adv50: pd.DataFrame,
    active10: pd.DataFrame,
    *,
    threshold: float,
    max_symbols: int,
) -> pd.Series:
    """ADV50 (VND) for names passing threshold + active10, truncated to top max_symbols."""
    sess = last_session_on_or_before(sessions, asof)
    if sess is None or sess not in adv50.index:
        return pd.Series(dtype=float)
    row = adv50.loc[sess]
    act = active10.loc[sess].reindex(row.index).fillna(False)
    ok = row[(row >= threshold) & act].sort_values(ascending=False)
    if len(ok) > max_symbols:
        ok = ok.iloc[:max_symbols]
    return ok


def weekly_bars_asof(panel: pd.DataFrame) -> pd.DataFrame:
    """Long table: symbol, week_end, close, cum_weeks (as-of that week)."""
    g = panel[["symbol", "date", "close"]].copy()
    g["close"] = pd.to_numeric(g["close"], errors="coerce")
    rows = []
    for sym, sg in g.groupby("symbol", sort=False):
        w = (
            sg.set_index("date")
            .sort_index()
            .resample("W-FRI")["close"]
            .last()
            .dropna()
        )
        if w.empty:
            continue
        tmp = w.reset_index()
        tmp.columns = ["week_end", "close"]
        tmp["symbol"] = sym
        tmp["cum_weeks"] = np.arange(1, len(tmp) + 1)
        rows.append(tmp)
    if not rows:
        return pd.DataFrame(columns=["symbol", "week_end", "close", "cum_weeks"])
    return pd.concat(rows, ignore_index=True)


def weekly_bars_count_asof(weekly: pd.DataFrame, symbol: str, asof: date) -> int:
    if weekly.empty:
        return 0
    ends = pd.to_datetime(weekly["week_end"])
    sub = weekly[(weekly["symbol"] == symbol) & (ends.dt.date <= asof)]
    if sub.empty:
        return 0
    return int(sub["cum_weeks"].max())


def weekly_cum_lookup(weekly: pd.DataFrame) -> Tuple[pd.DatetimeIndex, pd.DataFrame]:
    """week_end × symbol cumulative week counts, forward-filled."""
    if weekly.empty:
        return pd.DatetimeIndex([]), pd.DataFrame()
    piv = (
        weekly.pivot_table(index="week_end", columns="symbol", values="cum_weeks", aggfunc="max")
        .sort_index()
        .ffill()
    )
    piv.index = pd.DatetimeIndex(pd.to_datetime(piv.index)).normalize()
    return piv.index, piv


def weekly_count_from_lookup(
    asof: date,
    week_index: pd.DatetimeIndex,
    cum: pd.DataFrame,
    symbol: str,
) -> int:
    if cum.empty or symbol not in cum.columns:
        return 0
    sess = last_session_on_or_before(week_index, asof)
    if sess is None:
        return 0
    val = cum.loc[sess, symbol]
    if pd.isna(val):
        return 0
    return int(val)


def daily_cum_lookup(panel: pd.DataFrame) -> Tuple[pd.DatetimeIndex, pd.DataFrame]:
    sessions = pd.DatetimeIndex(np.sort(panel["date"].unique())).normalize()
    piv = (
        panel.assign(_n=1)
        .pivot_table(index="date", columns="symbol", values="_n", aggfunc="sum")
        .reindex(sessions)
        .fillna(0.0)
        .sort_index()
        .cumsum()
    )
    return sessions, piv


def daily_count_from_lookup(
    asof: date,
    day_index: pd.DatetimeIndex,
    cum: pd.DataFrame,
    symbol: str,
) -> int:
    if cum.empty or symbol not in cum.columns:
        return 0
    sess = last_session_on_or_before(day_index, asof)
    if sess is None:
        return 0
    val = cum.loc[sess, symbol]
    if pd.isna(val):
        return 0
    return int(val)


def forward_weekly_labels(
    weekly: pd.DataFrame,
    horizons: Sequence[int],
) -> pd.DataFrame:
    """One row per (symbol, asof week) with fwd_hw and target_date_hw."""
    out_rows: List[Dict[str, Any]] = []
    for sym, g in weekly.groupby("symbol", sort=False):
        g = g.sort_values("week_end").reset_index(drop=True)
        closes = g["close"].to_numpy(dtype=float)
        dates = [pd.Timestamp(d).date() for d in g["week_end"]]
        n = len(g)
        for i, asof in enumerate(dates):
            row: Dict[str, Any] = {"symbol": sym, "asof": asof}
            c0 = closes[i]
            for h in horizons:
                j = i + h
                key_r = f"fwd_{h}w"
                key_t = f"target_date_{h}w"
                if j >= n or not np.isfinite(c0) or c0 <= 0:
                    row[key_r] = None
                    row[key_t] = None
                    continue
                c1 = closes[j]
                if not np.isfinite(c1) or c1 <= 0:
                    row[key_r] = None
                    row[key_t] = None
                    continue
                row[key_r] = float(c1 / c0 - 1.0)
                row[key_t] = dates[j]
            out_rows.append(row)
    return pd.DataFrame(out_rows)


def contained_in_fold(
    target_date: Optional[date],
    fold_oos_end: date,
) -> bool:
    if target_date is None:
        return False
    return target_date <= fold_oos_end


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 3:
        return float("nan")
    rx = pd.Series(x).rank().to_numpy()
    ry = pd.Series(y).rank().to_numpy()
    if np.std(rx) == 0 or np.std(ry) == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def date_level_ic_and_spread(
    df: pd.DataFrame,
    *,
    score_col: str = "score",
    ret_col: str = "fwd_13w",
    min_names: int = 80,
    min_per_quintile: int = 8,
) -> pd.DataFrame:
    """One row per asof: Spearman IC and within-date Q5-Q1 spread."""
    rows = []
    for asof, g in df.groupby("asof", sort=True):
        sub = g.dropna(subset=[score_col, ret_col])
        n = len(sub)
        ic = spearman(sub[score_col].to_numpy(), sub[ret_col].to_numpy()) if n >= 3 else float("nan")
        spread = float("nan")
        n_bins = 0
        if n >= 5 * min_per_quintile:
            q = pd.qcut(sub[score_col], 5, labels=False, duplicates="drop")
            n_bins = int(pd.Series(q).nunique())
            if n_bins == 5:
                tmp = sub.assign(_q=q)
                means = tmp.groupby("_q")[ret_col].mean()
                spread = float(means.loc[4] - means.loc[0]) if 0 in means.index and 4 in means.index else float("nan")
        usable = n >= min_names and np.isfinite(ic)
        rows.append(
            {
                "asof": asof,
                "n": n,
                "ic": ic if usable else float("nan"),
                "quintile_spread": spread if usable and n_bins == 5 else float("nan"),
                "n_bins": n_bins,
                "usable": bool(usable),
            }
        )
    return pd.DataFrame(rows)


def moving_block_bootstrap_mean(
    series: np.ndarray,
    *,
    block_length: int,
    replicates: int,
    seed: int,
) -> Dict[str, Any]:
    """Non-circular moving-block bootstrap of the mean (house pattern)."""
    x = np.asarray(series, dtype=float)
    x = x[np.isfinite(x)]
    t = len(x)
    out: Dict[str, Any] = {
        "T": t,
        "block_length": block_length,
        "replicates": replicates,
        "seed": seed,
        "mean": float(np.mean(x)) if t else None,
        "median": float(np.median(x)) if t else None,
        "pct_positive": float(np.mean(x > 0)) if t else None,
        "bootstrap_mean_ci95_low": None,
        "bootstrap_mean_ci95_high": None,
    }
    if t < block_length + 1 or replicates <= 0:
        return out
    n_starts = t - block_length + 1
    rng = np.random.Generator(np.random.PCG64(seed))
    n_blocks = int(math.ceil(t / block_length))
    means = np.empty(replicates, dtype=float)
    for i in range(replicates):
        starts = rng.integers(0, n_starts, size=n_blocks)
        conc = np.concatenate([x[s : s + block_length] for s in starts])[:t]
        means[i] = float(np.mean(conc))
    ordered = np.sort(means)
    out["bootstrap_mean_ci95_low"] = float(ordered[int(0.025 * replicates)])
    out["bootstrap_mean_ci95_high"] = float(ordered[min(int(0.975 * replicates), replicates - 1)])
    return out


def filter_outcome_contained(
    df: pd.DataFrame,
    horizon: int,
    fold_end: date,
) -> pd.DataFrame:
    col = f"target_date_{horizon}w"
    if col not in df.columns:
        return df.iloc[0:0]
    td = pd.to_datetime(df[col])
    mask = td.notna() & (td.dt.date <= fold_end)
    return df.loc[mask].copy()


def identity_payload(
    *,
    spec: Dict[str, Any],
    panel_sha256: str,
    panel_date_max: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = {
        "panel_sha256": panel_sha256,
        "panel_date_max": panel_date_max,
        "folds_yaml_sha256": sha256_file(FOLDS_YAML) if FOLDS_YAML.is_file() else None,
        "folds_version": "1.1",
        "spec_hash": spec_hash(spec),
        "core_sha256": sha256_file(Path(__file__)),
        "git": git_identifier(),
        "label": "RESEARCH_ONLY_NOT_PRODUCTION",
    }
    if extra:
        payload.update(extra)
    return payload


def identities_match(a: Dict[str, Any], b: Dict[str, Any], keys: Sequence[str]) -> bool:
    return all(a.get(k) == b.get(k) for k in keys)
