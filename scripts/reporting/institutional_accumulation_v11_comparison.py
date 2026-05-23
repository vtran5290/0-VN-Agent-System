"""Write METHODOLOGY_V11_COMPARISON for spot-check tickers (v1.0 sample vs v1.1 full universe)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
SCANS = REPO / "outputs" / "scans"
SPOT = ["MBB", "CTG", "MWG", "HPG", "GMD", "VIC", "VHM", "VCB", "STB"]

# Pre–full-universe v1.0-style sample (2026-04-30, ~9-symbol run)
V10_BASELINE = {
    "MBB": {"tier": "Reject", "score": 26.86, "score_money_flow": 22.0},
    "CTG": {"tier": "Reject", "score": 31.94, "score_money_flow": 28.0},
    "MWG": {"tier": "Tier 3", "score": 45.99, "score_money_flow": 52.0},
    "HPG": {"tier": "Tier 3", "score": 42.8, "score_money_flow": 48.0},
    "GMD": {"tier": "Reject", "score": 31.04, "score_money_flow": 30.0},
    "VIC": {"tier": "Reject", "score": 39.98, "score_money_flow": 55.0},
    "VHM": {"tier": "Tier 3", "score": 44.13, "score_money_flow": 50.0},
    "VCB": {"tier": "Tier 3", "score": 43.28, "score_money_flow": 49.0},
    "STB": {"tier": "Reject", "score": 36.69, "score_money_flow": 42.0},
}


def main(as_of: str = "2026-04-30") -> Path:
    csv_path = SCANS / f"institutional_accumulation_{as_of}.csv"
    if not csv_path.is_file():
        raise SystemExit(f"Missing scan: {csv_path}")
    df = pd.read_csv(csv_path)
    sub = df[df["ticker"].isin(SPOT)].copy()
    rows = []
    for sym in SPOT:
        before = V10_BASELINE.get(sym, {})
        cur = sub[sub["ticker"] == sym]
        if cur.empty:
            rows.append({"ticker": sym, "v11": "NOT_IN_UNIVERSE"})
            continue
        r = cur.iloc[0]
        rows.append(
            {
                "ticker": sym,
                "v10_tier": before.get("tier"),
                "v11_tier": r["tier"],
                "v10_score": before.get("score"),
                "v11_score": round(float(r["institutional_accumulation_score"]), 2),
                "v11_score_money_flow": round(float(r["score_money_flow"]), 2),
                "fund_context_bucket": r.get("fund_context_bucket"),
                "emerging": bool(r.get("emerging_accumulation_candidate")),
                "vingroup_distortion_flag": bool(r.get("vingroup_distortion_flag")),
                "vingroup_distortion_diagnosis": r.get("vingroup_distortion_diagnosis"),
            }
        )
    out = SCANS / "METHODOLOGY_V11_COMPARISON_20260430.md"
    lines = [
        "# Institutional Accumulation Scan — v1.0 sample vs v1.1 full universe",
        f"As-of: **{as_of}** | methodology **v1.1**",
        "",
        "| Ticker | v1.0 tier | v1.1 tier | v1.0 score | v1.1 score | MF | fund_context | emerging | VIN flag |",
        "|--------|-----------|-----------|------------|------------|-----|--------------|----------|----------|",
    ]
    for row in rows:
        if row.get("v11") == "NOT_IN_UNIVERSE":
            lines.append(f"| {row['ticker']} | — | NOT_IN_UNIVERSE | — | — | — | — | — | — |")
            continue
        vin = "Y" if row.get("vingroup_distortion_flag") else ""
        lines.append(
            f"| {row['ticker']} | {row['v10_tier']} | {row['v11_tier']} | "
            f"{row['v10_score']} | {row['v11_score']} | {row['v11_score_money_flow']} | "
            f"{row['fund_context_bucket']} | {row['emerging']} | {vin} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "- v1.0 column = pre–full-universe sample run (not full liquid universe).",
            "- v1.1 = full `data/stocks` liquid universe + grouped money-flow + fragile tier calibration.",
            "",
            "```json",
            json.dumps(rows, indent=2, ensure_ascii=False),
            "```",
        ]
    )
    out.write_text("\n".join(lines), encoding="utf-8")
    print(out)
    return out


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default="2026-04-30")
    main(ap.parse_args().as_of)
