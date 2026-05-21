"""
Write consolidated Phase36 daily scan report (parallel to weekly_report.md).

Outputs:
  - data/decision/daily_scan.md
  - data/decision/daily_scan.json

Regenerate from existing CSV:
  .venv\\Scripts\\python.exe scripts/reporting/daily_scan_report.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.scan_ssot import OPERATOR_ACTION_MAP, resolve_scan_path
from src.trading.portfolio_state import (
    get_current_nav_vnd,
    load_current_positions,
    load_portfolio_state,
)

OUT_MD = REPO / "data" / "decision" / "daily_scan.md"
OUT_JSON = REPO / "data" / "decision" / "daily_scan.json"
HOLDINGS_PATH = REPO / "data" / "trading" / "holdings.txt"
VIN_SYMBOLS = frozenset({"VIC", "VHM", "VRE", "VPL"})
_NEW_T1_ACTIONS = frozenset({"NEW_T1", "NEW_T1_MANUAL_REVIEW_BREADTH"})


def _load_holdings(path: Path = HOLDINGS_PATH) -> List[str]:
    if not path.is_file():
        return []
    out: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip().upper()
        if s and not s.startswith("#"):
            out.append(s)
    return out


def _fmt_num(v: Any, digits: int = 2) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return str(v)


def _md_table(headers: List[str], rows: List[List[str]]) -> str:
    if not rows:
        return "_None._\n"
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    lines = [
        "| " + " | ".join(headers) + " |",
        sep,
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines) + "\n"


def _portfolio_context() -> tuple[Optional[Dict[str, Any]], Optional[float], List[List[str]]]:
    """NAV + positions from portfolio_state.json SSoT (never infer NAV from positions)."""
    state = load_portfolio_state()
    if not state:
        return None, None, []
    nav_vnd = get_current_nav_vnd(state)
    pos_df, _src = load_current_positions(state)
    rows: List[List[str]] = []
    if pos_df is not None and not pos_df.empty:
        for _, pos in pos_df.iterrows():
            sym = str(pos.get("symbol") or pos.get("ticker") or "").upper()
            lots = pos.get("lots")
            entry = pos.get("entry_price")
            tag = pos.get("reason_tag") or "—"
            mv = None
            if pos.get("market_value_vnd") is not None and not pd.isna(pos.get("market_value_vnd")):
                try:
                    mv = float(pos["market_value_vnd"])
                except (TypeError, ValueError):
                    mv = None
            if mv is None:
                try:
                    mv = float(lots) * float(entry) if lots is not None and entry is not None else None
                except (TypeError, ValueError):
                    mv = None
            cost = None
            try:
                cost = float(lots) * float(entry) if lots is not None and entry is not None else None
            except (TypeError, ValueError):
                cost = None
            pct = f"{100.0 * mv / nav_vnd:.1f}%" if mv and nav_vnd and nav_vnd > 0 else "—"
            rows.append(
                [
                    sym,
                    str(int(lots)) if lots is not None and not pd.isna(lots) else "—",
                    _fmt_num(entry, 0),
                    _fmt_num(mv, 0) if mv else "—",
                    pct,
                    str(tag),
                ]
            )
    invested = 0.0
    if pos_df is not None and not pos_df.empty:
        for _, pos in pos_df.iterrows():
            lots = pos.get("lots")
            entry = pos.get("entry_price")
            try:
                invested += float(lots) * float(entry)
            except (TypeError, ValueError):
                pass
    market_sum = 0.0
    has_market = False
    if pos_df is not None and not pos_df.empty and "market_value_vnd" in pos_df.columns:
        for _, pos in pos_df.iterrows():
            if pos.get("market_value_vnd") is not None and not pd.isna(pos.get("market_value_vnd")):
                try:
                    market_sum += float(pos["market_value_vnd"])
                    has_market = True
                except (TypeError, ValueError):
                    pass
    meta = {
        "as_of_date": state.get("as_of_date"),
        "nav_vnd": nav_vnd,
        "positions_path": state.get("positions_path"),
        "port_excludes_cash": True,
        "nav_is_user_updated": True,
        "invested_cost_basis_vnd": invested if invested > 0 else None,
        "market_value_sum_vnd": market_sum if has_market else None,
        "nav_is_market_value": has_market and nav_vnd and abs(market_sum - nav_vnd) < 1.0,
    }
    return meta, nav_vnd, rows


def _operator_label(final_action: str) -> str:
    pair = OPERATOR_ACTION_MAP.get(final_action)
    return pair[0] if pair else final_action


def _short_reason(text: Any, max_len: int = 72) -> str:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return "—"
    s = str(text).replace("\n", " ").strip()
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


def write_daily_scan_report(
    scan_df: pd.DataFrame,
    *,
    scan_csv_path: Optional[Path] = None,
    holdings: Optional[List[str]] = None,
    generated_at: Optional[str] = None,
) -> Path:
    """Write daily_scan.md + daily_scan.json. Returns path to markdown."""
    holdings = holdings if holdings is not None else _load_holdings()
    generated_at = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if scan_df.empty:
        as_of = "n/a"
        breadth = breadth_zone = regime_bull = s3_breadth = None
    else:
        row0 = scan_df.iloc[0]
        as_of = str(row0.get("as_of_date", "n/a"))
        breadth = float(row0["pct_cloud_bull_a3"]) if pd.notna(row0.get("pct_cloud_bull_a3")) else None
        s3_breadth = float(row0["pct_cloud_bull_s3"]) if pd.notna(row0.get("pct_cloud_bull_s3")) else None
        breadth_zone = str(row0.get("breadth_zone", ""))
        regime_bull = bool(row0.get("regime_bull", False))

    if scan_csv_path:
        try:
            csv_rel = scan_csv_path.resolve().relative_to(REPO.resolve()).as_posix()
        except ValueError:
            csv_rel = scan_csv_path.as_posix()
    else:
        csv_rel = "phase36_daily_scan_latest.csv"
    n_symbols = len(scan_df)

    lines: List[str] = [
        f"# Daily Scan — Phase36 A3 — as-of {as_of}\n",
        f"_Generated: {generated_at} · SSOT CSV: `{csv_rel}` · {n_symbols} symbols in scan output_\n",
        "\n**Production rule:** OMS and capital decisions use **`final_action` only**. "
        "`a3_rank_score` is review sort order only (not a buy signal).\n",
    ]

    nav_meta, nav_vnd, pos_rows = _portfolio_context()
    if nav_meta and nav_vnd:
        lines.append("\n## Portfolio NAV & positions (operator)\n\n")
        lines.append(
            "**FACTS** (`data/trading/live/portfolio_state.json` — port excludes cash; "
            "NAV is user-updated, not inferred)\n\n"
        )
        invested = float(nav_meta.get("invested_cost_basis_vnd") or 0)
        gap = nav_vnd - invested if nav_vnd and invested else None
        nav_is_mkt = bool(nav_meta.get("nav_is_market_value"))
        gap_label = "Unrealized P&L (market − cost)" if nav_is_mkt else "Implied cash"
        gap_pct_label = "P&L % of NAV" if nav_is_mkt else "Cash %"
        nav_rows = [
            ["NAV (user-updated)", f"{nav_vnd:,.0f} VND"],
            ["Cost basis (positions)", f"{invested:,.0f} VND"],
            [gap_label, f"{gap:,.0f} VND" if gap is not None else "—"],
            [gap_pct_label, f"{100.0 * gap / nav_vnd:.1f}%" if gap is not None and nav_vnd else "—"],
            ["Position count", str(len(pos_rows))],
            ["Portfolio as-of", str(nav_meta.get("as_of_date", "—"))],
            ["positions_path", str(nav_meta.get("positions_path", "—"))],
        ]
        lines.append(_md_table(["Metric", "Value"], nav_rows))
        if pos_rows:
            lines.append("\n### Holdings detail\n\n")
            lines.append(
                _md_table(
                    ["Symbol", "Shares", "Avg entry (VND)", "Market value (VND)", "% NAV", "Sector"],
                    pos_rows,
                )
            )

    # --- Market gates ---
    lines.append("\n## Market regime & breadth\n")
    lines.append("**FACTS**\n\n")
    gate_rows = [
        ["VNINDEX regime", "Bull" if regime_bull else "Bear"],
        ["A3 cloud breadth", f"{breadth * 100:.1f}%" if breadth is not None else "—"],
        ["S3 cloud breadth", f"{s3_breadth * 100:.1f}%" if s3_breadth is not None else "—"],
        ["Breadth zone", breadth_zone or "—"],
        [
            "T1 permission",
            "Yes (manual review when flagged)"
            if scan_df.empty or bool(scan_df.iloc[0].get("breadth_t1_permission", True))
            else "No",
        ],
        [
            "T2 permission",
            "Yes" if (not scan_df.empty and bool(scan_df.iloc[0].get("breadth_t2_permission", False))) else "Blocked",
        ],
        ["Plain NEW_T1 count", str(int((scan_df["final_action"] == "NEW_T1").sum()) if not scan_df.empty else 0)],
    ]
    lines.append(_md_table(["Metric", "Value"], gate_rows))

    if breadth_zone == "defense":
        lines.append(
            "\n**INTERPRETATION:** Breadth &lt;40% → defense posture. "
            "No automatic new T1; manual review on flagged names; T2 adds blocked.\n"
        )

    # --- Distribution Risk Lens (refresh SSOT JSON, context only) ---
    from src.trading.reports.distribution_risk_card import build_distribution_risk_section_for_daily_scan

    drl_as_of = as_of if as_of != "n/a" else None
    drl_section, drl_warns = build_distribution_risk_section_for_daily_scan(as_of=drl_as_of, refresh=True)
    lines.append(drl_section)

    # --- Action counts ---
    lines.append("\n## final_action summary\n\n")
    if scan_df.empty:
        lines.append("_No scan rows._\n")
    else:
        count_rows = []
        for act, n in scan_df["final_action"].value_counts().items():
            count_rows.append([act, str(n), _operator_label(str(act))])
        lines.append(_md_table(["final_action", "Count", "Operator label"], count_rows))

    # --- New entry candidates ---
    lines.append("\n## New entry candidates (review sort)\n\n")
    if scan_df.empty:
        lines.append("_None._\n")
    else:
        ranked = scan_df[scan_df["final_action"].isin(_NEW_T1_ACTIONS)].copy()
        if ranked.empty:
            lines.append("_No NEW_T1 or NEW_T1_MANUAL_REVIEW_BREADTH today._\n")
        else:
            ranked = ranked.sort_values(
                ["final_action", "a3_rank_score", "symbol"],
                ascending=[True, False, True],
                na_position="last",
            )
            pending_entry_symbols: List[str] = []
            cand_rows = []
            for i, (_, r) in enumerate(ranked.iterrows(), 1):
                sig_today = bool(r.get("a3_signal_today", False))
                if sig_today:
                    pending_entry_symbols.append(str(r["symbol"]))
                    pb_cell = tp1_cell = trail_cell = "pending*"
                else:
                    pb_cell = _fmt_num(r.get("pb_trigger_price"))
                    tp1_cell = _fmt_num(r.get("tp1_price"))
                    trail_cell = _fmt_num(r.get("trail_price"))
                cand_rows.append(
                    [
                        str(i),
                        str(r["symbol"]),
                        str(r["final_action"]).replace("NEW_T1_MANUAL_REVIEW_BREADTH", "NEW_T1_MR"),
                        _fmt_num(r.get("close_kVND")),
                        _fmt_num(r.get("a3_rank_score"), 3),
                        _fmt_num(r.get("ed_score"), 3),
                        str(r.get("s3_lead_bucket") or "—"),
                        "Yes" if r.get("s3_fresh_lead_flag") else "No",
                        str(r.get("a3_rank_reason") or "—"),
                        pb_cell,
                        tp1_cell,
                        trail_cell,
                    ]
                )
            lines.append(
                _md_table(
                    [
                        "#",
                        "Symbol",
                        "final_action",
                        "Close",
                        "Rank",
                        "ED",
                        "S3 lead",
                        "S3 fresh",
                        "Rank reason",
                        "Trigger",
                        "TP1",
                        "Trail",
                    ],
                    cand_rows,
                )
            )
            if pending_entry_symbols:
                lines.append(
                    f"\n**\\* Pending entry ({', '.join(pending_entry_symbols)}):** "
                    "Signal confirmed at today's close; planned fill is next session open. "
                    "Entry levels are pending until the next-open fill price is known. "
                    "pb_trigger_price / tp1_price / trail_price will be computed after fill.\n"
                )
            lines.append("\n**Why (typical):** A3 cloud breakout; regime bull; breadth defense → T1 with operator review; T2 blocked.\n")
            detail_rows = []
            for _, r in ranked.iterrows():
                detail_rows.append([str(r["symbol"]), _short_reason(r.get("final_action_reason"), 100)])
            lines.append("\n### Per-symbol final_action_reason\n\n")
            lines.append(_md_table(["Symbol", "Reason"], detail_rows))

    # --- Holdings ---
    lines.append("\n## Portfolio holdings\n\n")
    if not holdings:
        lines.append("_No holdings file (`data/trading/holdings.txt`)._\n")
    elif scan_df.empty:
        lines.append("_Scan empty — cannot join holdings._\n")
    else:
        hd = scan_df[scan_df["symbol"].isin(holdings)].copy()
        in_scan = set(hd["symbol"])
        hold_rows = []
        for sym in sorted(holdings):
            if sym not in in_scan:
                hold_rows.append([sym, "No", "—", "—", "—", "Not in Phase36 scan universe today"])
                continue
            r = hd[hd["symbol"] == sym].iloc[0]
            hold_rows.append(
                [
                    sym,
                    "Yes",
                    str(r["final_action"]).replace("NEW_T1_MANUAL_REVIEW_BREADTH", "NEW_T1_MR"),
                    _fmt_num(r.get("a3_rank_score"), 3),
                    _fmt_num(r.get("close_kVND")),
                    _short_reason(r.get("final_action_reason")),
                ]
            )
        lines.append(
            _md_table(
                ["Symbol", "In scan", "final_action", "Rank", "Close", "Reason"],
                hold_rows,
            )
        )

    # --- Exits ---
    lines.append("\n## Exits & trims (A3 production)\n\n")
    if not scan_df.empty:
        for act in ("TRAIL_EXIT", "TP1_PARTIAL", "MAX_HOLD_EXIT"):
            sub = scan_df[scan_df["final_action"] == act].sort_values(
                "a3_rank_score", ascending=False, na_position="last"
            )
            if sub.empty:
                continue
            lines.append(f"### {act} ({len(sub)})\n\n")
            ex_rows = []
            for _, r in sub.iterrows():
                ex_rows.append(
                    [
                        str(r["symbol"]),
                        _fmt_num(r.get("close_kVND")),
                        _fmt_num(r.get("trail_price")),
                        _fmt_num(r.get("a3_rank_score"), 3),
                        _short_reason(r.get("final_action_reason")),
                    ]
                )
            lines.append(_md_table(["Symbol", "Close", "Trail", "Rank", "Reason"], ex_rows))

    # --- Hold / block T2 ---
    lines.append("\n## Hold T1 / block T2 adds\n\n")
    if not scan_df.empty:
        for act in ("NO_T2_BREADTH", "HOLD_T1_ONLY", "WAIT_PB"):
            sub = scan_df[scan_df["final_action"] == act].sort_values(
                "a3_rank_score", ascending=False, na_position="last"
            )
            if sub.empty:
                continue
            lines.append(f"### {act} ({len(sub)})\n\n")
            rows = [
                [
                    str(r["symbol"]),
                    _fmt_num(r.get("close_kVND")),
                    _fmt_num(r.get("a3_rank_score"), 3),
                    _short_reason(r.get("final_action_reason")),
                ]
                for _, r in sub.iterrows()
            ]
            lines.append(_md_table(["Symbol", "Close", "Rank", "Reason"], rows))

    # --- VIN ---
    if not scan_df.empty:
        vin = scan_df[scan_df["symbol"].isin(VIN_SYMBOLS)]
        if not vin.empty:
            lines.append("\n## Vingroup names in scan (distortion check)\n\n")
            lines.append(
                "> Cap-weight VNINDEX may be Vingroup-skewed in 2025–2026. "
                "Prefer breadth-based health for broad-market conclusions.\n\n"
            )
            vin_rows = [
                [
                    str(r["symbol"]),
                    str(r["final_action"]),
                    _fmt_num(r.get("a3_rank_score"), 3),
                    _fmt_num(r.get("close_kVND")),
                ]
                for _, r in vin.iterrows()
            ]
            lines.append(_md_table(["Symbol", "final_action", "Rank", "Close"], vin_rows))

    # --- Decision layer ---
    lines.append("\n## Decision layer\n\n")
    actions, risks, watch = _derive_decision_bullets(scan_df, holdings)
    lines.append("### Top 3 actions\n")
    for a in actions:
        lines.append(f"- {a}\n")
    lines.append("\n### Top 3 risks\n")
    for r in risks:
        lines.append(f"- {r}\n")
    lines.append("\n### Watchlist updates\n")
    for w in watch:
        lines.append(f"- {w}\n")

    lines.append("\n## Signals to monitor next session\n")
    lines.append("- `pct_cloud_bull_a3` vs 40% (exit defense → T2 may unlock)\n")
    lines.append("- Holdings with TRAIL_EXIT / NEW_T1_MR vs prices and trails\n")
    lines.append("- Names missing from scan universe (coverage gap)\n")
    lines.append("- VNINDEX regime flip (bear → SKIP_VNINDEX_BEAR on new T1)\n")

    lines.append("\n## If X happens → do Y\n")
    lines.append("- **Breadth ≥ 40%** → re-run scan; reassess T2 on NO_T2_BREADTH names\n")
    lines.append("- **TRAIL_EXIT persists** → execute exit discipline per A3 plan (not rank score)\n")
    lines.append("- **Approve manual T1** → size via execution layer only after review\n")
    lines.append("- **Holding still missing from CSV** → fix panel/universe before trusting portfolio coverage\n")

    lines.append("\n---\n\n")
    lines.append("**Related:** `phase36_daily_operator_report.md` (panels) · ")
    lines.append("`docs/trading/DAILY_SCAN_OPERATOR_GUIDE.md` · ")
    lines.append("`data/decision/weekly_report.md` (macro/policy weekly)\n")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("".join(lines), encoding="utf-8")

    payload: Dict[str, Any] = {
        "as_of_date": as_of,
        "generated_at": generated_at,
        "scan_csv": csv_rel,
        "n_symbols": n_symbols,
        "portfolio_state": nav_meta,
        "portfolio_nav_vnd": nav_vnd,
        "regime_bull": regime_bull,
        "pct_cloud_bull_a3": breadth,
        "pct_cloud_bull_s3": s3_breadth,
        "breadth_zone": breadth_zone,
        "final_action_counts": (
            scan_df["final_action"].value_counts().to_dict() if not scan_df.empty else {}
        ),
        "new_entry_symbols": (
            scan_df.loc[scan_df["final_action"].isin(_NEW_T1_ACTIONS), "symbol"].tolist()
            if not scan_df.empty
            else []
        ),
        "holdings": holdings,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return OUT_MD


def _derive_decision_bullets(
    scan_df: pd.DataFrame, holdings: List[str]
) -> tuple[List[str], List[str], List[str]]:
    actions: List[str] = []
    risks: List[str] = []
    watch: List[str] = []

    if scan_df.empty:
        return (
            ["Re-run Phase36 scan — output empty."],
            ["No scan data."],
            [],
        )

    zone = str(scan_df.iloc[0].get("breadth_zone", ""))
    if zone == "defense":
        risks.append("Defense breadth (<40%) with possible bull index — weak participation.")
        actions.append("No automatic NEW_T1; work manual-review queue only.")

    trail_hold = []
    if holdings:
        hd = scan_df[scan_df["symbol"].isin(holdings)]
        trail_hold = hd[hd["final_action"] == "TRAIL_EXIT"]["symbol"].tolist()
        mr_hold = hd[hd["final_action"].isin(_NEW_T1_ACTIONS)]["symbol"].tolist()
        if trail_hold:
            actions.insert(0, f"Priority exit review: {', '.join(trail_hold)} (TRAIL_EXIT).")
        if mr_hold:
            actions.append(f"Holdings flagged for manual T1 review: {', '.join(mr_hold)}.")
        missing = sorted(set(holdings) - set(hd["symbol"]))
        if missing:
            risks.append(f"Holdings not in scan: {', '.join(missing)}.")
            watch.append(f"Coverage gap: {', '.join(missing)}")

    new_syms = scan_df.loc[scan_df["final_action"].isin(_NEW_T1_ACTIONS), "symbol"].tolist()
    if new_syms:
        watch.append(f"Manual-review queue: {', '.join(new_syms)} (sort: a3_rank_score DESC).")

    plain_new = int((scan_df["final_action"] == "NEW_T1").sum())
    if plain_new == 0 and new_syms:
        risks.append("Zero plain NEW_T1 — all new entries require operator sign-off.")

    while len(actions) < 3:
        actions.append("Hold NO_T2_BREADTH names; no T2 adds until breadth improves.")
        if len(actions) >= 3:
            break
    actions = actions[:3]
    while len(risks) < 3:
        risks.append("Use final_action only for OMS — ignore S3 shadow for production.")
        if len(risks) >= 3:
            break
    risks = risks[:3]

    return actions, risks, watch


def main() -> int:
    path = resolve_scan_path()
    if path is None or not path.is_file():
        print("No Phase36 scan CSV found.", file=sys.stderr)
        return 1
    path = path.resolve()
    df = pd.read_csv(path)
    out = write_daily_scan_report(df, scan_csv_path=path)
    print(f"Wrote {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
