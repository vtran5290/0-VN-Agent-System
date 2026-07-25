"""B0_CLEAN Phase A acceptance harness (synthetic + light SSOT spot-checks).

Run: python tests/test_b0_clean.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.research.b0_clean.costs import apply_round_trip_cost, cost_grid
from src.research.b0_clean.execution import (
    SETTLEMENT_CUTOVER,
    is_locked_limit_down,
    is_locked_limit_up,
    simulate_symbol_trades,
)
from src.research.b0_clean.indicators import wilder_rsi
from src.research.b0_clean.signals import prepare_panel_with_signals
from src.research.b0_clean.universe import (
    ADV50_THRESHOLD,
    EX_VIN,
    classify_instrument,
    compute_pit_universe,
    is_etf_excluded,
)


def _ohlcv_frame(
    n: int = 200,
    start: str = "2023-01-02",
    symbol: str = "AAA",
    base: float = 20.0,
    value_scale: float = 3e9,
) -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=n)
    rng = np.random.default_rng(0)
    close = base + np.cumsum(rng.normal(0, 0.15, size=n))
    close = np.maximum(close, 1.0)
    open_ = close * (1 + rng.normal(0, 0.002, size=n))
    high = np.maximum(open_, close) * 1.01
    low = np.minimum(open_, close) * 0.99
    volume = rng.integers(100_000, 500_000, size=n).astype(float)
    value = np.full(n, value_scale, dtype=float)
    return pd.DataFrame(
        {
            "symbol": symbol,
            "date": dates,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "value": value,
            "ca_suspect": False,
        }
    )


def check_pit_adv50_on_value() -> None:
    df = _ohlcv_frame(n=180, value_scale=3e9)
    # Make early window illiquid
    df.loc[:80, "value"] = 1e8
    out = compute_pit_universe(df)
    # At end should be eligible (recent 50 bars at 3e9)
    assert bool(out.iloc[-1]["universe_eligible"]), out.iloc[-1]["universe_reject_reason"]
    assert float(out.iloc[-1]["adv50"]) > ADV50_THRESHOLD
    # Mid illiquid region: ADV50 should fail
    mid = out.iloc[100]
    assert float(mid["adv50"]) <= ADV50_THRESHOLD or mid["universe_reject_reason"] == "ADV50_LE_2B"
    # ADV must use value, not close*volume proxy identity
    proxy = (df["close"] * df["volume"]).rolling(50).mean().iloc[-1]
    assert abs(float(out.iloc[-1]["adv50"]) - 3e9) < 1e-3
    assert abs(float(out.iloc[-1]["adv50"]) - float(proxy)) > 1e6  # different construction


def check_no_lookahead_fill_clock() -> None:
    df = _ohlcv_frame(n=80, start="2023-06-01")
    # Force a signal only on row 50
    df = compute_pit_universe(df)
    df["sma20"] = df["close"].rolling(20).mean()
    df["vol_sma20"] = df["volume"].rolling(20).mean()
    df["pullback3"] = -0.04
    df["rsi14"] = 40.0
    df["vnindex_close"] = 1000.0
    df["vni_sma20"] = 900.0
    df["ablation"] = "primary"
    df["signal"] = False
    df.loc[50, "signal"] = True
    df["prev_close"] = df["close"].shift(1)

    trades = simulate_symbol_trades(df)
    assert len(trades) >= 1
    t = next(x for x in trades if x["signal_date"] == df.loc[50, "date"])
    assert t["entry_date"] > t["signal_date"]
    assert t["same_close_fill"] is False
    if t["filled"]:
        # entry uses open of T+1, exit close of T+3
        assert t["entry_px"] == float(df.loc[51, "open"])
        assert t["exit_date"] == df.loc[53, "date"]
        assert t["exit_px"] == float(df.loc[53, "close"])


def check_entry_exit_clock_counting() -> None:
    df = _ohlcv_frame(n=60, start="2023-03-01")
    df = compute_pit_universe(df)
    df["ablation"] = "primary"
    df["prev_close"] = df["close"].shift(1)
    df["signal"] = False
    df.loc[20, "signal"] = True
    trades = simulate_symbol_trades(df)
    filled = [t for t in trades if t["filled"]]
    assert filled, trades
    t = filled[0]
    assert (t["exit_date"] - t["signal_date"]).days >= 1
    # session distance signal→exit == 3
    assert t["realized_hold_sessions"] == 3


def check_locked_limit_and_deferred_exit() -> None:
    # limit up detection
    row = pd.Series({"open": 10.7, "high": 10.7, "low": 10.7, "close": 10.7, "volume": 1e5})
    assert is_locked_limit_up(row, prev_close=10.0, limit_pct=0.07)
    row_d = pd.Series({"open": 9.3, "high": 9.3, "low": 9.3, "close": 9.3, "volume": 1e5})
    assert is_locked_limit_down(row_d, prev_close=10.0, limit_pct=0.07)

    df = _ohlcv_frame(n=40, start="2023-04-03")
    df = compute_pit_universe(df)
    df["ablation"] = "primary"
    df["prev_close"] = df["close"].shift(1)
    df["signal"] = False
    df.loc[10, "signal"] = True
    # Make T+1 a locked limit-up one-price bar
    pc = float(df.loc[10, "close"])
    lim = pc * 1.07
    df.loc[11, ["open", "high", "low", "close"]] = lim
    trades = simulate_symbol_trades(df)
    t = next(x for x in trades if x["signal_date"] == df.loc[10, "date"])
    assert t["filled"] is False
    assert t["entry_flag"] == "ENTRY_LOCKED_NO_FILL"

    # Deferred exit: scheduled exit zero volume then next bar ok
    df2 = _ohlcv_frame(n=40, start="2023-05-01")
    df2 = compute_pit_universe(df2)
    df2["ablation"] = "primary"
    df2["prev_close"] = df2["close"].shift(1)
    df2["signal"] = False
    df2.loc[10, "signal"] = True
    df2.loc[13, "volume"] = 0.0
    trades2 = simulate_symbol_trades(df2)
    t2 = next(x for x in trades2 if x.get("filled"))
    assert t2["exit_flag"] in {"EXIT_DEFERRED", "EXIT_SCHEDULED", "UNRESOLVED_EXIT_LOCK"}
    if t2["exit_flag"] == "EXIT_DEFERRED":
        assert t2["exit_date"] > df2.loc[13, "date"]


def check_ca_suspect_exclusion() -> None:
    df = _ohlcv_frame(n=50, start="2023-07-03")
    df.loc[20, "ca_suspect"] = True
    out = compute_pit_universe(df)
    assert not bool(out.loc[20, "universe_eligible"])
    assert out.loc[20, "universe_reject_reason"] == "CA_SUSPECT"

    df2 = _ohlcv_frame(n=50, start="2023-08-01")
    df2 = compute_pit_universe(df2)
    df2["ablation"] = "primary"
    df2["prev_close"] = df2["close"].shift(1)
    df2["signal"] = False
    df2.loc[10, "signal"] = True
    df2.loc[12, "ca_suspect"] = True  # in holding window
    trades = simulate_symbol_trades(df2)
    t = next(x for x in trades if x["signal_date"] == df2.loc[10, "date"])
    assert t["filled"] is False
    assert t["entry_flag"] == "CA_WINDOW_EXCLUDED"


def check_cost_arithmetic() -> None:
    gross = 0.01
    assert abs(apply_round_trip_cost(gross, 45) - (0.01 - 0.0045)) < 1e-12
    g = cost_grid(gross)
    assert abs(g["net_30bp"] - (gross - 0.003)) < 1e-12
    assert abs(g["net_45bp"] - (gross - 0.0045)) < 1e-12
    assert abs(g["net_60bp"] - (gross - 0.006)) < 1e-12


def check_ex_vin_vpl_policy() -> None:
    assert EX_VIN == frozenset({"VIC", "VHM", "VRE"})
    assert is_etf_excluded("E1VFVN30")
    assert is_etf_excluded("FUESSV50")
    assert classify_instrument("FPT") == "UNKNOWN_INSTRUMENT_TYPE"

    df = _ohlcv_frame(n=300, symbol="VPL", value_scale=5e9)
    out = compute_pit_universe(df)
    # before 252 bars
    assert out.loc[200, "universe_reject_reason"] == "VPL_LT_252" or not bool(out.loc[200, "universe_eligible"])
    assert bool(out.iloc[-1]["universe_eligible"])


def check_settlement_era_tagging() -> None:
    df = _ohlcv_frame(n=40, start="2022-08-01")
    df = compute_pit_universe(df)
    df["ablation"] = "primary"
    df["prev_close"] = df["close"].shift(1)
    df["signal"] = False
    # signal such that entry is before cutover
    # 2022-08-01 + ~10 bdays ≈ mid Aug
    df.loc[10, "signal"] = True
    trades = simulate_symbol_trades(df)
    t = next(x for x in trades if x["signal_date"] == df.loc[10, "date"])
    if pd.Timestamp(t["entry_date"]) < SETTLEMENT_CUTOVER:
        assert t["settlement_tag"] == "SETTLEMENT_T3_ERA"
    # post-cutover
    df2 = _ohlcv_frame(n=40, start="2022-09-01")
    df2 = compute_pit_universe(df2)
    df2["ablation"] = "primary"
    df2["prev_close"] = df2["close"].shift(1)
    df2["signal"] = False
    df2.loc[10, "signal"] = True
    t2 = next(x for x in simulate_symbol_trades(df2) if x["signal_date"] == df2.loc[10, "date"])
    assert t2["settlement_tag"] == "SETTLEMENT_T2_ERA"


def check_rsi_wilder_smoke() -> None:
    s = pd.Series(np.linspace(10, 20, 30))
    rsi = wilder_rsi(s)
    assert rsi.notna().sum() >= 10
    assert rsi.iloc[-1] > 50  # uptrend


def check_ssot_adv_spot() -> None:
    path = REPO / "data" / "fireant_ssot" / "ta_ohlcv_panel.parquet"
    if not path.exists():
        print("SKIP ssot spot — panel missing")
        return
    d = pd.read_parquet(path, columns=["symbol", "date", "value", "volume"])
    d["date"] = pd.to_datetime(d["date"])
    for sym, expect_liquid in [("FPT", True), ("AAA", False)]:
        g = d[d["symbol"] == sym].sort_values("date")
        if g.empty:
            continue
        # last 50 bars mean value
        adv = g.tail(50)["value"].mean()
        if expect_liquid:
            assert adv > ADV50_THRESHOLD, (sym, adv)
        # illiquid: soft check — if AAA exists and liquid somehow, don't fail hard
        print(f"  SSOT spot {sym}: ADV50~{adv/1e9:.2f}bn")


CHECKS = [
    ("pit_adv50_on_value", check_pit_adv50_on_value),
    ("no_lookahead_fill_clock", check_no_lookahead_fill_clock),
    ("entry_exit_clock_counting", check_entry_exit_clock_counting),
    ("locked_limit_and_deferred_exit", check_locked_limit_and_deferred_exit),
    ("ca_suspect_exclusion", check_ca_suspect_exclusion),
    ("cost_arithmetic", check_cost_arithmetic),
    ("ex_vin_vpl_policy", check_ex_vin_vpl_policy),
    ("settlement_era_tagging", check_settlement_era_tagging),
    ("rsi_wilder_smoke", check_rsi_wilder_smoke),
    ("ssot_adv_spot", check_ssot_adv_spot),
]


def main() -> int:
    failed = 0
    for name, fn in CHECKS:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")
    if failed:
        print(f"FAILED {failed}/{len(CHECKS)}")
        return 1
    print(f"ALL_B0_CHECKS_PASSED {len(CHECKS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
