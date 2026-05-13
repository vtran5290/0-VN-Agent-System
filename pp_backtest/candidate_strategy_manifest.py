"""
Frozen strategy candidate set — VN equities 2012-2026.

Do NOT modify without an explicit research decision recorded in RESEARCH_REPORT.md.
Last updated: 2026-05-13
"""
from __future__ import annotations

# ── Production candidates ─────────────────────────────────────────────────────

PRIMARY: dict = {
    "label":         "B_cloud20_100_partial",
    "entry_type":    "cloud_only",
    "ema_fast":      20,
    "ema_slow":      100,
    "exit_mode":     "partial_tp",
    "max_hold":      250,
    "max_positions": 20,
    "universe":      "ex_vin3",
    "status":        "primary",
    "rationale": (
        "Best risk-adjusted result on 2012-2026 extended dataset. "
        "CAGR=10.7%, maxDD=-30.1%, Sharpe=1.136, MAR=0.36, OOS avg_trade=6.3%. "
        "VIN-neutral: full vs ex-VIN3 delta < 0.5pp."
    ),
}

SHADOW: dict = {
    "label":         "B_cloud21_55_partial",
    "entry_type":    "cloud_only",
    "ema_fast":      21,
    "ema_slow":      55,
    "exit_mode":     "partial_tp",
    "max_hold":      250,
    "max_positions": 20,
    "universe":      "ex_vin3",
    "status":        "shadow",
    "rationale": (
        "More OOS-stable at signal level. Lower headline portfolio CAGR but "
        "cleaner train→test degradation. Promoted to primary if 20/100 degrades "
        "significantly under hardening."
    ),
}

SANDBOX: list[dict] = [
    {
        "label":         "A_basehigh_partial_tp",
        "entry_type":    "base_high",
        "ema_fast":      10,
        "ema_slow":      50,
        "exit_mode":     "partial_tp",
        "max_hold":      120,
        "max_positions": 20,
        "universe":      "ex_vin3",
        "status":        "tactical_sandbox",
        "rationale": (
            "Short-horizon breakout. Full-universe CAGR is VIN-contaminated. "
            "Ex-VIN CAGR=5.2%. Not a standalone production strategy."
        ),
    },
    {
        "label":         "A_basehigh_trail25",
        "entry_type":    "base_high",
        "ema_fast":      10,
        "ema_slow":      50,
        "exit_mode":     "trailing_2.5",
        "max_hold":      120,
        "max_positions": 20,
        "universe":      "ex_vin3",
        "status":        "tactical_sandbox",
        "rationale": (
            "Highest raw ex-VIN CAGR=15.0% but maxDD=-51.8%. "
            "Drawdown disqualifies it as standalone production strategy."
        ),
    },
]

# ── Permanently discarded — do not revive ────────────────────────────────────

DISCARDED: dict[str, str] = {
    "level_breakout": (
        "Sharpe=-0.131, test avg_return=-1.3% on 2012-2026 data. "
        "Overfit to favorable 2018-2022 regime."
    ),
    "cloud_loss_3": (
        "Inferior to partial_tp on risk-adjusted metrics in both A and B."
    ),
    "atr_fixed_stop":       "Ineffective across all tested configurations.",
    "breakout_retest":      "Discarded Phase 1.",
    "standalone_reclaim":   "Discarded Phase 1.",
    "lookback_60_longhold": "Overfit confirmed.",
}

# ── Convenience iterators ─────────────────────────────────────────────────────

PRODUCTION_CANDIDATES: list[dict] = [PRIMARY, SHADOW]
ALL_CANDIDATES:        list[dict] = [PRIMARY, SHADOW] + SANDBOX

FROZEN_DATE = "2026-05-13"
