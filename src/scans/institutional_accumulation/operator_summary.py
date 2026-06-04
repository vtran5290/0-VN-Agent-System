"""Operator-facing summary MD + JSON (research prioritization only)."""

from __future__ import annotations



import json

from pathlib import Path

from typing import Any, Dict, List



import pandas as pd



from .operator_changes import format_operator_changes

from .operator_diagnostics import compute_bucket_diagnostics, compute_evidence_lists, row_to_operator_card

from .operator_explain import attach_backtest_evidence_fields, load_dashboard_evidence_config

from .operator_lists import (

    caution_top,

    emerging_top,

    fund_backed_top,

    important_rejects,

)

from .operator_sector import enrich_sectors_for_display, load_master_sector_fallback





def _tier2_focus(df: pd.DataFrame) -> List[dict[str, Any]]:

    t2 = df[df["tier"] == "Tier 2"].sort_values("institutional_accumulation_score", ascending=False)

    return [row_to_operator_card(t2.loc[i]) for i in t2.head(15).index]





def build_operator_summary_payload(

    df: pd.DataFrame,

    ctx: Dict[str, Any],

    scan_date: str,

    diff: Dict[str, Any],

    *,

    methodology_version: str = "v1.1",

) -> Dict[str, Any]:

    df_disp = enrich_sectors_for_display(df, load_master_sector_fallback())

    df_ev = attach_backtest_evidence_fields(df_disp)

    diag = compute_bucket_diagnostics(df)

    changes = format_operator_changes(diff)

    evidence = compute_evidence_lists(df_ev)

    return {

        "scan_date": scan_date,

        "workflow_role": "research_prioritization_only",

        "workflow_note": {

            "for": "Human research / allocator monitoring after Smart Money monthly + full scan.",

            "not_for": "Orders, final_action, sizing, OMS, or execution — use separate execution workflow.",

        },

        "methodology_version": methodology_version,

        "context_source": ctx.get("context_source"),

        "smart_money_month": ctx.get("month") or "2026-04",

        "regime_label": ctx.get("regime_label"),

        "bucket_diagnostics": diag,

        "tier2_focus_list": _tier2_focus(df_ev),

        "look_first": {

            "fund_backed_candidates": [

                row_to_operator_card(fund_backed_top(df_ev).loc[i])

                for i in fund_backed_top(df_ev).index

            ],

            "emerging_candidates": [

                row_to_operator_card(emerging_top(df_ev).loc[i]) for i in emerging_top(df_ev).index

            ],

            "important_rejects": [

                {

                    **row_to_operator_card(important_rejects(df_ev).loc[i]),

                    "reject_failure_reason": str(

                        important_rejects(df_ev).loc[i].get("reject_failure_reason", "")

                    ),

                }

                for i in important_rejects(df_ev).index

            ],

            "distortion_caution": [

                row_to_operator_card(caution_top(df_ev).loc[i]) for i in caution_top(df_ev).index

            ],

        },

        "changes_since_previous": changes,

        "key_warnings": diag.get("warning_messages") or [],

        "evidence_lists": evidence,
        "evidence_config": load_dashboard_evidence_config(),
        "evidence_version": "full_history_v0.2",

    }





def _cards_md(title: str, cards: List[dict[str, Any]], *, extra_cols: List[str] | None = None) -> List[str]:

    lines = [f"### {title}", ""]

    if not cards:

        lines.append("_None this run._")

        lines.append("")

        return lines

    for c in cards:

        sector = c.get("sector") or "Unknown"

        lines.append(

            f"- **{c['ticker']}** ({c['tier']}, score {c['institutional_accumulation_score']:.1f}, "

            f"MF {c['score_money_flow']:.0f}, risk {c['score_risk_penalty']:.0f}, sector `{sector}`) — "

            f"`{c['fund_context_bucket']}`"

        )

        lines.append(f"  - **Why:** {c.get('primary_driver', '')}")

        if c.get("secondary_driver"):

            lines.append(f"  - **Also:** {c['secondary_driver']}")

        lines.append(f"  - **Risk:** {c.get('main_risk', '')}")

        lines.append(f"  - **Note:** {c.get('operator_note', '')}")

        if extra_cols and c.get("reject_failure_reason"):

            lines.append(f"  - **Failed because:** {c['reject_failure_reason']}")

    lines.append("")

    return lines





def _bucket_mix_md(diag: dict[str, Any]) -> List[str]:

    lines = ["## C. Bucket mix", ""]

    denom = diag.get("bucket_mix_denominator") or "Tier 1–3"

    lines.append(f"**Denominator:** {denom}")

    lines.append("")

    defs = diag.get("bucket_mix_definition") or {}

    counts = diag.get("bucket_mix_counts_top_tier") or {}

    mix = diag.get("bucket_mix_percentages_top_tier") or {}

    if not mix:

        lines.append("_No top-tier names._")

        lines.append("")

        return lines

    lines.append("| Bucket | Count | % | Definition |")

    lines.append("| --- | ---: | ---: | --- |")

    for key in ("fund_backed", "emerging", "vin_distortion_flagged", "caution_proxy", "outside_fund_disclosure"):

        lines.append(

            f"| {key} | {counts.get(key, 0)} | {mix.get(key, 0)}% | {defs.get(key, '')} |"

        )

    n_vin_watch = diag.get("count_vin_watch_in_caution_proxy")

    if n_vin_watch:

        lines.append("")

        lines.append(

            f"_VIN watch (VIC/VHM/VRE/VPL) in **caution-proxy** list: {n_vin_watch} — "

            "may appear in section 4 without `vin_distortion_flagged` % moving._"

        )

    lines.append("")

    disp = diag.get("displayed_lists_combined_unknown") or {}

    if disp.get("n"):

        lines.append(

            f"**Unknown sector in displayed look-first lists:** {disp.get('unknown')}/{disp.get('n')} "

            f"({disp.get('unknown_pct', 0)}%)"

        )

        enriched = diag.get("sector_enriched_from_master_count", 0)

        if enriched:

            lines.append(f"_({enriched} names enriched from `data/master/sector_map.csv` for display only.)_")

    lines.append("")

    return lines





def _changes_md(ch: dict[str, Any]) -> List[str]:

    lines = ["## D. Changes since previous scan", ""]

    if ch.get("note") == "no_previous_scan":

        lines.append(f"_{ch.get('summary_line', 'No prior scan.')}_")

        lines.append("")

        return lines

    prev_d = ch.get("previous_scan_date")

    if prev_d:

        lines.append(f"_Previous scan date: {prev_d}_")

        lines.append("")

    if not ch.get("has_meaningful_changes"):

        lines.append(f"_{ch.get('summary_line')}_")

        lines.append("")

        return lines

    lines.append(f"- **New Tier 1–2:** {', '.join(ch.get('new_tier12') or []) or '—'}")

    lines.append(f"- **Dropped Tier 1–2:** {', '.join(ch.get('dropped_tier12') or []) or '—'}")

    for tc in ch.get("tier_changes") or []:

        d = tc.get("score_delta")

        d_s = f", Δ{d:+.1f}" if d is not None else ""

        lines.append(

            f"- **Tier change:** {tc.get('ticker')} {tc.get('tier_prev')} → {tc.get('tier_cur')}{d_s}"

        )

    for g in ch.get("biggest_score_gains") or []:

        lines.append(

            f"- **Score up:** {g.get('ticker')} Δ{g.get('score_delta', 0):+.1f} → {g.get('tier_cur')}"

        )

    for l in ch.get("biggest_score_losses") or []:

        lines.append(

            f"- **Score down:** {l.get('ticker')} Δ{l.get('score_delta', 0):+.1f} → {l.get('tier_cur')}"

        )

    lines.append("")

    return lines





def write_operator_summary_md(path: Path, payload: Dict[str, Any]) -> None:

    diag = payload.get("bucket_diagnostics") or {}

    tiers = diag.get("tier_counts") or {}

    lines = [

        "# Institutional Accumulation — Operator Summary",

        "",

        f"**Scan date:** {payload.get('scan_date')}  ",

        f"**Role:** {payload.get('workflow_role')}  ",

        f"**Regime:** `{payload.get('regime_label')}` | **Context:** {payload.get('context_source')}",

        "",

        "## What this file is / is not",

        "",

        f"- **For:** {payload['workflow_note']['for']}",

        f"- **Not for:** {payload['workflow_note']['not_for']}",

        "",

        "## A. Regime & scan snapshot",

        "",

        f"| Metric | Value |",

        f"| --- | --- |",

        f"| Rows scored | {diag.get('rows_scored')} |",

        f"| Tier 1 | {tiers.get('Tier 1', 0)} |",

        f"| Tier 2 | {tiers.get('Tier 2', 0)} |",

        f"| Tier 3 | {tiers.get('Tier 3', 0)} |",

        f"| Reject | {tiers.get('Reject', 0)} |",

        f"| Emerging (universe) | {diag.get('emerging_count_total')} |",

        f"| Top-tier fund-backed | {diag.get('count_top_tier_fund_backed')} |",

        f"| Unknown sector (Tier 1–3) | {diag.get('unknown_sector_count_top_tier')}/{diag.get('count_top_tier')} |",

        "",

        "## B. What to look at first",

        "",

    ]

    look = payload.get("look_first") or {}

    lines.extend(_cards_md("1. Top fund-backed candidates (Tier 1–3)", look.get("fund_backed_candidates") or []))

    lines.extend(_cards_md("2. Top emerging candidates (no fund tag)", look.get("emerging_candidates") or []))

    lines.extend(

        _cards_md(

            "3. Important rejects (fund-linked, flow failed)",

            look.get("important_rejects") or [],

            extra_cols=["reject_failure_reason"],

        )

    )

    lines.extend(

        _cards_md(

            "4. Elevated risk / distortion / distribution (Tier 1–3; matches caution-proxy %)",

            look.get("distortion_caution") or [],

        )

    )



    lines.extend(_bucket_mix_md(diag))

    lines.extend(_changes_md(payload.get("changes_since_previous") or {}))



    lines.extend(["## E. Workflow warnings (priority order)", ""])

    for w in payload.get("key_warnings") or []:

        lines.append(f"- {w}")

    if not payload.get("key_warnings"):

        lines.append("- No elevated workflow warnings.")

    lines.extend(

        [

            "",

            "## File map",

            "",

            "| File | Role |",

            "| --- | --- |",

            "| `institutional_accumulation_{date}.csv` | Full ranked universe |",

            "| `institutional_accumulation_{date}.json` | Machine payload |",

            "| `institutional_accumulation_{date}.md` | Detailed methodology report |",

            "| `institutional_accumulation_operator_summary_{date}.html` | **Browser view** — start here |",

            "| `institutional_accumulation_operator_summary_{date}.md` | Same summary, markdown |",

            "| `institutional_accumulation_operator_summary_{date}.json` | Same summary, JSON |",

            "| `data/decision/institutional_accumulation_compact.json` | Weekly/council compact |",

            "| `emerging_accumulation_{date}.csv` | Emerging-only list |",

            "| `institutional_accumulation_diff_{date}.json` | WoW tier/score diff |",

            "",

            "---",

            "*End operator summary.*",

        ]

    )

    path.write_text("\n".join(lines), encoding="utf-8")





def write_operator_summary_json(path: Path, payload: Dict[str, Any]) -> None:

    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_all_operator_outputs(
    *,
    output_dir: Path,
    scan_date: str,
    df: pd.DataFrame,
    ctx: Dict[str, Any],
    diff_payload: Dict[str, Any],
    scan_json: Dict[str, Any],
    preserve_weekly_brief_md: bool = True,
) -> Dict[str, str]:
    """Operator summary JSON/MD/HTML + weekly brief MD→HTML sync."""
    import shutil

    from .operator_summary_html import write_operator_summary_html
    from .weekly_brief import write_weekly_brief_artifacts

    op_payload = build_operator_summary_payload(
        df, ctx, scan_date, diff_payload, methodology_version="v1.1"
    )
    paths: Dict[str, str] = {}
    op_sum_json = output_dir / f"institutional_accumulation_operator_summary_{scan_date}.json"
    op_sum_md = output_dir / f"institutional_accumulation_operator_summary_{scan_date}.md"
    op_sum_html = output_dir / f"institutional_accumulation_operator_summary_{scan_date}.html"
    op_sum_html_latest = output_dir / "institutional_accumulation_operator_summary_latest.html"
    write_operator_summary_json(op_sum_json, op_payload)
    write_operator_summary_md(op_sum_md, op_payload)
    write_operator_summary_html(op_sum_html, op_payload)
    shutil.copy2(op_sum_html, op_sum_html_latest)
    paths["operator_summary_json"] = str(op_sum_json)
    paths["operator_summary_md"] = str(op_sum_md)
    paths["operator_summary_html"] = str(op_sum_html)
    paths["operator_summary_html_latest"] = str(op_sum_html_latest)

    weekly_paths = write_weekly_brief_artifacts(
        output_dir,
        scan_date,
        op_payload,
        df,
        scan_json,
        preserve_existing_md=preserve_weekly_brief_md,
    )
    paths.update(weekly_paths)
    return paths

