"""Cloud Daily Report — operator decision support for A3/S3 strategy.

Read-only: reads CSVs, writes HTML/MD/JSON only.
No external JS/CSS dependencies.
No auto orders. No S3 live capital.

Includes VNINDEX Distribution Risk Lens v1.2 (Section G) — context only; does not change final_action.
"""
from __future__ import annotations

import html
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.trading.reports.distribution_risk_card import (
    load_distribution_risk_latest,
    refresh_distribution_risk_for_reports,
    render_distribution_risk_html,
    render_distribution_risk_md,
)

REPO = Path(__file__).resolve().parents[3]
SCAN_DIR = REPO / "data/research/portfolio_optimization/missing_work"
INTRADAY_DIR = REPO / "data/research/intraday"
REPORTS_DIR = REPO / "data/research/reports"
HOLDINGS_PATH = REPO / "data/trading/holdings.txt"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(v: Any, digits: int = 2) -> str:
    """Format numeric value; return '—' for None/NaN."""
    if v is None:
        return "—"
    try:
        fv = float(v)
        if math.isnan(fv) or math.isinf(fv):
            return "—"
        return f"{fv:.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def _badge(text: str, color: str) -> str:
    """Return HTML badge span."""
    return f'<span class="badge bg-{color}">{_esc(text)}</span>'


def _esc(x: Any) -> str:
    """HTML-escape a value."""
    return html.escape(str(x if x is not None else ""))


def _col(df: pd.DataFrame, col: str, default: Any = None) -> pd.Series:
    """Get column from DataFrame or return series of defaults."""
    if col in df.columns:
        return df[col]
    return pd.Series([default] * len(df), index=df.index)


def _get(row: dict, key: str, default: Any = None) -> Any:
    """Safe dict get."""
    val = row.get(key, default)
    if val is None:
        return default
    try:
        if isinstance(val, float) and math.isnan(val):
            return default
    except TypeError:
        pass
    return val


def normalize_bool(value: Any) -> "bool | None":
    """Normalize bool-like values to Python True/False/None.

    Handles: bool, numpy.bool_, int 0/1, strings 'true'/'false'/'1'/'0'/'yes'/'no'.
    Returns None for NaN, None, or unrecognized values.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "1", "yes"):
            return True
        if v in ("false", "0", "no"):
            return False
        return None
    try:
        fv = float(value)
        if math.isnan(fv):
            return None
        return fv != 0.0
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

CSS = """
body { font-family: system-ui, 'Segoe UI', sans-serif; background: #0f1419; color: #e7ecf3; margin: 0; padding: 1rem; }
.container { max-width: 1280px; margin: 0 auto; }
.card { background: #1a2332; border-radius: 12px; padding: 1rem; margin: 0.75rem 0; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; margin: 2px; }
.bg-green { background: #1a3a1a; color: #5edd5e; border: 1px solid #2d6a2d; }
.bg-amber { background: #3a2800; color: #ffc107; border: 1px solid #6a4e00; }
.bg-red { background: #3a1010; color: #f77; border: 1px solid #6a2020; }
.bg-gray { background: #1e2a38; color: #8ab4f8; border: 1px solid #2d3f57; }
.section-title { font-size: 1rem; font-weight: 700; color: #8ab4f8; border-bottom: 1px solid #253040; padding-bottom: 4px; margin: 1rem 0 0.5rem; }
.card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 0.75rem; }
.action-card { border-left: 4px solid; }
.action-card.green { border-color: #4caf50; }
.action-card.amber { border-color: #ffc107; }
.action-card.red { border-color: #f44336; }
.action-list { margin: 0.3rem 0; padding-left: 1.2rem; }
.action-list li { margin: 0.25rem 0; font-size: 0.9rem; }
table { border-collapse: collapse; width: 100%; font-size: 0.82rem; margin: 0.5rem 0; }
th, td { border: 1px solid #253040; padding: 0.28rem 0.45rem; text-align: left; vertical-align: top; }
th { background: #243044; font-weight: 600; position: sticky; top: 0; }
tr:nth-child(even) td { background: rgba(255,255,255,0.02); }
.row-green td:first-child { border-left: 3px solid #4caf50; }
.row-amber td:first-child { border-left: 3px solid #ffc107; }
.row-red td:first-child { border-left: 3px solid #f44336; }
.row-gray td:first-child { border-left: 3px solid #555; }
.warn-banner { background: #3a0f0f; border: 2px solid #c0392b; border-radius: 8px; padding: 0.75rem 1rem; margin: 0.5rem 0; color: #f7a0a0; font-weight: 600; }
.preview-banner { background: #3a2800; border: 2px solid #c9a227; border-radius: 8px; padding: 0.75rem 1rem; margin: 0.5rem 0; color: #ffc107; font-weight: 600; }
.s3-section { border: 1px dashed #4a3000; background: #111005; }
details summary { cursor: pointer; color: #8ab4f8; font-weight: 600; padding: 0.3rem 0; }
.meta { color: #5a7090; font-size: 0.78rem; }
.pending { color: #ffc107; font-style: italic; }
.footnote { font-size: 0.78rem; color: #8a9bb5; margin-top: 0.3rem; }
"""

# ---------------------------------------------------------------------------
# classify_operator_action
# ---------------------------------------------------------------------------

_A3_SSOT_FINAL_ACTIONS = frozenset({
    "NEW_T1",
    "NEW_T1_MANUAL_REVIEW_BREADTH",
    "ADD_T2",
    "NO_T2_BREADTH",
    "WAIT_PB",
    "HOLD_T1_ONLY",
    "TP1_PARTIAL",
    "TRAIL_EXIT",
    "MAX_HOLD_EXIT",
    "SKIP_LIQUIDITY",
    "SKIP_VNINDEX_BEAR",
    "WATCH_ONLY",
})


def classify_operator_action(row: dict, mode: str) -> dict:
    """Return dict with action_group, operator_action, reason."""
    final_action = str(_get(row, "final_action", "")).strip()
    s3_shadow = str(_get(row, "s3_shadow_action", "")).strip()
    is_intraday = mode in ("pre-lunch", "pre-atc")

    planning_action = final_action
    if is_intraday:
        wbfa_plan = str(_get(row, "would_be_final_action", "")).strip()
        if wbfa_plan:
            planning_action = wbfa_plan

    # S3 shadow applies only to watch-only / non-planning rows — not production T1/T2 SSOT actions
    if s3_shadow == "PAPER_S3_SHADOW" and planning_action in (
        "",
        "WATCH_ONLY",
        "INTRADAY_PREVIEW",
    ):
        return {
            "action_group": "S3_PAPER",
            "operator_action": "PAPER_ONLY",
            "reason": "s3_shadow_action=PAPER_S3_SHADOW",
        }

    if is_intraday:
        wbfa = planning_action
        # Map would_be to action_group
        EOD_GROUP_MAP = {
            "NEW_T1": "NEW_T1",
            "NEW_T1_MANUAL_REVIEW_BREADTH": "MANUAL_REVIEW_T1",
            "ADD_T2": "ADD_T2",
            "NO_T2_BREADTH": "T2_BLOCKED",
            "WAIT_PB": "ADD_T2",
            "HOLD_T1_ONLY": "HOLD",
            "TP1_PARTIAL": "EXIT_REVIEW",
            "TRAIL_EXIT": "EXIT_REVIEW",
            "MAX_HOLD_EXIT": "EXIT_REVIEW",
            "SKIP_LIQUIDITY": "SKIP",
            "SKIP_VNINDEX_BEAR": "SKIP",
            "WATCH_ONLY": "SKIP",
        }
        action_group = EOD_GROUP_MAP.get(wbfa, "UNKNOWN")
        # Intraday operator_action is never PREPARE_NEXT_OPEN
        if action_group in ("SKIP", "UNKNOWN", "T2_BLOCKED"):
            operator_action = "NO_ACTION"
        else:
            operator_action = "REVIEW_MANUAL"
        return {
            "action_group": action_group,
            "operator_action": operator_action,
            "reason": f"intraday preview; would_be={wbfa}",
        }

    # EOD mapping (report layer: manual review wording only — no order instructions)
    _EOD_MAP = {
        "NEW_T1":                         ("NEW_T1",           "REVIEW_MANUAL"),
        "NEW_T1_MANUAL_REVIEW_BREADTH":   ("MANUAL_REVIEW_T1", "REVIEW_MANUAL"),
        "ADD_T2":                         ("ADD_T2",           "ADD_T2"),
        "NO_T2_BREADTH":                  ("T2_BLOCKED",       "ADD_BLOCKED_BY_BREADTH"),
        "WAIT_PB":                        ("ADD_T2",           "WAIT_FOR_PULLBACK"),
        "HOLD_T1_ONLY":                   ("HOLD",             "HOLD_ONLY"),
        "TP1_PARTIAL":                    ("EXIT_REVIEW",      "TAKE_PARTIAL"),
        "TRAIL_EXIT":                     ("EXIT_REVIEW",      "REVIEW_TRAIL_EXIT"),
        "MAX_HOLD_EXIT":                  ("EXIT_REVIEW",      "REVIEW_TRAIL_EXIT"),
        "SKIP_LIQUIDITY":                 ("SKIP",             "NO_ACTION"),
        "SKIP_VNINDEX_BEAR":              ("SKIP",             "NO_ACTION"),
        "WATCH_ONLY":                     ("SKIP",             "WATCH_ONLY"),
    }
    if final_action in _EOD_MAP:
        ag, oa = _EOD_MAP[final_action]
    else:
        ag, oa = "UNKNOWN", "NO_ACTION"

    return {
        "action_group": ag,
        "operator_action": oa,
        "reason": f"final_action={final_action}",
    }


# ---------------------------------------------------------------------------
# load_inputs
# ---------------------------------------------------------------------------

def load_inputs(mode: str, scan_path: Path | None = None) -> dict:
    """Load scan_df, intraday_df, intraday_meta, holdings, prev_json, warnings."""
    warnings_list: list[str] = []
    files_used: list[str] = []

    # ---- Resolve mode ----
    if mode == "auto":
        intraday_csv = INTRADAY_DIR / "phase36_intraday_scan_latest.csv"
        if intraday_csv.exists():
            mtime = datetime.fromtimestamp(intraday_csv.stat().st_mtime, tz=timezone.utc)
            age_h = (datetime.now(tz=timezone.utc) - mtime).total_seconds() / 3600
            resolved_mode = "pre-lunch" if age_h <= 6 else "eod"
        else:
            resolved_mode = "eod"
    else:
        resolved_mode = mode

    # ---- EOD scan (SSOT: phase36_daily_scan_latest.csv) ----
    ssot_scan = SCAN_DIR / "phase36_daily_scan_latest.csv"
    _scan_candidates: list[Path] = []
    if scan_path:
        _scan_candidates.append(Path(scan_path))
    if ssot_scan.exists():
        _scan_candidates.append(ssot_scan)
    for cand in (
        SCAN_DIR / "phase36_daily_scan_sample.csv",
        SCAN_DIR / "phase35_daily_scan_sample.csv",
        SCAN_DIR / "phase34_daily_scan_sample.csv",
    ):
        if cand not in _scan_candidates:
            _scan_candidates.append(cand)

    scan_df = pd.DataFrame()
    scan_file_used: Path | None = None
    for cand in _scan_candidates:
        if cand.exists():
            try:
                scan_df = pd.read_csv(cand)
                scan_file_used = cand
                files_used.append(str(cand.relative_to(REPO)))
                if cand != ssot_scan and ssot_scan.exists():
                    warnings_list.append(
                        f"scan_path override: using {cand.name} instead of phase36_daily_scan_latest.csv"
                    )
                break
            except Exception as e:
                warnings_list.append(f"Failed to read {cand.name}: {e}")

    if scan_df.empty:
        warnings_list.append("scan_file_missing: no EOD scan CSV found")
    elif scan_file_used and scan_file_used.resolve() != ssot_scan.resolve() and ssot_scan.exists():
        warnings_list.append(
            "NEEDS_REVIEW: EOD scan not loaded from phase36_daily_scan_latest.csv"
        )

    # ---- Intraday ----
    intraday_df = pd.DataFrame()
    intraday_meta: dict = {}

    if resolved_mode in ("pre-lunch", "pre-atc"):
        intraday_csv = INTRADAY_DIR / "phase36_intraday_scan_latest.csv"
        intraday_meta_path = INTRADAY_DIR / "phase36_intraday_scan_latest_meta.json"
        if intraday_csv.exists():
            try:
                intraday_df = pd.read_csv(intraday_csv)
                files_used.append(str(intraday_csv.relative_to(REPO)))
            except Exception as e:
                warnings_list.append(f"Failed to read intraday CSV: {e}")
        else:
            warnings_list.append("intraday CSV not found")
        if intraday_meta_path.exists():
            try:
                intraday_meta = json.loads(intraday_meta_path.read_text(encoding="utf-8"))
                files_used.append(str(intraday_meta_path.relative_to(REPO)))
            except Exception as e:
                warnings_list.append(f"Failed to read intraday meta: {e}")

    # ---- Portfolio state (SSoT for NAV + current positions) ----
    from src.trading.portfolio_state import (
        PORTFOLIO_STATE_PATH,
        get_current_nav_vnd,
        load_current_positions,
        load_portfolio_state,
    )
    port_state = load_portfolio_state()
    nav_vnd: float | None = None
    positions_df: pd.DataFrame = pd.DataFrame()
    positions_source: str = "missing"
    portfolio_state_path_str: str | None = None

    portfolio_as_of_date: str | None = port_state.get("as_of_date") if port_state else None

    if not port_state:
        warnings_list.append(
            "Portfolio state file missing — NAV/current port context not available."
        )
    else:
        try:
            portfolio_state_path_str = str(PORTFOLIO_STATE_PATH.relative_to(REPO))
        except ValueError:
            portfolio_state_path_str = str(PORTFOLIO_STATE_PATH)
        files_used.append(portfolio_state_path_str)
        nav_vnd = get_current_nav_vnd(port_state)
        if nav_vnd is None:
            warnings_list.append("NAV missing or invalid in portfolio state.")

    positions_df, positions_source = load_current_positions(port_state)

    if positions_source == "missing":
        warnings_list.append(
            "Current positions file missing — duplicate-position check not performed."
        )
    elif "holdings.txt" in positions_source:
        warnings_list.append(
            "Using legacy holdings.txt fallback — consider updating portfolio_state.json positions_path."
        )
    else:
        if positions_source not in files_used:
            files_used.append(positions_source)

    # Symbol list (backward compat; extracted from positions_df)
    holdings: list[str] = []
    if not positions_df.empty and "symbol" in positions_df.columns:
        holdings = positions_df["symbol"].dropna().astype(str).str.upper().tolist()

    # ---- Previous report JSON ----
    prev_json: dict | None = None
    prev_path = REPORTS_DIR / "cloud_daily_report_latest.json"
    if prev_path.exists():
        try:
            prev_json = json.loads(prev_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "mode": resolved_mode,
        "scan_df": scan_df,
        "intraday_df": intraday_df,
        "intraday_meta": intraday_meta,
        "holdings": holdings,
        "nav_vnd": nav_vnd,
        "positions_df": positions_df,
        "positions_source": positions_source,
        "portfolio_state_path": portfolio_state_path_str,
        "portfolio_as_of_date": portfolio_as_of_date,
        "prev_json": prev_json,
        "warnings": warnings_list,
        "scan_path": str(scan_file_used.relative_to(REPO)) if scan_file_used else None,
        "files_used": files_used,
    }


# ---------------------------------------------------------------------------
# HTML/MD helpers
# ---------------------------------------------------------------------------

def _html_table(headers: list[str], rows: list[list[str]], row_classes: list[str] | None = None) -> str:
    th_html = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    rows_html = ""
    for i, row_cells in enumerate(rows):
        cls = ""
        if row_classes and i < len(row_classes):
            cls = f' class="{row_classes[i]}"'
        tds = "".join(f"<td>{cell}</td>" for cell in row_cells)
        rows_html += f"<tr{cls}>{tds}</tr>"
    return f"<table><thead><tr>{th_html}</tr></thead><tbody>{rows_html}</tbody></table>"


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    head = "| " + " | ".join(headers) + " |"
    body = "\n".join("| " + " | ".join(str(c) for c in row) + " |" for row in rows)
    return f"{head}\n{sep}\n{body}"


# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------

def build_report(mode: str, inputs: dict, ts: datetime) -> tuple[str, str, dict]:
    """Build HTML, MD, and JSON. Returns (html_str, md_str, json_payload)."""
    scan_df: pd.DataFrame = inputs["scan_df"]
    intraday_df: pd.DataFrame = inputs["intraday_df"]
    intraday_meta: dict = inputs.get("intraday_meta", {})
    holdings: list[str] = inputs.get("holdings", [])
    nav_vnd: float | None = inputs.get("nav_vnd")
    positions_df: pd.DataFrame = inputs.get("positions_df", pd.DataFrame())
    positions_source: str = inputs.get("positions_source", "missing")
    portfolio_state_path: str | None = inputs.get("portfolio_state_path")
    portfolio_as_of_date: str | None = inputs.get("portfolio_as_of_date")
    prev_json: dict | None = inputs.get("prev_json")
    warnings_list: list[str] = list(inputs.get("warnings", []))
    files_used: list[str] = list(inputs.get("files_used", []))
    scan_path_str: str | None = inputs.get("scan_path")
    is_intraday = mode in ("pre-lunch", "pre-atc")

    drl_data = inputs.get("distribution_risk_lens")
    drl_warns = list(inputs.get("distribution_risk_warnings") or [])
    if drl_data is None:
        drl_data, load_warns = load_distribution_risk_latest()
        drl_warns.extend(load_warns)
    for w in drl_warns:
        if w not in warnings_list:
            warnings_list.append(w)

    ts_str = ts.strftime("%Y-%m-%d %H:%M UTC")
    ts_file = ts.strftime("%Y%m%d_%H%M")

    # ---- Safety checks ----
    if not intraday_df.empty and is_intraday:
        if "auto_order_allowed" in intraday_df.columns:
            bad_mask = intraday_df["auto_order_allowed"].apply(lambda v: normalize_bool(v) is True)
            bad = intraday_df[bad_mask]
            if not bad.empty:
                syms_bad = list(bad["symbol"]) if "symbol" in bad.columns else list(bad.index)
                warnings_list.append(
                    f"auto_order_allowed=True found in intraday rows: {syms_bad}"
                )
        if "final_action" in intraday_df.columns:
            bad2 = intraday_df[intraday_df["final_action"] != "INTRADAY_PREVIEW"]
            if not bad2.empty:
                symbols_bad = list(bad2["symbol"]) if "symbol" in bad2.columns else []
                warnings_list.append(
                    f"intraday final_action != INTRADAY_PREVIEW for: {symbols_bad}"
                )

    if not scan_df.empty and "s3_no_real_order_flag" in scan_df.columns:
        bad_s3_mask = scan_df["s3_no_real_order_flag"].apply(lambda v: normalize_bool(v) is False)
        bad_s3 = scan_df[bad_s3_mask]
        if not bad_s3.empty:
            syms = list(bad_s3["symbol"]) if "symbol" in bad_s3.columns else []
            warnings_list.append(f"s3_no_real_order_flag=False for: {syms}")

    # ---- Signal-today with numeric prices → data integrity ----
    if not scan_df.empty and "a3_signal_today" in scan_df.columns:
        for _, srow in scan_df.iterrows():
            if normalize_bool(srow.get("a3_signal_today")) is True:
                for price_col in ("pb_trigger_price", "tp1_price", "trail_price"):
                    val = srow.get(price_col)
                    if val is not None:
                        try:
                            fv = float(val)
                            if not math.isnan(fv):
                                sym = srow.get("symbol", "?")
                                warnings_list.append(
                                    f"[NEEDS_REVIEW] a3_signal_today=True but "
                                    f"{price_col}={fv:.4f} is non-null for {sym} — expected NaN"
                                )
                        except (TypeError, ValueError):
                            pass

    # ---- Intraday quote-quality ----
    if is_intraday and intraday_meta:
        qc = intraday_meta.get("intraday_quote_coverage_pct")
        if qc is not None:
            try:
                qc_f = float(qc)
                pct = qc_f * 100 if qc_f <= 1.0 else qc_f
                if pct < 100:
                    warnings_list.append(f"intraday_quote_coverage_pct < 100%: {pct:.1f}%")
            except (TypeError, ValueError):
                pass
        mq = intraday_meta.get("missing_quote_count")
        if mq is not None:
            try:
                if float(mq) > 0:
                    warnings_list.append(f"missing_quote_count={int(float(mq))}")
            except (TypeError, ValueError):
                pass
        stale_keys = [k for k in intraday_meta if "stale" in k.lower()]
        for sk in stale_keys:
            sv = intraday_meta[sk]
            if sv and str(sv).lower() not in ("false", "0", "none", ""):
                warnings_list.append(f"stale data: {sk}={sv}")

    if scan_df.empty:
        warnings_list.append("scan_file_missing: report may be incomplete")

    # Check for unknown final_action
    if not scan_df.empty and "final_action" in scan_df.columns:
        known = {
            "NEW_T1", "NEW_T1_MANUAL_REVIEW_BREADTH", "ADD_T2", "NO_T2_BREADTH",
            "WAIT_PB", "HOLD_T1_ONLY", "TP1_PARTIAL", "TRAIL_EXIT", "MAX_HOLD_EXIT",
            "SKIP_LIQUIDITY", "SKIP_VNINDEX_BEAR", "WATCH_ONLY", "INTRADAY_PREVIEW",
        }
        unk_mask = ~scan_df["final_action"].isin(known)
        unk_actions = scan_df.loc[unk_mask, "final_action"].unique().tolist()
        if unk_actions:
            warnings_list.append(f"unexpected final_action values: {unk_actions}")

    # ---- Macro context from scan ----
    def _macro_val(col: str, default: Any = None) -> Any:
        if not scan_df.empty and col in scan_df.columns:
            vals = scan_df[col].dropna()
            if not vals.empty:
                return vals.iloc[0]
        return default

    regime_bull = normalize_bool(_macro_val("regime_bull", intraday_meta.get("regime_bull")))
    breadth_zone = str(_macro_val("breadth_zone", intraday_meta.get("breadth_zone", ""))).lower()
    pct_cloud_bull_a3 = _macro_val("pct_cloud_bull_a3", intraday_meta.get("last_breadth"))
    pct_cloud_bull_s3 = _macro_val("pct_cloud_bull_s3", intraday_meta.get("last_s3_breadth"))
    breadth_t1_perm = _macro_val("breadth_t1_permission", True)
    breadth_t2_perm = _macro_val("breadth_t2_permission", True)

    try:
        breadth_pct = float(pct_cloud_bull_a3) if pct_cloud_bull_a3 is not None else None
    except (TypeError, ValueError):
        breadth_pct = None

    panel_asof = str(_macro_val("as_of_date", intraday_meta.get("panel_asof", "")))
    scan_date = panel_asof[:10] if panel_asof else ""

    # ---- Classify all scan rows ----
    classified: list[dict] = []
    if not scan_df.empty:
        for _, row in scan_df.iterrows():
            rd = row.to_dict()
            ca = classify_operator_action(rd, mode)
            rd["_action_group"] = ca["action_group"]
            rd["_operator_action"] = ca["operator_action"]
            rd["_reason"] = ca["reason"]
            classified.append(rd)

    def _filter(group: str) -> list[dict]:
        return [r for r in classified if r["_action_group"] == group]

    new_t1_rows = _filter("NEW_T1")
    manual_t1_rows = _filter("MANUAL_REVIEW_T1")
    add_t2_rows = _filter("ADD_T2")
    t2_blocked_rows = _filter("T2_BLOCKED")
    hold_rows = _filter("HOLD")
    exit_rows = _filter("EXIT_REVIEW")
    skip_rows = _filter("SKIP")
    s3_rows = _filter("S3_PAPER")
    unknown_rows = _filter("UNKNOWN")

    # Intraday rows classified
    intraday_classified: list[dict] = []
    if not intraday_df.empty:
        for _, row in intraday_df.iterrows():
            rd = row.to_dict()
            ca = classify_operator_action(rd, mode)
            rd["_action_group"] = ca["action_group"]
            rd["_operator_action"] = ca["operator_action"]
            intraday_classified.append(rd)

    # Sort all T1 candidates together: rank DESC → liq_warn_T1 OK first →
    # s3_fresh_lead_flag True first → symbol ASC.  action_group does NOT take precedence.
    def _sort_key_t1(r: dict):
        rank = float(_get(r, "a3_rank_score", 0) or 0)
        liq_ok = 0 if str(_get(r, "liq_warn_T1", "")).strip().upper() == "OK" else 1
        s3_fresh = 0 if normalize_bool(_get(r, "s3_fresh_lead_flag", False)) is True else 1
        sym = str(_get(r, "symbol", "")).upper()
        return (-rank, liq_ok, s3_fresh, sym)

    new_t1_rows_combined = sorted(
        [r for r in classified if r["_action_group"] in ("NEW_T1", "MANUAL_REVIEW_T1")],
        key=_sort_key_t1,
    )

    # ---- New entry symbols ----
    new_entry_symbols = [_get(r, "symbol", "") for r in new_t1_rows_combined]

    # ---- Counts ----
    counts = {
        "new_t1": sum(1 for r in classified if r["_action_group"] == "NEW_T1"),
        "manual_review_t1": sum(1 for r in classified if r["_action_group"] == "MANUAL_REVIEW_T1"),
        "add_t2": sum(1 for r in classified if r["_action_group"] == "ADD_T2"),
        "no_t2_breadth": sum(1 for r in classified if r["_action_group"] == "T2_BLOCKED"),
        "hold": sum(1 for r in classified if r["_action_group"] == "HOLD"),
        "exit_review": sum(1 for r in classified if r["_action_group"] == "EXIT_REVIEW"),
        "s3_paper": sum(1 for r in classified if r["_action_group"] == "S3_PAPER"),
        "intraday_candidates": len(intraday_classified),
    }

    # ---- Warnings: if unknown actions found ----
    if unknown_rows:
        unk_syms = [_get(r, "symbol", "?") for r in unknown_rows]
        warnings_list.append(f"unexpected final_action for symbols: {unk_syms}")

    # ---- Delta vs prev ----
    delta: dict = {}
    if prev_json:
        prev_symbols = set(prev_json.get("new_entry_symbols", []))
        curr_symbols = set(new_entry_symbols)
        added = sorted(curr_symbols - prev_symbols)
        removed = sorted(prev_symbols - curr_symbols)
        delta["new_candidates_added"] = added
        delta["new_candidates_removed"] = removed
        prev_zone = prev_json.get("breadth_zone", "")
        if prev_zone != breadth_zone:
            delta["breadth_zone_changed"] = {"from": prev_zone, "to": breadth_zone}
        prev_regime = prev_json.get("regime_bull")
        if prev_regime != regime_bull:
            delta["regime_changed"] = {"from": prev_regime, "to": regime_bull}
        prev_counts = prev_json.get("counts", {})
        count_delta = {}
        for k in counts:
            if counts[k] != prev_counts.get(k):
                count_delta[k] = {"from": prev_counts.get(k), "to": counts[k]}
        if count_delta:
            delta["count_changes"] = count_delta

    # ---- Report status ----
    if drl_data and drl_data.get("report_status") == "NEEDS_REVIEW":
        warnings_list.append(
            "distribution_risk_lens: PRIMARY_VIEW_STALE or lens NEEDS_REVIEW — see freshness table"
        )

    has_safety_warning = any(
        "auto_order_allowed" in w.lower() or
        "s3_no_real_order_flag" in w.lower() or
        "scan_file_missing" in w.lower() or
        "PRIMARY_VIEW_STALE" in w or
        "NEEDS_REVIEW" in w
        for w in warnings_list
    )
    if has_safety_warning:
        report_status = "NEEDS_REVIEW"
    elif is_intraday:
        report_status = "PREVIEW_OK"
    else:
        report_status = "OK"

    # ---- Top actions ----
    top_actions: list[dict] = []
    for r in new_t1_rows_combined[:5]:
        top_actions.append({
            "symbol": _get(r, "symbol"),
            "action_group": r["_action_group"],
            "operator_action": r["_operator_action"],
            "rank_score": _get(r, "a3_rank_score"),
        })

    # ========================================================================
    # BUILD HTML
    # ========================================================================

    def _section(title: str, content: str, cls: str = "card") -> str:
        return f'<div class="{cls}"><div class="section-title">{_esc(title)}</div>{content}</div>'

    parts: list[str] = []
    parts.append(f"<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>"
                 f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
                 f"<title>Cloud Daily Report — {_esc(ts_str)}</title>"
                 f"<style>{CSS}</style></head><body><div class='container'>")

    # ---- Section A: Header strip ----
    mode_label = {"eod": "EOD", "pre-lunch": "PRE-LUNCH PREVIEW", "pre-atc": "PRE-ATC PREVIEW", "auto": "AUTO"}.get(mode, mode.upper())
    mode_color = "green" if mode == "eod" else "amber"

    regime_label = "BULL" if regime_bull is True else ("BEAR" if regime_bull is False else "UNKNOWN")
    regime_color = "green" if regime_bull is True else ("red" if regime_bull is False else "gray")

    bz_upper = breadth_zone.upper() if breadth_zone else "UNKNOWN"
    bz_color = {"normal": "green", "caution": "amber", "defense": "red"}.get(breadth_zone, "gray")

    t1_perm_label = "OK" if breadth_t1_perm else "BLOCKED"
    t1_perm_color = "green" if breadth_t1_perm else "red"
    if not breadth_t1_perm and counts.get("manual_review_t1", 0) > 0:
        t1_perm_label = "MANUAL REVIEW"
        t1_perm_color = "amber"

    t2_perm_label = "OK" if breadth_t2_perm else "BLOCKED"
    t2_perm_color = "green" if breadth_t2_perm else "red"

    if nav_vnd is not None:
        nav_label = f"NAV: {nav_vnd/1e9:.2f}bn VND"
        nav_color = "gray"
    else:
        nav_label = "NAV: unknown"
        nav_color = "amber"

    header_badges = (
        _badge(f"Mode: {mode_label}", mode_color) +
        _badge(nav_label, nav_color) +
        _badge(f"VNINDEX: {regime_label}", regime_color) +
        _badge(f"Breadth: {bz_upper}", bz_color) +
        _badge(f"T1: {t1_perm_label}", t1_perm_color) +
        _badge(f"T2: {t2_perm_label}", t2_perm_color)
    )
    if is_intraday:
        header_badges += _badge("PREVIEW ONLY | AUTO ORDER OFF | IF_CLOSE_NOW", "amber")

    pos_src_label = _esc(positions_source) if positions_source != "missing" else "missing"
    header_html = (
        f"<div class='card'>"
        f"<h2 style='margin:0 0 0.5rem;'>Cloud Daily Report &mdash; {_esc(ts_str)}</h2>"
        f"{header_badges}"
        f"<div class='footnote' style='margin-top:0.5rem;'>Daily scan is source of truth. AFL is visual cockpit.</div>"
        f"<div class='footnote'>Port = stock holdings only (excludes cash). "
        f"NAV is user-updated; not inferred from positions. "
        f"Positions source: <code>{pos_src_label}</code></div>"
    )
    if is_intraday:
        header_html += (
            "<div class='footnote'>Intraday preview only. "
            "final_action=INTRADAY_PREVIEW. would_be_final_action is planning only.</div>"
        )
    header_html += "</div>"
    parts.append(header_html)

    # ---- Warnings banner ----
    if warnings_list:
        warn_items = "".join(f"<li>{_esc(w)}</li>" for w in warnings_list)
        parts.append(f"<div class='warn-banner'>⚠ Warnings:<ul>{warn_items}</ul></div>")

    # ---- Section B: Decision cards ----
    # ACTION NOW
    action_now_items: list[str] = []
    if new_t1_rows_combined:
        n_new = counts["new_t1"]
        n_manual = counts["manual_review_t1"]
        if n_new:
            action_now_items.append(f"Review {n_new} A3 NEW_T1 candidate(s) for manual checklist")
        if n_manual:
            mr_syms = ", ".join(
                _get(r, "symbol", "?") for r in sorted(manual_t1_rows, key=_sort_key_t1)
            )
            action_now_items.append(
                f"Prepare manual review checklist for next-open candidates: {mr_syms} (breadth gate)"
            )
        pending_rows = [
            r for r in new_t1_rows_combined
            if normalize_bool(_get(r, "a3_signal_today", False)) is True
        ]
        if pending_rows and not is_intraday:
            pend_syms = ", ".join(_get(r, "symbol", "?") for r in pending_rows)
            action_now_items.append(
                f"Review next-open candidate(s): {pend_syms} (pending levels)"
            )

    # Intraday-only signal preview (EOD covered via new_t1_rows_combined above)
    if is_intraday:
        signal_today_rows = [
            r for r in intraday_classified
            if normalize_bool(_get(r, "a3_signal_today", False)) is True
        ]
        if signal_today_rows:
            sym_list = ", ".join(_get(r, "symbol", "?") for r in signal_today_rows)
            action_now_items.append(
                f"Review would-be A3 candidate(s) if close now; wait for EOD confirmation. ({sym_list})"
            )

    exit_holdings = [r for r in exit_rows if _get(r, "symbol", "") in holdings]
    if exit_holdings:
        sym_list = ", ".join(_get(r, "symbol", "?") for r in exit_holdings)
        action_now_items.append(f"Review exit-risk holdings: {sym_list}")

    action_now_li = "".join(f"<li>{_esc(item)}</li>" for item in action_now_items) if action_now_items else "<li><em>No immediate actions required</em></li>"
    action_now_card = (
        f"<div class='card action-card green'>"
        f"<strong style='color:#5edd5e;'>ACTION NOW</strong>"
        f"<ul class='action-list'>{action_now_li}</ul>"
        f"</div>"
    )

    # WATCH/PREPARE
    watch_items: list[str] = []
    if is_intraday:
        would_be_new = [r for r in intraday_classified if r.get("_action_group") in ("NEW_T1", "MANUAL_REVIEW_T1")]
        if would_be_new:
            watch_items.append(f"{len(would_be_new)} would-be NEW_T1 if close now")
    watch_items.append(f"S3 paper setups: {counts['s3_paper']}")
    watch_items.append(f"T2 candidates (ADD_T2 + WAIT_PB): {counts['add_t2']}")

    watch_li = "".join(f"<li>{_esc(item)}</li>" for item in watch_items)
    watch_card = (
        f"<div class='card action-card amber'>"
        f"<strong style='color:#ffc107;'>WATCH / PREPARE</strong>"
        f"<ul class='action-list'>{watch_li}</ul>"
        f"</div>"
    )

    # DO NOT DO
    dont_items: list[str] = []
    if breadth_pct is not None and breadth_pct < 0.40:
        dont_items.append(f"Do not add T2 (breadth < 40%: {breadth_pct*100:.1f}%)")
    elif not breadth_t2_perm:
        dont_items.append("Do not add T2 (T2 permission blocked)")
    dont_items.append("Do not trade S3 as live capital")
    if is_intraday:
        dont_items.append("Do not use intraday preview as order source")

    # New T1 symbols already in holdings
    dup_holdings = [_get(r, "symbol", "") for r in new_t1_rows_combined if _get(r, "symbol", "") in holdings]
    if dup_holdings:
        dont_items.append(f"Do not duplicate held positions: {', '.join(dup_holdings)}")
    dont_items.append("Do not base orders on AFL visuals")

    dont_li = "".join(f"<li>{_esc(item)}</li>" for item in dont_items)
    dont_card = (
        f"<div class='card action-card red'>"
        f"<strong style='color:#f77;'>DO NOT DO</strong>"
        f"<ul class='action-list'>{dont_li}</ul>"
        f"</div>"
    )

    parts.append(
        f"<div class='section-title'>B. Decision Summary</div>"
        f"<div class='card-grid'>{action_now_card}{watch_card}{dont_card}</div>"
    )

    # ---- Section C: A3 Action Board ----
    c_parts = ['<div class="section-title">C. A3 Action Board</div>']

    # Group 1: New T1
    if new_t1_rows_combined:
        c_parts.append("<strong>Group 1: New T1 Candidates</strong>")
        headers_t1 = ["Symbol", "Action", "Rank", "Close", "Signal timing", "PB trigger", "TP1", "Trail", "Liquidity", "S3 lead", "Sector L4", "Note"]
        rows_t1 = []
        row_cls_t1 = []
        for r in new_t1_rows_combined:
            sym = _get(r, "symbol", "?")
            fa = _get(r, "final_action", "")
            rank = _fmt(_get(r, "a3_rank_score"))
            close = _fmt(_get(r, "close_kVND"))
            sig_timing = _esc(str(_get(r, "a3_planned_entry_timing", "—")))

            sig_today = normalize_bool(_get(r, "a3_signal_today", False))
            if sig_today is True:
                pb = '<span class="pending">pending*</span>'
                tp1 = '<span class="pending">pending*</span>'
                trail = '<span class="pending">pending*</span>'
                note = (
                    "Signal confirmed at today&#39;s close; planned fill is next session open. "
                    "Entry levels are pending until the next-open fill price is known."
                )
            else:
                pb = _fmt(_get(r, "pb_trigger_price"))
                tp1 = _fmt(_get(r, "tp1_price"))
                trail = _fmt(_get(r, "trail_price"))
                note = ""

            liq = _esc(str(_get(r, "liq_warn_T1", "OK")))
            s3_lead = _esc(str(_get(r, "s3_lead_bucket", "none")))
            sector = _esc(str(_get(r, "sector_l4", "—")))
            cls_str = "row-green" if r["_action_group"] == "NEW_T1" else "row-amber"
            rows_t1.append([_esc(sym), _esc(str(fa)), rank, close, sig_timing, pb, tp1, trail, liq, s3_lead, sector, note])
            row_cls_t1.append(cls_str)
        c_parts.append(_html_table(headers_t1, rows_t1, row_cls_t1))
        c_parts.append(
            '<p class="footnote">* Signal confirmed at today\'s close; planned fill is next session open. '
            'Entry levels are pending until the next-open fill price is known.</p>'
        )

    # Group 2: T2/pullback
    t2_all = add_t2_rows + t2_blocked_rows
    if t2_all:
        c_parts.append("<strong>Group 2: T2 / Pullback Candidates</strong>")
        headers_t2 = ["Symbol", "Action", "Reason", "Close", "Rank"]
        rows_t2 = []
        row_cls_t2 = []
        for r in t2_all:
            sym = _get(r, "symbol", "?")
            fa = _get(r, "final_action", r.get("would_be_final_action", ""))
            reason = _get(r, "final_action_reason", "")
            close = _fmt(_get(r, "close_kVND"))
            rank = _fmt(_get(r, "a3_rank_score"))
            cls_str = "row-amber" if r["_action_group"] == "ADD_T2" else "row-red"
            rows_t2.append([_esc(str(sym)), _esc(str(fa)), _esc(str(reason)), close, rank])
            row_cls_t2.append(cls_str)
        c_parts.append(_html_table(headers_t2, rows_t2, row_cls_t2))

    # Group 3: Exits
    if exit_rows:
        c_parts.append("<strong>Group 3: Exits</strong>")
        headers_ex = ["Symbol", "Action", "Close", "Trail", "Reason"]
        rows_ex = []
        for r in exit_rows:
            sym = _get(r, "symbol", "?")
            fa = _get(r, "final_action", "")
            close = _fmt(_get(r, "close_kVND"))
            trail = _fmt(_get(r, "trail_price"))
            reason = _get(r, "final_action_reason", "")
            rows_ex.append([_esc(str(sym)), _esc(str(fa)), close, trail, _esc(str(reason))])
        c_parts.append(_html_table(headers_ex, rows_ex, ["row-red"] * len(rows_ex)))

    # Group 4: Hold only (top 10)
    if hold_rows:
        c_parts.append("<strong>Group 4: Hold Only</strong>")
        headers_h = ["Symbol", "Close", "Rank", "Reason"]
        rows_h = []
        for r in hold_rows[:10]:
            sym = _get(r, "symbol", "?")
            close = _fmt(_get(r, "close_kVND"))
            rank = _fmt(_get(r, "a3_rank_score"))
            reason = _get(r, "final_action_reason", "")
            rows_h.append([_esc(str(sym)), close, rank, _esc(str(reason))])
        c_parts.append(_html_table(headers_h, rows_h, ["row-gray"] * len(rows_h)))
        if len(hold_rows) > 10:
            c_parts.append(f'<p class="footnote">+ {len(hold_rows)-10} more in appendix</p>')

    parts.append('<div class="card">' + "".join(c_parts) + "</div>")

    # ---- Section D: Portfolio Overlay ----
    d_parts = ['<div class="section-title">D. Portfolio Overlay</div>']
    d_parts.append(
        f'<p class="footnote">Port = stock holdings only (excludes cash). '
        f'NAV is user-updated independently. '
        f'Source: <code>{_esc(positions_source)}</code></p>'
    )
    if not holdings:
        d_parts.append('<p class="meta">Current positions missing or empty — skipping overlay.</p>')
    else:
        scan_sym_map = {_get(r, "symbol", ""): r for r in classified}
        # Build position detail map from positions_df
        pos_detail: dict[str, dict] = {}
        if not positions_df.empty and "symbol" in positions_df.columns:
            for _, pr in positions_df.iterrows():
                s = str(pr.get("symbol", "")).upper()
                pos_detail[s] = pr.to_dict()

        has_lots = any("lots" in d for d in pos_detail.values())
        has_entry = any("entry_price" in d for d in pos_detail.values())
        headers_port = ["In Scan?", "Symbol", "A3 Action", "Close kVND", "Dist to Trail", "Dist to TP1", "Operator Action"]
        if has_lots:
            headers_port.insert(2, "Lots")
        if has_entry:
            headers_port.insert(3 if has_lots else 2, "Entry kVND")

        rows_port = []
        row_cls_port = []

        def _dist(price: Any, ref: Any) -> str:
            try:
                p, rr = float(price), float(ref)
                if math.isnan(p) or math.isnan(rr) or rr == 0:
                    return "—"
                return f"{((p - rr) / rr * 100):.1f}%"
            except (TypeError, ValueError):
                return "—"

        for sym in holdings:
            r = scan_sym_map.get(sym)
            pd_row = pos_detail.get(sym, {})
            lots_str = _fmt(pd_row.get("lots"), 0) if has_lots else None
            # entry_price in raw VND → convert to kVND for display
            ep = pd_row.get("entry_price")
            entry_str = _fmt(float(ep) / 1000.0 if ep is not None else None) if has_entry else None

            if r is None:
                base_row = ["NO", _esc(sym)]
                if has_lots:
                    base_row.append(lots_str or "—")
                if has_entry:
                    base_row.append(entry_str or "—")
                base_row += ["NOT IN SCAN", "—", "—", "—", "VERIFY"]
                rows_port.append(base_row)
                row_cls_port.append("row-amber")
            else:
                fa = _get(r, "final_action", "")
                close = _get(r, "close_kVND")
                trail = _get(r, "trail_price")
                tp1 = _get(r, "tp1_price")
                dist_trail = _dist(close, trail)
                dist_tp1 = _dist(close, tp1)
                oa = _esc(r["_operator_action"])
                cls_str = "row-red" if r["_action_group"] == "EXIT_REVIEW" else "row-gray"
                base_row = ["YES", _esc(sym)]
                if has_lots:
                    base_row.append(lots_str or "—")
                if has_entry:
                    base_row.append(entry_str or "—")
                base_row += [_esc(str(fa)), _fmt(close), dist_trail, dist_tp1, oa]
                rows_port.append(base_row)
                row_cls_port.append(cls_str)
        d_parts.append(_html_table(headers_port, rows_port, row_cls_port))
    parts.append('<div class="card">' + "".join(d_parts) + "</div>")

    # ---- Section E: Intraday Preview Board ----
    if is_intraday:
        e_parts = ['<div class="section-title">E. Intraday Preview Board</div>']
        e_parts.append(
            '<div class="preview-banner">PREVIEW ONLY — no auto orders — '
            'would_be_final_action is planning only</div>'
        )
        e_parts.append(
            '<div class="preview-banner">'
            'auto_order_allowed = False for all rows. '
            'AUTO ORDER OFF. IF_CLOSE_NOW signal only.</div>'
        )

        # Meta info
        session_phase = intraday_meta.get("session_phase", "UNKNOWN")
        quote_cov = intraday_meta.get("intraday_quote_coverage_pct", None)
        missing_q = intraday_meta.get("missing_quote_count", "?")
        quoted_count = intraday_meta.get("quoted_symbols_count", "?")
        scan_count = intraday_meta.get("scan_symbols_count", "?")
        e_parts.append(
            f'<p class="meta">Session phase: {_esc(str(session_phase))} | '
            f'Quote coverage: {_fmt(quote_cov, 1) if quote_cov is not None else "?"} | '
            f'Quoted: {quoted_count}/{scan_count} | Missing quotes: {missing_q}</p>'
        )

        # VNINDEX
        vni = intraday_meta.get("vnindex", {})
        if vni:
            vni_eod = vni.get("vnindex_eod_close")
            vni_intra = vni.get("vnindex_intraday_close")
            vni_changed = vni.get("vnindex_regime_changed", False)
            e_parts.append(
                f'<p class="meta">VNINDEX EOD: {_fmt(vni_eod, 2)} | '
                f'Intraday: {_fmt(vni_intra, 2)} | '
                f'Regime changed: {vni_changed}</p>'
            )

        # Table
        if not intraday_df.empty:
            headers_intra = ["Symbol", "would_be", "auto_order", "data_quality", "session_phase"]
            rows_intra = []
            row_cls_intra = []
            for r in intraday_classified:
                sym = _get(r, "symbol", "?")
                wbfa = _get(r, "would_be_final_action", "—")
                auto_ord = _get(r, "auto_order_allowed", False)
                dq = _get(r, "intraday_data_quality", "—")
                sp = _get(r, "session_phase", "—")
                auto_ord_str = str(auto_ord)
                cls_str = "row-red" if str(auto_ord).lower() == "true" else "row-gray"
                rows_intra.append([_esc(str(sym)), _esc(str(wbfa)), _esc(auto_ord_str), _esc(str(dq)), _esc(str(sp))])
                row_cls_intra.append(cls_str)
            e_parts.append(_html_table(headers_intra, rows_intra, row_cls_intra))
        else:
            e_parts.append('<p class="meta">No intraday rows.</p>')

        parts.append('<div class="card">' + "".join(e_parts) + "</div>")

    # ---- Section F: S3 Radar ----
    f_parts = ['<div class="section-title">F. S3 Radar</div>']
    f_parts.append('<p class="footnote" style="color:#ffc107;">S3 is paper-shadow only. Do not trade as live capital.</p>')
    if s3_rows:
        headers_s3 = ["Symbol", "S3 action", "GK5", "s3_top100_adv", "S3 lead bucket", "A3 link", "s3_no_real_order_flag"]
        rows_s3 = []
        for r in s3_rows:
            sym = _get(r, "symbol", "?")
            s3a = _get(r, "s3_shadow_action", "")
            gk5 = _fmt(_get(r, "s3_gk5"))
            top100 = _get(r, "s3_top100_adv", "—")
            lead_b = _get(r, "s3_lead_bucket", "none")
            a3_link = _get(r, "a3_active", "")
            no_real = _get(r, "s3_no_real_order_flag", True)
            rows_s3.append([_esc(str(sym)), _esc(str(s3a)), gk5, _esc(str(top100)),
                            _esc(str(lead_b)), _esc(str(a3_link)), _esc(str(no_real))])
        f_parts.append(_html_table(headers_s3, rows_s3, ["row-gray"] * len(rows_s3)))
    else:
        f_parts.append('<p class="meta">No S3 paper-shadow candidates.</p>')
    parts.append('<div class="card s3-section">' + "".join(f_parts) + "</div>")

    # ---- Section G: Market context ----
    g_parts = ['<div class="section-title">G. Market / Breadth / Risk</div>']
    sector_stress = 0
    liq_warn = 0
    if not scan_df.empty:
        if "sector_l4_stress_flag" in scan_df.columns:
            sector_stress = int(scan_df["sector_l4_stress_flag"].isin(["OK", "UNKNOWN"]).sum() - len(scan_df))
            # Actually count non-OK and non-UNKNOWN
            sector_stress = int((~scan_df["sector_l4_stress_flag"].isin(["OK", "UNKNOWN"])).sum())
        if "liq_warn_T1" in scan_df.columns:
            liq_warn = int((scan_df["liq_warn_T1"] != "OK").sum())

    quote_cov_str = ""
    stale_str = ""
    if is_intraday:
        qc = intraday_meta.get("intraday_quote_coverage_pct")
        quote_cov_str = f"{_fmt(qc, 3)}" if qc is not None else "?"
        stale_keys = [k for k in intraday_meta if "stale" in k.lower()]
        stale_str = "; ".join(f"{k}={intraday_meta[k]}" for k in stale_keys)

    kv_rows = [
        ["VNINDEX regime", regime_label],
        ["A3 breadth %", f"{_fmt(pct_cloud_bull_a3, 4)}" if pct_cloud_bull_a3 is not None else "—"],
        ["S3 breadth %", f"{_fmt(pct_cloud_bull_s3, 4)}" if pct_cloud_bull_s3 is not None else "—"],
        ["Breadth zone", bz_upper],
        ["T1 permission", t1_perm_label],
        ["T2 permission", t2_perm_label],
        ["Sector L4 stress count", str(sector_stress)],
        ["Liquidity warnings", str(liq_warn)],
    ]
    if is_intraday:
        kv_rows.append(["Quote coverage", quote_cov_str])
        if stale_str:
            kv_rows.append(["Stale data", stale_str])

    kv_html = "<table><tbody>"
    for k, v in kv_rows:
        kv_html += f"<tr><th style='width:220px;'>{_esc(k)}</th><td>{_esc(v)}</td></tr>"
    kv_html += "</tbody></table>"
    g_parts.append(kv_html)
    g_parts.append(
        '<p class="footnote">Breadth &lt;40% blocks T2 only. '
        'VNINDEX bear blocks new T1. '
        'Sector L4 = dashboard warning only.</p>'
    )
    if drl_data:
        g_parts.append(render_distribution_risk_html(drl_data))
    parts.append('<div class="card">' + "".join(g_parts) + "</div>")

    # ---- Section H: Delta ----
    h_parts = ['<div class="section-title">H. Delta vs Previous</div>']
    if prev_json:
        if delta.get("new_candidates_added"):
            h_parts.append(f"<p>New candidates added: <strong>{', '.join(delta['new_candidates_added'])}</strong></p>")
        if delta.get("new_candidates_removed"):
            h_parts.append(f"<p>Candidates removed: <strong>{', '.join(delta['new_candidates_removed'])}</strong></p>")
        if delta.get("breadth_zone_changed"):
            bz_ch = delta["breadth_zone_changed"]
            h_parts.append(f"<p>Breadth zone changed: {_esc(str(bz_ch.get('from')))} → {_esc(str(bz_ch.get('to')))}</p>")
        if delta.get("regime_changed"):
            rc = delta["regime_changed"]
            h_parts.append(f"<p>Regime changed: {_esc(str(rc.get('from')))} → {_esc(str(rc.get('to')))}</p>")
        if delta.get("count_changes"):
            cc_rows = [[k, str(v.get("from")), str(v.get("to"))] for k, v in delta["count_changes"].items()]
            h_parts.append(_html_table(["Metric", "Previous", "Current"], cc_rows))
        if not any(delta.values()):
            h_parts.append('<p class="meta">No changes from previous report.</p>')
    else:
        h_parts.append('<p class="meta">No previous report found — first run.</p>')
    parts.append('<div class="card">' + "".join(h_parts) + "</div>")

    # ---- Section I: Appendix (collapsible) ----
    i_parts = ['<div class="section-title">I. Appendix</div>']
    i_parts.append("<details><summary>Full scan table (click to expand)</summary>")
    if not scan_df.empty:
        cols_show = [c for c in scan_df.columns if not c.startswith("_")][:30]
        app_headers = list(cols_show)
        app_rows = []
        for _, row in scan_df[cols_show].iterrows():
            app_rows.append([_esc(str(row[c])) for c in cols_show])
        i_parts.append(_html_table(app_headers, app_rows))
    else:
        i_parts.append('<p class="meta">No scan data.</p>')
    i_parts.append("</details>")
    i_parts.append("<details><summary>Files used</summary><ul>")
    for f in files_used:
        i_parts.append(f"<li>{_esc(f)}</li>")
    i_parts.append("</ul></details>")
    parts.append('<div class="card">' + "".join(i_parts) + "</div>")

    parts.append("</div></body></html>")
    html_str = "\n".join(parts)

    # ========================================================================
    # BUILD MD
    # ========================================================================

    md_parts: list[str] = []
    md_parts.append(f"# Cloud Daily Report — {ts_str}")
    nav_md = f"{nav_vnd/1e9:.2f}bn VND" if nav_vnd is not None else "unknown"
    pos_src_md = positions_source if positions_source != "missing" else "missing"
    md_parts.append(
        f"\n**Mode:** {mode_label} | **VNINDEX:** {regime_label} | "
        f"**Breadth:** {bz_upper} | **T1:** {t1_perm_label} | **T2:** {t2_perm_label} | "
        f"**NAV:** {nav_md} | **Positions:** {pos_src_md}"
    )

    if is_intraday:
        md_parts.append("\n> PREVIEW ONLY | AUTO ORDER OFF | IF_CLOSE_NOW")
        md_parts.append("> Intraday preview only. final_action=INTRADAY_PREVIEW. would_be_final_action is planning only.")

    md_parts.append("\n> Daily scan is source of truth. AFL is visual only.")

    if warnings_list:
        md_parts.append("\n## Warnings")
        for w in warnings_list:
            md_parts.append(f"- {w}")

    md_parts.append("\n## B. Decision Summary")
    md_parts.append("\n### ACTION NOW")
    for item in action_now_items:
        md_parts.append(f"- {item}")
    if not action_now_items:
        md_parts.append("- No immediate actions required")

    md_parts.append("\n### WATCH / PREPARE")
    for item in watch_items:
        md_parts.append(f"- {item}")

    md_parts.append("\n### DO NOT DO")
    for item in dont_items:
        md_parts.append(f"- {item}")

    md_parts.append("\n## C. A3 Action Board")

    if new_t1_rows_combined:
        md_parts.append("\n### Group 1: New T1 Candidates")
        t1_md_rows = []
        for r in new_t1_rows_combined:
            sig_today = normalize_bool(_get(r, "a3_signal_today", False))
            if sig_today is True:
                pb = "pending*"
                tp1_v = "pending*"
                trail_v = "pending*"
                note = (
                    "Signal confirmed at today's close; planned fill is next session open. "
                    "Entry levels are pending until the next-open fill price is known."
                )
            else:
                pb = _fmt(_get(r, "pb_trigger_price"))
                tp1_v = _fmt(_get(r, "tp1_price"))
                trail_v = _fmt(_get(r, "trail_price"))
                note = ""
            t1_md_rows.append([
                str(_get(r, "symbol", "?")),
                str(_get(r, "final_action", "")),
                _fmt(_get(r, "a3_rank_score")),
                _fmt(_get(r, "close_kVND")),
                pb, tp1_v, trail_v, note,
            ])
        md_parts.append(_md_table(["Symbol", "Action", "Rank", "Close", "PB", "TP1", "Trail", "Note"], t1_md_rows))
        md_parts.append(
            "\n*Signal confirmed at today's close; planned fill is next session open. "
            "Entry levels are pending until the next-open fill price is known.*"
        )

    if t2_all:
        md_parts.append("\n### Group 2: T2 / Pullback")
        t2_md_rows = [[str(_get(r, "symbol")), str(_get(r, "final_action")), _fmt(_get(r, "close_kVND")), _fmt(_get(r, "a3_rank_score"))] for r in t2_all]
        md_parts.append(_md_table(["Symbol", "Action", "Close", "Rank"], t2_md_rows))

    if exit_rows:
        md_parts.append("\n### Group 3: Exits")
        ex_md_rows = [[str(_get(r, "symbol")), str(_get(r, "final_action")), _fmt(_get(r, "close_kVND")), _fmt(_get(r, "trail_price")), str(_get(r, "final_action_reason", ""))] for r in exit_rows]
        md_parts.append(_md_table(["Symbol", "Action", "Close", "Trail", "Reason"], ex_md_rows))

    md_parts.append("\n## G. Market Context")
    md_parts.append(f"- VNINDEX regime: {regime_label}")
    md_parts.append(f"- A3 breadth: {_fmt(pct_cloud_bull_a3, 4)}")
    md_parts.append(f"- Breadth zone: {bz_upper}")
    md_parts.append(f"- T1 permission: {t1_perm_label}")
    md_parts.append(f"- T2 permission: {t2_perm_label}")
    md_parts.append(f"- Sector L4 stress: {sector_stress}")
    md_parts.append(f"- Liquidity warnings: {liq_warn}")
    if drl_data:
        md_parts.append("\n" + render_distribution_risk_md(drl_data))

    if delta:
        md_parts.append("\n## H. Delta vs Previous")
        if delta.get("new_candidates_added"):
            md_parts.append(f"- New: {', '.join(delta['new_candidates_added'])}")
        if delta.get("new_candidates_removed"):
            md_parts.append(f"- Removed: {', '.join(delta['new_candidates_removed'])}")
    else:
        if prev_json is not None:
            md_parts.append("\n## H. Delta vs Previous\nNo changes from previous report.")
        else:
            md_parts.append("\n## H. Delta vs Previous\nNo previous report found — first run.")

    md_str = "\n".join(md_parts)

    # ========================================================================
    # BUILD JSON
    # ========================================================================

    json_payload = {
        "report_mode": mode,
        "report_timestamp": ts.isoformat(),
        "scan_path": scan_path_str,
        "panel_asof_date": panel_asof,
        "scan_date": scan_date,
        "report_status": report_status,
        "counts": counts,
        "top_actions": top_actions,
        "warnings": warnings_list,
        "files_used": files_used,
        "previous_report_delta": delta,
        "new_entry_symbols": new_entry_symbols,
        "regime_bull": regime_bull,
        "breadth_zone": breadth_zone,
        # Portfolio state fields
        "portfolio_state_path": portfolio_state_path,
        "portfolio_nav_vnd": nav_vnd,
        "portfolio_as_of_date": portfolio_as_of_date,
        "positions_path": positions_source if positions_source != "missing" else None,
        "port_excludes_cash": True,
        "nav_is_user_updated": True,
        "distribution_risk_lens": drl_data,
        "distribution_risk_lens_version": (
            drl_data.get("method_version") if isinstance(drl_data, dict) else None
        ),
    }

    return html_str, md_str, json_payload


# ---------------------------------------------------------------------------
# write_report
# ---------------------------------------------------------------------------

def write_report(mode: str, ts: datetime | None = None, scan_path: Path | None = None) -> dict:
    """Top-level: load, build, write files. Returns dict of output paths."""
    if ts is None:
        ts = datetime.now(tz=timezone.utc)

    inputs = load_inputs(mode, scan_path=scan_path)
    resolved_mode = inputs["mode"]

    drl_as_of = None
    scan_df = inputs.get("scan_df")
    if scan_df is not None and not scan_df.empty:
        raw = scan_df.iloc[0].get("as_of_date")
        if raw is not None and str(raw) not in ("", "nan"):
            drl_as_of = str(raw)[:10]

    drl_warnings: list[str] = []
    try:
        drl_warnings.extend(refresh_distribution_risk_for_reports(as_of=drl_as_of))
        drl_data, load_warns = load_distribution_risk_latest()
        drl_warnings.extend(load_warns)
        inputs["distribution_risk_lens"] = drl_data
        inputs["distribution_risk_warnings"] = drl_warnings
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Distribution Risk Lens refresh skipped: %s", exc)
        inputs["distribution_risk_lens"] = None
        inputs["distribution_risk_warnings"] = [f"distribution_risk_lens refresh failed: {exc}"]

    html_str, md_str, json_payload = build_report(resolved_mode, inputs, ts)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    ts_file = ts.strftime("%Y%m%d_%H%M")

    html_latest = REPORTS_DIR / "cloud_daily_report_latest.html"
    html_ts = REPORTS_DIR / f"cloud_daily_report_{ts_file}.html"
    md_latest = REPORTS_DIR / "cloud_daily_report_latest.md"
    md_ts = REPORTS_DIR / f"cloud_daily_report_{ts_file}.md"
    json_path = REPORTS_DIR / "cloud_daily_report_latest.json"

    html_latest.write_text(html_str, encoding="utf-8")
    html_ts.write_text(html_str, encoding="utf-8")
    md_latest.write_text(md_str, encoding="utf-8")
    md_ts.write_text(md_str, encoding="utf-8")
    json_path.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    return {
        "mode": resolved_mode,
        "report_status": json_payload["report_status"],
        "html_latest": str(html_latest),
        "html_ts": str(html_ts),
        "md_latest": str(md_latest),
        "md_ts": str(md_ts),
        "json_path": str(json_path),
        "warnings": json_payload["warnings"],
        "counts": json_payload["counts"],
    }
