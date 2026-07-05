#!/usr/bin/env python3
"""
S17 — VN cumulative buy/sell flow filter on S1+ A3_RS pool (NOT isolated A3).

IS: derive P75 ratio thresholds (1d/5d/20d) from S1-filtered IS trades.
OOS: filter S1+S17 combined; G1a = 1.850 vs S1 baseline 1.7844.

Pre-reg: knowledge/backtests/2026-07-05_schwager_s17_buysell_flow_prereg.md
Status: RE-SCOPED 2026-07-05 (opus REDIRECT) — do not run until FireAnt cache ready.
RESEARCH_ONLY_NOT_PRODUCTION

Usage: python pp_backtest/cortex_schwager_s17_buysell.py
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
    IS_END,
    IS_START,
    MIN_N_OOS,
    OOS_WINDOW,
    PANEL_START,
    S17_G1A,
    S1_BASELINE_N_OOS,
    S1_BASELINE_OOS_MAR,
    N_TOLERANCE,
    build_stack_with_sector,
    fetch_buy_sell_raw,
    load_or_build_buy_sell_cache,
    oos_sub_mar,
    ratio_on_signal,
    run_filtered_sim,
    signal_date_col,
    verify_s1_baseline,
    write_harness_report,
)
from pp_backtest.d3_sector_rs_validation import RESEARCH_LABEL
from src.data.fireant_client import _BROWSER_HEADERS, _load_token

OUT_MD = REPO / "knowledge" / "backtests" / "s17_harness_results.md"
OUT_META = REPO / "data" / "research" / "cortex_schwager" / "s17_harness_meta.json"
GATES_ADDENDUM = REPO / "knowledge" / "backtests" / "2026-07-05_schwager_s17_gates_addendum.md"
PREREG = "knowledge/backtests/2026-07-05_schwager_s17_buysell_flow_prereg.md"

Q2_PROBE_SYMBOLS = ("VNM", "VCB", "HPG", "ACB", "SSI")

CANDIDATES = [
    ("C1_ratio1d", 1),
    ("C2_ratio5d", 5),
    ("C3_ratio20d", 20),
]


def _attach_ratios(trades: pd.DataFrame, cache: pd.DataFrame) -> pd.DataFrame:
    t = trades.copy()
    t["_sig"] = signal_date_col(t)
    r1, r5, r20 = [], [], []
    for _, row in t.iterrows():
        sym = str(row["symbol"])
        sig = pd.Timestamp(row["_sig"]).normalize()
        r1.append(ratio_on_signal(cache, sym, sig, 1))
        r5.append(ratio_on_signal(cache, sym, sig, 5))
        r20.append(ratio_on_signal(cache, sym, sig, 20))
    t["ratio_1d"] = r1
    t["ratio_5d"] = r5
    t["ratio_20d"] = r20
    return t


def _check_q2_putthrough() -> tuple[str, bool, dict[str, Any]]:
    """Verify putthroughVolume is separate from buyQuantity/sellQuantity in FireAnt API."""
    token = _load_token(None)
    if not token:
        return "UNRESOLVED", True, {"error": "FIREANT_TOKEN missing"}
    headers = {**_BROWSER_HEADERS, "Authorization": f"Bearer {token}"}
    samples: list[dict[str, Any]] = []
    has_putthrough_field = False
    putthrough_days = 0
    for sym in Q2_PROBE_SYMBOLS:
        df = fetch_buy_sell_raw(sym, "2020-01-01", str(date.today()), headers)
        if df.empty:
            continue
        # Re-fetch one row with raw JSON for putthrough field check
        import requests
        from src.data.fireant_client import RESTV2_BASE

        r = requests.get(
            f"{RESTV2_BASE}/symbols/{sym}/historical-quotes",
            headers=headers,
            params={"startDate": "2024-01-01", "endDate": "2024-12-31", "offset": 0, "limit": 500},
            timeout=60,
        )
        if r.status_code != 200 or not r.json():
            continue
        fields = list(r.json()[0].keys())
        if "putthroughVolume" in fields:
            has_putthrough_field = True
        for item in r.json():
            pt = item.get("putthroughVolume")
            bq = float(item.get("buyQuantity") or 0)
            sq = float(item.get("sellQuantity") or 0)
            dv = float(item.get("dealVolume") or item.get("totalVolume") or 0)
            pt_f = float(pt) if pt is not None else 0.0
            if pt_f > 0:
                putthrough_days += 1
                samples.append(
                    {
                        "symbol": sym,
                        "date": str(item.get("date", ""))[:10],
                        "buy": bq,
                        "sell": sq,
                        "putthrough": pt_f,
                        "deal_volume": dv,
                        "buy_plus_sell": bq + sq,
                    }
                )
    detail = {
        "has_putthrough_field": has_putthrough_field,
        "putthrough_days_in_sample": putthrough_days,
        "sample_rows": samples[:5],
        "fields_note": "buyQuantity/sellQuantity used for ratios; putthroughVolume not added to cache",
    }
    if not has_putthrough_field:
        return "UNRESOLVED", True, detail
    # Separate field + ratio builder excludes putthrough -> PASS
    return "PASS", False, detail


def _write_gates_addendum(
    s1_mar: float,
    s1_n: int,
    drift: bool,
    q2_verdict: str,
    thresholds: dict[str, float],
    n_is_days: int,
) -> None:
    GATES_ADDENDUM.write_text(
        "\n".join(
            [
                "# Gates Addendum: S17 — Buy/Sell Flow (locked before OOS)",
                f"# date: {date.today()}",
                "",
                "```yaml",
                "locked: true",
                f"date: {date.today()}",
                f"baseline_s1_oos_mar: {S1_BASELINE_OOS_MAR}",
                f"g1a_threshold: {S17_G1A}",
                f"g1b_threshold: {G1B_FLOOR}",
                f"p75_ratio1d: {thresholds.get('C1_ratio1d', float('nan')):.6f}",
                f"p75_ratio5d: {thresholds.get('C2_ratio5d', float('nan')):.6f}",
                f"p75_ratio20d: {thresholds.get('C3_ratio20d', float('nan')):.6f}",
                f"q2_verdict: {q2_verdict}",
                f"baseline_verification: {'FAIL' if drift else 'PASS'}",
                f"n_s1_is_signal_days_used_for_p75: {n_is_days}",
                "```",
                "",
                f"- Verified S1 OOS MAR at run time: **{s1_mar:.4f}** (N={s1_n})",
                "- P75 derived on **S1-filtered IS signal days only** (not raw A3 IS days).",
            ]
        ),
        encoding="utf-8",
    )


def _filter_ratio(t: pd.DataFrame, col: str, thresh: float) -> pd.DataFrame:
    return t[t[col].notna() & (t[col] > thresh)].drop(columns=["_sig"], errors="ignore")


def main() -> dict[str, Any]:
    print("S17 buy/sell flow harness (S1+S17)", flush=True)
    stack = build_stack_with_sector()
    s1_trades = stack["s1_trades"]

    # Step 2 — baseline verification
    s1_m, s1_n, drift = verify_s1_baseline(stack)
    print(f"  S1 baseline OOS MAR={s1_m['mar']:.4f} N={s1_n} drift={drift}", flush=True)
    if drift:
        raise RuntimeError(
            f"[BASELINE-DRIFT] S1 OOS MAR {s1_m['mar']:.4f} vs locked {S1_BASELINE_OOS_MAR}. Halt."
        )
    if abs(s1_n - S1_BASELINE_N_OOS) > N_TOLERANCE:
        raise RuntimeError(
            f"[BASELINE-DRIFT] S1 N_OOS {s1_n} vs expected {S1_BASELINE_N_OOS} +/- {N_TOLERANCE}. Halt."
        )

    # Step 1/3 — cache + Q2 check
    print("  Q2 put-through check...", flush=True)
    q2_verdict, q2_risk, q2_detail = _check_q2_putthrough()
    print(f"  Q2 verdict: {q2_verdict} q2_risk={q2_risk}", flush=True)

    syms = sorted(s1_trades["symbol"].astype(str).unique())
    print(f"  FireAnt buy/sell cache fetch ({len(syms)} symbols)...", flush=True)
    cache = load_or_build_buy_sell_cache(syms, PANEL_START, str(date.today()))
    n_cache_syms = cache["symbol"].nunique()
    print(f"  Cache: {len(cache)} rows, {n_cache_syms} symbols", flush=True)

    enriched = _attach_ratios(s1_trades, cache)
    is_tr = enriched[(enriched["_sig"] >= IS_START) & (enriched["_sig"] <= IS_END)]

    # Step 4 — IS P75 on S1-filtered IS signal days only
    thresholds: dict[str, float] = {}
    n_is_with_ratio: dict[str, int] = {}
    for label, win in CANDIDATES:
        col = f"ratio_{win}d" if win > 1 else "ratio_1d"
        vals = is_tr[col].dropna()
        n_is_with_ratio[label] = len(vals)
        thresholds[label] = float(np.percentile(vals, 75)) if len(vals) else np.nan
        print(f"  IS P75 {label} ({col}): {thresholds[label]:.4f} (n={len(vals)} S1 IS days)", flush=True)

    n_is_days = len(is_tr)
    # Step 5 — lock gates addendum BEFORE OOS
    _write_gates_addendum(s1_m["mar"], s1_n, drift, q2_verdict, thresholds, n_is_days)
    print(f"  Gates addendum locked: {GATES_ADDENDUM}", flush=True)

    q2_tag = " [Q2-RISK]" if q2_risk else ""

    # Step 6/7 — OOS run + gate verdicts
    results: list[dict[str, Any]] = []
    for label, win in CANDIDATES:
        col = f"ratio_{win}d" if win > 1 else "ratio_1d"
        th = thresholds[label]
        if not np.isfinite(th):
            results.append({"label": label, "verdict": "VN-THIN", "reason": "no IS threshold", "q2_risk_flag": q2_risk})
            continue
        filt = _filter_ratio(enriched, col, th)
        eq, m, n_oos = run_filtered_sim(
            stack, filt.drop(columns=["ratio_1d", "ratio_5d", "ratio_20d"], errors="ignore")
        )
        sub_a, sub_b = oos_sub_mar(eq)
        g1a = np.isfinite(m["mar"]) and m["mar"] >= S17_G1A
        g1b = np.isfinite(m["mar"]) and m["mar"] >= G1B_FLOOR
        g2 = n_oos >= MIN_N_OOS
        margin = m["mar"] - S17_G1A if np.isfinite(m["mar"]) else -999

        if not g2:
            verdict = "VN-THIN"
        elif np.isfinite(m["mar"]) and m["mar"] < 0:
            verdict = "PARKED"
        elif g1a and g1b:
            verdict = "ADVANCE"
        elif g1a and margin < 0.020:
            verdict = "CONDITIONAL-ADVANCE"
        else:
            verdict = "FAIL"

        results.append(
            {
                "label": label,
                "window": win,
                "is_p75": th,
                "oos_mar": m["mar"],
                "oos_maxdd": m["max_dd"],
                "sub_a_mar": sub_a,
                "sub_b_mar": sub_b,
                "n_oos": n_oos,
                "gates": {"G1a": g1a, "G1b": g1b, "G2": g2},
                "verdict": verdict,
                "q2_risk_flag": q2_risk,
            }
        )
        print(
            f"  {label}: OOS MAR={m['mar']:.4f} subA={sub_a:.4f} subB={sub_b:.4f} "
            f"N={n_oos} -> {verdict}{q2_tag}",
            flush=True,
        )

    best = max(
        (r for r in results if r.get("verdict") not in ("VN-THIN",)),
        key=lambda x: x.get("oos_mar", -999),
        default=None,
    )
    final = best["verdict"] if best else "FAIL"

    lines = [
        "# S17 Buy/Sell Flow Harness Results",
        "",
        f"**Generated:** {date.today()}",
        f"**Research label:** {RESEARCH_LABEL}",
        f"**Pre-registration:** `{PREREG}`",
        f"**Gates addendum:** `{GATES_ADDENDUM.relative_to(REPO).as_posix()}`",
        f"**Source:** FireAnt REST `buyQuantity`/`sellQuantity` (method=REST API)",
        f"**Test design:** S1+S17 combined (re-scoped 2026-07-05 opus REDIRECT)",
        f"**Q2 verdict:** {q2_verdict}{' — [Q2-RISK] annotated on all rows' if q2_risk else ''}",
        f"**FINAL VERDICT:** {final}{q2_tag}",
        "",
        f"S1 baseline OOS MAR: {s1_m['mar']:.4f} (locked {S1_BASELINE_OOS_MAR}) | G1a floor: {S17_G1A} | G1b: {G1B_FLOOR}",
        f"S1-filtered IS signal days for P75: **{n_is_days}**",
        "",
        "## IS P75 thresholds (locked before OOS)",
        "",
        "| Candidate | Window | IS P75 | n (S1 IS days w/ ratio) |",
        "|-----------|--------|--------|-------------------------|",
    ]
    for label, win in CANDIDATES:
        lines.append(
            f"| {label} | {win}d | {thresholds.get(label, float('nan')):.4f} | {n_is_with_ratio.get(label, 0)} |"
        )
    lines += [
        "",
        "## OOS gate results",
        "",
        "| Candidate | OOS MAR | sub-A MAR | sub-B MAR | N_OOS | G1a | G1b | G2 | Verdict |",
        "|-----------|---------|-----------|-----------|-------|-----|-----|----|---------|",
    ]
    for r in results:
        g = r.get("gates", {})
        v = r.get("verdict", "") + (" [Q2-RISK]" if r.get("q2_risk_flag") else "")
        lines.append(
            f"| {r.get('label','')} | {r.get('oos_mar', float('nan')):.4f} | "
            f"{r.get('sub_a_mar', float('nan')):.4f} | {r.get('sub_b_mar', float('nan')):.4f} | "
            f"{r.get('n_oos','')} | {'PASS' if g.get('G1a') else 'FAIL'} | "
            f"{'PASS' if g.get('G1b') else 'FAIL'} | {'PASS' if g.get('G2') else 'FAIL'} | {v} |"
        )

    meta = {
        "belief_id": "S17",
        "run_date": str(date.today()),
        "baseline_verification": {
            "s1_oos_mar": s1_m["mar"],
            "s1_n_oos": s1_n,
            "baseline_drift_flag": drift,
        },
        "q2_verdict": q2_verdict,
        "q2_detail": q2_detail,
        "p75_thresholds": {
            "ratio_1d": thresholds.get("C1_ratio1d"),
            "ratio_5d": thresholds.get("C2_ratio5d"),
            "ratio_20d": thresholds.get("C3_ratio20d"),
            "n_is_signal_days": n_is_days,
        },
        "candidates": {
            r["label"]: {
                "g1a_oos_mar": r.get("oos_mar"),
                "g1a_pass": r.get("gates", {}).get("G1a"),
                "g1b_pass": r.get("gates", {}).get("G1b"),
                "g2_n_oos": r.get("n_oos"),
                "g2_pass": r.get("gates", {}).get("G2"),
                "sub_a_mar": r.get("sub_a_mar"),
                "sub_b_mar": r.get("sub_b_mar"),
                "verdict": r.get("verdict"),
                "q2_risk_flag": r.get("q2_risk_flag"),
            }
            for r in results
        },
        "overall_verdict": final,
    }
    write_harness_report(OUT_MD, "S17", lines, meta)
    OUT_META.write_text(__import__("json").dumps(meta, indent=2, default=str), encoding="utf-8")
    print(f"Report: {OUT_MD}", flush=True)
    return meta


if __name__ == "__main__":
    main()
