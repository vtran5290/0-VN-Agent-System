"""
Write consolidated Phase36 daily scan report — CEO/Operator Command Dashboard.
Reports-layer and observation-layer only.

HARD GUARDRAILS (this file NEVER touches):
  - final_action  — A3 SSOT signal; OMS and capital decisions use this only
  - a3_rank_score — review sort order only
  - OMS / DNSE routing / order_intent
  - Position sizing

Outputs:
  - data/decision/daily_scan.md
  - data/decision/daily_scan.json
  - data/research/capital_footprint/cf_annotation_observation_ledger.csv (when CF enabled)

Regenerate from existing CSV:
  .venv\\Scripts\\python.exe scripts/reporting/daily_scan_report.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
CF_OBS_LEDGER = (
    REPO / "data" / "research" / "capital_footprint" / "cf_annotation_observation_ledger.csv"
)
VIN_SYMBOLS = frozenset({"VIC", "VHM", "VRE", "VPL"})
_NEW_T1_ACTIONS = frozenset({"NEW_T1", "NEW_T1_MANUAL_REVIEW_BREADTH"})
_EXIT_ACTIONS = frozenset({"TRAIL_EXIT", "TP1_PARTIAL", "MAX_HOLD_EXIT"})

CF_OBS_LEDGER_HEADERS = [
    "scan_date", "symbol", "final_action", "current_holding_flag",
    "cf_phase_label", "cf_operator_note", "cf_event_age", "cf_event_cooldown_flag",
    "cf_breadth_regime_bucket", "close_price", "operator_action",
    "forward_5d_return", "forward_10d_return", "forward_20d_return",
    "max_drawdown_20d", "operator_comment", "hindsight_result",
]


# ── Unchanged helpers ─────────────────────────────────────────────────────────

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


def _operator_label(final_action: str) -> str:
    pair = OPERATOR_ACTION_MAP.get(final_action)
    return pair[0] if pair else final_action


def _short_reason(text: Any, max_len: int = 72) -> str:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return "—"
    s = str(text).replace("\n", " ").strip()
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


# ── Portfolio context (returns pos_df for Portfolio Command) ──────────────────

def _portfolio_context() -> Tuple[
    Optional[Dict[str, Any]], Optional[float], Optional[pd.DataFrame], List[List[str]]
]:
    """NAV + positions from portfolio_state.json SSoT (never infer NAV from positions).

    Returns (meta, nav_vnd, pos_df, pos_rows).
    pos_df is the raw positions DataFrame; pos_rows is pre-formatted for display.
    """
    state = load_portfolio_state()
    if not state:
        return None, None, None, []
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
    return (
        meta,
        nav_vnd,
        pos_df if (pos_df is not None and not pos_df.empty) else None,
        rows,
    )


# ── CIO Cockpit helpers ───────────────────────────────────────────────────────

def _collapse_section(header: str, content: str, *, expanded: bool = False) -> str:
    """Wrap a section in HTML <details>/<summary> for collapsible display."""
    open_attr = " open" if expanded else ""
    return (
        f"\n<details{open_attr}>\n"
        f"<summary><strong>{header}</strong></summary>\n\n"
        f"{content}\n"
        f"</details>\n"
    )


def _regime_one_liner(
    regime_bull: Optional[bool],
    breadth_zone: str,
    t2_permitted: bool,
    exit_n: int,
    new_t1_n: int,
) -> str:
    """Generate a single-line operator regime interpretation."""
    if regime_bull is None:
        return "Regime unknown — verify scan data before acting."
    zone_upper = (breadth_zone or "unknown").upper()
    if not regime_bull:
        return (
            f"VNINDEX BEAR + {zone_upper}: no new T1/T2; "
            f"run exit discipline on {exit_n} signal(s)."
        )
    t2_str = "T2 permitted" if t2_permitted else "T2 blocked"
    if breadth_zone == "defense":
        return (
            f"VNINDEX bull but breadth defense: selective T1 only, T2 blocked; "
            f"prioritize {exit_n} exit(s)/partials before new entries."
        )
    if breadth_zone in ("bull_broad", "broad"):
        return (
            f"VNINDEX bull + BULL_BROAD: {t2_str}; "
            f"{new_t1_n} new T1 candidate(s); {exit_n} exit signal(s) — execute exits first."
        )
    return (
        f"VNINDEX bull + {zone_upper}: {t2_str}; "
        f"{new_t1_n} new T1 candidate(s); {exit_n} exit signal(s)."
    )


def _build_forbidden_actions(
    regime_bull: Optional[bool],
    breadth_zone: str,
    t2_permitted: bool,
) -> List[str]:
    """Derive top 3 forbidden actions from current regime state."""
    forbidden: List[str] = []
    if not t2_permitted:
        forbidden.append(
            "Do NOT execute T2 adds — breadth blocked (NO_T2_BREADTH rule active)."
        )
    if regime_bull is False:
        forbidden.append("Do NOT add new T1 positions — VNINDEX regime is BEAR.")
    if breadth_zone == "defense":
        forbidden.append(
            "Do NOT approve new T1 without manual review — breadth defense zone."
        )
    forbidden.append("Do NOT use CF annotation as buy/sell trigger — research context only.")
    return forbidden[:3]


def _cf_cockpit_counts(scan_df: pd.DataFrame) -> str:
    """Compact CF annotation counts line for CIO Cockpit (CF enabled only)."""
    if scan_df.empty or "cf_annotation_active" not in scan_df.columns:
        return ""
    cf_active = scan_df["cf_annotation_active"].fillna(0)
    phase_col = (
        scan_df["cf_phase_label"]
        if "cf_phase_label" in scan_df.columns
        else pd.Series(dtype=str, index=scan_df.index)
    )
    regime_col = (
        scan_df["cf_breadth_regime_bucket"]
        if "cf_breadth_regime_bucket" in scan_df.columns
        else pd.Series(dtype=str, index=scan_df.index)
    )
    age_col = (
        scan_df["cf_event_age"].fillna(0)
        if "cf_event_age" in scan_df.columns
        else pd.Series(0, index=scan_df.index, dtype=float)
    )
    sa_bull = int(
        ((phase_col == "SUPPLY_ABSORPTION_SETUP") & (regime_col == "BULL_BROAD") & (cf_active == 1)).sum()
    )
    sa_weak = int(
        ((phase_col == "SUPPLY_ABSORPTION_SETUP") & (regime_col != "BULL_BROAD") & (cf_active == 1)).sum()
    )
    ext_age5 = int(
        ((phase_col == "EXTENSION_DISTRIBUTION_RISK") & (age_col >= 5) & (cf_active == 1)).sum()
    )
    research_only = int(
        ((cf_active == 0) & phase_col.notna() & (phase_col != "NEUTRAL") & (phase_col != "")).sum()
    )
    return (
        f"**CF active notes:** SA Bull: {sa_bull} / "
        f"SA weak-regime: {sa_weak} / "
        f"Extension age≥5: {ext_age5} / "
        f"Research-only: {research_only}"
    )


def _build_ceo_cockpit_section(
    scan_df: pd.DataFrame,
    holdings: List[str],
    regime_bull: Optional[bool],
    breadth_zone: str,
    t2_permitted: bool,
    cf_enabled: bool,
    required_actions: List[str],
) -> str:
    """Build the CIO Cockpit section — operator decision in <90 seconds."""
    new_t1_n = exit_n = trail_exit_n = tp1_n = t2_blocked_n = 0
    port_trail_n = port_tp1_n = holdings_not_in_scan_n = 0

    if not scan_df.empty:
        new_t1_n = int(scan_df["final_action"].isin(_NEW_T1_ACTIONS).sum())
        trail_exit_n = int((scan_df["final_action"] == "TRAIL_EXIT").sum())
        tp1_n = int((scan_df["final_action"] == "TP1_PARTIAL").sum())
        t2_blocked_n = int((scan_df["final_action"] == "NO_T2_BREADTH").sum())
        exit_n = (
            trail_exit_n + tp1_n + int((scan_df["final_action"] == "MAX_HOLD_EXIT").sum())
        )

    if holdings:
        if not scan_df.empty:
            scan_syms = set(scan_df["symbol"].tolist())
            holdings_not_in_scan_n = sum(1 for h in holdings if h not in scan_syms)
            hd = scan_df[scan_df["symbol"].isin(holdings)]
            port_trail_n = int((hd["final_action"] == "TRAIL_EXIT").sum())
            port_tp1_n = int((hd["final_action"] == "TP1_PARTIAL").sum())
        else:
            holdings_not_in_scan_n = len(holdings)

    one_liner = _regime_one_liner(regime_bull, breadth_zone, t2_permitted, exit_n, new_t1_n)

    if regime_bull is False:
        t1_perm = "No (BEAR regime)"
    elif breadth_zone == "defense":
        t1_perm = "Manual review only (defense)"
    else:
        t1_perm = "Yes"

    perm_rows = [
        ["New T1", t1_perm],
        ["T2 adds", "Yes" if t2_permitted else "**Blocked** (breadth <40%)"],
        ["S3 paper", "Paper shadow only (research)"],
        ["Exits", "Always execute per A3 plan"],
        ["Manual override", "Operator sign-off required"],
    ]

    count_rows: List[List[str]] = [
        ["Portfolio TRAIL_EXIT", str(port_trail_n), "⚠ Priority" if port_trail_n > 0 else ""],
        ["Portfolio TP1_PARTIAL", str(port_tp1_n), "⚠ Priority" if port_tp1_n > 0 else ""],
        [
            "Holdings NOT in scan",
            str(holdings_not_in_scan_n),
            "⚠ Verify" if holdings_not_in_scan_n > 0 else "",
        ],
        ["New T1 candidates (scan)", str(new_t1_n), ""],
        ["T2 blocked (NO_T2_BREADTH)", str(t2_blocked_n), ""],
    ]
    if cf_enabled:
        cf_active_n = (
            int(scan_df["cf_annotation_active"].sum())
            if not scan_df.empty and "cf_annotation_active" in scan_df.columns
            else 0
        )
        count_rows.append(["Active CF annotations", str(cf_active_n), "Research context only"])

    forbidden = _build_forbidden_actions(regime_bull, breadth_zone, t2_permitted)

    lines = [
        "\n## CIO Cockpit — Operator Dashboard\n\n",
        f"> {one_liner}\n\n",
        "### Permission Matrix\n\n",
        _md_table(["Action", "Status"], perm_rows),
        "\n### Action Counts\n\n",
        _md_table(["Metric", "Count", "Flag"], count_rows),
        "\n### Top 3 Required Actions\n\n",
    ]
    for a in required_actions:
        lines.append(f"- {a}\n")
    lines.append("\n### Top 3 Forbidden Actions\n\n")
    for f_act in forbidden:
        lines.append(f"- {f_act}\n")
    if cf_enabled and not scan_df.empty:
        cf_str = _cf_cockpit_counts(scan_df)
        if cf_str:
            lines.append(f"\n{cf_str}\n")

    return "".join(lines)


# ── Data Quality Exceptions ───────────────────────────────────────────────────

def _build_data_quality_exceptions(
    scan_df: pd.DataFrame,
    holdings: List[str],
    nav_vnd: Optional[float],
    cf_enabled: bool,
) -> str:
    """Returns a DQ exceptions box, or empty string if no issues."""
    issues: List[str] = []
    scan_syms = set(scan_df["symbol"].tolist()) if not scan_df.empty else set()

    not_in_scan = [h for h in holdings if h not in scan_syms]
    if not_in_scan:
        issues.append(
            f"Holdings NOT in scan universe: **{', '.join(not_in_scan)}** — verify coverage."
        )
    if not nav_vnd:
        issues.append("NAV missing — update `data/trading/live/portfolio_state.json`.")
    if not holdings:
        issues.append("No holdings on record (`data/trading/holdings.txt` empty or missing).")
    if scan_df.empty:
        issues.append("Scan DataFrame is empty — re-run Phase36 scan.")
    if cf_enabled and not scan_df.empty and "cf_phase_label" not in scan_df.columns:
        issues.append(
            "CF annotation enabled but CF columns missing — CF panel build may have failed."
        )

    if not issues:
        return ""

    lines = ["\n## ⚠ Data Quality Exceptions\n\n"]
    for issue in issues:
        lines.append(f"- {issue}\n")
    return "".join(lines)


# ── Portfolio Command ─────────────────────────────────────────────────────────

def _build_portfolio_command_section(
    scan_df: pd.DataFrame,
    holdings: List[str],
    nav_vnd: Optional[float],
    pos_df: Optional[pd.DataFrame],
    nav_meta: Optional[Dict[str, Any]],
    cf_enabled: bool,
) -> str:
    """Portfolio Command — renamed from Portfolio NAV & positions. Split into three buckets."""
    lines = ["\n## Portfolio Command\n\n"]
    lines.append(
        "**FACTS** (`data/trading/live/portfolio_state.json` — port excludes cash; "
        "NAV is user-updated, not inferred)\n\n"
    )

    if nav_vnd:
        invested = float(nav_meta.get("invested_cost_basis_vnd") or 0) if nav_meta else 0.0
        nav_is_mkt = bool(nav_meta.get("nav_is_market_value")) if nav_meta else False
        if invested and nav_vnd:
            gap = nav_vnd - invested
            gap_label = "Unrealized P&L" if nav_is_mkt else "Implied cash"
            lines.append(
                f"**NAV:** {nav_vnd:,.0f} VND · "
                f"**Cost basis:** {invested:,.0f} VND · "
                f"**{gap_label}:** {gap:,.0f} VND ({100.0 * gap / nav_vnd:.1f}%)\n\n"
            )
        else:
            lines.append(f"**NAV:** {nav_vnd:,.0f} VND\n\n")

    if not holdings:
        lines.append("_No holdings on record (`data/trading/holdings.txt`)._\n\n")

    # Build position lookup
    pos_map: Dict[str, Dict[str, Any]] = {}
    if pos_df is not None and not pos_df.empty:
        for _, pos in pos_df.iterrows():
            sym = str(pos.get("symbol") or pos.get("ticker") or "").upper()
            if not sym:
                continue
            lots = pos.get("lots")
            entry = pos.get("entry_price")
            mv_raw = pos.get("market_value_vnd")
            mv = None
            try:
                mv = float(mv_raw) if mv_raw is not None and not pd.isna(mv_raw) else None
            except (TypeError, ValueError):
                pass
            if mv is None and lots is not None and entry is not None:
                try:
                    mv = float(lots) * float(entry)
                except (TypeError, ValueError):
                    pass
            cost = None
            if lots is not None and entry is not None:
                try:
                    cost = float(lots) * float(entry)
                except (TypeError, ValueError):
                    pass
            pos_map[sym] = {
                "lots": lots,
                "entry": entry,
                "mv": mv,
                "cost": cost,
                "pct_nav": 100.0 * mv / nav_vnd if (mv and nav_vnd and nav_vnd > 0) else None,
                "unreal_pnl_pct": (
                    100.0 * (mv - cost) / cost
                    if (mv is not None and cost and cost > 0)
                    else None
                ),
            }

    # Build scan lookup
    scan_syms = set(scan_df["symbol"].tolist()) if not scan_df.empty else set()
    scan_map: Dict[str, Dict[str, Any]] = {}
    if not scan_df.empty:
        for _, row in scan_df.iterrows():
            sym = str(row["symbol"]).upper()
            cf_note = ""
            if cf_enabled and "cf_operator_note" in scan_df.columns:
                cf_note = str(row.get("cf_operator_note") or "")
            scan_map[sym] = {
                "final_action": str(row.get("final_action", "—")),
                "reason": _short_reason(row.get("final_action_reason"), 72),
                "cf_note": cf_note,
            }

    # Split into three buckets
    must_act: List[str] = []
    verify: List[str] = []
    hold_watch: List[str] = []
    for sym in sorted(holdings):
        if sym not in scan_syms:
            verify.append(sym)
        elif scan_map.get(sym, {}).get("final_action") in ("TRAIL_EXIT", "TP1_PARTIAL", "MAX_HOLD_EXIT"):
            must_act.append(sym)
        else:
            hold_watch.append(sym)

    def _row(sym: str, show_action: bool = True) -> List[str]:
        pd_ = pos_map.get(sym, {})
        lots_raw = pd_.get("lots")
        try:
            lots_str = (
                str(int(lots_raw))
                if lots_raw is not None and not pd.isna(lots_raw)
                else "—"
            )
        except (TypeError, ValueError):
            lots_str = "—"
        entry_str = _fmt_num(pd_.get("entry"), 0)
        mv = pd_.get("mv")
        mv_str = f"{mv:,.0f}" if mv else "—"
        pct_str = f"{pd_['pct_nav']:.1f}%" if pd_.get("pct_nav") is not None else "—"
        unreal_str = (
            f"{pd_['unreal_pnl_pct']:.1f}%" if pd_.get("unreal_pnl_pct") is not None else "—"
        )
        if show_action:
            sd = scan_map.get(sym, {})
            action_str = str(sd.get("final_action", "—")).replace(
                "NEW_T1_MANUAL_REVIEW_BREADTH", "NEW_T1_MR"
            )
            row = [sym, lots_str, entry_str, mv_str, pct_str, unreal_str, action_str, sd.get("reason", "—")]
            if cf_enabled:
                row.append(sd.get("cf_note", ""))
            return row
        return [sym, lots_str, entry_str, mv_str, pct_str, unreal_str]

    # --- Must act ---
    if must_act:
        lines.append("### Must Act / Review — TRAIL_EXIT / TP1_PARTIAL\n\n")
        headers = ["Symbol", "Shares", "Entry", "Mkt Value", "% NAV", "Unreal P&L%", "final_action", "Reason"]
        if cf_enabled:
            headers.append("CF Note")
        lines.append(_md_table(headers, [_row(s) for s in must_act]))
    else:
        lines.append("### Must Act / Review\n\n_No TRAIL_EXIT or TP1_PARTIAL in portfolio._\n\n")

    # --- Verify ---
    if verify:
        lines.append("\n### Verify — Not in Scan Universe\n\n")
        lines.append(
            "> ⚠ These holdings are NOT in today's Phase36 scan universe. "
            "Verify positions and scan coverage manually.\n\n"
        )
        v_headers = ["Symbol", "Shares", "Entry", "Mkt Value", "% NAV", "Unreal P&L%"]
        lines.append(_md_table(v_headers, [_row(s, show_action=False) for s in verify]))
    else:
        lines.append("\n### Verify\n\n_All holdings present in scan universe._\n\n")

    # --- Hold / watch ---
    if hold_watch:
        lines.append("\n### Hold / Watch\n\n")
        h_headers = ["Symbol", "Shares", "Entry", "Mkt Value", "% NAV", "Unreal P&L%", "final_action", "Reason"]
        if cf_enabled:
            h_headers.append("CF Note")
        lines.append(_md_table(h_headers, [_row(s) for s in hold_watch]))

    return "".join(lines)


# ── Action Register ───────────────────────────────────────────────────────────

def _build_action_register_section(
    scan_df: pd.DataFrame,
    holdings: List[str],
    nav_vnd: Optional[float],
    pos_df: Optional[pd.DataFrame],
    cf_enabled: bool,
) -> str:
    """Unified Action Register — all active items requiring operator attention."""
    # Position MV lookup
    pos_mv: Dict[str, Optional[float]] = {}
    if pos_df is not None and not pos_df.empty:
        for _, pos in pos_df.iterrows():
            sym = str(pos.get("symbol") or pos.get("ticker") or "").upper()
            mv = None
            try:
                mv_raw = pos.get("market_value_vnd")
                mv = float(mv_raw) if mv_raw is not None and not pd.isna(mv_raw) else None
            except (TypeError, ValueError):
                pass
            if mv is None:
                lots, entry = pos.get("lots"), pos.get("entry_price")
                if lots is not None and entry is not None:
                    try:
                        mv = float(lots) * float(entry)
                    except (TypeError, ValueError):
                        pass
            if sym:
                pos_mv[sym] = mv

    holdings_set = set(holdings)
    scan_syms = set(scan_df["symbol"].tolist()) if not scan_df.empty else set()

    # CF note and active lookups
    cf_note_map: Dict[str, str] = {}
    cf_active_set: set = set()
    if cf_enabled and not scan_df.empty and "cf_operator_note" in scan_df.columns:
        for _, row in scan_df.iterrows():
            sym = str(row["symbol"])
            note = str(row.get("cf_operator_note") or "")
            if note:
                cf_note_map[sym] = note
            if row.get("cf_annotation_active") == 1:
                cf_active_set.add(sym)

    register: List[Dict[str, Any]] = []

    def _mv_fmt(sym: str) -> str:
        mv = pos_mv.get(sym)
        return f"{mv:,.0f} VND" if mv else "?"

    # P1: Portfolio exits (TRAIL_EXIT, TP1_PARTIAL, MAX_HOLD_EXIT in holdings)
    if not scan_df.empty:
        for act in ("TRAIL_EXIT", "TP1_PARTIAL", "MAX_HOLD_EXIT"):
            sub = scan_df[(scan_df["final_action"] == act) & scan_df["symbol"].isin(holdings_set)]
            for _, row in sub.iterrows():
                sym = str(row["symbol"])
                mv = pos_mv.get(sym)
                if act == "TRAIL_EXIT":
                    capital = f"Exit full (~{_mv_fmt(sym)})"
                elif act == "TP1_PARTIAL":
                    capital = f"Partial ~50% (~{f'{mv/2:,.0f} VND' if mv else '?'})"
                else:
                    capital = "Exit (max hold)"
                register.append({
                    "p": 1, "symbol": sym, "source": "portfolio_exit",
                    "portfolio": "Yes", "final_action": act,
                    "op_action": _operator_label(act),
                    "reason": _short_reason(row.get("final_action_reason"), 60),
                    "capital_impact": capital, "deadline": "Today / Next open",
                    "cf_note": cf_note_map.get(sym, "") if cf_enabled else "",
                })

    # P2: Holdings NOT in scan
    for sym in sorted(holdings_set - scan_syms):
        register.append({
            "p": 2, "symbol": sym, "source": "not_in_scan",
            "portfolio": "Yes", "final_action": "—",
            "op_action": "Verify position",
            "reason": "Not in Phase36 scan universe",
            "capital_impact": "Unknown — verify", "deadline": "Investigate",
            "cf_note": cf_note_map.get(sym, "") if cf_enabled else "",
        })

    # P3: New T1 manual review candidates (from scan)
    if not scan_df.empty:
        mr_sub = scan_df[scan_df["final_action"] == "NEW_T1_MANUAL_REVIEW_BREADTH"]
        for _, row in mr_sub.iterrows():
            sym = str(row["symbol"])
            register.append({
                "p": 3, "symbol": sym, "source": "scan_new_t1",
                "portfolio": "Yes" if sym in holdings_set else "No",
                "final_action": "NEW_T1_MR",
                "op_action": "Manual review required",
                "reason": _short_reason(row.get("final_action_reason"), 60),
                "capital_impact": "+T1 size (manual review)", "deadline": "Review before open",
                "cf_note": cf_note_map.get(sym, "") if cf_enabled else "",
            })

    # P4: T2 blocked holdings (portfolio symbols with NO_T2_BREADTH)
    if not scan_df.empty:
        t2_sub = scan_df[
            (scan_df["final_action"] == "NO_T2_BREADTH") & scan_df["symbol"].isin(holdings_set)
        ]
        for _, row in t2_sub.iterrows():
            sym = str(row["symbol"])
            register.append({
                "p": 4, "symbol": sym, "source": "t2_blocked",
                "portfolio": "Yes", "final_action": "NO_T2_BREADTH",
                "op_action": "Hold — no T2 add",
                "reason": "T2 add blocked by breadth",
                "capital_impact": "No add", "deadline": "Hold",
                "cf_note": cf_note_map.get(sym, "") if cf_enabled else "",
            })

    # P5: CF-only active annotations (not already represented above)
    if cf_enabled and not scan_df.empty:
        already = {r["symbol"] for r in register}
        for sym in sorted(cf_active_set - already):
            register.append({
                "p": 5, "symbol": sym, "source": "cf_annotation",
                "portfolio": "Yes" if sym in holdings_set else "No",
                "final_action": "—",
                "op_action": "Research review",
                "reason": "CF annotation active (non-binding)",
                "capital_impact": "n/a", "deadline": "Research review",
                "cf_note": cf_note_map.get(sym, ""),
            })

    if not register:
        return "\n## Action Register\n\n_No active items requiring operator action today._\n"

    register.sort(key=lambda r: (r["p"], r["symbol"]))

    if cf_enabled:
        headers = [
            "#", "Symbol", "Source", "Portfolio", "final_action",
            "Op. Action", "Reason", "Capital Impact", "Deadline", "CF Note",
        ]
        table_rows = [
            [
                str(i + 1), r["symbol"], r["source"], r["portfolio"], r["final_action"],
                r["op_action"], r["reason"], r["capital_impact"], r["deadline"], r["cf_note"],
            ]
            for i, r in enumerate(register)
        ]
    else:
        headers = [
            "#", "Symbol", "Source", "Portfolio", "final_action",
            "Op. Action", "Reason", "Capital Impact", "Deadline",
        ]
        table_rows = [
            [
                str(i + 1), r["symbol"], r["source"], r["portfolio"], r["final_action"],
                r["op_action"], r["reason"], r["capital_impact"], r["deadline"],
            ]
            for i, r in enumerate(register)
        ]

    return (
        "\n## Action Register\n\n"
        "> Priority: **1**=Portfolio exits · **2**=Not in scan · "
        "**3**=New T1 MR · **4**=T2 blocked · **5**=CF annotation\n\n"
        + _md_table(headers, table_rows)
    )


# ── Delta section ─────────────────────────────────────────────────────────────

def _load_previous_scan_json() -> Optional[Dict[str, Any]]:
    """Load existing daily_scan.json for delta computation before overwriting it."""
    if OUT_JSON.exists():
        try:
            return json.loads(OUT_JSON.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _build_delta_section(
    scan_df: pd.DataFrame,
    prev_json: Optional[Dict[str, Any]],
    breadth_zone: str,
    t2_permitted: bool,
    cf_enabled: bool,
) -> str:
    """Improved Delta from Previous Session section."""
    if prev_json is None:
        return (
            "\n## Delta from Previous Session\n\n"
            "_No prior snapshot — first run or `data/decision/daily_scan.json` missing._\n"
        )

    changes: List[str] = []

    # New T1 symbols
    prev_new_t1 = set(prev_json.get("new_entry_symbols", []))
    curr_new_t1 = (
        set(scan_df.loc[scan_df["final_action"].isin(_NEW_T1_ACTIONS), "symbol"].tolist())
        if not scan_df.empty
        else set()
    )
    if curr_new_t1 - prev_new_t1:
        changes.append(
            f"**New actions:** NEW_T1 added: {', '.join(sorted(curr_new_t1 - prev_new_t1))}"
        )
    if prev_new_t1 - curr_new_t1:
        changes.append(
            f"**Removed actions:** NEW_T1 dropped: {', '.join(sorted(prev_new_t1 - curr_new_t1))}"
        )

    # Exit count changes
    prev_counts = prev_json.get("final_action_counts", {})
    curr_counts = (
        scan_df["final_action"].value_counts().to_dict() if not scan_df.empty else {}
    )
    for act in ("TRAIL_EXIT", "TP1_PARTIAL"):
        p, c = prev_counts.get(act, 0), curr_counts.get(act, 0)
        if p != c:
            changes.append(f"**Portfolio action change:** {act}: {p} → {c}")

    # Regime change
    prev_regime = prev_json.get("regime_bull")
    curr_regime = bool(scan_df.iloc[0].get("regime_bull", False)) if not scan_df.empty else None
    if prev_regime != curr_regime:
        ps = "BULL" if prev_regime else ("BEAR" if prev_regime is False else "unknown")
        cs = "BULL" if curr_regime else ("BEAR" if curr_regime is False else "unknown")
        changes.append(f"**Regime change:** {ps} → {cs}")

    # Breadth zone change
    prev_zone = prev_json.get("breadth_zone", "")
    if prev_zone != breadth_zone:
        changes.append(
            f"**Breadth change:** "
            f"{(prev_zone or 'unknown').upper()} → {(breadth_zone or 'unknown').upper()}"
        )

    # CF annotation count change
    if cf_enabled and not scan_df.empty and "cf_annotation_active" in scan_df.columns:
        prev_cf = prev_json.get("cf_annotation") or {}
        prev_n = prev_cf.get("n_active", 0) if isinstance(prev_cf, dict) else 0
        curr_n = int(scan_df["cf_annotation_active"].sum())
        if prev_n != curr_n:
            changes.append(
                f"**CF annotation changes:** active: {prev_n} → {curr_n}"
            )

    if not changes:
        t2_str = "permitted" if t2_permitted else "blocked"
        zone_str = (breadth_zone or "unknown").upper()
        return (
            "\n## Delta from Previous Session\n\n"
            f"No final_action changes; breadth remains **{zone_str}**, T2 remains **{t2_str}**.\n"
        )

    lines = ["\n## Delta from Previous Session\n\n"]
    for c in changes:
        lines.append(f"- {c}\n")
    return "".join(lines)


# ── CF observation ledger ─────────────────────────────────────────────────────

def _append_cf_observation_ledger(
    scan_df: pd.DataFrame,
    holdings_set: set,
    as_of_date: str,
) -> None:
    """Append CF observations to the 4-week ledger CSV (CF enabled runs only)."""
    if scan_df.empty or "cf_phase_label" not in scan_df.columns:
        return

    cf_active = (
        scan_df["cf_annotation_active"].fillna(0)
        if "cf_annotation_active" in scan_df.columns
        else pd.Series(0, index=scan_df.index)
    )
    cf_phase = scan_df["cf_phase_label"] if "cf_phase_label" in scan_df.columns else pd.Series(dtype=str)

    mask = (
        (cf_active == 1)
        | (scan_df["symbol"].isin(holdings_set) & cf_phase.notna())
        | (scan_df["final_action"].isin(_NEW_T1_ACTIONS | _EXIT_ACTIONS) & cf_phase.notna())
    )
    subset = scan_df[mask].copy()
    if subset.empty:
        return

    ledger_rows = []
    for _, row in subset.iterrows():
        sym = str(row["symbol"])
        fa = str(row.get("final_action", ""))
        ledger_rows.append({
            "scan_date": as_of_date,
            "symbol": sym,
            "final_action": fa,
            "current_holding_flag": "Y" if sym in holdings_set else "N",
            "cf_phase_label": str(row.get("cf_phase_label") or ""),
            "cf_operator_note": str(row.get("cf_operator_note") or ""),
            "cf_event_age": str(row.get("cf_event_age") or ""),
            "cf_event_cooldown_flag": str(int(row.get("cf_event_cooldown_flag") or 0)),
            "cf_breadth_regime_bucket": str(row.get("cf_breadth_regime_bucket") or ""),
            "close_price": str(row.get("close_kVND") or ""),
            "operator_action": _operator_label(fa),
            "forward_5d_return": "",
            "forward_10d_return": "",
            "forward_20d_return": "",
            "max_drawdown_20d": "",
            "operator_comment": "",
            "hindsight_result": "",
        })

    if not ledger_rows:
        return

    file_exists = CF_OBS_LEDGER.exists()
    CF_OBS_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(CF_OBS_LEDGER, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CF_OBS_LEDGER_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(ledger_rows)


# ── Main report writer ────────────────────────────────────────────────────────

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

    # Load previous JSON before we overwrite it (for delta)
    _prev_scan_json = _load_previous_scan_json()

    # ── CF annotation (non-binding, feature-flagged) ──────────────────────────
    _cf_annotation_json: Optional[Dict[str, Any]] = None
    _cf_enabled = False
    try:
        from src.trading.research.capital_footprint.annotation import (
            is_cf_annotation_enabled,
            annotate_scan_df,
            build_cf_annotation_section,
            build_cf_annotation_json,
        )
        _cf_enabled = not scan_df.empty and is_cf_annotation_enabled()
        if _cf_enabled:
            _as_of = str(scan_df.iloc[0].get("as_of_date", ""))
            scan_df = annotate_scan_df(scan_df, as_of_date=_as_of)
            _cf_annotation_json = build_cf_annotation_json(scan_df, as_of_date=_as_of)
    except Exception as _cf_exc:
        print(f"  [CF annotation] WARN: annotation failed ({_cf_exc}); continuing without it.")
        _cf_annotation_json = {"enabled": True, "error": str(_cf_exc)}

    # ── Core metrics ──────────────────────────────────────────────────────────
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

    t2_permitted = bool(
        scan_df.iloc[0].get("breadth_t2_permission", False) if not scan_df.empty else False
    )

    if scan_csv_path:
        try:
            csv_rel = scan_csv_path.resolve().relative_to(REPO.resolve()).as_posix()
        except ValueError:
            csv_rel = scan_csv_path.as_posix()
    else:
        csv_rel = "phase36_daily_scan_latest.csv"
    n_symbols = len(scan_df)

    # ── Portfolio context ─────────────────────────────────────────────────────
    nav_meta, nav_vnd, pos_df, pos_rows = _portfolio_context()

    # ── Decision bullets (for CIO Cockpit and Decision layer) ─────────────────
    required_actions, risks, watch = _derive_decision_bullets(scan_df, holdings)

    # ── Lens sections (load before rendering report) ──────────────────────────
    from src.trading.reports.distribution_risk_card import (
        build_distribution_risk_section_for_daily_scan,
    )
    drl_as_of = as_of if as_of != "n/a" else None
    _skip_lens = os.environ.get("SKIP_LENS_REFRESH", "").strip() in ("1", "true", "yes")
    drl_section, drl_warns = build_distribution_risk_section_for_daily_scan(
        as_of=drl_as_of, refresh=not _skip_lens
    )
    from src.trading.reports.rs_correction_card import build_rs_correction_section_for_daily_scan
    rs_section, rs_warns = build_rs_correction_section_for_daily_scan(
        as_of=drl_as_of,
        refresh=not _skip_lens,
        holdings=holdings,
        scan_symbols=scan_df["symbol"].tolist() if not scan_df.empty else [],
        scan_df=scan_df if not scan_df.empty else None,
    )
    from src.trading.reports.rs_c3_card import build_rs_c3_section_for_daily_scan
    c3_section, c3_warns = build_rs_c3_section_for_daily_scan(
        scan_date=drl_as_of,
        scan_df=scan_df if not scan_df.empty else None,
    )

    # ════════════════════════════════════════════════════════════════════════
    # REPORT ASSEMBLY
    # ════════════════════════════════════════════════════════════════════════

    lines: List[str] = [
        f"# Daily Scan — Phase36 A3 — as-of {as_of}\n",
        f"_Generated: {generated_at} · SSOT CSV: `{csv_rel}` · {n_symbols} symbols_\n",
        "\n**Production rule:** OMS and capital decisions use **`final_action` only**. "
        "`a3_rank_score` is review sort order only (not a buy signal).\n",
    ]

    # ── Section 1: CIO Cockpit ────────────────────────────────────────────────
    lines.append(
        _build_ceo_cockpit_section(
            scan_df, holdings, regime_bull, breadth_zone,
            t2_permitted, _cf_enabled, required_actions,
        )
    )

    # ── Section 2: Data Quality Exceptions (near top) ─────────────────────────
    dq = _build_data_quality_exceptions(scan_df, holdings, nav_vnd, _cf_enabled)
    if dq:
        lines.append(dq)

    # ── Section 3: Portfolio Command (promoted above A3 board) ────────────────
    lines.append(
        _build_portfolio_command_section(
            scan_df, holdings, nav_vnd, pos_df, nav_meta, _cf_enabled
        )
    )

    # ── Section 4: Action Register ────────────────────────────────────────────
    lines.append(
        _build_action_register_section(scan_df, holdings, nav_vnd, pos_df, _cf_enabled)
    )

    # ── Section 5: Market regime & breadth ───────────────────────────────────
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
        ["T2 permission", "Yes" if t2_permitted else "Blocked"],
        [
            "Plain NEW_T1 count",
            str(int((scan_df["final_action"] == "NEW_T1").sum()) if not scan_df.empty else 0),
        ],
    ]
    lines.append(_md_table(["Metric", "Value"], gate_rows))
    if breadth_zone == "defense":
        lines.append(
            "\n**INTERPRETATION:** Breadth &lt;40% → defense posture. "
            "No automatic new T1; manual review on flagged names; T2 adds blocked.\n"
        )

    # ── Sections 6–8: Collapsed lens sections ─────────────────────────────────
    lines.append(_collapse_section("Distribution Risk Lens", drl_section))
    lines.append(_collapse_section("RS Correction Lens", rs_section))
    lines.append(
        _collapse_section(
            "RS C3 Lens — review-ranking only; OOS IC near zero", c3_section
        )
    )

    # ── Section 9: CF Annotation Details (collapsed, CF-enabled only) ─────────
    if _cf_enabled and not scan_df.empty:
        try:
            from src.trading.research.capital_footprint.annotation import (
                build_cf_annotation_section,
            )
            cf_detail = build_cf_annotation_section(scan_df)
            lines.append(
                _collapse_section(
                    "CF Annotation Details (research only, non-binding)", cf_detail
                )
            )
        except Exception:
            pass

    # ════════════════════════════════════════════════════════════════════════
    # APPENDIX
    # ════════════════════════════════════════════════════════════════════════

    # --- final_action summary ---
    lines.append("\n## final_action summary\n\n")
    if scan_df.empty:
        lines.append("_No scan rows._\n")
    else:
        cnt_rows = [
            [act, str(n), _operator_label(str(act))]
            for act, n in scan_df["final_action"].value_counts().items()
        ]
        lines.append(_md_table(["final_action", "Count", "Operator label"], cnt_rows))

    # --- New entry candidates ---
    lines.append("\n## New entry candidates (review sort)\n\n")
    if scan_df.empty:
        lines.append("_None._\n")
    else:
        ranked = scan_df[scan_df["final_action"].isin(_NEW_T1_ACTIONS)].copy()
        if ranked.empty:
            lines.append("_No NEW_T1 or NEW_T1_MANUAL_REVIEW_BREADTH today._\n")
        else:
            if "a3_rank_score" in ranked.columns:
                ranked = ranked.sort_values(
                    ["final_action", "a3_rank_score", "symbol"],
                    ascending=[True, False, True], na_position="last",
                )
            elif "pct_cloud_bull_a3" in ranked.columns:
                ranked = ranked.sort_values(
                    ["final_action", "pct_cloud_bull_a3", "symbol"],
                    ascending=[True, False, True], na_position="last",
                )
            elif "recommendation" in ranked.columns:
                ranked = ranked.sort_values(
                    ["final_action", "recommendation", "symbol"],
                    ascending=[True, True, True], na_position="last",
                )
            else:
                ranked = ranked.sort_values(["final_action", "symbol"], na_position="last")

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
                cand_rows.append([
                    str(i), str(r["symbol"]),
                    str(r["final_action"]).replace("NEW_T1_MANUAL_REVIEW_BREADTH", "NEW_T1_MR"),
                    _fmt_num(r.get("close_kVND")), _fmt_num(r.get("a3_rank_score"), 3),
                    _fmt_num(r.get("ed_score"), 3), str(r.get("s3_lead_bucket") or "—"),
                    "Yes" if r.get("s3_fresh_lead_flag") else "No",
                    str(r.get("a3_rank_reason") or "—"),
                    pb_cell, tp1_cell, trail_cell,
                ])
            lines.append(
                _md_table(
                    ["#", "Symbol", "final_action", "Close", "Rank", "ED", "S3 lead",
                     "S3 fresh", "Rank reason", "Trigger", "TP1", "Trail"],
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
            lines.append(
                "\n**Why (typical):** A3 cloud breakout; regime bull; "
                "breadth defense → T1 with operator review; T2 blocked.\n"
            )
            detail_rows = [
                [str(r["symbol"]), _short_reason(r.get("final_action_reason"), 100)]
                for _, r in ranked.iterrows()
            ]
            lines.append("\n### Per-symbol final_action_reason\n\n")
            lines.append(_md_table(["Symbol", "Reason"], detail_rows))

    # --- Portfolio holdings (appendix — full join) ---
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
            hold_rows.append([
                sym, "Yes",
                str(r["final_action"]).replace("NEW_T1_MANUAL_REVIEW_BREADTH", "NEW_T1_MR"),
                _fmt_num(r.get("a3_rank_score"), 3),
                _fmt_num(r.get("close_kVND")),
                _short_reason(r.get("final_action_reason")),
            ])
        lines.append(
            _md_table(["Symbol", "In scan", "final_action", "Rank", "Close", "Reason"], hold_rows)
        )

    # --- Exits & trims ---
    lines.append("\n## Exits & trims (A3 production)\n\n")
    if not scan_df.empty:
        for act in ("TRAIL_EXIT", "TP1_PARTIAL", "MAX_HOLD_EXIT"):
            sub = scan_df[scan_df["final_action"] == act].copy()
            if "a3_rank_score" in sub.columns:
                sub = sub.sort_values("a3_rank_score", ascending=False, na_position="last")
            elif "pct_cloud_bull_a3" in sub.columns:
                sub = sub.sort_values("pct_cloud_bull_a3", ascending=False, na_position="last")
            else:
                sub = sub.sort_values("symbol", na_position="last")
            if sub.empty:
                continue
            lines.append(f"### {act} ({len(sub)})\n\n")
            ex_rows = [
                [
                    str(r["symbol"]), _fmt_num(r.get("close_kVND")),
                    _fmt_num(r.get("trail_price")), _fmt_num(r.get("a3_rank_score"), 3),
                    _short_reason(r.get("final_action_reason")),
                ]
                for _, r in sub.iterrows()
            ]
            lines.append(_md_table(["Symbol", "Close", "Trail", "Rank", "Reason"], ex_rows))

    # --- Hold T1 / block T2 ---
    lines.append("\n## Hold T1 / block T2 adds\n\n")
    if not scan_df.empty:
        for act in ("NO_T2_BREADTH", "HOLD_T1_ONLY", "WAIT_PB"):
            sub = scan_df[scan_df["final_action"] == act].copy()
            if "a3_rank_score" in sub.columns:
                sub = sub.sort_values("a3_rank_score", ascending=False, na_position="last")
            elif "pct_cloud_bull_a3" in sub.columns:
                sub = sub.sort_values("pct_cloud_bull_a3", ascending=False, na_position="last")
            else:
                sub = sub.sort_values("symbol", na_position="last")
            if sub.empty:
                continue
            lines.append(f"### {act} ({len(sub)})\n\n")
            rows_act = [
                [
                    str(r["symbol"]), _fmt_num(r.get("close_kVND")),
                    _fmt_num(r.get("a3_rank_score"), 3),
                    _short_reason(r.get("final_action_reason")),
                ]
                for _, r in sub.iterrows()
            ]
            lines.append(_md_table(["Symbol", "Close", "Rank", "Reason"], rows_act))

    # --- VIN distortion check ---
    if not scan_df.empty:
        vin = scan_df[scan_df["symbol"].isin(VIN_SYMBOLS)]
        if not vin.empty:
            lines.append("\n## Vingroup names in scan (distortion check)\n\n")
            lines.append(
                "> Cap-weight VNINDEX may be Vingroup-skewed in 2025–2026. "
                "Prefer breadth-based health for broad-market conclusions.\n\n"
            )
            vin_rows = [
                [str(r["symbol"]), str(r["final_action"]),
                 _fmt_num(r.get("a3_rank_score"), 3), _fmt_num(r.get("close_kVND"))]
                for _, r in vin.iterrows()
            ]
            lines.append(_md_table(["Symbol", "final_action", "Rank", "Close"], vin_rows))

    # --- Group Rotation ---
    try:
        from scripts.research.group_rotation.report_section import render_group_rotation_context_md
        lines.append("\n")
        lines.append(render_group_rotation_context_md())
    except Exception as exc:
        lines.append(
            f"\n## Group Rotation Context (dashboard only)\n\n- WARN: not rendered ({exc})\n"
        )

    # --- Decision layer (retained for backward compatibility) ---
    lines.append("\n## Decision layer\n\n")
    lines.append("### Top 3 actions\n")
    for a in required_actions:
        lines.append(f"- {a}\n")
    lines.append("\n### Top 3 risks\n")
    for r in risks:
        lines.append(f"- {r}\n")
    lines.append("\n### Watchlist updates\n")
    for w in watch:
        lines.append(f"- {w}\n")

    # --- Delta from Previous Session (improved) ---
    lines.append(
        _build_delta_section(scan_df, _prev_scan_json, breadth_zone, t2_permitted, _cf_enabled)
    )

    # --- Signals to monitor / If X → do Y ---
    lines.append("\n## Signals to monitor next session\n")
    lines.append("- `pct_cloud_bull_a3` vs 40% (exit defense → T2 may unlock)\n")
    lines.append("- Holdings with TRAIL_EXIT / NEW_T1_MR vs prices and trails\n")
    lines.append("- Names missing from scan universe (coverage gap)\n")
    lines.append("- VNINDEX regime flip (bear → SKIP_VNINDEX_BEAR on new T1)\n")

    lines.append("\n## If X happens → do Y\n")
    lines.append("- **Breadth ≥ 40%** → re-run scan; reassess T2 on NO_T2_BREADTH names\n")
    lines.append(
        "- **TRAIL_EXIT persists** → execute exit discipline per A3 plan (not rank score)\n"
    )
    lines.append("- **Approve manual T1** → size via execution layer only after review\n")
    lines.append(
        "- **Holding still missing from CSV** → fix panel/universe before trusting portfolio coverage\n"
    )

    lines.append("\n---\n\n")
    lines.append("**Related:** `phase36_daily_operator_report.md` (panels) · ")
    lines.append("`docs/trading/DAILY_SCAN_OPERATOR_GUIDE.md` · ")
    lines.append("`data/decision/weekly_report.md` (macro/policy weekly)\n")

    # ── Write markdown ────────────────────────────────────────────────────────
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("".join(lines), encoding="utf-8")

    # ── Write JSON ────────────────────────────────────────────────────────────
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
    from src.trading.reports.rs_correction_card import load_rs_correction_latest
    rs_data, _ = load_rs_correction_latest()
    if rs_data:
        payload["rs_correction_lens"] = {
            "method_version": rs_data.get("method_version"),
            "anchor": rs_data.get("anchor"),
            "n_outperform_rs_gt_0": rs_data.get("n_outperform_rs_gt_0"),
            "n_leader_rs_ge_3": rs_data.get("n_leader_rs_ge_3"),
            "leaders_top10": (rs_data.get("leaders_top25") or [])[:10],
        }
    if _cf_annotation_json is not None:
        payload["cf_annotation"] = _cf_annotation_json

    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── CF observation ledger (only when CF enabled) ──────────────────────────
    if _cf_enabled and as_of != "n/a":
        try:
            _append_cf_observation_ledger(scan_df, set(holdings), as_of)
        except Exception as _ledger_exc:
            print(f"  [CF ledger] WARN: ledger append failed ({_ledger_exc})")

    return OUT_MD


# ── Decision layer helper ─────────────────────────────────────────────────────

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


# ── Entry point ───────────────────────────────────────────────────────────────

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
