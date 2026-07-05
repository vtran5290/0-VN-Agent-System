#!/usr/bin/env python3
"""
S18 — VN sector same-day persistence filter on S1+ A3_RS pool.

Run order: baseline verify -> IS lock -> OOS (C2_thresh075 first, then C1_thresh100).

Pre-reg: knowledge/backtests/2026-07-05_schwager_s18_sector_persistence_prereg.md
Handoff: 05_AI_Handoffs/2026-07-05-1500_CursorHandoff_S18SectorPersistence.md
RESEARCH_ONLY_NOT_PRODUCTION

Usage: python pp_backtest/cortex_schwager_s18_sector_persistence.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pp_backtest.cortex_schwager_common import (
    G1B_FLOOR,
    G_CONTINUATION,
    IS_WINDOW,
    MIN_N_OOS,
    OOS_WINDOW,
    S18_G1A,
    S1_BASELINE_OOS_MAR,
    band_limit_fraction,
    build_sector_triggers,
    build_stack_with_sector,
    filter_trades_s18,
    oos_sub_mar,
    persistence_by_sector,
    persistence_rate,
    run_filtered_sim,
    verify_s1_baseline,
    write_harness_report,
)
from pp_backtest.d3_sector_rs_validation import RESEARCH_LABEL

OUT_MD = REPO / "knowledge" / "backtests" / "s18_harness_results.md"
OUT_REPORT = REPO / "data" / "research" / "cortex_schwager" / "s18_sector_persistence_report.md"
OUT_META = REPO / "data" / "research" / "cortex_schwager" / "s18_sector_persistence_meta.json"
GATES_ADDENDUM = REPO / "knowledge" / "backtests" / "2026-07-05_schwager_s18_gates_addendum.md"
PREREG = "knowledge/backtests/2026-07-05_schwager_s18_sector_persistence_prereg.md"

# C2 first per handoff; k=2 only
CANDIDATES = [
    ("C2_thresh075", 0.75, 20),
    ("C1_thresh100", 1.0, 20),
]
ROLL_WINDOWS = [20, 60]


def _is_window_diagnostics(sector_rets: pd.DataFrame, k: float, roll: int) -> dict[str, Any]:
    triggers = build_sector_triggers(sector_rets, k, roll=roll)
    rate, n = persistence_rate(triggers, IS_WINDOW)
    sr = sector_rets.copy()
    sr["date"] = pd.to_datetime(sr["date"])
    is_mask = sr["date"].dt.year.between(IS_WINDOW[0], IS_WINDOW[1])
    n_sector_days = len(sr[is_mask])
    fire_rate = n / n_sector_days if n_sector_days else 0.0
    return {"roll": roll, "is_persistence": rate, "is_n": n, "is_fire_rate": fire_rate}


def _evaluate_s18(
    oos_mar: float,
    s1_mar: float,
    n_oos: int,
    persist_oos: float,
) -> tuple[dict[str, bool], str]:
    g1a = np.isfinite(oos_mar) and oos_mar >= S18_G1A
    g1b = np.isfinite(oos_mar) and oos_mar >= G1B_FLOOR
    g2 = np.isfinite(persist_oos) and persist_oos >= G_CONTINUATION
    g3 = n_oos >= MIN_N_OOS
    margin = oos_mar - S18_G1A if np.isfinite(oos_mar) else -999
    both_neg = s1_mar < 0 and oos_mar < 0

    gates = {"G1a": g1a, "G1b": g1b, "G2_continuation": g2, "G3_N_OOS": g3}

    if not g3:
        return gates, "VN-THIN"
    if np.isfinite(oos_mar) and oos_mar < 0:
        return gates, "PARKED"
    if not g2:
        return gates, "NEUTRAL"
    if both_neg:
        return gates, "CONDITIONAL-ADVANCE" if g1a and g1b else "FAIL"
    if g1a and g1b:
        return gates, "ADVANCE"
    if g1a and margin < 0.020:
        return gates, "CONDITIONAL-ADVANCE"
    return gates, "FAIL"


def main() -> dict[str, Any]:
    print("S18 sector persistence harness (S1+S18)", flush=True)
    stack = build_stack_with_sector()
    s1_trades = stack["s1_trades"]
    sector_rets = stack["sector_rets"]
    panel = stack["ctx"].panel

    # --- Baseline verification ---
    s1_m, s1_n, drift = verify_s1_baseline(stack)
    print(f"  S1 baseline OOS MAR={s1_m['mar']:.4f} N={s1_n} drift={drift}", flush=True)
    if drift:
        raise RuntimeError(
            f"[BASELINE-DRIFT] S1 OOS MAR {s1_m['mar']:.4f} vs locked {S1_BASELINE_OOS_MAR} "
            f"+/- {0.05}. Halt."
        )

    # --- IS diagnostics (both roll windows; lock N=20) ---
    is_diag: list[dict[str, Any]] = []
    for roll in ROLL_WINDOWS:
        for label, k, _ in CANDIDATES:
            d = _is_window_diagnostics(sector_rets, k, roll)
            d["candidate"] = label
            is_diag.append(d)
            print(
                f"  IS roll={roll} {label}: persist={d['is_persistence']:.1%} n={d['is_n']}",
                flush=True,
            )

    GATES_ADDENDUM.write_text(
        "\n".join(
            [
                "# Gates Addendum: S18 — locked IS diagnostics",
                f"# Written: {date.today()} (before OOS run)",
                f"# Pre-reg: {PREREG}",
                "",
                "## Baseline verification",
                f"- S1-filtered OOS MAR: **{s1_m['mar']:.4f}** (locked ref {S1_BASELINE_OOS_MAR})",
                f"- N_OOS: **{s1_n}**",
                f"- Baseline drift flag: **{drift}**",
                "",
                "## Locked rolling window",
                "- **N=20** (candidates C1/C2 use N=20; N=60 IS diagnostics recorded for reference)",
                "",
                "## IS diagnostics",
                "",
                "| Roll | Candidate | IS persistence | IS trigger n | IS fire rate |",
                "|------|-----------|----------------|--------------|--------------|",
            ]
            + [
                f"| {d['roll']} | {d['candidate']} | {d['is_persistence']:.1%} | {d['is_n']} | {d['is_fire_rate']:.1%} |"
                for d in is_diag
            ]
            + [
                "",
                "## Locked OOS gate parameters (pre-reg)",
                f"- G1a: OOS MAR >= **{S18_G1A}**",
                f"- G1b: OOS MAR >= **{G1B_FLOOR}**",
                f"- G2 continuation: OOS >= **{G_CONTINUATION:.0%}**",
                f"- G3: N_OOS >= **{MIN_N_OOS}**",
                "- Borderline: G1a pass margin < 0.020 -> CONDITIONAL-ADVANCE (requires pre-registered follow-up)",
            ],
        ),
        encoding="utf-8",
    )
    print(f"  Gates addendum: {GATES_ADDENDUM}", flush=True)

    # --- OOS candidates ---
    results: list[dict[str, Any]] = []
    for label, k, roll in CANDIDATES:
        triggers = build_sector_triggers(sector_rets, k, roll=roll)
        is_p, is_n = persistence_rate(triggers, IS_WINDOW)
        oos_p, oos_n = persistence_rate(triggers, OOS_WINDOW)
        filt = filter_trades_s18(s1_trades, stack["sector_map"], triggers)
        eq, m_cand, n_trades = run_filtered_sim(stack, filt)
        sub_a, sub_b = oos_sub_mar(eq)
        sec_oos = persistence_by_sector(triggers, OOS_WINDOW)
        band_pct = band_limit_fraction(panel, stack["sector_map"], triggers)
        gates, verdict = _evaluate_s18(m_cand["mar"], s1_m["mar"], n_trades, oos_p)
        results.append(
            {
                "label": label,
                "k": k,
                "roll": roll,
                "is_persistence": is_p,
                "is_n": is_n,
                "oos_persistence": oos_p,
                "oos_trigger_n": oos_n,
                "oos_mar": m_cand["mar"],
                "oos_sub_a_mar": sub_a,
                "oos_sub_b_mar": sub_b,
                "n_oos_trades": n_trades,
                "band_limit_flag_pct": band_pct,
                "sector_oos": sec_oos.to_dict(orient="records") if not sec_oos.empty else [],
                "gates": gates,
                "verdict": verdict,
            }
        )
        print(
            f"  {label}: IS persist={is_p:.1%} OOS persist={oos_p:.1%} "
            f"MAR={m_cand['mar']:.4f} N={n_trades} -> {verdict}",
            flush=True,
        )

    primary = results[0] if results else {}
    final = primary.get("verdict", "FAIL")
    best = max(results, key=lambda r: r.get("oos_mar", -999), default=primary)
    overall = best.get("verdict", final)

    band_warn = any(
        np.isfinite(r.get("band_limit_flag_pct", np.nan)) and r["band_limit_flag_pct"] > 0.15
        for r in results
    )

    lines = [
        "# S18 Sector Persistence Harness Results",
        "",
        f"**Generated:** {date.today()}",
        f"**Research label:** {RESEARCH_LABEL}",
        f"**Pre-registration:** `{PREREG}`",
        f"**Gates addendum:** `{GATES_ADDENDUM.relative_to(REPO).as_posix()}`",
        "",
        f"**FINAL VERDICT (primary C2_thresh075):** {final}",
        f"**Best candidate verdict:** {overall} ({best.get('label', '')})",
        "",
        f"S1 baseline OOS MAR: **{s1_m['mar']:.4f}** (locked {S1_BASELINE_OOS_MAR}) | G1a floor: **{S18_G1A}** | G2 continuation: **>={G_CONTINUATION:.0%}**",
        "",
        "## Baseline verification",
        f"- S1-only OOS MAR: {s1_m['mar']:.4f} | N={s1_n} | drift={drift}",
        "",
        "## OOS gate results",
        "",
        "| Candidate | k | IS persist | OOS persist | OOS MAR | sub-A MAR | sub-B MAR | N_OOS | G2 | Verdict |",
        "|-----------|---|------------|-------------|---------|-----------|-----------|-------|----|---------|",
    ]
    for r in results:
        lines.append(
            f"| {r['label']} | {r['k']} | {r['is_persistence']:.1%} (n={r['is_n']}) | "
            f"{r['oos_persistence']:.1%} (n={r['oos_trigger_n']}) | {r['oos_mar']:.4f} | "
            f"{r['oos_sub_a_mar']:.4f} | {r['oos_sub_b_mar']:.4f} | {r['n_oos_trades']} | "
            f"{'PASS' if r['gates']['G2_continuation'] else 'FAIL'} | {r['verdict']} |"
        )

    lines += ["", "## Sector-level OOS continuation (primary C2)", ""]
    if primary.get("sector_oos"):
        lines += ["| Sector | Rate | n |", "|--------|------|---|"]
        for row in primary["sector_oos"]:
            lines.append(f"| {row['sector']} | {row['rate']:.1%} | {row['n']} |")
    else:
        lines.append("_No sector breakdown._")

    lines += [
        "",
        "## Band limit check (report-only)",
        f"- Fraction of trigger days with >=20% members at +/-7% band: **{primary.get('band_limit_flag_pct', float('nan')):.1%}**",
    ]
    if band_warn:
        lines.append("- **[BAND-LIMIT-WARN]** >15% of trigger days show heavy band clamping")

    meta = {
        "belief_id": "S18",
        "run_date": str(date.today()),
        "baseline_verification": {
            "s1_oos_mar": s1_m["mar"],
            "s1_n_oos": s1_n,
            "baseline_drift_flag": drift,
        },
        "candidates": {
            r["label"]: {
                "g1a_oos_mar": r["oos_mar"],
                "g1a_pass": r["gates"]["G1a"],
                "g1b_pass": r["gates"]["G1b"],
                "g2_continuation_rate": r["oos_persistence"],
                "g2_pass": r["gates"]["G2_continuation"],
                "g3_n_oos": r["n_oos_trades"],
                "g3_pass": r["gates"]["G3_N_OOS"],
                "verdict": r["verdict"],
            }
            for r in results
        },
        "overall_verdict": overall,
        "band_limit_flag_pct": primary.get("band_limit_flag_pct"),
        "sub_a_oos_mar": primary.get("oos_sub_a_mar"),
        "sub_b_oos_mar": primary.get("oos_sub_b_mar"),
    }

    write_harness_report(OUT_MD, "S18", lines, meta)
    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")
    OUT_META.write_text(__import__("json").dumps(meta, indent=2, default=str), encoding="utf-8")
    print(f"Report: {OUT_MD}", flush=True)
    return meta


if __name__ == "__main__":
    main()
