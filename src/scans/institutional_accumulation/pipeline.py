from __future__ import annotations

import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from src.data_loader import load_ohlcv_csv

from .config import (
    COMPACT_TIER3_NEAR_MISS,
    ETF_EXCLUSION_SECTORS,
    ETF_EXCLUSION_SYMBOLS,
    REPO,
    SECTOR_MAP_PATH,
    ScanConfig,
    VIN_DISTORTION_SYMBOLS,
)
from .context import context_score, load_sector_map, load_smart_money_context, tag_symbol
from .filters import (
    detect_scan_date,
    discover_symbols,
    is_etf_or_open_fund,
    liquidity_metrics,
    load_symbol_ohlcv,
    passes_liquidity,
    read_watchlist,
    resolve_benchmark_path,
)
from .indicators import (
    compute_money_flow_metrics,
    compute_price_structure_metrics,
    slice_through,
    vingroup_distortion_diagnosis,
)
from .operator_diagnostics import compute_bucket_diagnostics
from .scoring import (
    assign_tier,
    build_notes,
    composite_score,
    detect_one_bar_spike,
    score_money_flow,
    score_price_structure,
    score_risk_penalty,
)


def run_institutional_accumulation_scan(cfg: ScanConfig) -> Dict[str, Any]:
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    bench_path = resolve_benchmark_path(cfg.benchmark_dir, cfg.benchmark_ticker)

    scan_date = detect_scan_date(bench_path, cfg.scan_date)
    month_ref = cfg.smart_money_month or scan_date[:7]
    ctx = load_smart_money_context(month_ref)
    regime_label = str(ctx.get("regime_label") or "")
    sector_map = load_sector_map(SECTOR_MAP_PATH)

    bench_full = load_ohlcv_csv(bench_path)
    bench = slice_through(bench_full, scan_date)

    watchlist = None
    if cfg.watchlist_path:
        watchlist = read_watchlist(cfg.watchlist_path)
    symbols = cfg.symbols or discover_symbols(cfg.stocks_dir, watchlist)
    universe_policy = _build_universe_policy(cfg, ctx, len(symbols))

    staged: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    skipped = 0
    etf_excluded = 0

    for sym in symbols:
        raw = load_symbol_ohlcv(cfg.stocks_dir, sym)
        if raw is None or raw.empty:
            skipped += 1
            continue
        daily = slice_through(raw, scan_date)
        if daily.empty:
            skipped += 1
            continue

        liq = liquidity_metrics(daily)
        liq_ok, liq_reason = passes_liquidity(
            liq,
            min_history=cfg.min_history_days,
            min_adv20=cfg.min_adv20_vnd,
            min_adv50=cfg.min_adv50_vnd,
        )

        sector = sector_map.get(sym, "Unknown")
        if is_etf_or_open_fund(sym, sector):
            etf_excluded += 1
            continue
        tag_info = tag_symbol(sym, sector, ctx)
        ctx_pts = context_score(tag_info, ctx)

        money = compute_money_flow_metrics(daily)
        price = compute_price_structure_metrics(daily, bench)
        price["distribution_risk_flag"] = bool(
            price.get("distribution_days_25") is not None and price["distribution_days_25"] >= 5
        )

        vin_flag, vin_diag = vingroup_distortion_diagnosis(sym, money, price, VIN_DISTORTION_SYMBOLS)
        one_bar = detect_one_bar_spike(money, price)

        money_pts, money_reasons, mf_groups = score_money_flow(money)
        price_pts, price_reasons = score_price_structure(price)
        risk_pen, risk_reasons = score_risk_penalty(
            money,
            price,
            vingroup_distortion=vin_flag,
            illiquid=not liq_ok,
            one_bar_spike=one_bar,
        )

        total = composite_score(ctx_pts, money_pts, price_pts, risk_pen)

        staged.append(
            {
                "ticker": sym,
                "scan_date": scan_date,
                "institutional_accumulation_score": round(total, 2),
                "tier": "pending",
                "score_context": round(ctx_pts, 2),
                "score_money_flow": round(money_pts, 2),
                "score_mf_cmf": round(mf_groups.get("cmf", 0), 2),
                "score_mf_obv_pvt": round(mf_groups.get("obv_pvt", 0), 2),
                "score_mf_adl": round(mf_groups.get("adl", 0), 2),
                "score_mf_participation": round(mf_groups.get("participation", 0), 2),
                "score_price_structure": round(price_pts, 2),
                "score_risk_penalty": round(risk_pen, 2),
                "score_percentile": None,
                "smart_money_tag": tag_info.get("smart_money_tag"),
                "smart_money_tags": ",".join(tag_info.get("smart_money_tags") or []),
                "fund_context_bucket": tag_info.get("fund_context_bucket"),
                "has_fund_disclosure_tag": tag_info.get("has_fund_disclosure_tag"),
                "emerging_accumulation_candidate": False,
                "in_consensus_core": tag_info.get("in_consensus_core"),
                "in_commentary_mention": tag_info.get("in_commentary_mention"),
                "sector": sector,
                "adv20_value": liq.get("adv20_value"),
                "adv50_value": liq.get("adv50_value"),
                "price_unit_mode": liq.get("price_unit_mode"),
                "value_scale_factor": liq.get("value_scale_factor"),
                "unit_warning": liq.get("unit_warning"),
                "liquidity_ok": liq_ok,
                "liquidity_reject_reason": None if liq_ok else liq_reason,
                "cmf20_daily": money.get("cmf20_daily"),
                "cmf20_weekly": money.get("cmf20_weekly"),
                "obv_slope_20": money.get("obv_slope_20"),
                "obv_slope_50": money.get("obv_slope_50"),
                "adl_slope_20": money.get("adl_slope_20"),
                "pvt_slope_20": money.get("pvt_slope_20"),
                "up_down_volume_ratio_20": money.get("up_down_volume_ratio_20"),
                "turnover_accel_ratio_5d50d": money.get("turnover_accel_ratio_5d50d"),
                "distribution_weeks_6": money.get("distribution_weeks_6"),
                "rs_vs_vnindex_20": price.get("rs_vs_vnindex_20"),
                "rs_vs_vnindex_60": price.get("rs_vs_vnindex_60"),
                "volatility_contraction_flag": price.get("volatility_contraction_flag"),
                "pullback_quality_flag": price.get("pullback_quality_flag"),
                "distribution_risk_flag": price.get("distribution_risk_flag"),
                "vingroup_distortion_flag": vin_flag,
                "vingroup_distortion_diagnosis": vin_diag,
                "cmf_flow_conflict": money.get("cmf_flow_conflict"),
                "_money_reasons": money_reasons,
                "_price_reasons": price_reasons,
                "_risk_reasons": risk_reasons,
                "_ctx_pts": ctx_pts,
            }
        )

    df = pd.DataFrame(staged)
    if df.empty:
        meta = _build_meta(scan_date, ctx, cfg, 0, skipped, {})
        return {"scan_date": scan_date, "rows": 0, "outputs": {}, "meta": meta}

    liquid = df[df["liquidity_ok"] == True]  # noqa: E712
    if not liquid.empty:
        df.loc[liquid.index, "score_percentile"] = (
            liquid["institutional_accumulation_score"].rank(pct=True).values
        )

    tiers: List[str] = []
    notes_list: List[str] = []
    for _, row in df.iterrows():
        tier = assign_tier(
            float(row["institutional_accumulation_score"]),
            float(row["score_money_flow"]),
            float(row["score_risk_penalty"]),
            liquidity_ok=bool(row["liquidity_ok"]),
            regime_label=regime_label,
            score_percentile=float(row["score_percentile"]) if pd.notna(row.get("score_percentile")) else None,
            in_consensus_core=bool(row.get("in_consensus_core")),
        )
        tiers.append(tier)
        notes_list.append(
            build_notes(
                tier,
                [f"context={row['_ctx_pts']:.0f}"],
                list(row["_money_reasons"]),
                list(row["_price_reasons"]),
                list(row["_risk_reasons"]),
            )
        )
    df["tier"] = tiers
    df["notes"] = notes_list
    df = df.drop(columns=[c for c in df.columns if c.startswith("_")])

    emerg_mask = (
        df["tier"].isin(["Tier 1", "Tier 2", "Tier 3"])
        & (df["has_fund_disclosure_tag"] == False)  # noqa: E712
        & (df["liquidity_ok"] == True)  # noqa: E712
        & (df["score_money_flow"] >= cfg.emerging_min_money_flow)
        & (df["score_risk_penalty"] <= cfg.emerging_max_risk_penalty)
    )
    df.loc[emerg_mask, "emerging_accumulation_candidate"] = True

    from .operator_explain import attach_operator_explain

    df = attach_operator_explain(df)

    for _, row in df.iterrows():
        if row["tier"] == "Reject" and row["liquidity_ok"] and row["institutional_accumulation_score"] >= cfg.near_miss_min_score:
            r = row.to_dict()
            r["reject_reason"] = row.get("notes", "")
            rejected.append(r)

    tier_order = {"Tier 1": 0, "Tier 2": 1, "Tier 3": 2, "Reject": 3}
    df["_tier_ord"] = df["tier"].map(tier_order).fillna(9)
    df = df.sort_values(["_tier_ord", "institutional_accumulation_score"], ascending=[True, False])
    df = df.drop(columns=["_tier_ord"]).reset_index(drop=True)

    sector_summary = _sector_summary(df)
    validation = _quick_validation(df, scan_date, ctx)

    stem = f"institutional_accumulation_{scan_date}"
    csv_path = cfg.output_dir / f"{stem}.csv"
    json_path = cfg.output_dir / f"{stem}.json"
    md_path = cfg.output_dir / f"{stem}.md"
    rej_path = cfg.output_dir / f"institutional_accumulation_rejected_{scan_date}.csv"
    latest_path = cfg.output_dir / "institutional_accumulation_latest.csv"

    df.to_csv(csv_path, index=False)
    top80_path = cfg.output_dir / f"{stem}_top80.csv"
    df.head(cfg.top_n_export).to_csv(top80_path, index=False)
    emerg_path = cfg.output_dir / f"emerging_accumulation_{scan_date}.csv"
    emerg_df = df[df["emerging_accumulation_candidate"] == True].sort_values(  # noqa: E712
        "institutional_accumulation_score", ascending=False
    )
    emerg_df.to_csv(emerg_path, index=False)

    if cfg.include_rejected_near_miss and rejected:
        pd.DataFrame(rejected).sort_values("institutional_accumulation_score", ascending=False).head(
            cfg.max_rejected_export
        ).to_csv(rej_path, index=False)
    else:
        rej_path = None

    payload = {
        "scan_type": "institutional_accumulation",
        "workflow_role": "research_ranking_only",
        "methodology_version": "v1.1",
        "scan_date": scan_date,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "context": {
            "source": ctx.get("context_source"),
            "month": ctx.get("month") or month_ref,
            "regime_label": regime_label,
            "risk_flags": ctx.get("risk_flags"),
            "universe_policy": universe_policy,
        },
        "emerging_accumulation": _emerging_summary(df),
        "operator_diagnostics": compute_bucket_diagnostics(df),
        "config": {
            "min_adv20_vnd": cfg.min_adv20_vnd,
            "min_adv50_vnd": cfg.min_adv50_vnd,
            "min_history_days": cfg.min_history_days,
            "benchmark": cfg.benchmark_ticker,
            "data_source": "local_csv:data/stocks",
            "method": "OHLCV-derived; no lookahead slice",
            "price_unit_convention": "thousand_vnd_scaled_to_vnd_when_median_close<500",
            "emerging_min_money_flow": cfg.emerging_min_money_flow,
            "emerging_max_risk_penalty": cfg.emerging_max_risk_penalty,
            "etf_exclusion_sectors": sorted(ETF_EXCLUSION_SECTORS),
            "etf_exclusion_symbols": sorted(ETF_EXCLUSION_SYMBOLS),
        },
        "sector_summary": sector_summary,
        "validation": validation,
        "candidates": df.to_dict(orient="records"),
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    shutil.copy2(csv_path, latest_path)

    from .operator_summary import write_all_operator_outputs
    from .report import write_markdown_report
    from .weekly_diff import diff_vs_previous, write_compact_for_workflow

    write_markdown_report(md_path, df, payload, rejected)
    diff_path = cfg.output_dir / f"institutional_accumulation_diff_{scan_date}.json"
    diff_payload = diff_vs_previous(csv_path, out_path=diff_path)

    artifact_paths = write_all_operator_outputs(
        output_dir=cfg.output_dir,
        scan_date=scan_date,
        df=df,
        ctx=ctx,
        diff_payload=diff_payload,
        scan_json=payload,
        preserve_weekly_brief_md=True,
    )
    op_sum_json_path = Path(artifact_paths["operator_summary_json"])
    op_sum_md_path = Path(artifact_paths["operator_summary_md"])
    op_sum_html_path = Path(artifact_paths["operator_summary_html"])

    compact_path = REPO / "data" / "decision" / "institutional_accumulation_compact.json"
    compact_scans_copy = cfg.output_dir / f"institutional_accumulation_compact_{scan_date}.json"
    write_compact_for_workflow(
        df, ctx, scan_date, compact_path, near_miss_n=COMPACT_TIER3_NEAR_MISS, diff=diff_payload
    )
    write_compact_for_workflow(
        df, ctx, scan_date, compact_scans_copy, near_miss_n=COMPACT_TIER3_NEAR_MISS, diff=diff_payload
    )

    meta = _build_meta(scan_date, ctx, cfg, len(df), skipped, sector_summary)
    meta["n_etf_excluded"] = etf_excluded
    return {
        "scan_date": scan_date,
        "rows": len(df),
        "outputs": {
            "csv": str(csv_path),
            "top80_csv": str(top80_path),
            "emerging_csv": str(emerg_path),
            "json": str(json_path),
            "md": str(md_path),
            "latest_csv": str(latest_path),
            "rejected_csv": str(rej_path) if rej_path else None,
            "compact_json": str(compact_path),
            "compact_json_dated": str(compact_scans_copy),
            "operator_summary_md": str(op_sum_md_path),
            "operator_summary_json": str(op_sum_json_path),
            "operator_summary_html": str(op_sum_html_path),
            "operator_summary_html_latest": str(
                cfg.output_dir / "institutional_accumulation_operator_summary_latest.html"
            ),
            "weekly_brief_md": artifact_paths.get("weekly_brief_md"),
            "weekly_brief_html": artifact_paths.get("weekly_brief_html"),
            "weekly_diff_json": str(diff_path),
        },
        "meta": meta,
        "validation": validation,
    }


def _build_universe_policy(cfg: ScanConfig, ctx: Dict[str, Any], n_symbols: int) -> Dict[str, Any]:
    base = dict(ctx.get("universe_policy") or {})
    if cfg.symbols:
        mode = "override_symbols"
        note = f"Explicit symbol list ({n_symbols} tickers); not full market."
    elif cfg.watchlist_path:
        mode = "override_watchlist"
        note = f"Watchlist file ({n_symbols} tickers); not full market."
    else:
        mode = "full_liquid_universe"
        note = (
            "All symbols in data/stocks passing ADV/history gates; "
            "fund lists are Smart Money context priors only."
        )
    return {
        "mode": mode,
        "note": note,
        "n_symbols_scored": n_symbols,
        "stocks_dir": str(cfg.stocks_dir),
        **{k: v for k, v in base.items() if k not in ("mode", "note")},
    }


def _emerging_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """High-flow names with tier 1-3 but no fund disclosure tag (possible non-reported accumulation)."""
    sub = df[df["emerging_accumulation_candidate"] == True].copy()  # noqa: E712
    if sub.empty:
        return {"count": 0, "top": []}
    sub = sub.sort_values("institutional_accumulation_score", ascending=False)
    top = sub.head(25)[
        [
            "ticker",
            "tier",
            "institutional_accumulation_score",
            "score_money_flow",
            "score_risk_penalty",
            "sector",
            "fund_context_bucket",
        ]
    ].to_dict(orient="records")
    return {"count": int(len(sub)), "top": top}


def _sector_summary(df: pd.DataFrame) -> Dict[str, Any]:
    top = df[df["tier"].isin(["Tier 1", "Tier 2"])]
    by_sector: Dict[str, List[float]] = defaultdict(list)
    for _, r in df.iterrows():
        by_sector[str(r.get("sector") or "Unknown")].append(float(r["institutional_accumulation_score"]))
    counts = top.groupby("sector").size().to_dict() if not top.empty else {}
    avgs = {k: round(float(sum(v) / len(v)), 2) for k, v in by_sector.items() if v}
    sectors_sorted = sorted(counts.items(), key=lambda x: -x[1])
    concentration_warning = False
    if sectors_sorted and sectors_sorted[0][1] >= max(3, len(top) * 0.5):
        concentration_warning = True
    return {
        "tier12_count_by_sector": counts,
        "avg_score_by_sector": avgs,
        "concentration_warning": concentration_warning,
        "dominant_sector": sectors_sorted[0][0] if sectors_sorted else None,
    }


def _quick_validation(df: pd.DataFrame, scan_date: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    from .validation import (
        confirm_no_execution_fields,
        money_flow_correlation_check,
        run_spot_checks,
        score_component_balance,
        unit_handling_check,
    )

    payload_stub = {
        "workflow_role": "research_ranking_only",
        "layer": "institutional_accumulation_scan",
    }
    exec_ok, exec_issues = confirm_no_execution_fields(payload_stub)

    return {
        "spot_checks": run_spot_checks(df, scan_date),
        "component_balance": score_component_balance(df),
        "money_flow_redundancy": money_flow_correlation_check(df),
        "unit_handling": unit_handling_check(df),
        "execution_leakage_check": {"ok": exec_ok, "issues": exec_issues},
    }


def _build_meta(
    scan_date: str,
    ctx: Dict[str, Any],
    cfg: ScanConfig,
    n_rows: int,
    skipped: int,
    sector_summary: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "scan_date": scan_date,
        "n_scored": n_rows,
        "n_skipped_no_data": skipped,
        "context_source": ctx.get("context_source"),
        "regime_label": ctx.get("regime_label"),
        "sector_summary": sector_summary,
    }
