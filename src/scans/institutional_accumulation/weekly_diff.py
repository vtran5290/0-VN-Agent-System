from __future__ import annotations



import json

from pathlib import Path

from typing import Any, Dict, Optional



import pandas as pd



from .operator_changes import format_operator_changes

from .operator_diagnostics import compute_bucket_diagnostics

from .operator_explain import explain_row


def _compact_changes(diff: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    formatted = format_operator_changes(diff or {})
    return {
        "note": formatted.get("note"),
        "summary_line": formatted.get("summary_line"),
        "has_meaningful_changes": formatted.get("has_meaningful_changes"),
        "new_tier12": formatted.get("new_tier12") or [],
        "dropped_tier12": formatted.get("dropped_tier12") or [],
        "tier_changes": formatted.get("tier_changes") or [],
        "biggest_score_gains": formatted.get("biggest_score_gains") or [],
        "biggest_score_losses": formatted.get("biggest_score_losses") or [],
    }





def diff_vs_previous(

    current_csv: Path,

    previous_csv: Optional[Path] = None,

    out_path: Optional[Path] = None,

) -> Dict[str, Any]:

    cur = pd.read_csv(current_csv)

    if cur.empty:

        return {"error": "empty_current"}

    scan_date = str(cur["scan_date"].iloc[0])

    if previous_csv is None or not previous_csv.is_file():

        parent = current_csv.parent

        dated = sorted(

            parent.glob("institutional_accumulation_2*.csv"),

            key=lambda p: p.name,

            reverse=True,

        )

        for p in dated:

            if p.name == current_csv.name or p.name == "institutional_accumulation_latest.csv":

                continue

            if any(
                x in p.name
                for x in ("_top80", "_before_v11", "rejected_", "operator", "emerging_accumulation")
            ):

                continue

            previous_csv = p

            break

    if previous_csv is None or not Path(previous_csv).is_file():

        payload = {"scan_date": scan_date, "previous_scan": None, "note": "no_previous_scan"}

        if out_path:

            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        return payload



    prev = pd.read_csv(previous_csv)

    cur_t = set(cur[cur["tier"].isin(["Tier 1", "Tier 2"])]["ticker"])

    prev_t = set(prev[prev["tier"].isin(["Tier 1", "Tier 2"])]["ticker"])

    merged = cur.merge(

        prev[["ticker", "institutional_accumulation_score", "tier"]],

        on="ticker",

        how="outer",

        suffixes=("_cur", "_prev"),

    )

    merged["score_delta"] = (

        merged["institutional_accumulation_score_cur"] - merged["institutional_accumulation_score_prev"]

    )



    tier_changes: list[dict[str, Any]] = []

    for _, r in merged.dropna(subset=["tier_cur", "tier_prev"]).iterrows():

        if r["tier_cur"] != r["tier_prev"]:

            tier_changes.append(

                {

                    "ticker": r["ticker"],

                    "tier_prev": r["tier_prev"],

                    "tier_cur": r["tier_cur"],

                    "score_delta": round(float(r["score_delta"]), 2) if pd.notna(r["score_delta"]) else None,

                }

            )



    MIN_DELTA = 0.05
    merged_scored = merged.dropna(subset=["score_delta"])
    merged_scored = merged_scored[merged_scored["score_delta"].abs() >= MIN_DELTA]

    payload = {

        "scan_date": scan_date,

        "previous_scan": str(previous_csv),

        "new_tier12": sorted(cur_t - prev_t),

        "dropped_tier12": sorted(prev_t - cur_t),

        "tier_changes": tier_changes[:20],

        "biggest_score_gains": (

            merged_scored.nlargest(10, "score_delta")[["ticker", "score_delta", "tier_cur", "tier_prev"]]

            .to_dict(orient="records")

        ),

        "biggest_score_losses": (

            merged_scored.nsmallest(10, "score_delta")[["ticker", "score_delta", "tier_cur", "tier_prev"]]

            .to_dict(orient="records")

        ),

    }

    if out_path:

        out_path.parent.mkdir(parents=True, exist_ok=True)

        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return payload





def _tier3_near_miss(df: pd.DataFrame, n: int = 5) -> list[dict[str, Any]]:

    t3 = df[df["tier"] == "Tier 3"].sort_values("institutional_accumulation_score", ascending=False)

    out: list[dict[str, Any]] = []

    for _, r in t3.head(n).iterrows():

        ex = explain_row(r)

        out.append(

            {

                "ticker": r["ticker"],

                "institutional_accumulation_score": float(r["institutional_accumulation_score"]),

                "score_money_flow": float(r.get("score_money_flow", 0)),

                "score_risk_penalty": float(r.get("score_risk_penalty", 0)),

                "fund_context_bucket": str(r.get("fund_context_bucket", "outside_fund_disclosure")),

                "primary_driver": ex["primary_driver"],

                "operator_note": ex["operator_note"],

            }

        )

    return out





def write_compact_for_workflow(

    df: pd.DataFrame,

    ctx: Dict[str, Any],

    scan_date: str,

    path: Path,

    *,

    near_miss_n: int = 5,

    diff: Optional[Dict[str, Any]] = None,

) -> Dict[str, Any]:

    """Council/weekly compact signal — no execution fields."""

    t1 = df[df["tier"] == "Tier 1"]["ticker"].tolist()

    t2 = df[df["tier"] == "Tier 2"]["ticker"].tolist()

    diag = compute_bucket_diagnostics(df)

    t2_focus = (

        df[df["tier"] == "Tier 2"]

        .sort_values("institutional_accumulation_score", ascending=False)[

            ["ticker", "institutional_accumulation_score", "score_money_flow", "fund_context_bucket"]

        ]

        .head(15)

        .to_dict(orient="records")

    )



    compact: Dict[str, Any] = {

        "layer": "institutional_accumulation_scan",

        "workflow_role": "research_prioritization_only",

        "scan_date": scan_date,

        "context_source": ctx.get("context_source"),

        "regime_label": ctx.get("regime_label"),

        "tier1_tickers": t1[:20],

        "tier2_tickers": t2[:30],

        "tier1_count": len(t1),

        "tier2_count": len(t2),

        "tier2_focus_list": t2_focus,

        "tier3_near_miss": _tier3_near_miss(df, near_miss_n),

        "tier3_near_miss_note": "Secondary list; Tier 2 focus is primary when Tier 2 exists.",

        "bucket_diagnostics": diag,

        "key_warnings": diag.get("warning_messages") or [],

        "changes_since_previous": _compact_changes(diff),

        "important_rejects_top": _important_rejects_compact(df, 6),

        "operator_summary_pointer": f"outputs/scans/institutional_accumulation_operator_summary_{scan_date}.html",
        "operator_summary_md_pointer": f"outputs/scans/institutional_accumulation_operator_summary_{scan_date}.md",
        "weekly_brief_html_pointer": f"outputs/scans/institutional_accumulation_weekly_brief_{scan_date}.html",
        "weekly_brief_md_pointer": f"outputs/scans/institutional_accumulation_weekly_brief_{scan_date}.md",

        "safety_note": "Ranking layer only; does not set final_action or orders.",

    }

    if len(t1) == 0 and len(t2) == 0:

        compact["fallback_note"] = (

            "No Tier 1/2 names; tier3_near_miss is primary near-miss list for research prioritization only."

        )

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(json.dumps(compact, indent=2, ensure_ascii=False), encoding="utf-8")

    return compact





def _important_rejects_compact(df: pd.DataFrame, n: int) -> list[dict[str, Any]]:

    from .operator_explain import FUND_BUCKETS



    sub = df[

        (df["tier"] == "Reject")

        & (df["fund_context_bucket"].isin(FUND_BUCKETS) | (df.get("in_consensus_core") == True))  # noqa: E712

    ].sort_values("institutional_accumulation_score", ascending=False)

    out = []

    for _, r in sub.head(n).iterrows():

        out.append(

            {

                "ticker": r["ticker"],

                "fund_context_bucket": r.get("fund_context_bucket"),

                "score_money_flow": float(r.get("score_money_flow", 0)),

                "reject_failure_reason": str(r.get("reject_failure_reason", "")),

            }

        )

    return out


