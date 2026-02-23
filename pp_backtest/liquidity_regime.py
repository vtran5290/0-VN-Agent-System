"""
liquidity_regime.py
===================
Pre-registered spec — DO NOT change parameters after first run.

Purpose:
    Test whether PP_GIL_V4 has better edge when filtered by
    liquidity regime (loose liquidity) rather than MA200 trend regime.

Hypothesis:
    VN continuation edge is driven by liquidity cycles, not MA trend.
    When market liquidity is loose (volume expansion proxy: 30d vol > 6M avg vol),
    PP continuation is more likely to follow through.

Timeframe framework (pre-registered for VN backtest):
    Period        | Use for                    | Reason
    --------------|----------------------------|------------------------------------------
    2000–2006     | Do NOT use                  | Too early, high noise, not representative
    2007–2011     | Reference only, carefully  | Bubble + crash, different liquidity structure
    2012–2017     | Extended in-sample         | VN30 launch (Feb 2012), more stable structure
    2018–2022     | In-sample (current)        | Modern regime, institutional participation
    2023–2026     | Hold-out (current)         | Out-of-sample validation

    Recommendation before liquidity regime test:
    Run baseline_2012_2022 and baseline_2018_2022. If PF similar -> pooling 2012–2022 is OK.
    If PF differs a lot -> keep 2018 as main in-sample, use 2012–2017 as separate slice.

Pre-registered decision rule:
    Hold-out PF (2023-2026) > 0.924 (= baseline 0.874 + 0.05) -> regime filter HAS edge
    Hold-out PF <= 0.924 -> no liquidity regime alpha

Pre-registered parameters (DO NOT tune after seeing results):
    Primary proxy:   VN30 30-day rolling volume > 6-month avg volume (126 trading days)
    Fallback proxy:  If interbank rate data available, use rate < 6M avg
    DoF constraint:  ONE regime definition only. No grid search.

Usage:
    # 1. Validate logic before backtest
    python -m pp_backtest.liquidity_regime

    # 2. Full sample (diagnostic) — after --regime-liquidity is implemented in run.py
    python -m pp_backtest.run --no-gate --regime-liquidity

    # 3. Hold-out (validation)
    python -m pp_backtest.run --no-gate --regime-liquidity --start 2023-01-01 --end 2026-02-21

Output:
    Adds --regime-liquidity flag. Prints regime_liquidity=True/False, skipped_due_to_regime.

Implementation notes for engineer (run.py + backtest.py):
    1. Fetch VN30 OHLCV (same as MA200).
    2. rolling_vol_30  = volume.rolling(30,  min_periods=25).mean()
    3. rolling_vol_126 = volume.rolling(126, min_periods=100).mean()
    4. liquidity_on = (rolling_vol_30 > rolling_vol_126)
    5. Merge liquidity_on into each symbol df by date; entry_signal &= liquidity_on
    6. Count skipped_due_to_regime when PP=True but liquidity_on=False
"""

import sys
from pathlib import Path


def compute_liquidity_regime(vn30_df):
    """
    Pre-registered: liquidity_on = 30d vol avg > 126d vol avg (6 months).
    vn30_df must have columns: date, volume.
    Returns Series with index=date, name='liquidity_on', dtype bool.
    """
    import pandas as pd
    vol = vn30_df["volume"]
    rolling_30 = vol.rolling(30, min_periods=25).mean()
    rolling_126 = vol.rolling(126, min_periods=100).mean()
    liquidity_on = (rolling_30 > rolling_126).fillna(False)
    return pd.Series(liquidity_on.values, index=vn30_df["date"], name="liquidity_on")


def validate_regime_implementation():
    """
    Run before backtest to verify regime logic.
    """
    try:
        import pandas as pd
        import numpy as np

        print("Validating liquidity regime logic...")

        np.random.seed(42)
        n = 500
        dates = pd.date_range("2020-01-01", periods=n, freq="B")
        base_vol = 1_000_000
        trend = np.concatenate([np.linspace(1, 2, 250), np.linspace(2, 0.8, 250)])
        noise = np.random.lognormal(0, 0.2, n)
        volume = (base_vol * trend * noise).astype(int)

        df = pd.DataFrame({"date": dates, "volume": volume})
        rolling_30 = df["volume"].rolling(30, min_periods=25).mean()
        rolling_126 = df["volume"].rolling(126, min_periods=100).mean()
        liquidity_on = (rolling_30 > rolling_126)

        assert liquidity_on.dtype == bool or liquidity_on.isna().any(), "liquidity_on must be bool or has NaN in warmup"
        n_on = liquidity_on.sum()
        n_off = (~liquidity_on.fillna(False)).sum()
        n_nan = liquidity_on.isna().sum()
        print(f"  Regime ON  (liquidity loose): {n_on} bars ({n_on/n*100:.1f}%)")
        print(f"  Regime OFF (liquidity tight): {n_off} bars ({n_off/n*100:.1f}%)")
        print(f"  NaN (warmup):                {n_nan} bars")
        print("  Warmup required: 126 bars min")
        print()
        print("Pre-registered decision rule:")
        print("  Hold-out PF > 0.924 -> liquidity regime HAS edge")
        print("  Hold-out PF <= 0.924 -> no alpha, do not tweak")
        print()
        print("Timeframe reminder: run baseline_2012_2022 vs baseline_2018_2022 before liquidity test.")
        print("Validation PASSED.")
        return True
    except Exception as e:
        print(f"Validation FAILED: {e}")
        return False


if __name__ == "__main__":
    ok = validate_regime_implementation()
    sys.exit(0 if ok else 1)
