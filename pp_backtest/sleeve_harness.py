"""Shared canonical sleeve harness — P0 realism + standardized evaluation."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pp_backtest.ema_portfolio_sim import portfolio_metrics
from pp_backtest.phase_exit_sweep_core import (
    YEAR_COLS,
    ADV_PARTICIPATION,
    DATA_END,
    DATA_START,
    GK_MULT,
    MAX_POSITIONS,
    PORTFOLIO_VND,
    binary_gate_ema20_100,
)
from pp_backtest.portfolio_optimization_phase31 import (
    _annual_return,
    _build_adv50_map,
    _build_equity_adv_capped_v2,
    _tag_adv50,
)

BUY_COMM = 0.0015
SELL_COMM = 0.0015
SELL_TAX = 0.0010
COST_RT_P0 = BUY_COMM + SELL_COMM + SELL_TAX
SLIPPAGE_PENALTY = 0.005
FLOOR_MULT = 0.93
CEILING_MULT = 1.07
LOCK_TOL = 0.002
SETTLEMENT_BDAY = 2
IDEALIZED_COST_RT = 0.0035

STANDARD_COLUMNS = [
    "symbol", "signal_date", "entry_date", "exit_date",
    "ep1", "ep2", "blended_ep", "t1_frac", "total_frac", "has_pullback",
    "gross_return", "net_return", "hold_bars", "exit_reason",
]


def is_ceiling_locked(close: float, prior_close: float) -> bool:
    if prior_close <= 0 or np.isnan(close) or np.isnan(prior_close):
        return False
    return close >= prior_close * CEILING_MULT * (1.0 - LOCK_TOL)


def is_floor_locked(close: float, prior_close: float) -> bool:
    if prior_close <= 0 or np.isnan(close) or np.isnan(prior_close):
        return False
    return close <= prior_close * FLOOR_MULT * (1.0 + LOCK_TOL)


def net_return_from_gross(gross: float) -> float:
    return gross - BUY_COMM - SELL_COMM - SELL_TAX


def earliest_exit_bar(dates: np.ndarray, entry_i: int) -> int:
    entry_dt = pd.Timestamp(dates[entry_i])
    settle_dt = entry_dt + pd.tseries.offsets.BDay(SETTLEMENT_BDAY)
    for k in range(entry_i + 1, len(dates)):
        if pd.Timestamp(dates[k]) > settle_dt:
            return k
    return len(dates)


def build_ohlcv_cache(panel: pd.DataFrame, universe: set[str]) -> dict[str, dict]:
    cache: dict[str, dict] = {}
    sub = panel[panel["symbol"].isin(universe)].copy()
    for sym, sdf in sub.groupby("symbol", sort=False):
        sdf = sdf.sort_values("date").reset_index(drop=True)
        close = sdf["close"].astype(float)
        opn = sdf["open"].astype(float)
        high = sdf["high"].astype(float)
        low = sdf.get("low", close).astype(float)
        dates = pd.to_datetime(sdf["date"]).values
        cache[sym] = {
            "open": opn.values.astype(float),
            "high": high.values.astype(float),
            "low": low.values.astype(float),
            "close": close.values.astype(float),
            "dates": dates,
        }
    return cache


def _date_to_index(dates: np.ndarray, dt: pd.Timestamp) -> int | None:
    dt = pd.Timestamp(dt).normalize()
    for i, d in enumerate(dates):
        if pd.Timestamp(d).normalize() == dt:
            return i
    return None


def adv_cap_binds(adv50: float, t1_target_vnd: float) -> bool:
    if adv50 <= 0:
        return False
    cap = adv50 * ADV_PARTICIPATION
    return cap < t1_target_vnd * 0.95


def apply_p0_reprice(
    ideal_trades: pd.DataFrame,
    ohlcv_cache: dict[str, dict],
    adv50_map: dict,
) -> pd.DataFrame:
    slot_vnd = PORTFOLIO_VND / MAX_POSITIONS
    t1_target = slot_vnd * 0.5
    rows: list[dict] = []

    for _, tr in ideal_trades.iterrows():
        sym = str(tr["symbol"])
        data = ohlcv_cache.get(sym)
        if data is None:
            continue

        open_arr = data["open"]
        close_arr = data["close"]
        dates = data["dates"]
        n = len(dates)

        entry_dt = pd.Timestamp(tr["entry_date"]).normalize()
        exit_dt = pd.Timestamp(tr["exit_date"]).normalize()
        entry_i = _date_to_index(dates, entry_dt)
        exit_i = _date_to_index(dates, exit_dt)
        if entry_i is None or exit_i is None or entry_i >= n:
            continue

        sig_i = max(0, entry_i - 1)
        prior_for_entry = close_arr[sig_i] if sig_i >= 0 else close_arr[entry_i]
        if is_ceiling_locked(close_arr[entry_i], prior_for_entry):
            continue

        entry_px = float(open_arr[entry_i])
        if entry_px <= 0 or np.isnan(entry_px):
            continue

        min_exit_i = earliest_exit_bar(dates, entry_i)
        target_exit_i = max(exit_i, min_exit_i)
        floor_delay = 0
        exit_delayed = False

        fill_i = target_exit_i + 1
        for k in range(target_exit_i, min(n - 1, target_exit_i + 10)):
            prior_c = close_arr[k - 1] if k > 0 else close_arr[k]
            if is_floor_locked(close_arr[k], prior_c):
                floor_delay += 1
                exit_delayed = True
                continue
            fill_i = k + 1
            break

        if fill_i >= n:
            fill_i = n - 1
        exit_px = float(open_arr[fill_i])
        if exit_px <= 0 or np.isnan(exit_px):
            continue

        gross = exit_px / entry_px - 1.0
        net = net_return_from_gross(gross)

        adv_s = adv50_map.get(sym)
        adv50 = 0.0
        if adv_s is not None:
            valid = adv_s[adv_s.index <= entry_dt].dropna()
            if not valid.empty:
                adv50 = float(valid.iloc[-1])
        binds = adv_cap_binds(adv50, t1_target)
        slip = SLIPPAGE_PENALTY if (binds or exit_delayed) else 0.0
        net -= slip

        rows.append({
            "symbol": sym,
            "signal_date": tr.get("signal_date", pd.Timestamp(dates[sig_i]).date()),
            "entry_date": entry_dt.date(),
            "exit_date": pd.Timestamp(dates[fill_i]).date(),
            "ep1": entry_px,
            "ep2": None,
            "blended_ep": entry_px,
            "t1_frac": tr.get("t1_frac", 0.5),
            "total_frac": tr.get("total_frac", 0.5),
            "has_pullback": bool(tr.get("has_pullback", False)),
            "gross_return": gross,
            "net_return": net,
            "hold_bars": fill_i - entry_i,
            "exit_reason": tr.get("exit_reason", "p0_reprice"),
            "adv50_value": adv50,
            "slippage_penalty": slip,
            "floor_exit_delay_bars": floor_delay,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["entry_date"] = pd.to_datetime(df["entry_date"])
        df["exit_date"] = pd.to_datetime(df["exit_date"])
    return df


def normalize_trades(df: pd.DataFrame, cost_rt: float = IDEALIZED_COST_RT) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["entry_date"] = pd.to_datetime(out["entry_date"])
    out["exit_date"] = pd.to_datetime(out["exit_date"])
    if "blended_ep" not in out.columns:
        out["blended_ep"] = out.get("ep1", out.get("entry_price", np.nan))
    if "ep1" not in out.columns:
        out["ep1"] = out["blended_ep"]
    if "t1_frac" not in out.columns:
        out["t1_frac"] = 0.5
    if "total_frac" not in out.columns:
        out["total_frac"] = 0.5
    if "has_pullback" not in out.columns:
        out["has_pullback"] = False
    if "gross_return" not in out.columns and "ret" in out.columns:
        out["gross_return"] = out["ret"]
    if "net_return" not in out.columns:
        out["net_return"] = out["gross_return"] - cost_rt
    if "hold_bars" not in out.columns and "hold_days" in out.columns:
        out["hold_bars"] = out["hold_days"]
    if "signal_date" not in out.columns:
        out["signal_date"] = out["entry_date"]
    return out


def evaluate_trades(trades: pd.DataFrame, adv50_map: dict, *, rank_col: str | None = None) -> dict[str, Any]:
    tagged = _tag_adv50(trades, adv50_map)
    eq_in = tagged.drop(columns=["ema_dist_at_entry", "rs_score_at_entry"], errors="ignore")
    eq, liq = _build_equity_adv_capped_v2(
        eq_in, MAX_POSITIONS, PORTFOLIO_VND, ADV_PARTICIPATION, GK_MULT, rank_col=rank_col,
    )
    m = portfolio_metrics(eq, eq_in) if not eq.empty else {}
    row: dict[str, Any] = {
        "mar_full": m.get("mar", np.nan),
        "cagr": m.get("cagr", np.nan),
        "max_dd": m.get("max_dd", np.nan),
        "sharpe": m.get("sharpe", np.nan),
        "win_rate": m.get("hit_rate", np.nan),
        "avg_trade": m.get("avg_trade_ret", np.nan),
        "n_trades": m.get("n_trades", len(tagged)),
        "pct_adv_capped_t1": liq.get("pct_partial_T1", np.nan),
        "avg_hold_bars": m.get("avg_hold_bars", np.nan),
        "equity": eq,
    }
    for yr in YEAR_COLS:
        row[f"y{yr}"] = _annual_return(eq, yr) if not eq.empty else np.nan
    return row


def mean_cash_fraction(trades: pd.DataFrame, adv50_map: dict) -> float:
    tagged = _tag_adv50(trades, adv50_map)
    if tagged.empty:
        return np.nan
    base_w = 1.0 / MAX_POSITIONS
    tf = tagged["total_frac"].astype(float).fillna(0.5)
    adv = tagged["adv50_value"].fillna(0).astype(float) if "adv50_value" in tagged.columns else pd.Series(0.0, index=tagged.index)
    max_w = (adv * ADV_PARTICIPATION / PORTFOLIO_VND).clip(upper=base_w)
    eff = np.minimum(base_w * tf, max_w) * tf
    min_w = 100_000 / PORTFOLIO_VND
    eff_ok = eff[eff >= min_w]
    if eff_ok.empty:
        return 1.0
    return float(max(0.0, 1.0 - eff_ok.mean() * min(len(eff_ok), MAX_POSITIONS)))


@dataclass
class SleeveResult:
    sleeve: str
    mode: str
    metrics: dict[str, Any]
    trades: pd.DataFrame
    meta: dict[str, Any] = field(default_factory=dict)


class SleeveAdapter(ABC):
    name: str
    signal_family: str
    regime_gate_description: str

    @abstractmethod
    def generate_trades(self, panel: pd.DataFrame, vnx: pd.DataFrame, gate: pd.Series) -> pd.DataFrame:
        """Idealized trade ledger (standard columns)."""


def run_sleeve(adapter: SleeveAdapter, out_dir: Path, *, panel=None, vnx=None) -> SleeveResult:
    from pp_backtest.portfolio_optimization_phase1 import load_panel, load_vnindex, get_universe, STRATEGY_CONFIGS

    out_dir.mkdir(parents=True, exist_ok=True)
    if panel is None:
        panel = load_panel()
    panel = panel[(panel["date"] >= DATA_START) & (panel["date"] <= DATA_END)].copy()
    if vnx is None:
        vnx = load_vnindex()
    gate = binary_gate_ema20_100(vnx)
    adv = _build_adv50_map(panel)
    universe = set(get_universe(panel, STRATEGY_CONFIGS["A3"]["universe"]))
    ohlcv = build_ohlcv_cache(panel, universe)

    ideal = normalize_trades(adapter.generate_trades(panel, vnx, gate))
    honest = apply_p0_reprice(ideal, ohlcv, adv)

    rows = []
    for mode, trades in [("idealized", ideal), ("honest_p0", honest)]:
        m = evaluate_trades(trades, adv)
        row = {k: v for k, v in m.items() if k not in ("equity",)}
        row["mode"] = mode
        row["sleeve"] = adapter.name
        rows.append(row)
        trades.to_csv(out_dir / f"{adapter.name.lower()}_{mode}_trades.csv", index=False)

    results_df = pd.DataFrame(rows)
    results_df.to_csv(out_dir / f"{adapter.name.lower()}_results.csv", index=False, float_format="%.6f")

    honest_m = evaluate_trades(honest, adv)
    annual = pd.DataFrame([{"year": y, "annual_return": honest_m.get(f"y{y}", np.nan)} for y in YEAR_COLS])
    annual.to_csv(out_dir / f"{adapter.name.lower()}_annual_returns.csv", index=False, float_format="%.6f")

    meta = {
        "generated": str(date.today()),
        "sleeve": adapter.name,
        "signal_family": adapter.signal_family,
        "regime_gate": adapter.regime_gate_description,
        "honest_mar": float(honest_m.get("mar_full", np.nan)),
        "honest_cagr": float(honest_m.get("cagr", np.nan)),
        "honest_n_trades": int(honest_m.get("n_trades", len(honest))),
        "mean_cash_fraction": mean_cash_fraction(honest, adv),
        "p0_realism": {
            "fills": "next_open",
            "floor_ceiling_lock": True,
            "settlement_bdays": SETTLEMENT_BDAY,
            "cost_rt": COST_RT_P0,
            "slippage_penalty": SLIPPAGE_PENALTY,
        },
    }
    (out_dir / f"{adapter.name.lower()}_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    report = f"""# {adapter.name} Sleeve — P0 Honest Results

Generated: {date.today()}

- Signal family: {adapter.signal_family}
- Regime gate: {adapter.regime_gate_description}
- Honest MAR: **{meta['honest_mar']:.4f}**
- Honest CAGR: **{meta['honest_cagr']:.4f}**
- MaxDD: {honest_m.get('max_dd', np.nan):.4f}
- n_trades: {meta['honest_n_trades']}
- Mean cash fraction: {meta['mean_cash_fraction']:.1%}

## Idealized vs Honest

| Mode | MAR | CAGR | n_trades |
|------|-----|------|----------|
"""
    for _, r in results_df.iterrows():
        report += f"| {r['mode']} | {r['mar_full']:.4f} | {r['cagr']:.4f} | {int(r['n_trades'])} |\n"

    (out_dir / f"{adapter.name.lower()}_report.md").write_text(report, encoding="utf-8")
    print(report.encode("ascii", errors="replace").decode("ascii"))
    return SleeveResult(adapter.name, "honest_p0", honest_m, honest, meta)
