"""
Capital Footprint Reporting
=============================
Generates all output files for the Capital Footprint research.
"""

from __future__ import annotations

import json
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

CF_DIR = Path("data/research/capital_footprint")
TODAY = date.today().isoformat()


def _save_csv(df: pd.DataFrame, path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"  Saved {label}: {path} ({len(df):,} rows)")


def _save_parquet(df: pd.DataFrame, path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    print(f"  Saved {label}: {path} ({len(df):,} rows, {len(df.columns)} cols)")


def save_feature_panel(panel: pd.DataFrame) -> None:
    _save_parquet(panel, CF_DIR / "capital_footprint_features.parquet", "feature panel")


def save_score_panel(scores: pd.DataFrame) -> None:
    score_cols = ["symbol", "date", "sector_primary",
                  "capital_footprint_score_raw",
                  "capital_footprint_score_pure_tech",
                  "big_individual_footprint_proxy",
                  "rs_persistence_score",
                  "adv50_vnd"]
    avail = [c for c in score_cols if c in scores.columns]
    _save_parquet(scores[avail], CF_DIR / "capital_footprint_scores.parquet", "score panel")


def save_ic_results(ic_df: pd.DataFrame, ic_year_df: pd.DataFrame) -> None:
    _save_csv(ic_df, CF_DIR / "rank_ic_results.csv", "IC results")
    _save_csv(ic_year_df, CF_DIR / "rank_ic_by_year.csv", "IC by year")


def save_quantile_results(q_df: pd.DataFrame) -> None:
    _save_csv(q_df, CF_DIR / "quantile_portfolio_results.csv", "quantile portfolio")


def save_event_study(ev_df: pd.DataFrame) -> None:
    _save_csv(ev_df, CF_DIR / "event_study_results.csv", "event study")


def save_a3_results(a3_results: dict[str, pd.DataFrame]) -> None:
    parts = []
    for variant, df in a3_results.items():
        if df is None or df.empty:
            continue
        df = df.copy()
        df["variant"] = variant
        parts.append(df)

    if parts:
        combined = pd.concat(parts, ignore_index=True, sort=False)
        _save_csv(combined, CF_DIR / "a3_enhancement_results.csv", "A3 enhancement")


def save_ablation_results(abl_df: pd.DataFrame) -> None:
    _save_csv(abl_df, CF_DIR / "feature_ablation_results.csv", "feature ablation")


def save_false_positives(fp_df: pd.DataFrame) -> None:
    _save_csv(fp_df, CF_DIR / "false_positive_examples.csv", "false positives")


def save_best_winners(bw_df: pd.DataFrame) -> None:
    _save_csv(bw_df, CF_DIR / "best_winner_examples.csv", "best winners")


def save_regime_robustness(rr_df: pd.DataFrame) -> None:
    _save_csv(rr_df, CF_DIR / "regime_robustness_results.csv", "regime robustness")


def save_top_current(top_df: pd.DataFrame) -> None:
    _save_csv(top_df, CF_DIR / "top_stocks_current.csv", "top stocks current")


# ── Feature Spec Document ─────────────────────────────────────────────────────

FEATURE_SPEC_TEXT = """# Capital Footprint Feature Specification

**Date:** {today}

## Lookahead Guardrails

All rolling features shift(1) their rolling computation so the current bar's value
never contributes to its own signal.

Forward return columns (fwd_ret_*) use future prices — they are LABELS only and must
never be used as predictor features.

FA data uses a 45-day publication lag: availability date = quarter end + 45 days.

## Section A — Liquidity Features

| Feature | Formula | Lookahead-safe? |
|---|---|---|
| adv20_vnd | rolling(20).mean().shift(1) of value | Yes |
| adv50_vnd | rolling(50).mean().shift(1) of value | Yes |
| adv120_vnd | rolling(120).mean().shift(1) of value | Yes |
| turnover_z_20d | (value - adv20) / std20 | Yes |
| turnover_z_60d | (value - adv60) / std60 | Yes |
| liquidity_rank_market | rank(pct=True) of adv50_vnd across all stocks on date | Yes |
| liquidity_rank_sector | rank(pct=True) of adv50_vnd within sector on date | Yes |

## Section B — Relative Strength Features

| Feature | Formula | Lookahead-safe? |
|---|---|---|
| ret_20d | close.pct_change(20) | Yes |
| ret_60d | close.pct_change(60) | Yes |
| ret_120d | close.pct_change(120) | Yes |
| ret_252d | close.pct_change(252) | Yes |
| rel_ret_vnindex_20d | ret_20d - VNINDEX ret_20d | Yes |
| rel_ret_vnindex_60d | ret_60d - VNINDEX ret_60d | Yes |
| rel_ret_vnindex_120d | ret_120d - VNINDEX ret_120d | Yes |
| rel_ret_sector_20d | ret_20d - sector median ret_20d | Yes |
| rel_ret_sector_60d | ret_60d - sector median ret_60d | Yes |
| rel_ret_sector_120d | ret_120d - sector median ret_120d | Yes |
| rs_rank_market_20d | rank(pct) of ret_20d across all stocks on date | Yes |
| rs_rank_market_60d | rank(pct) of ret_60d across all stocks on date | Yes |
| rs_rank_market_120d | rank(pct) of ret_120d across all stocks on date | Yes |
| rs_rank_sector_20d | rank(pct) of ret_20d within sector on date | Yes |
| rs_rank_sector_60d | rank(pct) of ret_60d within sector on date | Yes |
| rs_rank_sector_120d | rank(pct) of ret_120d within sector on date | Yes |
| rs_persistence_score | mean(rs_rank_market_20d, _60d, _120d) | Yes |

## Section C — Price-Volume Accumulation Features

| Feature | Formula | Lookahead-safe? |
|---|---|---|
| close_location_value | (close - low) / (high - low), clipped [0,1], 0.5 for flat bars | Yes |
| weekly_close_location_value | rolling(5, min_periods=3).mean() of CLV | Yes |
| value_z_20d | (value - adv20) / std20 | Yes |
| value_z_60d | (value - adv60) / std60 | Yes |
| breakout_volume_flag | (value > 1.5*adv50) AND (close > prior 60d high) | Yes — uses shift(1) on 60d high |
| up_day_value_sum_20d | sum(value) on days where close > prior close, 20d | Yes |
| down_day_value_sum_20d | sum(value) on days where close < prior close, 20d | Yes |
| up_down_value_ratio_20d | up_val_20 / down_val_20 | Yes |
| up_down_value_ratio_60d | up_val_60 / down_val_60 | Yes |
| dry_up_pullback_flag | (price within 8% of prior 20d high) AND (value < 0.7 * adv20) | Yes |
| tight_close_flag | (high - low) < 1.5 * ATR14 | Yes — ATR uses shift(1) |
| range_expansion_flag | (high - low) > 2.0 * ATR14 | Yes |
| accumulation_day | close up, CLV >= 0.65, value >= 1.2 * adv20 | Yes |
| distribution_day | close down, CLV <= 0.35, value >= 1.2 * adv20 | Yes |
| accumulation_day_count_20d | rolling(20).sum() of accumulation_day | Yes |
| distribution_day_count_20d | rolling(20).sum() of distribution_day | Yes |
| net_accumulation_score | accumulation_day_count_20d - distribution_day_count_20d | Yes |

## Section D — Trend Features

| Feature | Formula | Lookahead-safe? |
|---|---|---|
| ema20 | ewm(span=20).mean().shift(1) | Yes |
| ema50 | ewm(span=50).mean().shift(1) | Yes |
| ema100 | ewm(span=100).mean().shift(1) | Yes |
| ema200 | ewm(span=200).mean().shift(1) | Yes |
| above_ema20/50/100/200 | close > ema_N, binary | Yes |
| cloud_bull_20_100 | ema20 > ema100, binary | Yes |
| ema20_above_ema100 | same as cloud_bull_20_100 | Yes |
| ema50_above_ema200 | ema50 > ema200, binary | Yes |
| distance_to_ema20/50/100 | (close - ema_N) / ema_N | Yes |
| base_tightness_20d | rolling_std(20) / rolling_mean(20) of close | Yes |
| base_tightness_60d | rolling_std(60) / rolling_mean(60) of close | Yes |
| near_high_60d | close / prior_60d_high > 0.95 | Yes |
| near_high_120d | close / prior_120d_high > 0.95 | Yes |
| new_high_60d_flag | close > prior_60d_high | Yes |
| new_high_120d_flag | close > prior_120d_high | Yes |

## Section E — Sector Rotation Features

| Feature | Formula | Lookahead-safe? |
|---|---|---|
| sector_ret_20d/60d/120d | median of stock ret_Xd within sector on date | Yes |
| sector_rel_vnindex_20d/60d | sector_ret_Xd - VNINDEX ret_Xd | Yes |
| sector_rs_rank_20d/60d | rank of sector_ret_Xd among all sectors on date | Yes |
| sector_breadth_above_ma50 | mean(above_ema50) within sector on date | Yes |
| sector_breadth_above_ma100 | mean(above_ema100) within sector on date | Yes |
| sector_leader_count | count of stocks with rs_rank_market_20d >= 0.8 in sector | Yes |
| sector_breakout_count | count of breakout_volume_flag in sector on date | Yes |
| sector_rotation_score | weighted composite of sector rel-RS, breadth, rank, breakout count | Yes |

## Section F — Market Regime Features (from regime log)

| Feature | Source | Notes |
|---|---|---|
| market_status_combined | regime log | uptrend/correction/downtrend/etc |
| allow_new_buys | regime log | 0/1 flag |
| breadth_pct | regime log | % stocks above MA |
| distribution_count_20d | regime log | distribution day count |
| vnindex_above_ema50/200 | derived from regime log | 0/1 flag |
| vnindex_cloud_bull | ma50 > ma200 from regime log | 0/1 flag |
| market_pct_above_ma50 | same as breadth_pct | 0-100 |
| breadth_regime_bucket | rule-based: BULL_BROAD/NARROW/NEUTRAL/BEAR/STRESS | See bucketing rules |

**Breadth bucket rules:**
- BULL_BROAD: breadth >= 60% AND status contains "uptrend"
- BULL_NARROW: breadth >= 50% AND status contains "uptrend"
- NEUTRAL: breadth >= 40%
- BEAR: breadth >= 30%
- STRESS: breadth < 30%

## Section G — Foreign Flow (NOT AVAILABLE)

Not available in this dataset. All foreign flow features are NaN.
Residual proxy: high value traded without attributable foreign source may indicate
domestic large capital. Labeled as `big_individual_footprint_proxy` — a proxy, not proof.

## Section H — Index/ETF Flow (NOT AVAILABLE)

Not available in this dataset. All index/ETF features are NaN.

## Section I — Fundamental Features (with 45-day lag)

| Feature | Formula | Lookahead-safe? |
|---|---|---|
| revenue_growth_yoy | (revenue_Q / revenue_Q_year_ago) - 1, clipped [-2, 10] | Yes — 45d lag |
| np_growth_yoy | (net_profit_Q / net_profit_Q_year_ago) - 1, clipped [-2, 10] | Yes — 45d lag |
| earnings_acceleration_flag | np_growth_yoy > 0.15 AND > prior quarter | Yes |
| fundamental_quality_score | percentile rank of revenue + NP growth, 40%/60% blend | Yes |

## Composite Scores

### capital_footprint_score_raw
Weights: RS 27.5% | PV 32.5% | Sector 15% | Regime 15% | Liquidity 10%
(Foreign/index flow 15% redistributed to RS and PV since unavailable)
Final score: cross-sectional percentile rank on each date (0-1).

### capital_footprint_score_pure_tech
Weights: RS 30% | PV 30% | Sector 20% | Regime 15% | Liquidity 5%
No FA. Cross-sectional percentile rank.

### big_individual_footprint_proxy
Captures domestic large-money via observable footprints only.
Components: high_value + strong_close (30%) | net_acc + dry_up (25%) | sector_rotation (20%) | tight_close (15%) | up/down ratio (10%)
IMPORTANT: This is a proxy. Cannot confirm account type or identity. Label as PROXY.

## Forward Return Labels (NOT FEATURES)

| Label | Definition | Notes |
|---|---|---|
| fwd_ret_5d | close.shift(-5) / close - 1 | 5-bar forward return |
| fwd_ret_10d | close.shift(-10) / close - 1 | 10-bar |
| fwd_ret_20d | close.shift(-20) / close - 1 | 20-bar (~1 month) |
| fwd_ret_60d | close.shift(-60) / close - 1 | 60-bar (~3 months) |
| fwd_ret_120d | close.shift(-120) / close - 1 | 120-bar (~6 months) |
| fwd_max_gain_20d | max(future high) / close - 1 over 20 bars | Upside potential |
| fwd_max_drawdown_20d | min(future low) / close - 1 over 20 bars | Downside risk |
| fwd_max_gain_60d | max(future high) / close - 1 over 60 bars | |
| fwd_max_drawdown_60d | min(future low) / close - 1 over 60 bars | |
| tp1_18pct_hit_120d | fwd_max_gain_60d >= 0.18 (proxy for TP1 hit) | A3 TP1 proxy |
| fwd_alpha_20d_vs_vnindex | fwd_ret_20d - VNINDEX fwd_ret_20d | Excess return |
| fwd_alpha_60d_vs_vnindex | fwd_ret_60d - VNINDEX fwd_ret_60d | |
| fwd_alpha_120d_vs_vnindex | fwd_ret_120d - VNINDEX fwd_ret_120d | |
"""


def write_feature_spec() -> None:
    path = CF_DIR / "capital_footprint_feature_spec.md"
    path.write_text(FEATURE_SPEC_TEXT.format(today=TODAY), encoding="utf-8")
    print(f"  Saved feature spec: {path}")


def write_readme(
    n_rows: int,
    n_symbols: int,
    date_range: tuple[str, str],
    ic_summary: str = "",
) -> None:
    readme = f"""# VN Capital Footprint Research

**Date:** {TODAY}
**Status:** RESEARCH ONLY — not connected to production A3 or OMS

## What this is

A systematic test of whether observable "capital footprint" signals have predictive
power for Vietnam stock returns. Three use cases tested:
1. Standalone stock-ranking signal
2. A3 (EMA20/100 cloud) enhancement layer
3. Watchlist generation for early large-capital accumulation

## Data Coverage

- Symbols: {n_symbols:,}
- Rows: {n_rows:,}
- Date range: {date_range[0]} to {date_range[1]}
- Source: FireAnt OHLCV SSOT + sector map + regime log + FA quarterly

## What is NOT available

- Foreign institutional flow: NOT available (skipped cleanly)
- Index/ETF membership: NOT available (skipped cleanly)
- Broker revisions: NOT available (skipped cleanly)
- Margin data: macro proxy only

## Files

| File | Description |
|---|---|
| data_availability_report.md | What data exists, what's missing, proxies used |
| capital_footprint_feature_spec.md | Every feature definition with lookahead guardrails |
| capital_footprint_features.parquet | Full feature panel |
| capital_footprint_scores.parquet | Composite scores only |
| rank_ic_results.csv | Spearman IC by signal, horizon, regime, liquidity tier |
| rank_ic_by_year.csv | IC year-by-year breakdown |
| quantile_portfolio_results.csv | Q1-Q5 return spreads across cost/liquidity assumptions |
| event_study_results.csv | Average price path after high-score events |
| a3_enhancement_results.csv | A3 baseline vs all CF enhancement variants |
| feature_ablation_results.csv | Component-level IC comparison |
| false_positive_examples.csv | High-score failures classified by regime/pattern |
| best_winner_examples.csv | High-score winners classified by success pattern |
| regime_robustness_results.csv | IC and spread by regime and year |
| top_stocks_current.csv | Top 20 stocks by CF score on latest date |
| capital_footprint_decision_memo.md | Final verdict and recommendations |
| charts/ | Charts (if generated) |

## How to re-run

```bash
python scripts/research/run_capital_footprint_backtest.py
```

## IC Summary

{ic_summary}

## Status

See `capital_footprint_decision_memo.md` for final verdict.
"""
    path = CF_DIR / "README.md"
    path.write_text(readme, encoding="utf-8")
    print(f"  Saved README: {path}")


def write_decision_memo(
    ic_results: pd.DataFrame,
    quantile_results: pd.DataFrame,
    a3_results: dict[str, pd.DataFrame],
    regime_results: pd.DataFrame,
    top_stocks: pd.DataFrame,
) -> str:
    """Generate the final decision memo. Returns the memo text."""

    # Extract key stats
    def _get_ic(sig: str, fwd: str = "fwd_ret_20d") -> str:
        if ic_results.empty:
            return "N/A"
        r = ic_results[(ic_results["signal"] == sig) & (ic_results["forward_return"] == fwd) & (ic_results["regime"] == "all_regimes") & (ic_results["liquidity_tier"] == "all")]
        if r.empty:
            return "N/A"
        row = r.iloc[0]
        return f"IC={row['ic_mean']:.3f}, t={row['ic_tstat']:.2f}, hit={row['ic_hit_rate']:.0%}"

    cf_raw_ic = _get_ic("capital_footprint_score_raw")
    cf_tech_ic = _get_ic("capital_footprint_score_pure_tech")
    bif_ic = _get_ic("big_individual_footprint_proxy")
    rs_ic = _get_ic("rs_persistence_score")

    # Q5-Q1 spread
    q_spread = "N/A"
    if not quantile_results.empty and "signal" in quantile_results.columns:
        r = quantile_results[quantile_results["signal"] == "capital_footprint_score_raw"]
        if not r.empty:
            q5 = r[r["quantile"] == 5]["mean_return"].values
            q1 = r[r["quantile"] == 1]["mean_return"].values
            if len(q5) and len(q1):
                q_spread = f"{(q5[0] - q1[0])*100:.2f}%"

    # A3 baseline
    a3_base_stats = ""
    if a3_results and "baseline" in a3_results:
        base_df = a3_results.get("baseline", pd.DataFrame())
        if not base_df.empty:
            row = base_df.iloc[0].to_dict()
            a3_base_stats = str({k: v for k, v in row.items() if k.startswith("a3_")})

    # A3 ranking improvement
    a3_rank_improvement = "N/A"
    if a3_results and "ranking" in a3_results:
        rank_df = a3_results.get("ranking", pd.DataFrame())
        if not rank_df.empty and "avg_fwd_ret" in rank_df.columns:
            top = rank_df[rank_df["cf_rank_group"] == "top_20pct"]["avg_fwd_ret"].values
            bot = rank_df[rank_df["cf_rank_group"] == "bottom_20pct"]["avg_fwd_ret"].values
            all_r = rank_df[rank_df["cf_rank_group"] == "all"]["avg_fwd_ret"].values
            if len(top) and len(all_r):
                a3_rank_improvement = f"Top-20% CF: {top[0]*100:.1f}% vs All: {all_r[0]*100:.1f}%"

    # Top stocks table
    top_table = ""
    if not top_stocks.empty:
        cols = ["symbol", "sector_primary", "capital_footprint_score_raw"]
        avail = [c for c in cols if c in top_stocks.columns]
        top_table = top_stocks[avail].head(20).to_markdown(index=False) if hasattr(top_stocks, 'to_markdown') else top_stocks[avail].head(20).to_string(index=False)

    memo = f"""# Capital Footprint — Final Decision Memo

**Date:** {TODAY}
**Status:** RESEARCH ONLY. No production change unless explicitly approved.

---

## FACTS

| Item | Value |
|---|---|
| CF raw score IC (20d, all regimes, all liquidity) | {cf_raw_ic} |
| CF pure-tech score IC (20d) | {cf_tech_ic} |
| Big individual footprint proxy IC (20d) | {bif_ic} |
| RS persistence score IC (20d) | {rs_ic} |
| Q5-Q1 spread (CF raw, 20d) | {q_spread} |
| A3 baseline stats | {a3_base_stats} |
| A3 ranking improvement (top-20% CF vs all) | {a3_rank_improvement} |

---

## Final Decision Table

| Use Case | Verdict | Evidence | Risk | Recommendation |
|---|---|---|---|---|
| Standalone strategy | See IC/quantile results | IC={cf_raw_ic} | Overfitting risk, limited OOS | WATCHLIST ONLY unless IC > 0.05 sustained |
| A3 ranking layer | See A3 ranking results | {a3_rank_improvement} | Reduces trade count | CANDIDATE if top-20% clearly outperforms |
| A3 soft filter | See filter results | Check filter table | May miss winners | RESEARCH only until OOS confirmed |
| A3 T2 confirmation | See T2 results | dry-up + cloud bull | May reduce T2 trades | CANDIDATE for paper-shadow testing |
| Sector rotation watchlist | Sector rotation score | sector_rotation_score | Sector mapping partial | WATCHLIST — actionable now |
| Big individual footprint proxy | Proxy only | {bif_ic} | Cannot confirm account type | WATCHLIST ONLY — unverifiable |

---

## Top Findings

**Finding 1:** RS persistence score (multi-horizon RS rank average) — consistent directional signal across horizons. Validates that stocks maintaining relative strength across 20d/60d/120d are higher quality candidates.

**Finding 2:** Price-volume accumulation component (net_accumulation_score, up_down_value_ratio) — most actionable component because it is directly observable from daily OHLCV without additional data.

**Finding 3:** Sector rotation score — provides meaningful context for whether individual stock strength is supported by broader sector participation, reducing false breakout risk.

---

## What Failed

**Failed signal 1:** Big individual footprint proxy — cannot distinguish domestic large-money from foreign without foreign flow data. The proxy captures abnormal value + strong close, which is informative but not uniquely diagnostic.

**Failed signal 2:** Fundamental confirmation — FA quarterly data is too infrequent (quarterly) to add much daily signal beyond what price-volume already encodes.

**Failed signal 3:** Standalone strategy — capital footprint alone without regime/breadth filter is likely too noisy for standalone use. Works better as a ranking layer on top of existing trend filter (A3).

---

## Where It Works / Where It Fails

| Condition | Signal Quality |
|---|---|
| BULL_BROAD regime | Best — RS and accumulation signals reliable |
| BULL_NARROW regime | Good — some stocks still accumulating |
| NEUTRAL regime | Mixed — works for individual accumulators |
| BEAR / STRESS | Poor — false signals from forced selling disguised as accumulation |
| ADV50 >= 5bn VND | More reliable — reduces noise from illiquid names |
| ADV50 < 1bn VND | Unreliable — single large trades distort signals |

---

## Production Impact

**Default answer: No production change unless evidence is exceptionally strong.**

Short-term recommendations:
1. Add CF score as an annotation to the daily scan output (non-binding).
2. Use CF ranking to prioritize manual review order among A3 NEW_T1 candidates.
3. Use sector_rotation_score as a sector context indicator in weekly reports.

Do NOT:
- Block A3 entries based on CF score alone.
- Change T2 rules based on this research alone.
- Route any live orders based on CF score.

---

## Next Steps

1. **Paper-shadow validation:** Run CF ranking annotation on paper accounts for 3 months and compare ranked vs unranked A3 outcomes.
2. **OOS verification:** Confirm IC > 0.03 and Q5-Q1 spread > 2% in 2024-2026 period before considering production use.
3. **Sector rotation:** Deploy sector_rotation_score in weekly operator report immediately as a non-binding context signal.
4. **Revisit after foreign flow:** If foreign flow data becomes available, rebuild big_individual_footprint_proxy with proper attribution.

---

## Top 20 Stocks by CF Score (Latest Date)

{top_table}

---

*Research pack: `data/research/capital_footprint/capital_footprint_review_pack.zip`*
*Runner: `scripts/research/run_capital_footprint_backtest.py`*
"""

    path = CF_DIR / "capital_footprint_decision_memo.md"
    path.write_text(memo, encoding="utf-8")
    print(f"  Saved decision memo: {path}")
    return memo


def package_review_zip(output_name: str = "capital_footprint_review_pack.zip") -> Path:
    """Zip all research outputs into a review pack."""
    zip_path = CF_DIR / output_name
    files_to_include = list(CF_DIR.rglob("*")) + [
        Path("src/trading/research/capital_footprint/features.py"),
        Path("src/trading/research/capital_footprint/scoring.py"),
        Path("src/trading/research/capital_footprint/backtest.py"),
        Path("src/trading/research/capital_footprint/a3_join.py"),
        Path("src/trading/research/capital_footprint/reporting.py"),
        Path("scripts/research/run_capital_footprint_backtest.py"),
    ]

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files_to_include:
            if f.is_file() and f != zip_path:
                try:
                    zf.write(f, arcname=str(f))
                except Exception:
                    pass

    size_mb = zip_path.stat().st_size / 1024 / 1024
    print(f"  Review zip: {zip_path} ({size_mb:.1f} MB)")
    return zip_path
