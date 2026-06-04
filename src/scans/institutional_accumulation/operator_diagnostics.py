"""Bucket mix and workflow warning diagnostics (research sanity-check only)."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .operator_lists import (
    CAUTION_RISK_THRESHOLD,
    caution_mask,
    caution_top,
    emerging_top,
    fund_backed_top,
    important_rejects,
    top_tier_df,
)
from .operator_sector import enrich_sectors_for_display, load_master_sector_fallback

VIN_WATCH_SYMBOLS = {"VIC", "VHM", "VRE", "VPL"}


def _pct(n: int, denom: int) -> float:
    return round(100.0 * n / denom, 1) if denom else 0.0


def _unknown_sector_stats(sub: pd.DataFrame, sector_col: str = "sector_display") -> dict[str, Any]:
    if sub.empty:
        return {"n": 0, "unknown": 0, "unknown_pct": 0.0, "tickers_unknown": []}
    col = sector_col if sector_col in sub.columns else "sector"
    unk = sub[col].fillna("Unknown") == "Unknown"
    n_unk = int(unk.sum())
    return {
        "n": len(sub),
        "unknown": n_unk,
        "unknown_pct": _pct(n_unk, len(sub)),
        "tickers_unknown": sub.loc[unk, "ticker"].astype(str).tolist()[:12],
    }


def compute_bucket_diagnostics(df: pd.DataFrame) -> dict[str, Any]:
    """
    Bucket mix uses explicit populations:
    - Primary denominator: all Tier 1–3 names in full scan.
    - Caution-proxy: same rule as section 4 display list (vin OR dist OR risk>=45).
    - Displayed-list stats: capped lists shown in operator summary.
    """
    df_disp = enrich_sectors_for_display(df, load_master_sector_fallback())
    top = top_tier_df(df_disp)
    n_top = len(top)
    n_all = len(df)

    fund_mask = top["has_fund_disclosure_tag"] == True  # noqa: E712
    emerg_mask = top["emerging_accumulation_candidate"] == True  # noqa: E712
    vin_flag_mask = top["vingroup_distortion_flag"] == True  # noqa: E712
    caution_proxy_mask = caution_mask(top)

    n_fund = int(fund_mask.sum())
    n_emerg = int(emerg_mask.sum())
    n_vin_flag = int(vin_flag_mask.sum())
    n_caution_proxy = int(caution_proxy_mask.sum())
    n_outside = int((top["fund_context_bucket"] == "outside_fund_disclosure").sum()) if n_top else 0

    vin_watch_top = top[top["ticker"].isin(VIN_WATCH_SYMBOLS)]
    n_vin_watch_caution = int(caution_proxy_mask[top["ticker"].isin(VIN_WATCH_SYMBOLS)].sum())

    tier_counts = df["tier"].value_counts().to_dict() if "tier" in df.columns else {}
    emerg_all = int((df["emerging_accumulation_candidate"] == True).sum())  # noqa: E712

    denom_label = f"All Tier 1–3 names in scan (n={n_top})"
    bucket_mix_pct: dict[str, float] = {}
    bucket_mix_counts: dict[str, int] = {}
    if n_top:
        bucket_mix_pct = {
            "fund_backed": _pct(n_fund, n_top),
            "emerging": _pct(n_emerg, n_top),
            "vin_distortion_flagged": _pct(n_vin_flag, n_top),
            "caution_proxy": _pct(n_caution_proxy, n_top),
            "outside_fund_disclosure": _pct(n_outside, n_top),
        }
        bucket_mix_counts = {
            "fund_backed": n_fund,
            "emerging": n_emerg,
            "vin_distortion_flagged": n_vin_flag,
            "caution_proxy": n_caution_proxy,
            "outside_fund_disclosure": n_outside,
        }

    displayed = {
        "fund_backed": _unknown_sector_stats(fund_backed_top(df_disp)),
        "emerging": _unknown_sector_stats(emerging_top(df_disp)),
        "caution": _unknown_sector_stats(caution_top(df_disp)),
        "important_rejects": _unknown_sector_stats(important_rejects(df_disp)),
    }
    all_displayed = pd.concat(
        [
            fund_backed_top(df_disp),
            emerging_top(df_disp),
            caution_top(df_disp),
            important_rejects(df_disp),
        ],
        ignore_index=True,
    ).drop_duplicates(subset=["ticker"])
    displayed_combined = _unknown_sector_stats(all_displayed)

    unknown_top = int((top["sector_display"].fillna("Unknown") == "Unknown").sum()) if n_top else 0
    enriched_n = int(df_disp.attrs.get("sector_enriched_from_master", 0)) if hasattr(df_disp, "attrs") else 0

    sector_conc = False
    dominant_sector = None
    if n_top >= 3:
        known = top[top["sector_display"] != "Unknown"]
        if len(known) >= 3:
            sc = known["sector_display"].value_counts()
            if not sc.empty and sc.iloc[0] >= max(3, len(known) * 0.45):
                sector_conc = True
                dominant_sector = str(sc.index[0])

    high_risk_emerg = 0
    if "emerging_accumulation_candidate" in df.columns:
        em = df[df["emerging_accumulation_candidate"] == True]  # noqa: E712
        if not em.empty and "score_risk_penalty" in em.columns:
            high_risk_emerg = int((em["score_risk_penalty"] > 25).sum())

    warnings = {
        "top_bucket_skew_warning": n_top > 0 and bucket_mix_pct.get("outside_fund_disclosure", 0) >= 70,
        "unknown_sector_warning": n_top > 0 and unknown_top >= max(3, n_top * 0.25),
        "unknown_sector_degrades_display_warning": displayed_combined["unknown"] >= 3,
        "too_few_fund_backed_warning": n_top > 0 and n_fund < 2,
        "too_many_high_risk_emerging_warning": emerg_all >= 8 and high_risk_emerg >= 3,
        "vin_distortion_elevated_warning": n_vin_flag >= 2,
        "vin_watch_caution_warning": n_vin_watch_caution >= 2 and n_vin_flag == 0,
        "no_tier1_warning": tier_counts.get("Tier 1", 0) == 0,
        "sector_concentration_warning": sector_conc,
    }

    return {
        "rows_scored": n_all,
        "tier_counts": {str(k): int(v) for k, v in tier_counts.items()},
        "emerging_count_total": emerg_all,
        "bucket_mix_denominator": denom_label,
        "bucket_mix_definition": {
            "fund_backed": "has_fund_disclosure_tag among Tier 1–3",
            "emerging": "emerging_accumulation_candidate among Tier 1–3",
            "vin_distortion_flagged": "vingroup_distortion_flag=True among Tier 1–3 (scan boolean)",
            "caution_proxy": (
                f"vin_flag OR distribution_risk_flag OR score_risk_penalty>={CAUTION_RISK_THRESHOLD} "
                "(matches section 4 list)"
            ),
            "outside_fund_disclosure": "fund_context_bucket=outside_fund_disclosure among Tier 1–3",
        },
        "count_top_tier": n_top,
        "count_top_tier_fund_backed": n_fund,
        "count_top_tier_emerging": n_emerg,
        "count_top_tier_vin_distortion_flag": n_vin_flag,
        "count_top_tier_caution_proxy": n_caution_proxy,
        "count_top_tier_outside_fund_disclosure": n_outside,
        "count_vin_watch_in_caution_proxy": n_vin_watch_caution,
        "bucket_mix_percentages_top_tier": bucket_mix_pct,
        "bucket_mix_counts_top_tier": bucket_mix_counts,
        "top_tier_outside_fund_dominated": n_top > 0 and n_outside > n_fund,
        "unknown_sector_count_top_tier": unknown_top,
        "unknown_sector_pct_top_tier": _pct(unknown_top, n_top),
        "sector_enriched_from_master_count": enriched_n,
        "dominant_sector_top_tier_known_only": dominant_sector,
        "displayed_list_unknown_sector": displayed,
        "displayed_lists_combined_unknown": displayed_combined,
        "high_risk_emerging_count": high_risk_emerg,
        "warnings": warnings,
        "warning_messages": _prioritized_warning_messages(
            warnings,
            bucket_mix_pct,
            bucket_mix_counts,
            tier_counts,
            dominant_sector,
            unknown_top,
            n_top,
            displayed_combined,
            n_vin_flag,
            n_vin_watch_caution,
            n_caution_proxy,
        ),
    }


def _prioritized_warning_messages(
    flags: dict[str, bool],
    mix: dict[str, float],
    counts: dict[str, int],
    tiers: dict[str, int],
    dominant_sector: str | None,
    unknown_top: int,
    n_top: int,
    displayed_combined: dict[str, Any],
    n_vin_flag: int,
    n_vin_watch_caution: int,
    n_caution_proxy: int,
) -> list[str]:
    """Ranked operator checklist: structural > data-quality > market-structure > caution."""
    ranked: list[tuple[int, str, str]] = []

    if flags.get("top_bucket_skew_warning"):
        ranked.append(
            (
                1,
                "structural",
                f"[P1 Structural] Top tier is {mix.get('outside_fund_disclosure', 0):.0f}% outside_fund_disclosure "
                f"({counts.get('outside_fund_disclosure', 0)}/{n_top}) — cross-check emerging vs April fund priors.",
            )
        )
    if flags.get("too_few_fund_backed_warning"):
        ranked.append(
            (
                1,
                "structural",
                f"[P1 Structural] Only {counts.get('fund_backed', 0)} fund-backed names in Tier 1–3 — "
                "Smart Money alignment weak this run.",
            )
        )

    if flags.get("unknown_sector_warning"):
        ranked.append(
            (
                2,
                "data_quality",
                f"[P2 Data] Unknown sector in Tier 1–3: {unknown_top}/{n_top} "
                f"({_pct(unknown_top, n_top):.0f}%) — "
                "sector concentration stats degraded.",
            )
        )
    if flags.get("unknown_sector_degrades_display_warning"):
        d = displayed_combined
        ranked.append(
            (
                2,
                "data_quality",
                f"[P2 Data] Unknown sector in displayed look-first lists: {d['unknown']}/{d['n']} — "
                "interpret sector/theme bullets cautiously.",
            )
        )

    if flags.get("no_tier1_warning"):
        ranked.append(
            (
                3,
                "market_structure",
                "[P3 Market] No Tier 1 names — narrow/fragile regime; prioritize Tier 2 focus + near-miss.",
            )
        )
    if flags.get("sector_concentration_warning") and dominant_sector:
        ranked.append(
            (
                3,
                "market_structure",
                f"[P3 Market] Known-sector concentration in top tier (dominant: {dominant_sector}).",
            )
        )

    if flags.get("vin_distortion_elevated_warning"):
        ranked.append(
            (
                4,
                "caution",
                f"[P4 Caution] {n_vin_flag} names with vingroup_distortion_flag in Tier 1–3 — cap-weight narrative risk.",
            )
        )
    if flags.get("vin_watch_caution_warning"):
        ranked.append(
            (
                4,
                "caution",
                f"[P4 Caution] VIN watch names (VIC/VHM/VRE/VPL) in caution-proxy list via elevated risk "
                f"({n_vin_watch_caution} names) but vin_distortion_flag=0 — see section 4, not vin_distortion_flagged %.",
            )
        )
    if flags.get("too_many_high_risk_emerging_warning"):
        ranked.append(
            (
                4,
                "caution",
                "[P4 Caution] Emerging universe has several elevated risk_penalty names — vet before prioritizing.",
            )
        )

    if n_caution_proxy > 0 and not flags.get("vin_distortion_elevated_warning"):
        ranked.append(
            (
                4,
                "caution",
                f"[P4 Caution] caution-proxy (section 4 rule): {n_caution_proxy}/{n_top} Tier 1–3 names "
                f"({mix.get('caution_proxy', 0):.0f}%) — includes high risk_penalty, not only vin_distortion_flag.",
            )
        )

    ranked.sort(key=lambda x: x[0])
    return [msg for _, _, msg in ranked]


def row_to_operator_card(row: pd.Series) -> dict[str, Any]:
    sector = str(row.get("sector_display") or row.get("sector") or "Unknown")
    return {
        "ticker": row["ticker"],
        "tier": row["tier"],
        "sector": sector,
        "institutional_accumulation_score": float(row["institutional_accumulation_score"]),
        "score_money_flow": float(row.get("score_money_flow", 0)),
        "score_risk_penalty": float(row.get("score_risk_penalty", 0)),
        "fund_context_bucket": str(row.get("fund_context_bucket", "")),
        "emerging_accumulation_candidate": bool(row.get("emerging_accumulation_candidate")),
        "vingroup_distortion_flag": bool(row.get("vingroup_distortion_flag")),
        "primary_driver": str(row.get("primary_driver", "")),
        "secondary_driver": str(row.get("secondary_driver", "")),
        "main_risk": str(row.get("main_risk", "")),
        "operator_note": str(row.get("operator_note", "")),
        # Evidence fields — present when attach_backtest_evidence_fields has been called
        "score_decile": int(row.get("score_decile", 0) or 0),
        "evidence_label": str(row.get("evidence_label", "INCONCLUSIVE_NOT_BUY_SIGNAL")),
        "risk_clean_flag": bool(row.get("risk_clean_flag", True)),
        "distribution_risk_clean": bool(row.get("distribution_risk_clean", True)),
        "top_decile_heat_risk": bool(row.get("top_decile_heat_risk", False)),
        "controlled_accumulation_flag": bool(row.get("controlled_accumulation_flag", False)),
        "risk_clean_research_candidate": bool(row.get("risk_clean_research_candidate", False)),
        "dashboard_priority_bucket": str(row.get("dashboard_priority_bucket", "standard")),
        "dashboard_operator_note": str(row.get("dashboard_operator_note", "")),
        "research_only_flag": str(row.get("research_only_flag", "RESEARCH_ONLY_NOT_PRODUCTION")),
        "distribution_risk_flag": bool(row.get("distribution_risk_flag", False)),
        "extension_pct_above_ma20": float(row.get("extension_pct_above_ma20", 0) or 0),
        "distribution_days_25": float(row.get("distribution_days_25", 0) or 0),
        "turnover_accel_ratio_5d50d": float(row.get("turnover_accel_ratio_5d50d", 0) or 0),
    }


def compute_evidence_lists(df: pd.DataFrame) -> dict[str, Any]:
    """Compute risk-clean queue, heat warnings, and distribution-avoidance lists from evidence fields."""
    from .operator_explain import EVIDENCE_LABEL_HEAT, attach_backtest_evidence_fields

    if "dashboard_priority_bucket" not in df.columns:
        df = attach_backtest_evidence_fields(df)

    top = top_tier_df(df)

    risk_clean_mask = (
        (~top["distribution_risk_flag"].fillna(False).astype(bool))
        & (~top["top_decile_heat_risk"].fillna(False).astype(bool))
    )
    risk_clean = top[risk_clean_mask].copy()
    if not risk_clean.empty:
        rc_dec = pd.to_numeric(risk_clean["score_decile"], errors="coerce").fillna(0).astype(int)
        risk_clean["_decile_pref"] = rc_dec.isin([5, 6, 7, 8]).astype(int)
        risk_clean = risk_clean.sort_values(
            ["_decile_pref", "institutional_accumulation_score"],
            ascending=[False, False],
        ).head(12)

    heat_mask = (
        (pd.to_numeric(df.get("score_decile"), errors="coerce").fillna(0).astype(int) >= 9)
        | (df.get("evidence_label", pd.Series("", index=df.index)).astype(str) == EVIDENCE_LABEL_HEAT)
    )
    heat = df[heat_mask.fillna(False)].sort_values(
        "institutional_accumulation_score", ascending=False
    ).head(10)

    dist_flag_mask = top["distribution_risk_flag"].fillna(False).astype(bool)
    dist_avoid = top[dist_flag_mask].sort_values(
        "institutional_accumulation_score", ascending=False
    ).head(10)

    return {
        "risk_clean_queue": [row_to_operator_card(risk_clean.loc[i]) for i in risk_clean.index],
        "heat_warning_names": [row_to_operator_card(heat.loc[i]) for i in heat.index],
        "dist_avoid_names": [row_to_operator_card(dist_avoid.loc[i]) for i in dist_avoid.index],
        "n_risk_clean": len(risk_clean),
        "n_heat_warnings": len(heat),
        "n_dist_avoid": len(dist_avoid),
    }
