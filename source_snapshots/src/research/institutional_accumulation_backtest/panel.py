from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.scans.institutional_accumulation.config import (
    ETF_EXCLUSION_SECTORS,
    ETF_EXCLUSION_SYMBOLS,
    FRAGILE_REGIME_LABEL,
    VIN_DISTORTION_SYMBOLS,
)
from src.scans.institutional_accumulation.context import (
    _empty_context,
    _normalize_monthly,
    context_score,
    tag_symbol,
)
from src.scans.institutional_accumulation.filters import liquidity_metrics, passes_liquidity
from src.scans.institutional_accumulation.indicators import (
    compute_money_flow_metrics,
    compute_price_structure_metrics,
    slice_through,
    vingroup_distortion_diagnosis,
)
from src.scans.institutional_accumulation.scoring import (
    assign_tier,
    composite_score,
    detect_one_bar_spike,
    score_money_flow,
    score_price_structure,
    score_risk_penalty,
)

from .data_loader import load_symbol_df
from .schema import ContextMode, VinPolicy


@dataclass
class PanelConfig:
    start: str
    end: str
    cadence: str
    context_mode: ContextMode
    min_history_days: int = 120
    min_adv20_vnd: float = 2_000_000_000.0
    min_adv50_vnd: float = 1_500_000_000.0


def _get_signal_dates(benchmark: pd.DataFrame, start: str, end: str, cadence: str) -> list[pd.Timestamp]:
    b = benchmark.copy()
    b["date"] = pd.to_datetime(b["date"], errors="coerce")
    b = b.dropna(subset=["date"])
    b = b[(b["date"] >= pd.Timestamp(start)) & (b["date"] <= pd.Timestamp(end))]
    if b.empty:
        return []
    if cadence.lower() == "monthly":
        return list(b.groupby(b["date"].dt.to_period("M"))["date"].max().sort_values())
    return list(b.groupby(b["date"].dt.to_period("W-FRI"))["date"].max().sort_values())


def _tier_num(tier: str) -> int:
    return {"Tier 1": 1, "Tier 2": 2, "Tier 3": 3, "Reject": 4}.get(tier, 9)


def _context_for_date(scan_date: str, mode: ContextMode) -> tuple[dict[str, Any], str]:
    if mode == ContextMode.OHLCV_ONLY:
        return _empty_context("ohlcv_only"), "OHLCV_ONLY"
    if mode == ContextMode.SYNTHETIC_APR2026_CONTEXT_ONLY_NOT_EMPIRICAL:
        from src.scans.institutional_accumulation.context import load_smart_money_context

        return (
            load_smart_money_context("2026-04"),
            "SYNTHETIC_APR2026_CONTEXT_ONLY_NOT_EMPIRICAL",
        )
    month = scan_date[:7]
    monthly_path = Path("data") / "smart_money" / "monthly" / f"smart_money_{month}.json"
    if not monthly_path.is_file():
        return _empty_context("pit_monthly_unavailable"), "PIT_MONTHLY_CONTEXT_UNAVAILABLE"
    try:
        raw = pd.read_json(monthly_path)
    except Exception:
        return _empty_context("pit_monthly_invalid"), "PIT_MONTHLY_CONTEXT_UNAVAILABLE"
    data = raw.to_dict() if isinstance(raw, pd.DataFrame) else {}
    return _normalize_monthly(data, source=f"monthly:{monthly_path.name}"), "PIT_MONTHLY_CONTEXT"


def _finalize_date_panel(
    dfd: pd.DataFrame,
    *,
    regime_by_date: pd.DataFrame,
    dt: pd.Timestamp,
    regime_label: str,
) -> pd.DataFrame:
    if dfd.empty:
        return dfd
    liq = dfd[dfd["is_liquid"] == True]  # noqa: E712
    if not liq.empty:
        dfd = dfd.copy()
        dfd.loc[liq.index, "score_percentile"] = liq["institutional_accumulation_score"].rank(pct=True).values
    tiers = []
    for _, r in dfd.iterrows():
        tiers.append(
            assign_tier(
                float(r["institutional_accumulation_score"]),
                float(r["score_money_flow"]),
                float(r["score_risk_penalty"]),
                liquidity_ok=bool(r["is_liquid"]),
                regime_label=regime_label,
                score_percentile=float(r["score_percentile"]) if pd.notna(r.get("score_percentile")) else None,
                in_consensus_core=bool("consensus_core" in str(r.get("smart_money_tags", ""))),
            )
        )
    dfd = dfd.copy()
    dfd["tier"] = tiers
    dfd["tier_num"] = dfd["tier"].map(_tier_num)
    dfd["is_tier1"] = dfd["tier"] == "Tier 1"
    dfd["is_tier2"] = dfd["tier"] == "Tier 2"
    dfd["is_tier3"] = dfd["tier"] == "Tier 3"
    dfd["is_reject"] = dfd["tier"] == "Reject"
    dfd["is_tier12"] = dfd["tier"].isin(["Tier 1", "Tier 2"])
    dfd["is_tier123"] = dfd["tier"].isin(["Tier 1", "Tier 2", "Tier 3"])
    dfd["emerging_accumulation_candidate"] = (
        dfd["is_tier123"]
        & (~dfd["has_fund_disclosure_tag"])
        & (dfd["score_money_flow"] >= 48)
        & (dfd["score_risk_penalty"] <= 30)
    )
    if dt in regime_by_date.index:
        for col in regime_by_date.columns:
            dfd[col] = bool(regime_by_date.loc[dt, col])
        dfd["regime_reconstructed"] = (
            FRAGILE_REGIME_LABEL
            if bool(regime_by_date.loc[dt, "fragile_uptrend_narrow_leadership_proxy"])
            else "normal_regime"
        )
    return dfd


def build_panel(
    panel_cfg: PanelConfig,
    benchmark: pd.DataFrame,
    benchmark_slice: pd.DataFrame,
    symbols: list[str],
    stocks_dir: Path,
    sector_map: dict[str, str],
    regimes: pd.DataFrame,
    vin_policy: VinPolicy,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    dates = _get_signal_dates(benchmark_slice, panel_cfg.start, panel_cfg.end, panel_cfg.cadence)
    regime_by_date = regimes.set_index(pd.to_datetime(regimes["date"]))
    blocked_columns: set[str] = set()
    vin_excl = set(vin_policy.exclude_symbols)
    bench_by_scan = {dt.strftime("%Y-%m-%d"): slice_through(benchmark, dt.strftime("%Y-%m-%d")) for dt in dates}
    ctx_cache: dict[str, tuple[dict[str, Any], str]] = {}
    flat_rows: list[dict[str, Any]] = []

    for sym in symbols:
        d = load_symbol_df(stocks_dir, sym)
        if d is None or d.empty:
            continue
        d = d.sort_values("date").reset_index(drop=True)
        sector = sector_map.get(sym, "Unknown")
        if sym in ETF_EXCLUSION_SYMBOLS or sector in ETF_EXCLUSION_SECTORS:
            continue
        d_dates = pd.to_datetime(d["date"], errors="coerce").to_numpy(dtype="datetime64[ns]")
        if len(d_dates) == 0:
            continue
        is_vin = sym in vin_excl
        for dt in dates:
            scan_date = dt.strftime("%Y-%m-%d")
            pos = int(np.searchsorted(d_dates, np.datetime64(dt), side="right"))
            if pos < panel_cfg.min_history_days:
                continue
            daily = d.iloc[:pos]
            if daily.empty:
                continue
            liq = liquidity_metrics(daily)
            liq_ok, _ = passes_liquidity(
                liq,
                min_history=panel_cfg.min_history_days,
                min_adv20=panel_cfg.min_adv20_vnd,
                min_adv50=panel_cfg.min_adv50_vnd,
            )
            has_min_history = len(daily) >= panel_cfg.min_history_days
            if scan_date not in ctx_cache:
                ctx_cache[scan_date] = _context_for_date(scan_date, panel_cfg.context_mode)
            ctx, ctx_status = ctx_cache[scan_date]
            regime_label = str(ctx.get("regime_label") or "")
            tag_info = tag_symbol(sym, sector, ctx)
            ctx_pts = context_score(tag_info, ctx) if panel_cfg.context_mode != ContextMode.OHLCV_ONLY else 50.0
            bench_cut = bench_by_scan[scan_date]
            money = compute_money_flow_metrics(daily)
            price = compute_price_structure_metrics(daily, bench_cut)
            price["distribution_risk_flag"] = bool(
                price.get("distribution_days_25") is not None and price.get("distribution_days_25", 0) >= 5
            )
            vin_flag, _ = vingroup_distortion_diagnosis(sym, money, price, VIN_DISTORTION_SYMBOLS)
            one_bar = detect_one_bar_spike(money, price)
            money_pts, _, mf_groups = score_money_flow(money)
            price_pts, _ = score_price_structure(price)
            risk_pen, _ = score_risk_penalty(
                money,
                price,
                vingroup_distortion=vin_flag,
                illiquid=not liq_ok,
                one_bar_spike=one_bar,
            )
            total = composite_score(ctx_pts, money_pts, price_pts, risk_pen)
            flat_rows.append(
                {
                    "scan_date": scan_date,
                    "ticker": sym,
                    "sector": sector,
                    "close": float(daily["close"].iloc[-1]),
                    "open": float(daily["open"].iloc[-1]),
                    "volume": float(daily["volume"].iloc[-1]),
                    "value": float(daily["value"].iloc[-1]) if "value" in daily.columns else None,
                    "adv20_vnd": liq.get("adv20_value"),
                    "adv50_vnd": liq.get("adv50_value"),
                    "is_liquid": bool(liq_ok),
                    "universe_full": bool(liq_ok and has_min_history),
                    "universe_ex_vin": bool(liq_ok and has_min_history and sym not in vin_excl),
                    "is_vin": is_vin,
                    "is_vpl": sym == "VPL",
                    "has_min_history": bool(has_min_history),
                    "context_mode": panel_cfg.context_mode.value,
                    "institutional_accumulation_score": round(total, 4),
                    "score_context": round(float(ctx_pts), 4),
                    "score_money_flow": round(float(money_pts), 4),
                    "score_mf_cmf": round(float(mf_groups.get("cmf", 0.0)), 4),
                    "score_mf_obv_pvt": round(float(mf_groups.get("obv_pvt", 0.0)), 4),
                    "score_mf_adl": round(float(mf_groups.get("adl", 0.0)), 4),
                    "score_mf_participation": round(float(mf_groups.get("participation", 0.0)), 4),
                    "score_price_structure": round(float(price_pts), 4),
                    "score_risk_penalty": round(float(risk_pen), 4),
                    "score_percentile": None,
                    "cmf20_daily": money.get("cmf20_daily"),
                    "cmf20_weekly": money.get("cmf20_weekly"),
                    "cmf_flow_conflict": bool(money.get("cmf_flow_conflict")),
                    "obv_slope_20": money.get("obv_slope_20"),
                    "obv_slope_50": money.get("obv_slope_50"),
                    "adl_slope_20": money.get("adl_slope_20"),
                    "adl_price_divergence_bearish": bool(money.get("adl_price_divergence_bearish")),
                    "pvt_slope_20": money.get("pvt_slope_20"),
                    "up_down_volume_ratio_20": money.get("up_down_volume_ratio_20"),
                    "hv_up_days_20": money.get("hv_up_days_20"),
                    "hv_down_days_20": money.get("hv_down_days_20"),
                    "turnover_accel_ratio_5d50d": money.get("turnover_accel_ratio_5d50d"),
                    "distribution_weeks_6": money.get("distribution_weeks_6"),
                    "rs_vs_vnindex_20": price.get("rs_vs_vnindex_20"),
                    "rs_vs_vnindex_60": price.get("rs_vs_vnindex_60"),
                    "rs_line_slope_20": price.get("rs_line_slope_20"),
                    "holds_ma50": bool(price.get("holds_ma50")),
                    "holds_ma20": bool(price.get("holds_ma20")),
                    "volatility_contraction_flag": bool(price.get("volatility_contraction_flag")),
                    "pullback_quality_flag": bool(price.get("pullback_quality_flag")),
                    "close_strength_10d": price.get("close_strength_10d"),
                    "extension_pct_above_ma20": price.get("extension_pct_above_ma20"),
                    "distribution_days_25": price.get("distribution_days_25"),
                    "distribution_risk_flag": bool(price.get("distribution_risk_flag")),
                    "vingroup_distortion_flag": bool(vin_flag),
                    "one_bar_spike_flag": bool(one_bar),
                    "caution_proxy": bool(vin_flag or price.get("distribution_risk_flag") or risk_pen >= 45),
                    "emerging_accumulation_candidate": False,
                    "has_fund_disclosure_tag": bool(tag_info.get("has_fund_disclosure_tag")),
                    "fund_context_bucket": tag_info.get("fund_context_bucket"),
                    "smart_money_tags": ",".join(tag_info.get("smart_money_tags") or []),
                    "regime_label": regime_label,
                    "regime_reconstructed": None,
                    "context_status": ctx_status,
                }
            )

    if not flat_rows:
        panel = pd.DataFrame()
    else:
        raw = pd.DataFrame(flat_rows)
        finalized: list[dict[str, Any]] = []
        for scan_date, dfd in raw.groupby("scan_date", sort=True):
            dt = pd.Timestamp(scan_date)
            regime_label = str(dfd["regime_label"].iloc[0]) if "regime_label" in dfd.columns else ""
            finalized.extend(
                _finalize_date_panel(dfd, regime_by_date=regime_by_date, dt=dt, regime_label=regime_label).to_dict(
                    orient="records"
                )
            )
        panel = pd.DataFrame(finalized)
    for col in ["market_cap_bucket"]:
        if col not in panel.columns:
            panel[col] = None
            blocked_columns.add(col)
    return panel, {"blocked_columns": sorted(blocked_columns)}
