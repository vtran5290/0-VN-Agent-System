"""
Portfolio Monitor — Live Position Dashboard Generator (v2)

Reads current_positions_derived.json, fetches live quotes from TradingView
scanner API, loads T1/T2 candidates from daily_scan.json, and generates
an HTML dashboard with client-side auto-refresh.

Usage:
  python scripts/reporting/generate_portfolio_monitor.py
  python scripts/reporting/generate_portfolio_monitor.py --serve
  python scripts/reporting/generate_portfolio_monitor.py --quotes data/quotes_snapshot.json
  python scripts/reporting/generate_portfolio_monitor.py --output reports/portfolio_monitor_latest.html
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import http.server
import json
import logging
import socketserver
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import date, datetime, timezone, timedelta
from html import escape
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.trading.reports.report_suite_common import (
    SUITE_NAV_CSS,
    PERMISSION_PRECEDENCE_PM,
    build_inst_accum_ticker_index,
    build_street_coverage_index,
    load_institutional_accumulation_compact,
    load_position_context,
    load_street_coverage_compact,
    position_context_by_symbol,
    render_inst_accum_cell,
    render_street_coverage_cell,
    render_provenance_header,
    render_suite_nav,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
logger = logging.getLogger("portfolio_monitor")

ICT = timezone(timedelta(hours=7))
QUOTES_FREEZE_PATH = ROOT / "reports" / "portfolio_monitor_quotes_freeze.json"
MA_CONTEXT_PATH = ROOT / "data" / "research" / "ma_context_daily.json"
CLOUD_PANEL_PATH = ROOT / "data/research/sector_l4_causality/stock_daily_cloud_panel.parquet"
MA_LOOKBACK = 210
FREEZE_STORAGE_KEY = "vn_portfolio_monitor_freeze_v1"

# Exchange prefixes for TradingView scanner (not all tickers are HOSE)
HNX_TICKERS = frozenset({"SHS", "MBS", "CEO", "PVC", "SHB", "TNG"})
UPCOM_TICKERS = frozenset({"BVB"})


def _tv_exchange(ticker: str) -> str:
    if ticker in HNX_TICKERS:
        return "HNX"
    if ticker in UPCOM_TICKERS:
        return "UPCOM"
    return "HOSE"


def _tv_symbol(ticker: str) -> str:
    return f"{_tv_exchange(ticker)}:{ticker}"


def save_quotes_freeze(quotes: Dict[str, Dict[str, Any]], path: Path = QUOTES_FREEZE_PATH) -> str:
    """Persist last good quote map for after-hours / offline freeze."""
    label = datetime.now(ICT).strftime("%Y-%m-%d %H:%M ICT")
    payload = {
        "saved_at": label,
        "saved_at_iso": datetime.now(ICT).isoformat(),
        "source": "tradingview",
        "quotes": quotes,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    logger.info("Quote freeze saved → %s (%s)", path, label)
    return label


def load_quotes_freeze(path: Path = QUOTES_FREEZE_PATH) -> Tuple[Dict[str, Dict[str, Any]], str]:
    if not path.exists():
        return {}, ""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read quote freeze: %s", exc)
        return {}, ""
    return raw.get("quotes") or {}, str(raw.get("saved_at") or "")


def quotes_for_client_embed(quotes: Dict[str, Dict[str, Any]]) -> str:
    """Minimal quote map embedded in HTML for offline / frozen display."""
    slim: Dict[str, Dict[str, Any]] = {}
    for tk, q in quotes.items():
        slim[tk] = {
            "close": q.get("close", 0) or 0,
            "change": q.get("change", 0) or 0,
            "change_abs": q.get("change_abs", 0) or 0,
        }
    return json.dumps(slim)

# ── Data loaders ─────────────────────────────────────────────────────────────

def load_positions(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    p = path or ROOT / "data" / "raw" / "current_positions_derived.json"
    return json.loads(p.read_text(encoding="utf-8"))


def load_regime(path: Optional[Path] = None) -> Dict[str, Any]:
    p = path or ROOT / "data" / "state" / "regime_state.json"
    if not p.exists():
        return {"regime": "?", "asof_date": "unknown"}
    return json.loads(p.read_text(encoding="utf-8"))


def load_daily_scan(path: Optional[Path] = None) -> Dict[str, Any]:
    p = path or ROOT / "data" / "decision" / "daily_scan.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def load_scan_csv_actions(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Read phase36 daily scan CSV and extract per-symbol action details."""
    p = path or ROOT / "data" / "research" / "portfolio_optimization" / "missing_work" / "phase36_daily_scan_latest.csv"
    if not p.exists():
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    with open(p, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sym = row.get("symbol", "")
            if not sym:
                continue
            def _boolish(v: str) -> Optional[bool]:
                if v in ("True", "true", "1"): return True
                if v in ("False", "false", "0"): return False
                return None
            out[sym] = {
                "final_action": row.get("final_action", ""),
                "final_action_reason": row.get("final_action_reason", ""),
                "close_kVND": float(row.get("close_kVND", 0) or 0),
                "a3_rank_bucket": row.get("a3_rank_bucket", ""),
                "ed_score": float(row.get("ed_score", 0) or 0),
                "sector_l3": row.get("sector_l3", ""),
                "sector_l4": row.get("sector_l4", ""),
                "breadth_zone": row.get("breadth_zone", ""),
                "breadth_t1_permission": row.get("breadth_t1_permission", ""),
                "breadth_t2_permission": row.get("breadth_t2_permission", ""),
                "a3_cloud_bull": _boolish(row.get("a3_cloud_bull", "")),
                "s3_cloud_bull": _boolish(row.get("s3_cloud_bull", "")),
                "a3_ema_dist_pct": float(row.get("a3_ema_dist_pct", 0) or 0),
                "a3_signal_today": _boolish(row.get("a3_signal_today", "")),
                "rs_correction_bucket": row.get("rs_correction_bucket", ""),
                "rs_correction_improving": _boolish(row.get("rs_correction_improving", "")),
                "ed_score_bucket": row.get("ed_score_bucket", ""),
                "trail_price": float(row.get("trail_price", 0) or 0),
                "rsi": None,
                # S2/S1 filter columns (phase36 schema v36+)
                "s2_vol_mult": float(row.get("s2_vol_mult", 0) or 0),
                "s2_pass": _boolish(row.get("s2_pass", "")),
                "s1_prox_52wk": float(row.get("s1_prox_52wk", 0) or 0),
                "s1_pass": _boolish(row.get("s1_pass", "")),
                "active_filter": row.get("active_filter", ""),
                "phase36_operator_priority": int(float(row.get("phase36_operator_priority", 9999) or 9999)),
            }
    return out


def load_quotes_from_file(path: Path) -> Dict[str, Dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: Dict[str, Dict[str, Any]] = {}
    symbols = raw.get("symbols", raw) if isinstance(raw, dict) else raw
    for item in symbols:
        sym = item.get("symbol", "")
        ticker = sym.split(":")[-1] if ":" in sym else sym
        out[ticker] = item
    return out


def fetch_quotes_tv(tickers: List[str]) -> Dict[str, Dict[str, Any]]:
    try:
        import requests
    except ImportError:
        logger.error("requests not installed — run: pip install requests")
        return {}
    symbols = [_tv_symbol(t) for t in tickers]
    columns = [
        "name", "close", "change", "change_abs", "open", "high", "low",
        "volume", "market_cap_basic",
        "price_52_week_high", "price_52_week_low",
        "EMA10", "EMA20", "EMA50", "SMA20", "SMA50", "SMA200", "RSI",
        "Perf.W", "Perf.1M", "Perf.3M",
        "average_volume_10d_calc", "sector", "Recommend.MA",
    ]
    payload = {"symbols": {"tickers": symbols}, "columns": columns}
    try:
        resp = requests.post(
            "https://scanner.tradingview.com/vietnam/scan",
            json=payload, timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("TradingView fetch failed: %s", exc)
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for item in data.get("data", []):
        sym = item.get("s", "")
        ticker = sym.split(":")[-1] if ":" in sym else sym
        vals = item.get("d", [])
        row = dict(zip(columns, vals))
        row["symbol"] = sym
        out[ticker] = row
    return out


# ── Portfolio computation ────────────────────────────────────────────────────

def compute_portfolio(
    positions: List[Dict[str, Any]],
    quotes: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    from datetime import date
    from src.trading.overlays.propagation_display import (
        is_cash_plus_display_enabled,
        is_sector_annotation_enabled,
        load_cash_plus_for_display,
        symbol_tilt_label,
    )

    tilt_enabled = is_sector_annotation_enabled()
    cash_attr = load_cash_plus_for_display() if is_cash_plus_display_enabled() else {}
    asof = str(date.today())
    rows = []
    total_cost = 0.0
    total_mkt = 0.0

    for pos in positions:
        tk = pos["ticker"]
        entry = pos.get("entry_price", 0) or 0
        lots = pos.get("lots", 0) or 0
        tag = pos.get("reason_tag", "—")
        q = quotes.get(tk, {})

        current = q.get("close", 0) or 0
        chg_pct = q.get("change", 0) or 0
        chg_abs = q.get("change_abs", 0) or 0
        vol = q.get("volume", 0) or 0
        rsi = q.get("RSI")
        ema10 = q.get("EMA10")
        ema20 = q.get("EMA20")
        ema50 = q.get("EMA50")
        sma20 = q.get("SMA20")
        sma50 = q.get("SMA50")
        sma200 = q.get("SMA200")
        perf_w = q.get("Perf.W")
        perf_1m = q.get("Perf.1M")
        adv10 = q.get("average_volume_10d_calc")
        hi52 = q.get("price_52_week_high")
        sector = q.get("sector", "—")
        rec_ma = q.get("Recommend.MA")

        cost_value = entry * lots
        mkt_value = current * lots
        pnl = mkt_value - cost_value
        pnl_pct = ((current / entry) - 1) * 100 if entry > 0 else 0

        vs_ema10 = ((current / ema10) - 1) * 100 if ema10 and ema10 > 0 else None
        vs_sma50 = ((current / sma50) - 1) * 100 if sma50 and sma50 > 0 else None
        vs_sma20 = ((current / sma20) - 1) * 100 if sma20 and sma20 > 0 else None
        vs_sma200 = ((current / sma200) - 1) * 100 if sma200 and sma200 > 0 else None

        total_cost += cost_value
        total_mkt += mkt_value

        rows.append({
            "ticker": tk, "tag": tag, "sector": sector,
            "sector_tilt": symbol_tilt_label(tk.replace("HOSE:", "").replace("HNX:", ""), asof) if tilt_enabled else "",
            "idle_cash_yield_vnd": cash_attr.get("accumulated_yield_vnd", 0) if cash_attr else 0,
            "entry": entry, "current": current,
            "day_chg_pct": chg_pct, "day_chg_abs": chg_abs,
            "lots": lots, "cost_value": cost_value, "mkt_value": mkt_value,
            "pnl": pnl, "pnl_pct": pnl_pct, "weight": 0,
            "rsi": rsi, "vs_ema10": vs_ema10, "vs_sma50": vs_sma50,
            "vs_sma20": vs_sma20, "vs_sma200": vs_sma200,
            "volume": vol, "adv10": adv10,
            "perf_w": perf_w, "perf_1m": perf_1m, "rec_ma": rec_ma,
        })

    for r in rows:
        r["weight"] = (r["mkt_value"] / total_mkt * 100) if total_mkt > 0 else 0

    total_pnl = total_mkt - total_cost
    total_pnl_pct = ((total_mkt / total_cost) - 1) * 100 if total_cost > 0 else 0

    weights = [r["weight"] for r in rows]
    hhi = sum(w ** 2 for w in weights)

    tag_weights: Dict[str, float] = {}
    for r in rows:
        tag_weights[r["tag"]] = tag_weights.get(r["tag"], 0) + r["weight"]

    rows.sort(key=lambda r: r["mkt_value"], reverse=True)
    largest = rows[0] if rows else None

    winners = [r for r in rows if r["pnl_pct"] > 0]
    losers = [r for r in rows if r["pnl_pct"] <= 0]

    alerts: List[Dict[str, str]] = []
    for r in rows:
        if r["pnl_pct"] < -10:
            alerts.append({"type": "r", "msg": f"{r['ticker']} down {r['pnl_pct']:.1f}% from entry"})
        if r["rsi"] is not None and r["rsi"] > 70:
            alerts.append({"type": "a", "msg": f"{r['ticker']} RSI {r['rsi']:.0f} — overbought"})
        if r["rsi"] is not None and r["rsi"] < 30:
            alerts.append({"type": "r", "msg": f"{r['ticker']} RSI {r['rsi']:.0f} — oversold"})

    max_sector_pct = max(tag_weights.values()) if tag_weights else 0
    max_sector_name = max(tag_weights, key=tag_weights.get) if tag_weights else "—"
    if max_sector_pct > 40:
        alerts.append({"type": "a", "msg": f"{max_sector_name} concentration {max_sector_pct:.1f}% > 40% threshold"})

    return {
        "rows": rows, "total_cost": total_cost, "total_mkt": total_mkt,
        "total_pnl": total_pnl, "total_pnl_pct": total_pnl_pct,
        "n_positions": len(rows), "n_winners": len(winners), "n_losers": len(losers),
        "hhi": hhi, "largest": largest, "tag_weights": tag_weights, "alerts": alerts,
    }


def build_candidates(
    daily_scan: Dict[str, Any],
    scan_csv: Dict[str, Dict[str, Any]],
    quotes: Dict[str, Dict[str, Any]],
    held_tickers: set,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Build T1 new-entry candidates, holding action status, and all-tickers list."""
    new_t1: List[Dict[str, Any]] = []
    holding_actions: List[Dict[str, Any]] = []
    all_tickers: List[Dict[str, Any]] = []

    new_entry_symbols = daily_scan.get("new_entry_symbols", [])
    for sym in new_entry_symbols:
        csv_row = scan_csv.get(sym, {})
        q = quotes.get(sym, {})
        new_t1.append({
            "ticker": sym,
            "close": q.get("close") or csv_row.get("close_kVND", 0) * 1000,
            "change": q.get("change", 0) or 0,
            "rsi": q.get("RSI"),
            "sector": csv_row.get("sector_l3", q.get("sector", "—")),
            "action": csv_row.get("final_action", "NEW_T1"),
            "reason": csv_row.get("final_action_reason", ""),
            "ed_score": csv_row.get("ed_score", 0),
            "rank": csv_row.get("a3_rank_bucket", "—"),
            "in_portfolio": sym in held_tickers,
            "perf_w": q.get("Perf.W"),
            "perf_1m": q.get("Perf.1M"),
            # S2/S1 filter quality
            "s2_pass": csv_row.get("s2_pass"),
            "s2_vol_mult": csv_row.get("s2_vol_mult", 0),
            "s1_pass": csv_row.get("s1_pass"),
            "s1_prox_52wk": csv_row.get("s1_prox_52wk", 0),
            "phase36_priority": csv_row.get("phase36_operator_priority", 9999),
        })

    for sym, csv_row in scan_csv.items():
        if sym in held_tickers:
            holding_actions.append({
                "ticker": sym,
                "action": csv_row.get("final_action", "—"),
                "reason": csv_row.get("final_action_reason", "")[:80],
                "t1_ok": csv_row.get("breadth_t1_permission", "") == "True",
                "t2_ok": csv_row.get("breadth_t2_permission", "") == "True",
            })
        q = quotes.get(sym, {})
        a3 = csv_row.get("a3_cloud_bull")
        s3 = csv_row.get("s3_cloud_bull")
        all_tickers.append({
            "ticker": sym,
            "close": q.get("close") or csv_row.get("close_kVND", 0) * 1000,
            "change": q.get("change", 0) or 0,
            "rsi": q.get("RSI"),
            "sector": csv_row.get("sector_l3", q.get("sector", "—")),
            "action": csv_row.get("final_action", ""),
            "a3_bull": a3,
            "s3_bull": s3,
            "ema_dist": csv_row.get("a3_ema_dist_pct", 0),
            "ed_score": csv_row.get("ed_score", 0),
            "ed_bucket": csv_row.get("ed_score_bucket", ""),
            "trail_price": csv_row.get("trail_price", 0),
            "rank": csv_row.get("a3_rank_bucket", "—"),
            "in_portfolio": sym in held_tickers,
            "perf_w": q.get("Perf.W"),
            "rec_ma": q.get("Recommend.MA"),
            "rs_bucket": csv_row.get("rs_correction_bucket", ""),
            "rs_improving": csv_row.get("rs_correction_improving"),
            # S2/S1 filter quality
            "s2_pass": csv_row.get("s2_pass"),
            "s2_vol_mult": csv_row.get("s2_vol_mult", 0),
            "s1_pass": csv_row.get("s1_pass"),
            "s1_prox_52wk": csv_row.get("s1_prox_52wk", 0),
            "phase36_priority": csv_row.get("phase36_operator_priority", 9999),
        })

    holding_actions.sort(key=lambda x: x["action"])
    # Sort T1 candidates by phase36 operator priority (lower = higher priority)
    new_t1.sort(key=lambda x: (int(x.get("phase36_priority") or 9999), x["ticker"]))
    # Sort all tickers: by action priority then ticker
    action_order = {"NEW_T1_MANUAL_REVIEW_BREADTH": 0, "HOLD_T1_ONLY": 1, "NO_T2_BREADTH": 2, "WATCH_ONLY": 3, "TRAIL_EXIT": 4}
    all_tickers.sort(key=lambda x: (action_order.get(x["action"], 3), x["ticker"]))
    return new_t1, holding_actions, all_tickers


# ── HTML rendering ───────────────────────────────────────────────────────────

_CSS = """\
html { scroll-behavior: smooth; }
:root {
  --bg:      #0d0f1a;
  --s1:      #13162a;
  --s2:      #1a1e35;
  --border:  #252a45;
  --text:    #e2e8f0;
  --muted:   #64748b;
  --faint:   #374060;
  --g:  #00c896;
  --a:  #f59e0b;
  --r:  #f43f5e;
  --b:  #3b82f6;
  --p:  #a855f7;
  --gb: rgba(0,200,150,.10);
  --ab: rgba(245,158,11,.10);
  --rb: rgba(244,63,94,.10);
  --bb: rgba(59,130,246,.10);
  --pb: rgba(168,85,247,.10);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg); color: var(--text);
  font-family: "IBM Plex Sans", Inter, system-ui, sans-serif;
  font-size: 13px; line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
  letter-spacing: -0.01em;
}
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,.10); border-radius: 3px; }
.page { max-width: 1280px; margin: 0 auto; padding: 24px 24px 48px; }
.hdr { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; border-bottom: 1px solid var(--border); padding-bottom: 14px; }
.hdr-title { font-size: 15px; font-weight: 700; letter-spacing: .02em; }
.hdr-meta { font-size: 11px; color: var(--muted); text-align: right; line-height: 1.6; }
.banner {
  background: rgba(244,63,94,.06); border: 1px solid rgba(244,63,94,.22);
  border-radius: 5px; padding: 8px 14px; margin-bottom: 20px;
  font-size: 11px; font-weight: 600; color: var(--r);
  letter-spacing: .04em; text-transform: uppercase; text-align: center;
}
.regime-badge {
  display: inline-block; font-size: 11px; font-weight: 700;
  padding: 2px 10px; border-radius: 20px; letter-spacing: .04em;
  margin-left: 10px; vertical-align: middle;
}
.regime-A { background: var(--gb); color: var(--g); border: 1px solid rgba(0,200,150,.25); }
.regime-B { background: var(--ab); color: var(--a); border: 1px solid rgba(245,158,11,.25); }
.regime-C { background: var(--rb); color: var(--r); border: 1px solid rgba(244,63,94,.25); }
.slabel { font-size: 10px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); margin-bottom: 10px; margin-top: 4px; }
.pulse { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; margin-bottom: 24px; }
@media (max-width: 900px) { .pulse { grid-template-columns: repeat(3, 1fr); } }
.kpi { background: var(--s1); border: 1px solid var(--border); border-radius: 6px; padding: 12px 14px; }
.kpi-label { font-size: 10px; color: var(--muted); font-weight: 600; letter-spacing: .06em; text-transform: uppercase; margin-bottom: 5px; }
.kpi-val { font-size: 18px; font-weight: 700; line-height: 1.1; font-family: "IBM Plex Mono", monospace; }
.kpi-sub { font-size: 10px; margin-top: 3px; color: var(--muted); }
.kpi.ok   { border-top: 2px solid var(--g); }
.kpi.warn { border-top: 2px solid var(--a); }
.kpi.bad  { border-top: 2px solid var(--r); }
.up   { color: var(--g); }
.down { color: var(--r); }
.flat { color: var(--a); }
.dim  { color: var(--muted); }
.sector-bar { display: flex; height: 28px; border-radius: 4px; overflow: hidden; margin-bottom: 6px; }
.sector-bar div { display: flex; align-items: center; justify-content: center; font-size: 9px; font-weight: 700; letter-spacing: .04em; color: #fff; min-width: 28px; }
.sector-legend { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; }
.sector-legend-item { font-size: 10px; display: flex; align-items: center; gap: 4px; }
.sector-legend-dot { width: 8px; height: 8px; border-radius: 2px; }
.board { background: var(--s1); border: 1px solid var(--border); border-radius: 8px; overflow-x: auto; margin-bottom: 24px; }
.board table { width: 100%; min-width: 700px; border-collapse: collapse; }
.board th {
  background: var(--s2); color: var(--muted);
  font-size: 10px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .08em; padding: 8px 10px; text-align: left;
  border-bottom: 1px solid var(--border); white-space: nowrap;
  position: sticky; top: 0; cursor: pointer;
}
.board th:hover { color: var(--text); }
.board td {
  padding: 7px 10px; border-bottom: 1px solid rgba(37,42,69,.6);
  vertical-align: middle; font-size: 12px;
}
.board tr:last-child td { border-bottom: none; }
.tilt-tag { font-size: 10px; font-weight: 600; margin-left: 4px; vertical-align: middle; }
.tilt-lead { color: var(--g); }
.tilt-lag { color: var(--muted); opacity: 0.85; }
.tilt-neutral { color: var(--muted); opacity: 0.5; }
.tilt-summary td.tilt-lead { color: var(--g); font-weight: 600; }
.tilt-summary td.tilt-lag { color: var(--muted); }
.board tr:hover td { background: rgba(255,255,255,.02); }
.tk { font-weight: 700; font-size: 13px; font-family: "IBM Plex Mono", monospace; }
.mono { font-family: "IBM Plex Mono", monospace; font-variant-numeric: tabular-nums; }
.tag-cell { font-size: 10px; color: var(--muted); }
.r-num { text-align: right; white-space: nowrap; }
.pos-border-g td:first-child { border-left: 3px solid var(--g); }
.pos-border-a td:first-child { border-left: 3px solid var(--a); }
.pos-border-r td:first-child { border-left: 3px solid var(--r); }
.pos-border-b td:first-child { border-left: 3px solid var(--b); }
.rsi-bar { width: 48px; height: 5px; background: var(--faint); border-radius: 2px; display: inline-block; vertical-align: middle; }
.rsi-fill { height: 100%; border-radius: 2px; }
.rsi-val { font-size: 10px; margin-left: 4px; vertical-align: middle; }
.alerts { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 8px; margin-bottom: 24px; }
.alert-card {
  background: var(--s1); border: 1px solid var(--border); border-radius: 6px;
  padding: 10px 14px; display: flex; align-items: center; gap: 10px;
}
.alert-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.dot-r { background: var(--r); }
.dot-a { background: var(--a); }
.dot-g { background: var(--g); }
.dot-b { background: var(--b); }
.alert-text { font-size: 11px; }
.footer { margin-top: 36px; padding-top: 14px; border-top: 1px solid var(--border); font-size: 10px; color: var(--muted); line-height: 1.7; }
.ma-det { font-size: 11px; max-width: 220px; }
.ma-det summary { cursor: pointer; list-style: none; line-height: 1.45; }
.ma-det summary::-webkit-details-marker { display: none; }
.ma-grid { display: grid; gap: 4px; margin-top: 6px; }
.ma-lbl { color: var(--muted); font-size: 10px; margin-right: 6px; }
.ma-val { font-size: 11px; }
.ma-foot { font-size: 9px; color: var(--faint); margin-top: 6px; line-height: 1.4; }
.ma-card { padding: 4px 0 2px; }
.sort-asc::after { content: " ▲"; font-size: 8px; }
.sort-desc::after { content: " ▼"; font-size: 8px; }
/* Live refresh */
.live-bar {
  display: flex; align-items: center; gap: 10px; margin-bottom: 16px;
  padding: 8px 14px; background: var(--s1); border: 1px solid var(--border); border-radius: 6px;
}
.live-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--g); animation: pulse-dot 2s infinite; }
.live-dot.off { background: var(--muted); animation: none; }
@keyframes pulse-dot { 0%,100% { opacity: 1; } 50% { opacity: .3; } }
.live-label { font-size: 11px; font-weight: 600; letter-spacing: .04em; }
.live-time { font-size: 10px; color: var(--muted); font-family: "IBM Plex Mono", monospace; margin-left: auto; }
.live-btn {
  font-size: 10px; font-weight: 600; padding: 3px 10px; border-radius: 4px;
  border: 1px solid var(--border); background: var(--s2); color: var(--text);
  cursor: pointer; letter-spacing: .04em; text-transform: uppercase;
}
.live-btn:hover { border-color: var(--g); color: var(--g); }
/* Action badges */
.action-badge {
  font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 3px;
  letter-spacing: .04em; text-transform: uppercase; white-space: nowrap;
}
.action-NEW_T1 { background: var(--gb); color: var(--g); border: 1px solid rgba(0,200,150,.25); }
.action-HOLD_T1 { background: var(--bb); color: var(--b); border: 1px solid rgba(59,130,246,.25); }
.action-NO_T2 { background: var(--ab); color: var(--a); border: 1px solid rgba(245,158,11,.25); }
.action-TRAIL_EXIT { background: var(--rb); color: var(--r); border: 1px solid rgba(244,63,94,.25); }
.action-WATCH { background: rgba(100,116,139,.1); color: var(--muted); border: 1px solid rgba(100,116,139,.25); }
.cand-table { width: 100%; min-width: 700px; }
.cand-reason { font-size: 10px; color: var(--muted); max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
/* Cloud badges */
.cloud-badge { font-size: 8px; font-weight: 700; padding: 1px 4px; border-radius: 2px; letter-spacing: .04em; margin-right: 2px; }
.cloud-bull { background: var(--gb); color: var(--g); border: 1px solid rgba(0,200,150,.2); }
.cloud-bear { background: var(--rb); color: var(--r); border: 1px solid rgba(244,63,94,.2); }
/* Signal quality badges (S2/S1 filter — standalone only, never additive) */
.sig-badge { font-size: 8px; font-weight: 700; padding: 1px 5px; border-radius: 2px; letter-spacing: .05em; white-space: nowrap; cursor: default; }
.sig-s2 { background: rgba(0,200,150,.12); color: var(--g); border: 1px solid rgba(0,200,150,.3); }
.sig-s1 { background: rgba(59,130,246,.12); color: var(--b); border: 1px solid rgba(59,130,246,.3); }
.sig-none { color: var(--muted); font-size: 10px; }
.sig-vol-dim { font-size: 9px; color: var(--muted); font-family: "IBM Plex Mono", monospace; margin-left: 2px; }
.filter-legend { font-size: 10px; color: var(--muted); margin: 0 0 10px; padding: 6px 10px; background: rgba(255,255,255,.02); border-radius: 4px; border-left: 2px solid var(--faint); line-height: 1.6; }
.filter-legend strong { color: var(--text); }
/* Index chart strip — FireAnt-style ATC boards */
.index-strip { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 16px; }
.index-chart-card {
  background: var(--s1); border: 1px solid var(--border); border-radius: 6px;
  overflow: hidden; padding: 8px 10px 10px; min-height: 240px;
}
.index-chart-label { font-size: 10px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }
.idx-head { display: flex; justify-content: space-between; align-items: baseline; margin-top: 2px; gap: 6px; flex-wrap: wrap; }
.idx-price { font-size: 18px; font-weight: 700; font-family: "IBM Plex Mono", monospace; color: var(--text); }
.idx-chg { font-size: 11px; font-weight: 600; font-family: "IBM Plex Mono", monospace; }
.idx-chg.up { color: var(--g); }
.idx-chg.down { color: var(--r); }
.idx-chg.flat { color: var(--muted); }
.idx-tv { display: none; }
.idx-chart-wrap { width: 100%; margin: 4px 0 2px; }
.idx-spark { width: 100%; height: 110px; display: block; border: 0; background: transparent; }
.idx-vol { width: 100%; height: 36px; display: block; margin: 0; }
.idx-axis { display: flex; justify-content: space-between; font-size: 8px; color: var(--faint); margin-top: 0; margin-bottom: 2px; font-family: "IBM Plex Mono", monospace; }
.idx-meta { font-size: 10px; color: var(--muted); line-height: 1.45; }
.idx-meta strong { color: var(--text); font-weight: 600; }
.idx-src { font-size: 9px; color: var(--faint); margin-top: 4px; }
@media (max-width: 1100px) { .index-strip { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 700px) { .index-strip { grid-template-columns: 1fr; } }
/* Prevent table reflow when price/change text updates */
.price-cell { min-width: 72px; white-space: nowrap; }
.chg-cell   { min-width: 54px; white-space: nowrap; }
.pnl-cell   { min-width: 72px; white-space: nowrap; }
/* All tickers toggle */
.toggle-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.toggle-btn {
  font-size: 11px; font-weight: 600; padding: 5px 14px; border-radius: 4px;
  border: 1px solid var(--border); background: var(--s2); color: var(--text);
  cursor: pointer; letter-spacing: .03em;
}
.toggle-btn:hover { border-color: var(--b); color: var(--b); }
.toggle-btn.active { border-color: var(--g); color: var(--g); }
.all-tickers-section { display: none; }
.all-tickers-section.visible { display: block; }
/* A3 CTX condensed cell */
.ctx-cell { font-size: 10px; white-space: nowrap; }
.ctx-cell span { margin-right: 1px; }
.action-group-label td {
  font-size: 10px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
  padding: 6px 10px; color: var(--muted); background: rgba(255,255,255,.02);
}
.scan-miss {
  font-size: 9px; color: var(--muted); font-style: italic; letter-spacing: .02em;
  opacity: .75; white-space: nowrap;
}
/* Sidebar TOC */
.layout { display: flex; min-height: 100vh; }
.sidebar { width: 158px; position: sticky; top: 0; height: 100vh; overflow-y: auto; overscroll-behavior: contain; border-right: 1px solid var(--border); background: var(--s1); padding: 12px 0; flex-shrink: 0; }
.sidebar-logo { padding: 8px 12px 10px; font-size: 9px; color: var(--muted); text-transform: uppercase; letter-spacing: .1em; border-bottom: 1px solid var(--border); margin-bottom: 8px; font-weight: 700; }
.sidebar h3 { margin: 10px 12px 3px; font-size: 8px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; }
.sidebar a { display: block; margin: 1px 6px; padding: 5px 8px; color: var(--muted); text-decoration: none; font-size: 11px; border-radius: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sidebar a:hover, .sidebar a.active { background: rgba(255,255,255,.06); color: var(--text); }
@media (max-width: 860px) { .sidebar { display: none; } }
""" + SUITE_NAV_CSS

_SECTOR_COLORS = [
    "#3b82f6", "#00c896", "#f59e0b", "#f43f5e", "#a855f7",
    "#06b6d4", "#ec4899", "#84cc16", "#f97316",
]


def _fmt_vnd(v: float) -> str:
    if abs(v) >= 1e9:
        return f"{v / 1e9:,.1f}B"
    if abs(v) >= 1e6:
        return f"{v / 1e6:,.1f}M"
    return f"{v:,.0f}"

def _fmt_price(v: float) -> str:
    return f"{v:,.0f}"

def _pnl_class(v: float) -> str:
    return "up" if v > 0 else ("down" if v < 0 else "flat")

def _border_class(pnl_pct: float) -> str:
    if pnl_pct > 2: return "pos-border-g"
    if pnl_pct < -5: return "pos-border-r"
    return "pos-border-a"

def _rsi_color(rsi: float) -> str:
    if rsi >= 70: return "var(--r)"
    if rsi <= 30: return "var(--g)"
    return "var(--b)"

def _action_badge_class(action: str) -> str:
    if "NEW_T1" in action: return "action-NEW_T1"
    if "HOLD_T1" in action: return "action-HOLD_T1"
    if "NO_T2" in action: return "action-NO_T2"
    if "TRAIL" in action or "EXIT" in action: return "action-TRAIL_EXIT"
    return "action-WATCH"

def _action_short(action: str) -> str:
    return action.replace("_MANUAL_REVIEW_BREADTH", "").replace("_BREADTH", "")


def _render_sig_quality(
    s2_pass: Optional[bool],
    s2_vol_mult: float,
    s1_pass: Optional[bool],
    s1_prox_52wk: float,
    *,
    is_current_day: bool = True,
) -> str:
    """Signal quality badge — S2 (vol filter) or S1 (52wk proximity), standalone only.

    Mutual exclusivity: S1 badge only shown when S2 fails (combined use FORBIDDEN).
    vol_mult tooltip carries current-day caveat if is_current_day=True.
    """
    vol_day_note = " (current-day reading, not entry-day)" if is_current_day else ""
    if s2_pass is True:
        vol_str = f"{s2_vol_mult:.2f}×" if s2_vol_mult else ""
        tooltip = (
            f"S2 PASS: vol ≥1.3× 50d avg ({vol_str}{vol_day_note}) | "
            "backtest MAR 2020-26: 2.48 — not per-trade expected return"
        )
        vol_html = f'<span class="sig-vol-dim">{vol_str}</span>' if vol_str else ""
        return f'<span class="sig-badge sig-s2" title="{escape(tooltip)}">S2 ✓</span>{vol_html}'
    if s1_pass is True:
        prox_str = f"{s1_prox_52wk:.1%}" if s1_prox_52wk else ""
        tooltip = (
            f"S1 PASS: 52wk proximity {prox_str} | "
            "backtest MAR 2020-26: 1.78 — not per-trade expected return. "
            "S1+S2 combined use FORBIDDEN (DEGRADING-REJECT)."
        )
        return f'<span class="sig-badge sig-s1" title="{escape(tooltip)}">S1 ✓</span>'
    # Both fail
    vol_str = f"{s2_vol_mult:.2f}×" if s2_vol_mult else "—"
    tooltip = f"S2 FAIL: vol {vol_str} <1.3× avg{vol_day_note} | S1 FAIL: 52wk prox {s1_prox_52wk:.1%}" if s1_prox_52wk else f"S2/S1 no data"
    return f'<span class="sig-none" title="{escape(tooltip)}">—</span>'


_ED_ABBREV = {
    "optimal": "O",
    "ok": "ok",
    "extended": "ext",
    "weak": "wk",
    "poor": "pr",
}

_RS_RANK_ABBREV = {
    "high": "H",
    "medium": "M",
    "low": "L",
}

_RS_CORR_ABBREV = {
    "leader_strong": "Ldr+",
    "leader": "Ldr",
    "outperform": "Outp",
    "underperform": "Underp",
    "laggard": "Lag",
}


def _abbrev_ed_bucket(bucket: str) -> str:
    if not bucket:
        return ""
    return _ED_ABBREV.get(bucket.lower(), bucket[:3])


def _abbrev_rs_rank(rank: str) -> str:
    if not rank:
        return ""
    return _RS_RANK_ABBREV.get(rank.lower(), rank[:1].upper())


def _abbrev_rs_corr(bucket: str) -> str:
    if not bucket:
        return ""
    key = bucket.lower().replace(" ", "_")
    for prefix, label in _RS_CORR_ABBREV.items():
        if key.startswith(prefix) or prefix in key:
            return label
    return bucket.replace("leader_", "Ldr_").replace("underperform", "Underp")[:8]


def _not_in_scan_html() -> str:
    return (
        '<span class="scan-miss" title="Outside phase36 active-setup universe '
        '(CLOUD/RS may still show from panel / RS lens)">⊘ setup</span>'
    )


def _no_setup_metric_html(metric: str) -> str:
    """Trail / SIG only exist for phase36 active setups — not a failed refresh."""
    return (
        f'<span class="scan-miss" title="{escape(metric)} only for active A3/S3 setups '
        f'in phase36 scan">—</span>'
    )


def load_ma_context_map(path: Path = MA_CONTEXT_PATH) -> Tuple[Dict[str, Dict[str, Any]], str]:
    """Read quick/slow MA lines from ma_context_daily.json (display-only)."""
    if not path.exists():
        return {}, ""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}, ""
    if not isinstance(raw, dict):
        return {}, ""
    asof = str(raw.get("asof_date") or raw.get("panel_end") or "")
    symbols = raw.get("symbols") or {}
    if not isinstance(symbols, dict):
        return {}, asof
    return symbols, asof


def _signed_pct(val: Optional[float]) -> str:
    if val is None:
        return ""
    try:
        return f"{float(val):+.1f}%"
    except (TypeError, ValueError):
        return ""


def _load_ma_panel():
    """OHLCV panel used by run_ma_context_daily (close in kVND)."""
    if not CLOUD_PANEL_PATH.exists():
        return None
    try:
        import pandas as pd

        panel = pd.read_parquet(CLOUD_PANEL_PATH)[["symbol", "date", "close"]].copy()
        panel["date"] = pd.to_datetime(panel["date"])
        return panel
    except Exception as exc:
        logger.warning("MA panel load failed: %s", exc)
        return None


def _ma_level_vnd(panel, symbol: str, ma_label: Optional[str]) -> Optional[float]:
    if panel is None or not ma_label:
        return None
    try:
        from scripts.run_ma_context_daily import _compute_ma_val

        grp = panel[panel["symbol"] == symbol].sort_values("date").tail(MA_LOOKBACK)
        if grp.empty:
            return None
        val = _compute_ma_val(grp["close"].astype(float), ma_label)
        if val is None:
            return None
        return float(val) * 1000.0
    except Exception:
        return None


def _dist_pct_vs_price(price_vnd: Optional[float], ma_level_vnd: Optional[float]) -> Optional[float]:
    if price_vnd is None or ma_level_vnd is None or ma_level_vnd <= 0:
        return None
    return (float(price_vnd) - float(ma_level_vnd)) / float(ma_level_vnd) * 100.0


def build_ma_display_ctx(
    symbol: str,
    ctx: Optional[Dict[str, Any]],
    price_vnd: Optional[float],
    panel,
) -> Optional[Dict[str, Any]]:
    """Quick/slow labels from ma_context; distance vs current/latest quote close."""
    if not ctx:
        return None
    quick_ma = ctx.get("quick_ma")
    slow_ma = ctx.get("slow_ma")
    if not quick_ma and not slow_ma:
        return None
    q_level = _ma_level_vnd(panel, symbol, quick_ma) if quick_ma else None
    s_level = _ma_level_vnd(panel, symbol, slow_ma) if slow_ma else None
    out: Dict[str, Any] = {
        "recent_window": ctx.get("recent_window"),
        "quick_ma": quick_ma,
        "slow_ma": slow_ma,
        "quick_level_vnd": q_level,
        "slow_level_vnd": s_level,
    }
    if quick_ma:
        out["quick_dist_pct"] = _dist_pct_vs_price(price_vnd, q_level)
        if out["quick_dist_pct"] is None:
            out["quick_dist_pct"] = ctx.get("quick_dist_pct")
    if slow_ma:
        out["slow_dist_pct"] = _dist_pct_vs_price(price_vnd, s_level)
        if out["slow_dist_pct"] is None:
            out["slow_dist_pct"] = ctx.get("slow_dist_pct")
    return out


def _ma_cell_open_tag(display_ctx: Optional[Dict[str, Any]]) -> str:
    if not display_ctx:
        return '<td class="ma-cell">'
    attrs = ['class="ma-cell"']
    if display_ctx.get("quick_ma"):
        attrs.append(f'data-quick-ma="{escape(str(display_ctx["quick_ma"]))}"')
    if display_ctx.get("slow_ma"):
        attrs.append(f'data-slow-ma="{escape(str(display_ctx["slow_ma"]))}"')
    if display_ctx.get("recent_window"):
        attrs.append(f'data-recent-window="{escape(str(display_ctx["recent_window"]))}"')
    qlev = display_ctx.get("quick_level_vnd")
    if qlev is not None:
        attrs.append(f'data-quick-level="{float(qlev):.4f}"')
    slev = display_ctx.get("slow_level_vnd")
    if slev is not None:
        attrs.append(f'data-slow-level="{float(slev):.4f}"')
    return "<td " + " ".join(attrs) + ">"


def _render_ma_quick_slow_cell(display_ctx: Optional[Dict[str, Any]], *, ma_panel_end: str = "") -> str:
    """Collapsible quick/slow MA lines — distance vs quote close (live or latest)."""
    if not display_ctx:
        return '<span class="dim">—</span>'
    quick_ma = display_ctx.get("quick_ma")
    slow_ma = display_ctx.get("slow_ma")
    if not quick_ma and not slow_ma:
        return '<span class="dim">—</span>'
    win_e = escape(str(display_ctx.get("recent_window") or "?"))
    q_txt = f"{escape(str(quick_ma))} {_signed_pct(display_ctx.get('quick_dist_pct'))}".strip() if quick_ma else "—"
    s_txt = f"{escape(str(slow_ma))} {_signed_pct(display_ctx.get('slow_dist_pct'))}".strip() if slow_ma else "—"
    summary = (
        f'<span class="mono dim">{win_e}</span> '
        f'<span class="mono">Q:{q_txt}</span> · <span class="mono">S:{s_txt}</span>'
    )
    rows = [
        (
            f'<div><span class="ma-lbl">Quick ({win_e})</span>'
            f'<span class="ma-val mono" data-ma-leg="quick">{q_txt}</span></div>'
        ),
        (
            f'<div><span class="ma-lbl">Slow ({win_e})</span>'
            f'<span class="ma-val mono" data-ma-leg="slow">{s_txt}</span></div>'
        ),
    ]
    grid = '<div class="ma-grid">' + "".join(rows) + "</div>"
    panel_note = f"MA level through {escape(ma_panel_end)} · " if ma_panel_end else ""
    foot = (
        f'<div class="ma-foot">{panel_note}Distance vs quote close · display only · '
        "ma_context_daily.json</div>"
    )
    card = f'<div class="ma-card">{grid}{foot}</div>'
    return f'<details class="ma-det"><summary>{summary}</summary>{card}</details>'


def _positions_content_key(pos_path: Path) -> str:
    """Structural fingerprint of the positions file — ticker/lots/entry only.

    Deliberately excludes price-derived fields (close_atc_kVND, market_value_vnd,
    unrealized_pnl_vnd, ...) so a routine price-refresh rewrite of the same file
    (e.g. scripts/ops/sync_operator_portfolio_snapshot.py re-running) does not look
    like a structural change. File mtime alone is too eager a signal — it bumps on
    every rewrite regardless of whether the position list actually changed, which
    was driving unwanted full-page reloads (location.replace) on every refresh.
    """
    if not pos_path.exists():
        return "0"
    try:
        raw = json.loads(pos_path.read_text(encoding="utf-8"))
        positions = raw.get("positions") if isinstance(raw, dict) else raw
        if not isinstance(positions, list):
            return "0"
        tuples = sorted(
            (str(r.get("ticker", "")), r.get("lots"), r.get("entry_price"))
            for r in positions
            if isinstance(r, dict)
        )
        blob = json.dumps(tuples, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:16]
    except (json.JSONDecodeError, OSError):
        return "0"


def _positions_meta(pos_path: Path, html_path: Path) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "positions_rev": 0,
        "positions_mtime": "",
        "positions_count": 0,
        "positions_content_key": "0",
        "html_rev": 0,
        "html_mtime": "",
    }
    if pos_path.exists():
        st = pos_path.stat()
        meta["positions_rev"] = int(st.st_mtime)
        meta["positions_mtime"] = datetime.fromtimestamp(st.st_mtime, tz=ICT).strftime("%Y-%m-%d %H:%M ICT")
        meta["positions_content_key"] = _positions_content_key(pos_path)
        try:
            raw = json.loads(pos_path.read_text(encoding="utf-8"))
            positions = raw.get("positions") if isinstance(raw, dict) else raw
            if isinstance(positions, list):
                meta["positions_count"] = len(positions)
        except (json.JSONDecodeError, OSError):
            pass
    if html_path.exists():
        ht = html_path.stat()
        meta["html_rev"] = int(ht.st_mtime)
        meta["html_mtime"] = datetime.fromtimestamp(ht.st_mtime, tz=ICT).strftime("%Y-%m-%d %H:%M ICT")
    return meta


def _regenerate_portfolio_monitor(output: Path) -> Tuple[bool, str]:
    cmd = [sys.executable, "scripts/reporting/generate_portfolio_monitor.py", "--output", str(output)]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "")[-2000:]
            return False, err
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "regeneration timeout"
    except OSError as exc:
        return False, str(exc)


def serve_dashboard(output: Path, port: int = 8080, pos_path: Optional[Path] = None) -> None:
    """Serve repo root over HTTP with /api/quotes proxy (no browser CORS issues)."""
    serve_dir = ROOT
    html_path = output.resolve()
    pos_path = pos_path or ROOT / "data" / "raw" / "current_positions_derived.json"
    rel_name = output.relative_to(ROOT).as_posix()
    url = f"http://localhost:{port}/{rel_name}"
    tv_url = "https://scanner.tradingview.com/vietnam/scan"
    freeze_cache: Dict[str, Any] = {"payload": None, "saved_at": ""}
    disk_quotes, disk_label = load_quotes_freeze()
    if disk_quotes:
        freeze_cache["payload"] = disk_quotes
        freeze_cache["saved_at"] = disk_label

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(serve_dir), **kwargs)

        def log_message(self, fmt: str, *args) -> None:
            if args and str(args[0]).startswith(("GET /", "POST /")):
                logger.debug("HTTP %s", fmt % args)

        def end_headers(self) -> None:
            path = self.path.split("?")[0]
            if path.endswith(".html"):
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("Pragma", "no-cache")
            super().end_headers()

        def _send_json(self, code: int, payload: Dict[str, Any], extra_headers: Optional[Dict[str, str]] = None) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            if extra_headers:
                for k, v in extra_headers.items():
                    self.send_header(k, v)
            self.end_headers()
            try:
                self.wfile.write(body)
            except (ConnectionAbortedError, BrokenPipeError, OSError):
                return

        def do_GET(self) -> None:
            path = self.path.split("?")[0]
            if path == "/api/meta":
                self._send_json(200, _positions_meta(pos_path, html_path))
                return
            if path == "/api/freeze":
                self._send_json(
                    200,
                    {
                        "saved_at": freeze_cache.get("saved_at") or disk_label,
                        "quotes": freeze_cache.get("payload") or disk_quotes,
                        "frozen": True,
                    },
                )
                return
            if path.startswith("/regenerate/"):
                key = path.split("/regenerate/", 1)[1]
                if key != "portfolio_monitor":
                    self._send_json(404, {"error": f"unknown report: {key}"})
                    return
                ok, err = _regenerate_portfolio_monitor(html_path)
                if not ok:
                    self._send_json(500, {"error": "regeneration failed", "stderr": err})
                    return
                self._send_json(200, {"ok": True, "report": key, "meta": _positions_meta(pos_path, html_path)})
                return
            return super().do_GET()

        def do_OPTIONS(self) -> None:
            if self.path.split("?")[0] in ("/api/quotes", "/api/freeze", "/api/meta") or self.path.split("?")[0].startswith("/regenerate/"):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()
                return
            self.send_error(404)

        def do_POST(self) -> None:
            if self.path.split("?")[0] != "/api/quotes":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length else b""
                req = urllib.request.Request(
                    tv_url,
                    data=body,
                    headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    payload = resp.read()
                # Cache TV response for freeze fallback
                try:
                    parsed = json.loads(payload.decode("utf-8"))
                    cached: Dict[str, Dict[str, Any]] = {}
                    for item in parsed.get("data", []):
                        tk = item.get("s", "").split(":")[-1]
                        vals = item.get("d", [])
                        if tk and len(vals) >= 3:
                            cached[tk] = {
                                "close": vals[1],
                                "change": vals[2],
                                "change_abs": vals[3] if len(vals) > 3 else 0,
                            }
                    if cached:
                        freeze_cache["payload"] = cached
                        freeze_cache["saved_at"] = datetime.now(ICT).strftime("%Y-%m-%d %H:%M ICT")
                except (json.JSONDecodeError, KeyError, IndexError):
                    pass
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                try:
                    self.wfile.write(payload)
                except (ConnectionAbortedError, BrokenPipeError, OSError):
                    return
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                logger.warning("Quote proxy failed: %s — serving freeze cache", exc)
                fallback = freeze_cache.get("payload") or disk_quotes
                if fallback:
                    self._send_json(
                        200,
                        {"data": [], "frozen": True, "saved_at": freeze_cache.get("saved_at") or disk_label, "quotes": fallback},
                        extra_headers={"X-Quote-Frozen": "1"},
                    )
                else:
                    self._send_json(502, {"error": str(exc), "frozen": False})

    class _ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        allow_reuse_address = True
        daemon_threads = True
    with _ThreadedServer(("127.0.0.1", port), _Handler) as httpd:
        logger.info(
            "Serving %s at %s (quotes: /api/quotes, regen: /regenerate/portfolio_monitor) — Ctrl+C to stop",
            serve_dir,
            url,
        )
        threading.Timer(0.8, lambda: webbrowser.open(url + "?live=1")).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("Server stopped.")


_VND_DCHART = "https://dchart-api.vndirect.com.vn/dchart/history"
_VND_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
    "Referer": "https://dchart.vndirect.com.vn/",
    "Origin": "https://dchart.vndirect.com.vn",
}

# Display boards like VNDirect: 4 indices. VND dchart tickers (verified 2026-07-14).
_INDEX_BOARD_SPECS = [
    # (fa_symbol or None, vnd_symbol, key, label)
    ("VNINDEX", "VNINDEX", "VNINDEX", "VN-INDEX"),
    ("VN30", "VN30", "VN30", "VN30"),
    (None, "VN100", "VN100", "VN100"),  # FireAnt historical-quotes often empty
    ("HNXINDEX", "HNX", "HNXINDEX", "HNX-INDEX"),  # VND ticker = HNX (not HNXINDEX)
]


def _fetch_vnd_intraday(symbol: str, session_date: date) -> Dict[str, Any]:
    """1-minute OHLC from VNDirect dchart-api (TradingView-compatible history)."""
    import requests

    start = datetime(session_date.year, session_date.month, session_date.day, 8, 45, tzinfo=ICT)
    end = datetime(session_date.year, session_date.month, session_date.day, 15, 15, tzinfo=ICT)
    url = (
        f"{_VND_DCHART}?symbol={symbol}&resolution=1"
        f"&from={int(start.timestamp())}&to={int(end.timestamp())}"
    )
    r = requests.get(url, headers=_VND_HEADERS, timeout=25)
    r.raise_for_status()
    raw = r.json()
    if not isinstance(raw, dict) or raw.get("s") not in ("ok", None):
        # some payloads omit s; require t/c
        if not (isinstance(raw, dict) and raw.get("t") and raw.get("c")):
            raise RuntimeError(f"VND dchart bad payload for {symbol}: {str(raw)[:120]}")
    times = list(raw.get("t") or [])
    closes = [float(x) for x in (raw.get("c") or [])]
    opens = [float(x) for x in (raw.get("o") or [])] or closes[:]
    highs = [float(x) for x in (raw.get("h") or [])] or closes[:]
    lows = [float(x) for x in (raw.get("l") or [])] or closes[:]
    vols = [float(x or 0) for x in (raw.get("v") or [])]
    if len(vols) < len(closes):
        vols.extend([0.0] * (len(closes) - len(vols)))
    if not times or not closes:
        raise RuntimeError(f"VND dchart empty for {symbol} on {session_date}")
    return {
        "t": times,
        "c": closes,
        "o": opens,
        "h": highs,
        "l": lows,
        "v": vols[: len(closes)],
        "n": len(closes),
    }


def _vnd_intraday_svg(
    times: List[int],
    closes: List[float],
    volumes: List[float],
    ref: float,
) -> str:
    """VNDirect-style: 9h–15h path vs ref + minute volume (display-only)."""
    if len(closes) < 2:
        return '<div class="idx-meta">No intraday bars</div>'

    w, h_price, h_vol, pad = 320.0, 108.0, 34.0, 4.0
    # Session window ICT for x-scale (ATO 9:00 → ATC 15:00)
    day0 = datetime.fromtimestamp(times[0], tz=ICT).date()
    t0 = datetime(day0.year, day0.month, day0.day, 9, 0, tzinfo=ICT).timestamp()
    t1 = datetime(day0.year, day0.month, day0.day, 15, 0, tzinfo=ICT).timestamp()
    span_t = (t1 - t0) or 1.0

    lo = min(min(closes), ref)
    hi = max(max(closes), ref)
    span_p = (hi - lo) or 1.0

    def x_of(ts: float) -> float:
        return pad + (w - 2 * pad) * max(0.0, min(1.0, (ts - t0) / span_t))

    def y_of(v: float) -> float:
        return h_price - pad - (h_price - 2 * pad) * (v - lo) / span_p

    # Split polyline by whether above/below ref for red/green segments
    segs_up: List[str] = []
    segs_dn: List[str] = []
    pts = [(x_of(float(ts)), y_of(c), c >= ref) for ts, c in zip(times, closes)]
    cur: List[str] = []
    cur_up = pts[0][2]
    for i, (x, y, is_up) in enumerate(pts):
        if i and is_up != cur_up and cur:
            # close segment at midpoint
            (lx, ly, _) = pts[i - 1]
            mx, my = (lx + x) / 2, (ly + y) / 2
            cur.append(f"{mx:.2f},{my:.2f}")
            (segs_up if cur_up else segs_dn).append(" ".join(cur))
            cur = [f"{mx:.2f},{my:.2f}", f"{x:.2f},{y:.2f}"]
            cur_up = is_up
        else:
            cur.append(f"{x:.2f},{y:.2f}")
    if cur:
        (segs_up if cur_up else segs_dn).append(" ".join(cur))

    y_ref = y_of(ref)
    polylines = []
    for seg in segs_up:
        polylines.append(
            f'<polyline points="{seg}" fill="none" stroke="var(--g)" stroke-width="1.6" '
            f'vector-effect="non-scaling-stroke"/>'
        )
    for seg in segs_dn:
        polylines.append(
            f'<polyline points="{seg}" fill="none" stroke="var(--r)" stroke-width="1.6" '
            f'vector-effect="non-scaling-stroke"/>'
        )

    vmax = max(volumes) if volumes else 0.0
    vmax = vmax or 1.0
    n = len(volumes)
    bar_w = max(0.6, (w - 2 * pad) / max(n, 1) * 0.85)
    rects = []
    for i, (ts, vol) in enumerate(zip(times, volumes)):
        if vol <= 0:
            continue
        bh = (h_vol - 2) * (vol / vmax)
        x = x_of(float(ts)) - bar_w / 2
        y = h_vol - bh
        rects.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{bh:.2f}" '
            f'fill="rgba(59,130,246,.7)"/>'
        )

    hours = [("9h", 9), ("10h", 10), ("11h", 11), ("12h", 12), ("13h", 13), ("14h", 14), ("15h", 15)]
    axis = "".join(
        f'<span>{lab}</span>' for lab, _ in hours
    )

    return (
        f'<div class="idx-chart-wrap">'
        f'<svg class="idx-spark" viewBox="0 0 {w:.0f} {h_price:.0f}" preserveAspectRatio="none" '
        f'aria-label="Intraday 1m">'
        f'<line x1="{pad}" y1="{y_ref:.2f}" x2="{w - pad}" y2="{y_ref:.2f}" '
        f'stroke="#eab308" stroke-width="1" stroke-dasharray="3 3" '
        f'vector-effect="non-scaling-stroke"/>'
        f'{"".join(polylines)}'
        f"</svg>"
        f'<svg class="idx-vol" viewBox="0 0 {w:.0f} {h_vol:.0f}" preserveAspectRatio="none" '
        f'aria-label="Intraday volume">'
        f'{"".join(rects)}</svg>'
        f'<div class="idx-axis">{axis}</div>'
        f"</div>"
    )


def load_index_boards(lookback_days: int = 12) -> List[Dict[str, Any]]:
    """
    VNDirect-style index boards: real 1m intraday from VND dchart + ATC facts.
    FireAnt used for ATC O/H/L/V when available; VND when FireAnt lacks the symbol (VN100).
    """
    from datetime import timedelta

    import pandas as pd
    import requests

    from src.data.fireant_client import get_client

    end = datetime.now(ICT).date()
    # Prefer last session with VND bars (weekends → walk back)
    session_date = end
    client = get_client()
    boards: List[Dict[str, Any]] = []

    for fa_sym, vnd_sym, key, label in _INDEX_BOARD_SPECS:
        board: Dict[str, Any] = {"key": key, "label": label, "symbol": vnd_sym}
        # ATC facts from FireAnt when possible
        atc: Dict[str, Any] = {}
        if fa_sym:
            try:
                start = (session_date - timedelta(days=lookback_days)).isoformat()
                df = client.get_ohlcv(fa_sym, start, session_date.isoformat())
                if df is not None and not df.empty:
                    df = df.sort_values("date")
                    last = df.iloc[-1]
                    prev = df.iloc[-2] if len(df) >= 2 else last
                    atc = {
                        "asof": str(pd.Timestamp(last["date"]).date()),
                        "close": float(last["close"]),
                        "open": float(last["open"]),
                        "high": float(last["high"]),
                        "low": float(last["low"]),
                        "prev_close": float(prev["close"]),
                        "volume": float(last.get("volume") or 0),
                        "atc_source": "FireAnt REST historical-quotes",
                    }
                    session_date = pd.Timestamp(last["date"]).date()
            except Exception as exc:
                logger.warning("FireAnt ATC %s failed: %s", fa_sym, exc)

        # Intraday 1m from VND
        try:
            # If ATC asof known, align session; else try today then yesterday
            attempt_dates = [session_date]
            if session_date != end:
                attempt_dates.append(end)
            attempt_dates.append(end - timedelta(days=1))
            intra = None
            used_date = session_date
            last_err = None
            for dtry in attempt_dates:
                try:
                    intra = _fetch_vnd_intraday(vnd_sym, dtry)
                    used_date = dtry
                    break
                except Exception as exc:
                    last_err = exc
            if intra is None:
                raise last_err or RuntimeError("no bars")
            closes = intra["c"]
            close = closes[-1]
            open_ = intra["o"][0]
            high = max(intra["h"])
            low = min(intra["l"])
            vol_sum = float(sum(intra["v"]))
            prev_close = float(atc.get("prev_close") or open_)
            # Prefer FireAnt ATC close if same session date; else VND last
            if atc and atc.get("asof") == str(used_date):
                close = float(atc["close"])
                open_ = float(atc.get("open") or open_)
                high = float(atc.get("high") or high)
                low = float(atc.get("low") or low)
                vol_disp = float(atc.get("volume") or vol_sum)
                prev_close = float(atc["prev_close"])
            else:
                vol_disp = vol_sum or float(atc.get("volume") or 0)
            chg = close - prev_close
            chg_pct = (chg / prev_close * 100.0) if prev_close else 0.0
            board.update(
                {
                    "asof": str(used_date),
                    "close": close,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "prev_close": prev_close,
                    "chg": chg,
                    "chg_pct": chg_pct,
                    "volume": vol_disp,
                    "intraday_t": intra["t"],
                    "intraday_c": closes,
                    "intraday_v": intra["v"],
                    "status": "Đóng cửa",
                    "vnd_symbol": vnd_sym,
                    "n_bars": intra["n"],
                    "chart_note": (
                        f"chart = VNDirect dchart 1m ({vnd_sym}) · "
                        f"ATC O/H/L/V = {atc.get('atc_source', 'VND 1m derived')}"
                    ),
                    "source": "VNDirect dchart-api + FireAnt ATC when available",
                }
            )
        except Exception as exc:
            logger.warning("VND intraday %s failed: %s", vnd_sym, exc)
            if atc:
                close = float(atc["close"])
                prev_close = float(atc["prev_close"])
                chg = close - prev_close
                board.update(
                    {
                        **{k: atc[k] for k in ("asof", "close", "open", "high", "low", "prev_close", "volume")},
                        "chg": chg,
                        "chg_pct": (chg / prev_close * 100.0) if prev_close else 0.0,
                        "status": "Đóng cửa",
                        "error_chart": str(exc),
                        "chart_note": "intraday unavailable — ATC only (FireAnt)",
                    }
                )
            else:
                board["error"] = str(exc)
        boards.append(board)
        time.sleep(0.05)
    return boards


def render_index_boards_html(boards: List[Dict[str, Any]]) -> str:
    cards = []
    for b in boards:
        if b.get("error") and not b.get("close"):
            cards.append(
                f'<div class="index-chart-card">'
                f'<div class="index-chart-label">{escape(b.get("label", "?"))}</div>'
                f'<div class="idx-meta" style="margin-top:10px">Unavailable: {escape(str(b["error"]))}</div>'
                f'<div class="idx-src">source = VNDirect / FireAnt</div></div>'
            )
            continue
        up = b.get("chg", 0) > 0
        flat = abs(b.get("chg", 0)) < 1e-9
        chg_cls = "flat" if flat else ("up" if up else "down")
        arrow = "→" if flat else ("▲" if up else "▼")
        chg_abs = f"{b.get('chg', 0):+,.2f}"
        chg_pct = f"{b.get('chg_pct', 0):+.2f}%"
        vol_s = f"{b.get('volume', 0):,.0f}"
        chart_html = ""
        if b.get("intraday_c") and b.get("intraday_t"):
            chart_html = _vnd_intraday_svg(
                b["intraday_t"],
                b["intraday_c"],
                b.get("intraday_v") or [],
                float(b.get("prev_close") or b["intraday_c"][0]),
            )
        elif b.get("error_chart"):
            chart_html = (
                f'<div class="idx-meta" style="margin:8px 0;color:var(--a)">'
                f'Intraday fail: {escape(str(b["error_chart"]))}</div>'
            )
        cards.append(
            f'<div class="index-chart-card">'
            f'<div class="index-chart-label">{escape(b["label"])} '
            f'<span style="font-weight:400;color:var(--faint)">'
            f'({escape(b.get("vnd_symbol") or b.get("symbol") or "")})</span></div>'
            f'<div class="idx-head">'
            f'<div class="idx-price">{b["close"]:,.2f}</div>'
            f'<div class="idx-chg {chg_cls}">{arrow} {chg_abs} ({chg_pct})</div>'
            f"</div>"
            f"{chart_html}"
            f'<div class="idx-meta">'
            f'KL: <strong>{vol_s}</strong> CP · O/H/L '
            f'{b["open"]:,.2f}/{b["high"]:,.2f}/{b["low"]:,.2f}<br>'
            f'Status: <strong>{escape(b.get("status", "—"))}</strong> · as-of {escape(b.get("asof", "?"))}'
            f' · bars={b.get("n_bars", "—")}'
            f"</div>"
            f'<div class="idx-src">{escape(b.get("chart_note", ""))}</div>'
            f"</div>"
        )
    return (
        '<div class="slabel" id="pm-index">Index Boards '
        '<span style="font-size:9px;color:var(--muted);font-weight:400;text-transform:none;letter-spacing:0">'
        "intraday 1m · VNDirect dchart · VNINDEX / VN30 / VN100 / HNX</span></div>\n"
        f'<div class="index-strip">\n{"".join(cards)}\n</div>'
    )


def render_html(
    portfolio: Dict[str, Any],
    regime: Dict[str, Any],
    positions_mtime: str,
    positions_rev: int,
    quote_time: str,
    new_t1: List[Dict[str, Any]],
    holding_actions: List[Dict[str, Any]],
    all_tickers_list: List[Dict[str, Any]],
    daily_scan: Dict[str, Any],
    scan_csv: Dict[str, Dict[str, Any]],
    all_tickers_json: str,
    initial_quotes_json: str = "{}",
    freeze_saved_at: str = "",
    ma_ctx_map: Optional[Dict[str, Dict[str, Any]]] = None,
    ma_ctx_asof: str = "",
    ma_panel=None,
    ma_panel_end: str = "",
    positions_content_key: str = "0",
    index_boards_html: str = "",
) -> str:
    ma_ctx_map = ma_ctx_map or {}
    _inst_accum_index = build_inst_accum_ticker_index(load_institutional_accumulation_compact())
    # Street-research availability (content-free contract). Watchlist tables only — the
    # holdings table is deliberately left alone so this never sits beside a P&L decision.
    _street_cov_index = build_street_coverage_index(load_street_coverage_compact())
    _position_ctx_map = position_context_by_symbol(load_position_context())
    rows = portfolio["rows"]
    tag_weights = portfolio["tag_weights"]
    alerts = portfolio["alerts"]
    n_positions = portfolio["n_positions"]
    regime_code = regime.get("regime", "?")
    regime_date = regime.get("asof_date", "?")

    total_pnl_cls = _pnl_class(portfolio["total_pnl"])
    kpi_pnl_border = "ok" if portfolio["total_pnl"] >= 0 else "bad"
    hhi_border = "ok" if portfolio["hhi"] < 1500 else ("warn" if portfolio["hhi"] < 2500 else "bad")
    largest_tk = portfolio["largest"]["ticker"] if portfolio["largest"] else "—"
    largest_wt = portfolio["largest"]["weight"] if portfolio["largest"] else 0

    # D3/D4 display footnotes (flags gated)
    prop_cash_line = ""
    prop_tilt_summary = ""
    prop_tilt_for_symbol = lambda sym: ""  # noqa: E731
    try:
        from src.trading.overlays.propagation_display import (
            build_portfolio_cash_footnote_html,
            build_portfolio_tilt_summary_html,
            is_sector_annotation_enabled,
            symbol_tilt_tag_html,
        )
        prop_cash_line = build_portfolio_cash_footnote_html()
        if is_sector_annotation_enabled():
            prop_tilt_for_symbol = lambda sym: symbol_tilt_tag_html(sym.replace("HOSE:", "").replace("HNX:", ""))  # noqa: E731
            prop_tilt_summary = build_portfolio_tilt_summary_html(
                [{"symbol": r["ticker"], "mkt_value_vnd": r["mkt_value"]} for r in rows],
                None,
                include_empty_sectors=True,
            )
    except Exception:
        pass

    # System controls + live mode (UI only; server on :8091)
    sys_controls_html = ""
    sys_controls_js = ""
    live_mode_js = ""
    report_controls_css = ""
    try:
        from src.trading.overlays.propagation_display import (
            build_live_mode_js,
            build_report_controls_css,
            build_system_controls_html,
            build_system_controls_js,
        )
        report_controls_css = build_report_controls_css()
        sys_controls_html = build_system_controls_html()
        sys_controls_js = build_system_controls_js()
        live_mode_js = build_live_mode_js("portfolio_monitor")
    except Exception:
        pass

    # Sector bar
    sorted_tags = sorted(tag_weights.items(), key=lambda x: -x[1])
    sector_html = []
    legend_html = []
    for i, (tag, wt) in enumerate(sorted_tags):
        color = _SECTOR_COLORS[i % len(_SECTOR_COLORS)]
        sector_html.append(
            f'<div style="width:{wt:.1f}%;background:{color}" title="{escape(tag)}: {wt:.1f}%">'
            f'{escape(tag)[:8] if wt > 8 else ""}</div>'
        )
        legend_html.append(
            f'<span class="sector-legend-item">'
            f'<span class="sector-legend-dot" style="background:{color}"></span>'
            f'{escape(tag)} <span class="dim">{wt:.1f}%</span></span>'
        )

    # Position rows
    pos_rows = []
    for r in rows:
        bc = _border_class(r["pnl_pct"])
        pnl_cls = _pnl_class(r["pnl"])
        day_cls = _pnl_class(r["day_chg_abs"])

        # Cloud status from scan CSV (position_context contract overrides frozen fields)
        csv_row = scan_csv.get(r["ticker"], {})
        ctx_rec = _position_ctx_map.get(r["ticker"], {})
        in_scan = bool(csv_row) or ctx_rec.get("in_scan")
        a3 = ctx_rec.get("a3_cloud_bull") if ctx_rec else csv_row.get("a3_cloud_bull")
        s3 = ctx_rec.get("s3_cloud_bull") if ctx_rec else csv_row.get("s3_cloud_bull")
        cloud_html = ""
        if a3 is True: cloud_html += '<span class="cloud-badge cloud-bull">A3</span>'
        elif a3 is False: cloud_html += '<span class="cloud-badge cloud-bear">A3</span>'
        if s3 is True: cloud_html += '<span class="cloud-badge cloud-bull">S3</span>'
        elif s3 is False: cloud_html += '<span class="cloud-badge cloud-bear">S3</span>'
        if not cloud_html:
            cloud_html = _not_in_scan_html() if not in_scan else '<span class="dim">—</span>'

        # A3 CTX: condensed cell = ema_dist · ED:bucket · RS:rank
        ema_dist = (ctx_rec.get("a3_ema_dist_pct") if ctx_rec else None) or csv_row.get("a3_ema_dist_pct", 0)
        ed_bucket = str((ctx_rec.get("ed_score_bucket") if ctx_rec else None) or csv_row.get("ed_score_bucket", "") or "")
        rs_rank = str((ctx_rec.get("a3_rank_bucket") if ctx_rec else None) or csv_row.get("a3_rank_bucket", "") or "")
        ctx_parts = []
        if ema_dist:
            ctx_parts.append(f'<span class="mono {_pnl_class(ema_dist)}">{ema_dist:+.1f}%</span>')
        if ed_bucket:
            ed_cls = "up" if ed_bucket == "optimal" else ("flat" if ed_bucket == "ok" else "dim")
            ctx_parts.append(f'<span class="{ed_cls}" title="ED: {escape(ed_bucket)}">ED:{_abbrev_ed_bucket(ed_bucket)}</span>')
        if rs_rank:
            rk_cls = "up" if rs_rank == "high" else ("flat" if rs_rank == "medium" else "dim")
            ctx_parts.append(f'<span class="{rk_cls}" title="RS rank: {escape(rs_rank)}">RS:{_abbrev_rs_rank(rs_rank)}</span>')
        if ctx_parts:
            a3_ctx_html = ' · '.join(ctx_parts)
        elif not in_scan:
            a3_ctx_html = _not_in_scan_html()
        else:
            a3_ctx_html = '<span class="dim">—</span>'

        # Trail Δ%: (current - trail) / current. CSV trail_price is in kVND.
        trail_price_kvnd = (ctx_rec.get("trail_price_kvnd") if ctx_rec else None) or csv_row.get("trail_price", 0)
        trail_price = trail_price_kvnd * 1000 if trail_price_kvnd else 0
        if trail_price and trail_price > 0 and r["current"] > 0:
            trail_delta = ((r["current"] - trail_price) / r["current"]) * 100
            trail_cls = "up" if trail_delta > 5 else ("flat" if trail_delta > 0 else "down")
            trail_html = f'<span class="mono {trail_cls}">{trail_delta:+.1f}%</span>'
        elif not in_scan:
            trail_html = _no_setup_metric_html("Trail Δ%")
        else:
            trail_html = '<span class="dim">—</span>'

        # RS Correction bucket + improving flag
        rs_bucket = str((ctx_rec.get("rs_correction_bucket") if ctx_rec else None) or csv_row.get("rs_correction_bucket", "") or "")
        rs_improving = (ctx_rec.get("rs_correction_improving") if ctx_rec else None)
        if rs_improving is None:
            rs_improving = csv_row.get("rs_correction_improving")
        if rs_bucket:
            rs_cls = "up" if "leader" in rs_bucket else ("flat" if "outperform" in rs_bucket else "dim")
            rs_short = _abbrev_rs_corr(rs_bucket)
            imp_flag = " ✦" if rs_improving else ""
            rs_html = f'<span class="{rs_cls}" title="{escape(rs_bucket)}">{rs_short}{imp_flag}</span>'
        elif not in_scan:
            rs_html = _not_in_scan_html()
        else:
            rs_html = '<span class="dim">—</span>'

        # Holding action badge
        h_action = next((h for h in holding_actions if h["ticker"] == r["ticker"]), None)
        action_html = ""
        if h_action:
            ac = _action_badge_class(h_action["action"])
            action_html = f'<span class="action-badge {ac}">{_action_short(h_action["action"])}</span>'

        # Signal quality badge — S2/S1 filter (current-day vol reading)
        pos_s2_pass = csv_row.get("s2_pass")
        pos_s2_vol = float(csv_row.get("s2_vol_mult", 0) or 0)
        pos_s1_pass = csv_row.get("s1_pass")
        pos_s1_prox = float(csv_row.get("s1_prox_52wk", 0) or 0)
        if in_scan:
            sig_qual_html = _render_sig_quality(pos_s2_pass, pos_s2_vol, pos_s1_pass, pos_s1_prox, is_current_day=True)
        else:
            sig_qual_html = _no_setup_metric_html("SIG")

        # P&L VND as tooltip on P&L% cell
        pnl_vnd_title = f'title="{_fmt_vnd(r["pnl"])} VND"'
        ma_display = build_ma_display_ctx(
            r["ticker"], ma_ctx_map.get(r["ticker"]), r["current"], ma_panel
        )
        ma_open = _ma_cell_open_tag(ma_display)
        ma_inner = _render_ma_quick_slow_cell(ma_display, ma_panel_end=ma_panel_end)

        pos_rows.append(f"""<tr class="{bc}" data-ticker="{escape(r["ticker"])}">
  <td><span class="tk">{escape(r["ticker"])}</span>{prop_tilt_for_symbol(r["ticker"])} {action_html}</td>
  <td class="r-num mono" data-field="lots">{r["lots"]:,.0f}</td>
  <td class="r-num mono" data-field="entry">{_fmt_price(r["entry"])}</td>
  <td class="r-num mono" data-field="weight">{r["weight"]:.1f}%</td>
  <td class="r-num mono" data-field="close">{_fmt_price(r["current"])} <span class="mono {day_cls}" style="font-size:10px" data-field="change">{r["day_chg_pct"]:+.1f}%</span></td>
  <td class="r-num mono {pnl_cls}" data-field="pnl_pct" {pnl_vnd_title}>{r["pnl_pct"]:+.1f}%</td>
  <td>{cloud_html}</td>
  <td class="ctx-cell">{a3_ctx_html}</td>
  {ma_open}{ma_inner}</td>
  <td class="r-num">{trail_html}</td>
  <td>{rs_html}</td>
  <td>{sig_qual_html}</td>
</tr>""")

    total_day_chg = sum(r["day_chg_abs"] * r["lots"] for r in rows)
    total_day_pct = (total_day_chg / (portfolio["total_mkt"] - total_day_chg) * 100) if portfolio["total_mkt"] > total_day_chg else 0
    tdc = _pnl_class(total_day_chg)
    tpc = _pnl_class(portfolio["total_pnl"])

    total_row = f"""<tr style="background:var(--s2);font-weight:700;">
  <td style="font-size:11px;text-transform:uppercase;letter-spacing:.06em;">TOTAL</td>
  <td colspan="2"></td>
  <td class="r-num mono">100%</td>
  <td class="r-num mono" id="total-mkt">{_fmt_vnd(portfolio["total_mkt"])} <span class="mono {tdc}" style="font-size:10px" id="total-day">{total_day_pct:+.1f}%</span></td>
  <td class="r-num mono {tpc}" id="total-pnl-pct" title="{_fmt_vnd(portfolio["total_pnl"])} VND">{portfolio["total_pnl_pct"]:+.1f}%</td>
  <td colspan="6"></td>
</tr>"""

    # Alert cards
    alert_cards = []
    for a in alerts:
        dot_cls = "dot-r" if a["type"] == "r" else "dot-a"
        alert_cards.append(
            f'<div class="alert-card"><span class="alert-dot {dot_cls}"></span>'
            f'<span class="alert-text">{escape(a["msg"])}</span></div>'
        )
    alerts_section = ""
    if alert_cards:
        alerts_section = f"""
<div class="slabel" id="pm-alerts">RISK ALERTS</div>
<div class="alerts">
{"".join(alert_cards)}
</div>"""

    # T1/T2 Candidates section
    cand_section = ""
    if new_t1:
        breadth = daily_scan.get("breadth_zone", "—")
        t1_rows = []
        for c in new_t1:
            chg_cls = _pnl_class(c["change"])
            rsi_html = f'<span class="mono">{c["rsi"]:.0f}</span>' if c["rsi"] is not None else "—"
            pw = f'{c["perf_w"]:+.1f}%' if c.get("perf_w") is not None else "—"
            pm = f'{c["perf_1m"]:+.1f}%' if c.get("perf_1m") is not None else "—"
            pw_cls = _pnl_class(c.get("perf_w", 0)) if c.get("perf_w") is not None else "dim"
            pm_cls = _pnl_class(c.get("perf_1m", 0)) if c.get("perf_1m") is not None else "dim"
            held_tag = ' <span class="dim">(held)</span>' if c["in_portfolio"] else ""
            bc = "pos-border-b" if not c["in_portfolio"] else "pos-border-g"
            cand_ma = build_ma_display_ctx(
                c["ticker"], ma_ctx_map.get(c["ticker"]), c.get("close"), ma_panel
            )
            ma_open = _ma_cell_open_tag(cand_ma)
            ma_inner = _render_ma_quick_slow_cell(cand_ma, ma_panel_end=ma_panel_end)
            ia_cell = render_inst_accum_cell(c["ticker"], _inst_accum_index)
            street_cell = render_street_coverage_cell(c["ticker"], _street_cov_index)
            cand_sig = _render_sig_quality(
                c.get("s2_pass"), float(c.get("s2_vol_mult") or 0),
                c.get("s1_pass"), float(c.get("s1_prox_52wk") or 0),
                is_current_day=True,
            )
            pri_str = str(c.get("phase36_priority", "")) or "—"
            t1_rows.append(f"""<tr class="{bc}" data-ticker="{escape(c["ticker"])}">
  <td><span class="tk">{escape(c["ticker"])}</span>{held_tag}{prop_tilt_for_symbol(c["ticker"])}</td>
  <td class="tag-cell">{escape(c["sector"])}</td>
  <td class="r-num mono" data-field="close">{_fmt_price(c["close"])}</td>
  <td class="r-num mono {chg_cls}" data-field="change">{c["change"]:+.1f}%</td>
  <td>{rsi_html}</td>
  <td class="r-num mono">{c["ed_score"]:.2f}</td>
  <td class="tag-cell">{escape(c["rank"])}</td>
  <td class="r-num mono {pw_cls}">{pw}</td>
  <td class="r-num mono {pm_cls}">{pm}</td>
  <td>{cand_sig}</td>
  <td class="r-num mono dim">{pri_str}</td>
  <td>{ia_cell}</td>
  <td>{street_cell}</td>
  {ma_open}{ma_inner}</td>
</tr>""")

        _filter_legend = (
            '<div class="filter-legend">'
            '<strong>Sig Quality:</strong> '
            '<span class="sig-badge sig-s2">S2 ✓</span> vol ≥1.3× 50d avg (backtest MAR 2020-26: 2.48) &nbsp;|&nbsp; '
            '<span class="sig-badge sig-s1">S1 ✓</span> 52wk proximity ≤15% (backtest MAR 2020-26: 1.78) &nbsp;|&nbsp; '
            '<span class="sig-none">—</span> neither filter &nbsp;·&nbsp; '
            '<strong>S1 and S2 are independently validated alternative filters — never additive</strong> '
            '(combined use = DEGRADING-REJECT). MAR = strategy backtest stat, not per-trade expected return.'
            '</div>'
        )
        cand_section = f"""
<div class="slabel" id="pm-candidates">T1 CANDIDATES — NEW ENTRIES <span class="dim" style="font-weight:400;letter-spacing:0;">(breadth: {escape(breadth)}, T1 allowed with review, T2 blocked — sorted by operator priority)</span></div>
{_filter_legend}
<div class="board">
<table class="cand-table">
<thead><tr>
  <th>Ticker</th><th>Sector</th><th class="r-num">Price</th><th class="r-num">Day %</th>
  <th>RSI</th><th class="r-num">ED Score</th><th>Rank</th><th class="r-num">Wk</th><th class="r-num">1M</th>
  <th title="S2=vol≥1.3× or S1=52wk prox — standalone only">Sig</th>
  <th class="r-num" title="phase36 operator priority (lower=higher)">Pri</th>
  <th>Inst Flow</th>
  <th title="Street research availability only (house count + freshness). Advisory — does not feed signals/universe/OMS. No ratings or target prices by contract.">Street</th>
  <th>MA Ctx</th>
</tr></thead>
<tbody>
{"".join(t1_rows)}
</tbody>
</table>
</div>"""

    # Build "all tickers" toggleable section (8-column philosophy — validated A3 fields only)
    all_tickers_html = ""
    if all_tickers_list:
        at_rows = []
        prev_action = None
        for t in all_tickers_list:
            action = t["action"] or "OTHER"
            if action != prev_action:
                ac = _action_badge_class(action)
                at_rows.append(
                    f'<tr class="action-group-label"><td colspan="10">'
                    f'<span class="action-badge {ac}">{_action_short(action)}</span> '
                    f'({sum(1 for x in all_tickers_list if x["action"] == action)})</td></tr>'
                )
                prev_action = action
            chg_cls = _pnl_class(t["change"])
            cloud_html = ""
            if t["a3_bull"] is True: cloud_html += '<span class="cloud-badge cloud-bull">A3</span>'
            elif t["a3_bull"] is False: cloud_html += '<span class="cloud-badge cloud-bear">A3</span>'
            if t["s3_bull"] is True: cloud_html += '<span class="cloud-badge cloud-bull">S3</span>'
            elif t["s3_bull"] is False: cloud_html += '<span class="cloud-badge cloud-bear">S3</span>'
            if not cloud_html: cloud_html = '<span class="dim">—</span>'

            ema_d = t.get("ema_dist") or 0
            ed_bucket = t.get("ed_bucket", "")
            rs_rank = t.get("rank", "")
            ctx_parts = []
            if ema_d:
                ctx_parts.append(f'<span class="mono {_pnl_class(ema_d)}">{ema_d:+.1f}%</span>')
            if ed_bucket and ed_bucket != "—":
                ed_cls = "up" if ed_bucket == "optimal" else ("flat" if ed_bucket == "ok" else "dim")
                ctx_parts.append(f'<span class="{ed_cls}">ED:{_abbrev_ed_bucket(ed_bucket)}</span>')
            if rs_rank and rs_rank != "—":
                rk_cls = "up" if rs_rank == "high" else ("flat" if rs_rank == "medium" else "dim")
                ctx_parts.append(f'<span class="{rk_cls}">RS:{_abbrev_rs_rank(rs_rank)}</span>')
            a3_ctx_html = ' · '.join(ctx_parts) if ctx_parts else '<span class="dim">—</span>'

            trail_price_kvnd = t.get("trail_price", 0) or 0
            trail_price = trail_price_kvnd * 1000 if trail_price_kvnd else 0
            close_px = t.get("close") or 0
            if trail_price and trail_price > 0 and close_px > 0:
                trail_delta = ((close_px - trail_price) / close_px) * 100
                trail_cls = "up" if trail_delta > 5 else ("flat" if trail_delta > 0 else "down")
                trail_html = f'<span class="mono {trail_cls}">{trail_delta:+.1f}%</span>'
            else:
                trail_html = '<span class="dim">—</span>'

            rs_bucket = t.get("rs_bucket", "")
            rs_improving = t.get("rs_improving")
            if rs_bucket:
                rs_cls = "up" if "leader" in rs_bucket else ("flat" if "outperform" in rs_bucket else "dim")
                imp_flag = " ✦" if rs_improving else ""
                rs_html = f'<span class="{rs_cls}" title="{escape(rs_bucket)}">{_abbrev_rs_corr(rs_bucket)}{imp_flag}</span>'
            else:
                rs_html = '<span class="dim">—</span>'

            held = ' <span class="dim">(held)</span>' if t["in_portfolio"] else ""
            at_ma = build_ma_display_ctx(
                t["ticker"], ma_ctx_map.get(t["ticker"]), t.get("close"), ma_panel
            )
            at_ma_open = _ma_cell_open_tag(at_ma)
            at_ma_inner = _render_ma_quick_slow_cell(at_ma, ma_panel_end=ma_panel_end)
            at_ia = render_inst_accum_cell(t["ticker"], _inst_accum_index)
            at_street = render_street_coverage_cell(t["ticker"], _street_cov_index)
            at_sig = _render_sig_quality(
                t.get("s2_pass"), float(t.get("s2_vol_mult") or 0),
                t.get("s1_pass"), float(t.get("s1_prox_52wk") or 0),
                is_current_day=True,
            )
            at_rows.append(f"""<tr data-ticker="{escape(t["ticker"])}">
  <td><span class="tk">{escape(t["ticker"])}</span>{held}</td>
  <td class="tag-cell">{escape(t["sector"])}</td>
  <td class="r-num mono" data-field="close">{_fmt_price(t["close"])} <span class="mono {chg_cls}" style="font-size:10px" data-field="change">{t["change"]:+.1f}%</span></td>
  <td>{cloud_html}</td>
  <td class="ctx-cell">{a3_ctx_html}</td>
  <td class="r-num">{trail_html}</td>
  <td>{rs_html}</td>
  <td>{at_sig}</td>
  <td>{at_ia}</td>
  <td>{at_street}</td>
  {at_ma_open}{at_ma_inner}</td>
</tr>""")

        all_tickers_html = f"""
<div class="toggle-bar">
  <button class="toggle-btn" id="toggle-all-btn" onclick="toggleAllTickers()">Show all {len(all_tickers_list)} scanned tickers</button>
  <span class="dim" style="font-size:10px;">from daily_scan — grouped by action</span>
</div>
<div class="all-tickers-section" id="all-tickers">
<div class="board">
<table class="cand-table">
<thead><tr>
  <th>Ticker</th><th>Sector</th><th class="r-num">Price / Day</th>
  <th>Cloud</th><th>A3 CTX</th><th class="r-num">Trail &Delta;%</th><th>RS Corr</th>
  <th title="S2=vol≥1.3× or S1=52wk prox — standalone only">Sig</th>
  <th>Inst Flow</th>
  <th title="Street research availability only (house count + freshness). Advisory — does not feed signals/universe/OMS. No ratings or target prices by contract.">Street</th>
  <th>MA Ctx</th>
</tr></thead>
<tbody>
{"".join(at_rows)}
</tbody>
</table>
</div>
</div>"""

    generated_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    scan_asof = str(daily_scan.get("scan_date") or regime_date or "—")
    prov_html = render_provenance_header(
        title="Portfolio Monitor",
        generated_at=generated_utc,
        data_as_of=scan_asof,
        data_mode="MIXED",
        universe_scope="Held positions + daily scan candidates; live quotes + frozen scan/MA context",
        source_files=[
            "data/raw/current_positions_derived.json",
            "phase36_daily_scan_latest.csv",
            "data/state/position_context_daily.json",
            "data/research/ma_context_daily.json",
        ],
    )
    suite_nav_html = render_suite_nav("portfolio_monitor")
    perm_note_html = f'<p class="perm-precedence-note">{PERMISSION_PRECEDENCE_PM}</p>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Portfolio Monitor — Live Positions</title>
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
{_CSS}
{report_controls_css}
</style>
</head>
<body>
<div class="layout">
<aside class="sidebar">
  <div class="sidebar-logo">Portfolio Monitor</div>
  <h3>Overview</h3>
  <a href="#pm-alerts">Risk Alerts</a>
  <a href="#pm-candidates">T1 Candidates</a>
  <h3>Portfolio</h3>
  <a href="#pm-index">Index Boards</a>
  <a href="#pm-summary">Summary</a>
  <a href="#pm-sector">Sector</a>
  <a href="#pm-positions">Positions</a>
</aside>
<div class="page">

{prov_html}
{suite_nav_html}

<div class="hdr">
  <div class="hdr-title">
    Portfolio Monitor
    <span class="regime-badge regime-{escape(regime_code)}">Regime {escape(regime_code)}</span>
  </div>
  <div class="hdr-meta">
    Quotes: <span id="quote-time">{escape(quote_time)}</span><br>
    Positions file: {escape(positions_mtime)}<br>
    MA context: {escape(ma_ctx_asof or "—")}{f" · levels through {escape(ma_panel_end)}" if ma_panel_end else ""}<br>
    Regime as-of: {escape(regime_date)}
  </div>
</div>

<div class="banner">
  MONITORING ONLY — Not an order surface. Paper mode, no live_auto.
  Entry prices are derived/manual averages, not confirmed fills.
</div>

{sys_controls_html}
{perm_note_html}

<div class="live-bar">
  <span class="live-dot" id="live-dot"></span>
  <span class="live-label" id="live-label">LIVE</span>
  <button class="live-btn" onclick="refreshNow()">REFRESH NOW</button>
  <span class="live-time" id="live-time">—</span>
</div>

{index_boards_html}

<div class="slabel" id="pm-summary">PORTFOLIO SUMMARY</div>
<div class="pulse">
  <div class="kpi {kpi_pnl_border}" id="kpi-mkt">
    <div class="kpi-label">Invested Value</div>
    <div class="kpi-val" id="kpi-mkt-val">{_fmt_vnd(portfolio["total_mkt"])}</div>
    <div class="kpi-sub">Cost: {_fmt_vnd(portfolio["total_cost"])}</div>
  </div>
  <div class="kpi {kpi_pnl_border}" id="kpi-pnl">
    <div class="kpi-label">Unrealized P&L</div>
    <div class="kpi-val {total_pnl_cls}" id="kpi-pnl-val">{_fmt_vnd(portfolio["total_pnl"])}</div>
    <div class="kpi-sub {total_pnl_cls}" id="kpi-pnl-pct">{portfolio["total_pnl_pct"]:+.2f}%</div>
  </div>
  <div class="kpi ok">
    <div class="kpi-label">Positions</div>
    <div class="kpi-val">{portfolio["n_positions"]}</div>
    <div class="kpi-sub up">W {portfolio["n_winners"]}</div>
  </div>
  <div class="kpi {"ok" if largest_wt < 20 else "warn"}">
    <div class="kpi-label">Largest</div>
    <div class="kpi-val mono">{escape(largest_tk)}</div>
    <div class="kpi-sub">{largest_wt:.1f}%</div>
  </div>
  <div class="kpi {hhi_border}">
    <div class="kpi-label">HHI Concentration</div>
    <div class="kpi-val mono">{portfolio["hhi"]:.0f}</div>
    <div class="kpi-sub">{"Low" if portfolio["hhi"] < 1500 else "Moderate" if portfolio["hhi"] < 2500 else "High"}</div>
  </div>
  <div class="kpi ok">
    <div class="kpi-label">Day Change</div>
    <div class="kpi-val {tdc}" id="kpi-day-val">{_fmt_vnd(total_day_chg)}</div>
    <div class="kpi-sub {tdc}" id="kpi-day-pct">{total_day_pct:+.2f}%</div>
  </div>
</div>

<div class="slabel" id="pm-sector">SECTOR EXPOSURE</div>
<div class="sector-bar">
{"".join(sector_html)}
</div>
<div class="sector-legend">
{"".join(legend_html)}
</div>

{alerts_section}

{cand_section}

{all_tickers_html}

{prop_tilt_summary}

<div class="slabel" id="pm-positions">POSITION DETAIL</div>
{prop_cash_line}
<div class="board">
<table id="pos-table">
<thead><tr>
  <th>Ticker</th><th class="r-num">Lots</th><th class="r-num">Entry</th><th class="r-num">Wt%</th><th class="r-num">Price / Day</th>
  <th class="r-num">P&L %</th><th>Cloud</th><th>A3 CTX</th><th>MA Lines</th>
  <th class="r-num">Trail &Delta;%</th><th>RS Corr</th><th title="Signal quality: S2=vol≥1.3× (MAR 2.48) or S1=52wk prox (MAR 1.78) — standalone only, current-day reading">Sig</th>
</tr></thead>
<tbody>
{"".join(pos_rows)}
{total_row}
</tbody>
</table>
</div>

<div class="footer">
  Generated by VN Agent System — Portfolio Monitor v3.0<br>
  Data sources: TradingView scanner (quotes), current_positions_derived.json (positions),
  daily_scan.json (T1/T2 candidates), regime_state.json (regime).<br>
  Entry prices are derived weighted averages — not confirmed broker fills.<br>
  Generic TradingView indicators (RSI column, vs EMA10/SMA50/SMA200, MA Sig, Wk Perf) deliberately
  removed — not backtested in the VN Agent system. Dashboard shows only validated A3 cloud context.<br>
  Monitoring only. Not financial advice.
</div>

</div>

<script>
// ── Embedded position data for live refresh ──
const POSITIONS = {all_tickers_json};
const POSITIONS_REV = {positions_rev};
const POSITIONS_COUNT = {n_positions};
const POSITIONS_CONTENT_KEY = "{positions_content_key}";
const EMBEDDED_QUOTES = {initial_quotes_json};
const FREEZE_SAVED_AT = "{escape(freeze_saved_at)}";
const FREEZE_STORAGE_KEY = "vn_portfolio_monitor_freeze_v1";
const TV_COLUMNS = ["name","close","change","change_abs","open","high","low","volume","market_cap_basic",
  "price_52_week_high","price_52_week_low","EMA10","EMA20","EMA50","SMA20","SMA50","SMA200","RSI",
  "Perf.W","Perf.1M","Perf.3M","average_volume_10d_calc","sector","Recommend.MA"];

function fmtVND(v) {{
  if (Math.abs(v) >= 1e9) return (v/1e9).toFixed(1) + 'B';
  if (Math.abs(v) >= 1e6) return (v/1e6).toFixed(1) + 'M';
  return v.toLocaleString('en', {{maximumFractionDigits:0}});
}}
function fmtPrice(v) {{ return v.toLocaleString('en', {{maximumFractionDigits:0}}); }}
function pnlClass(v) {{ return v > 0 ? 'up' : v < 0 ? 'down' : 'flat'; }}

function quoteEndpoint() {{
  if (location.protocol === 'http:' &&
      (location.hostname === 'localhost' || location.hostname === '127.0.0.1')) {{
    return '/api/quotes';
  }}
  return 'https://scanner.tradingview.com/vietnam/scan';
}}

function setPriceCell(cell, price, dayChg) {{
  if (!cell) return;
  const chgEl = cell.querySelector('[data-field="change"]');
  const priceText = fmtPrice(price);
  if (chgEl) {{
    let textNode = null;
    for (const node of cell.childNodes) {{
      if (node.nodeType === 3) {{ textNode = node; break; }}
    }}
    if (!textNode) {{
      cell.insertBefore(document.createTextNode(priceText + ' '), chgEl);
    }} else {{
      textNode.textContent = priceText + ' ';
    }}
    chgEl.textContent = (dayChg >= 0 ? '+' : '') + dayChg.toFixed(1) + '%';
    chgEl.className = 'mono ' + pnlClass(dayChg);
    chgEl.style.fontSize = '10px';
  }} else {{
    cell.textContent = priceText;
  }}
}}

let refreshTimer = null;
let isLive = false;
let refreshCount = 0;
let lastUpdateTime = null;
let lastFreezeSavedAt = FREEZE_SAVED_AT || null;

function loadFreezeFromStorage() {{
  try {{
    const raw = localStorage.getItem(FREEZE_STORAGE_KEY);
    if (!raw) return null;
    const p = JSON.parse(raw);
    if (p && p.quotes && Object.keys(p.quotes).length) {{
      if (p.saved_at) lastFreezeSavedAt = p.saved_at;
      return p.quotes;
    }}
  }} catch (e) {{ /* ignore */ }}
  return null;
}}

function saveFreezeToStorage(quotes) {{
  try {{
    const savedAt = new Date().toLocaleString('en-GB', {{
      hour:'2-digit', minute:'2-digit', second:'2-digit',
      day:'2-digit', month:'short', year:'numeric'
    }}) + ' ICT';
    localStorage.setItem(FREEZE_STORAGE_KEY, JSON.stringify({{ saved_at: savedAt, quotes }}));
    lastFreezeSavedAt = savedAt;
  }} catch (e) {{ /* private mode */ }}
}}

function activeFreezeQuotes() {{
  return loadFreezeFromStorage() || EMBEDDED_QUOTES || {{}};
}}

function buildQuotesFromTvData(data) {{
  const quotes = {{}};
  for (const item of (data.data || [])) {{
    const tk = item.s.split(':').pop();
    const vals = item.d;
    quotes[tk] = {{}};
    TV_COLUMNS.forEach((c, i) => quotes[tk][c] = vals[i]);
  }}
  return quotes;
}}

function maSignedPct(v) {{
  if (v == null || Number.isNaN(v)) return '';
  return (v >= 0 ? '+' : '') + v.toFixed(1) + '%';
}}

function formatMaLeg(maName, distPct) {{
  if (!maName) return '—';
  return maName + (distPct == null ? '' : ' ' + maSignedPct(distPct));
}}

function updateMaCell(row, price) {{
  const cell = row.querySelector('.ma-cell');
  if (!cell) return;
  const qMa = cell.dataset.quickMa || '';
  const sMa = cell.dataset.slowMa || '';
  if (!qMa && !sMa) return;
  const win = cell.dataset.recentWindow || '?';
  const qLevel = parseFloat(cell.dataset.quickLevel || '');
  const sLevel = parseFloat(cell.dataset.slowLevel || '');
  const qDist = (qMa && qLevel > 0) ? ((price - qLevel) / qLevel * 100) : null;
  const sDist = (sMa && sLevel > 0) ? ((price - sLevel) / sLevel * 100) : null;
  const qTxt = formatMaLeg(qMa, qDist);
  const sTxt = formatMaLeg(sMa, sDist);
  const summary = cell.querySelector('summary');
  if (summary) {{
    summary.innerHTML = '<span class="mono dim">' + win + '</span> <span class="mono">Q:' + qTxt + '</span> · <span class="mono">S:' + sTxt + '</span>';
  }}
  const qVal = cell.querySelector('[data-ma-leg="quick"]');
  const sVal = cell.querySelector('[data-ma-leg="slow"]');
  if (qVal) qVal.textContent = qTxt;
  if (sVal) sVal.textContent = sTxt;
}}

function applyQuotes(quotes) {{
  if (!quotes || !Object.keys(quotes).length) return;

  let totalMkt = 0, totalCost = 0, totalDayChg = 0;
  let pricedN = 0;

  for (const pos of POSITIONS) {{
    // Merge live over embedded so a partial TV response cannot collapse NAV
    // (e.g. 5.3B instead of ~7.4B when some tickers are missing).
    const emb = (EMBEDDED_QUOTES || {{}})[pos.ticker] || {{}};
    const live = quotes[pos.ticker] || {{}};
    const q = Object.assign({{}}, emb, live);
    const price = (live.close > 0 ? live.close : (emb.close || 0));
    if (!(price > 0)) continue;
    pricedN += 1;
    const mkt = price * pos.lots;
    const cost = pos.entry * pos.lots;
    const pnl = mkt - cost;
    const pnlPct = pos.entry > 0 ? ((price / pos.entry) - 1) * 100 : 0;
    const dayChg = (live.change != null ? live.change : (q.change || 0));
    const dayAbs = (live.change_abs != null ? live.change_abs : (q.change_abs || 0));

    totalMkt += mkt;
    totalCost += cost;
    totalDayChg += dayAbs * pos.lots;

    const row = document.querySelector(`#pos-table tbody tr[data-ticker="${{pos.ticker}}"]`);
    if (!row) continue;

    setPriceCell(row.querySelector('[data-field="close"]'), price, dayChg);

    const pnlPctCell = row.querySelector('[data-field="pnl_pct"]');
    if (pnlPctCell) {{
      pnlPctCell.textContent = (pnlPct >= 0 ? '+' : '') + pnlPct.toFixed(1) + '%';
      pnlPctCell.className = 'r-num mono ' + pnlClass(pnlPct);
      pnlPctCell.title = fmtVND(pnl) + ' VND';
    }}
    updateMaCell(row, price);
  }}

  // Incomplete book → update row cells only; keep static KPI/TOTAL NAV.
  if (pricedN < POSITIONS.length) return;

  document.querySelectorAll('.cand-table [data-ticker]').forEach(row => {{
    const tk = row.dataset.ticker;
    const q = quotes[tk];
    if (!q) return;
    const chg = q.change || 0;
    const closeCell = row.querySelector('[data-field="close"]');
    if (closeCell && closeCell.querySelector('[data-field="change"]')) {{
      setPriceCell(closeCell, q.close || 0, chg);
    }} else {{
      if (closeCell) closeCell.textContent = fmtPrice(q.close || 0);
      const chgCell = row.querySelector('[data-field="change"]');
      if (chgCell) {{
        chgCell.textContent = (chg >= 0 ? '+' : '') + chg.toFixed(1) + '%';
        chgCell.className = 'r-num mono ' + pnlClass(chg);
      }}
    }}
  }});

  const totalPnl = totalMkt - totalCost;
  const totalPnlPct = totalCost > 0 ? ((totalMkt / totalCost) - 1) * 100 : 0;
  const totalDayPct = totalMkt > totalDayChg ? (totalDayChg / (totalMkt - totalDayChg) * 100) : 0;
  const el = id => document.getElementById(id);
  if (el('kpi-mkt-val')) el('kpi-mkt-val').textContent = fmtVND(totalMkt);
  if (el('kpi-pnl-val')) {{ el('kpi-pnl-val').textContent = fmtVND(totalPnl); el('kpi-pnl-val').className = 'kpi-val ' + pnlClass(totalPnl); }}
  if (el('kpi-pnl-pct')) {{ el('kpi-pnl-pct').textContent = (totalPnlPct >= 0 ? '+' : '') + totalPnlPct.toFixed(2) + '%'; el('kpi-pnl-pct').className = 'kpi-sub ' + pnlClass(totalPnlPct); }}
  if (el('kpi-day-val')) {{ el('kpi-day-val').textContent = fmtVND(totalDayChg); el('kpi-day-val').className = 'kpi-val ' + pnlClass(totalDayChg); }}
  if (el('kpi-day-pct')) {{ el('kpi-day-pct').textContent = (totalDayPct >= 0 ? '+' : '') + totalDayPct.toFixed(2) + '%'; el('kpi-day-pct').className = 'kpi-sub ' + pnlClass(totalDayChg); }}
  if (el('total-mkt')) {{
    const dayEl = el('total-day');
    el('total-mkt').childNodes[0].textContent = fmtVND(totalMkt) + ' ';
    if (dayEl) {{ dayEl.textContent = (totalDayPct >= 0 ? '+' : '') + totalDayPct.toFixed(1) + '%'; dayEl.className = 'mono ' + pnlClass(totalDayChg); }}
  }}
  if (el('total-pnl-pct')) {{
    el('total-pnl-pct').textContent = (totalPnlPct >= 0 ? '+' : '') + totalPnlPct.toFixed(1) + '%';
    el('total-pnl-pct').className = 'r-num mono ' + pnlClass(totalPnlPct);
    el('total-pnl-pct').title = fmtVND(totalPnl) + ' VND';
  }}
}}

async function refreshQuotes(forceLive) {{
  const allTickers = [...new Set([
    ...POSITIONS.map(p => (p.exchange || 'HOSE') + ':' + p.ticker),
    ...Array.from(document.querySelectorAll('.cand-table [data-ticker]')).map(r => {{
      const ex = r.dataset.exchange || 'HOSE';
      return ex + ':' + r.dataset.ticker;
    }})
  ])];

  if (location.protocol === 'file:') {{
    const el = id => document.getElementById(id);
    if (el('live-label')) el('live-label').textContent = 'OPEN VIA HTTP — run: scripts\\start_portfolio_monitor.bat';
    if (el('live-dot')) el('live-dot').classList.add('off');
    return;
  }}

  if (!forceLive && !forceLiveMode() && !isMarketOpen()) {{
    const frozen = activeFreezeQuotes();
    if (Object.keys(frozen).length) applyQuotes(frozen);
    setStatus(frozenLabel(), false);
    return;
  }}

  try {{
    const resp = await fetch(quoteEndpoint(), {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{ symbols: {{ tickers: allTickers }}, columns: TV_COLUMNS }})
    }});
    const data = await resp.json();
    if (!resp.ok && !data.quotes) throw new Error('HTTP ' + resp.status);

    if (data.frozen && data.quotes) {{
      applyQuotes(data.quotes);
      if (data.saved_at) lastFreezeSavedAt = data.saved_at;
      setStatus('FROZEN (offline) — ' + (data.saved_at || 'cached'), false);
      isLive = false;
      return;
    }}
    if (data.error) throw new Error(data.error);

    const quotes = buildQuotesFromTvData(data);
    applyQuotes(quotes);
    saveFreezeToStorage(quotes);

    refreshCount += 1;
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-GB', {{hour:'2-digit',minute:'2-digit',second:'2-digit'}});
    lastUpdateTime = timeStr;
    const el = id => document.getElementById(id);
    if (el('live-time')) el('live-time').textContent = 'Updated: ' + timeStr + ' (#' + refreshCount + ')';
    if (el('quote-time')) el('quote-time').textContent = now.toISOString().slice(0,16).replace('T',' ') + ' (live)';
    if (el('live-dot')) el('live-dot').classList.remove('off');
    if (isMarketOpen()) {{
      setStatus(forceLiveMode() && !isMarketOpen() ? 'LIVE (off-hours)' : 'LIVE', true);
      isLive = true;
    }} else {{
      setStatus(forceLiveMode() ? 'LIVE (off-hours)' : frozenLabel(), !forceLiveMode());
      isLive = forceLiveMode();
    }}
  }} catch (err) {{
    console.warn('Quote refresh failed:', err.message);
    const frozen = activeFreezeQuotes();
    if (Object.keys(frozen).length) {{
      applyQuotes(frozen);
      setStatus(frozenLabel() + ' (offline)', false);
    }} else {{
      const el = id => document.getElementById(id);
      if (el('live-dot')) el('live-dot').classList.add('off');
      if (el('live-label')) el('live-label').textContent = 'OFFLINE — ' + err.message;
    }}
    isLive = false;
  }}
}}

function refreshNow() {{
  refreshQuotes(true);
}}

// ?live=1 on localhost — poll TradingView outside VN session (weekends / after hours)
function forceLiveMode() {{
  if (location.protocol !== 'http:') return false;
  if (location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') return false;
  const q = new URLSearchParams(location.search);
  return q.get('live') === '1' || q.get('force_live') === '1';
}}

// VN session: Mon–Fri 09:00–11:30 + 13:00–15:00 ICT (user window 9am–3pm)
function ictNow() {{
  const now = new Date();
  const utc = now.getTime() + now.getTimezoneOffset() * 60000;
  return new Date(utc + 7 * 3600000);
}}
function isMarketOpen() {{
  const ict = ictNow();
  const day = ict.getDay();
  if (day === 0 || day === 6) return false;
  const hm = ict.getHours() * 100 + ict.getMinutes();
  return (hm >= 900 && hm < 1130) || (hm >= 1300 && hm < 1500);
}}
function nextSessionLabel() {{
  const ict = ictNow();
  const hm = ict.getHours() * 100 + ict.getMinutes();
  const day = ict.getDay();
  if (day === 0 || day === 6) return 'Mon 09:00 ICT';
  if (hm < 900) return '09:00 ICT';
  if (hm >= 1130 && hm < 1300) return '13:00 ICT';
  return 'tomorrow 09:00 ICT';
}}

function setStatus(label, dotOn) {{
  const el = id => document.getElementById(id);
  if (el('live-label')) el('live-label').textContent = label;
  if (el('live-dot')) {{
    if (dotOn) el('live-dot').classList.remove('off');
    else el('live-dot').classList.add('off');
  }}
}}

function frozenLabel() {{
  const ts = lastFreezeSavedAt || lastUpdateTime || FREEZE_SAVED_AT || 'last close';
  return 'FROZEN @ ' + ts + ' — live ' + nextSessionLabel();
}}

function tick() {{
  if (document.hidden) return;
  if (isMarketOpen() || forceLiveMode()) {{
    refreshQuotes(false);
  }} else {{
    const frozen = activeFreezeQuotes();
    if (Object.keys(frozen).length) applyQuotes(frozen);
    setStatus(frozenLabel(), false);
  }}
}}

function startSmart() {{
  if (refreshTimer) clearInterval(refreshTimer);
  const frozen = activeFreezeQuotes();
  if (Object.keys(frozen).length) {{
    applyQuotes(frozen);
    lastUpdateTime = lastFreezeSavedAt || FREEZE_SAVED_AT;
  }}
  if (isMarketOpen() || forceLiveMode()) {{
    refreshQuotes(false);
  }} else {{
    setStatus(frozenLabel() + ' — add ?live=1 for off-hours polling', false);
  }}
  refreshTimer = setInterval(tick, 5000);
}}

document.addEventListener('visibilitychange', () => {{
  if (document.hidden) {{
    if (isMarketOpen() || forceLiveMode()) setStatus('PAUSED — tab hidden', false);
  }} else {{
    if (isMarketOpen() || forceLiveMode()) {{
      setStatus(forceLiveMode() && !isMarketOpen() ? 'LIVE (off-hours)' : 'LIVE', true);
      refreshQuotes(false);
    }} else {{
      const frozen = activeFreezeQuotes();
      if (Object.keys(frozen).length) applyQuotes(frozen);
      setStatus(frozenLabel(), false);
    }}
  }}
}});

async function ensureFreshPositions() {{
  if (location.protocol !== 'http:') return;
  if (location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') return;
  try {{
    const resp = await fetch('/api/meta', {{cache: 'no-store'}});
    if (!resp.ok) return;
    const meta = await resp.json();
    // Structural fingerprint (ticker/lots/entry) — deliberately ignores file mtime,
    // which bumps on every routine price-refresh rewrite of the same file even when
    // the position list itself hasn't changed (was causing reload-and-scroll-to-top
    // on every sync_operator_portfolio_snapshot.py run). Only reload on a real change.
    if (meta.positions_content_key && meta.positions_content_key !== POSITIONS_CONTENT_KEY) {{
      const q = new URLSearchParams(location.search);
      q.set('_', String(Date.now()));
      location.replace(location.pathname + '?' + q.toString());
    }}
  }} catch (e) {{ /* offline / file:// */ }}
}}

ensureFreshPositions().finally(() => startSmart());

// Toggle all tickers
function toggleAllTickers() {{
  const section = document.getElementById('all-tickers');
  const btn = document.getElementById('toggle-all-btn');
  if (!section) return;
  const visible = section.classList.toggle('visible');
  btn.textContent = visible ? 'Hide all tickers' : 'Show all {len(all_tickers_list)} scanned tickers';
  btn.classList.toggle('active', visible);
}}

// Column sort
(function() {{
  const table = document.getElementById('pos-table');
  if (!table) return;
  const headers = table.querySelectorAll('th');
  const tbody = table.querySelector('tbody');
  let sortCol = -1, sortDir = 1;
  headers.forEach((th, idx) => {{
    th.addEventListener('click', () => {{
      const rows = Array.from(tbody.querySelectorAll('tr:not(:last-child)'));
      if (sortCol === idx) sortDir *= -1;
      else {{ sortCol = idx; sortDir = 1; }}
      headers.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
      th.classList.add(sortDir === 1 ? 'sort-asc' : 'sort-desc');
      rows.sort((a, b) => {{
        const av = a.cells[idx]?.textContent.trim().replace(/[,%BM ]/g, '') || '';
        const bv = b.cells[idx]?.textContent.trim().replace(/[,%BM ]/g, '') || '';
        const an = parseFloat(av), bn = parseFloat(bv);
        if (!isNaN(an) && !isNaN(bn)) return (an - bn) * sortDir;
        return av.localeCompare(bv) * sortDir;
      }});
      const totalRow = tbody.querySelector('tr:last-child');
      rows.forEach(r => tbody.insertBefore(r, totalRow));
    }});
  }});
}})();
</script>
{sys_controls_js}
{live_mode_js}
<script>
(function(){{
  var anchors=document.querySelectorAll('[id^="pm-"]');
  var links=document.querySelectorAll('.sidebar a');
  if(!anchors.length||!links.length)return;
  var obs=new IntersectionObserver(function(entries){{entries.forEach(function(e){{if(e.isIntersecting){{links.forEach(function(l){{l.classList.remove('active');}});var a=document.querySelector('.sidebar a[href="#'+e.target.id+'"]');if(a)a.classList.add('active');}}}});}},{{threshold:0.1,rootMargin:'-10% 0px -70% 0px'}});
  anchors.forEach(function(s){{obs.observe(s);}});
}})();
</script>
</div></div>
</body>
</html>"""
    return html


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate portfolio monitor dashboard")
    parser.add_argument("--quotes", type=Path, help="Path to quotes JSON (skip live fetch)")
    parser.add_argument("--positions", type=Path, help="Path to positions JSON")
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "portfolio_monitor_latest.html")
    parser.add_argument("--regime", type=Path, help="Path to regime_state.json")
    parser.add_argument("--serve", action="store_true", help="Generate then serve via HTTP (fixes CORS for live refresh)")
    parser.add_argument("--port", type=int, default=8080, help="HTTP port for --serve (default: 8080)")
    args = parser.parse_args()

    positions = load_positions(args.positions)
    regime = load_regime(args.regime)
    daily_scan = load_daily_scan()
    scan_csv = load_scan_csv_actions()
    tickers = [p["ticker"] for p in positions]
    held_set = set(tickers)

    # Collect all tickers (positions + candidates + all scan) for quote fetch
    candidate_tickers = daily_scan.get("new_entry_symbols", [])
    scan_tickers = list(scan_csv.keys())
    all_tickers = list(set(tickers + candidate_tickers + scan_tickers))

    pos_path = args.positions or ROOT / "data" / "raw" / "current_positions_derived.json"
    if pos_path.exists():
        mtime = datetime.fromtimestamp(pos_path.stat().st_mtime, tz=ICT)
        positions_mtime = mtime.strftime("%Y-%m-%d %H:%M ICT")
        positions_rev = int(pos_path.stat().st_mtime)
    else:
        positions_mtime = "unknown"
        positions_rev = 0
    positions_content_key = _positions_content_key(pos_path)

    if args.quotes:
        logger.info("Loading quotes from %s", args.quotes)
        quotes = load_quotes_from_file(args.quotes)
    else:
        logger.info("Fetching live quotes from TradingView for %d tickers...", len(all_tickers))
        quotes = fetch_quotes_tv(all_tickers)
        if not quotes:
            frozen, freeze_label = load_quotes_freeze()
            if frozen:
                logger.warning("TV fetch failed — using frozen quotes from %s", freeze_label)
                quotes = frozen
            else:
                logger.error("Failed to fetch quotes and no freeze file — aborting")
                sys.exit(1)

    freeze_label = save_quotes_freeze(quotes) if quotes else ""
    quote_time = freeze_label or datetime.now(ICT).strftime("%Y-%m-%d %H:%M ICT")
    initial_quotes_json = quotes_for_client_embed(quotes)

    portfolio = compute_portfolio(positions, quotes)
    new_t1, holding_actions, all_tickers_list = build_candidates(daily_scan, scan_csv, quotes, held_set)

    pos_json = json.dumps([
        {
            "ticker": p["ticker"],
            "entry": p.get("entry_price", 0) or 0,
            "lots": p.get("lots", 0) or 0,
            "exchange": _tv_exchange(p["ticker"]),
        }
        for p in positions
    ])

    ma_ctx_map, ma_ctx_asof = load_ma_context_map()
    ma_panel = _load_ma_panel()
    ma_panel_end = ""
    if ma_panel is not None and not ma_panel.empty:
        ma_panel_end = str(ma_panel["date"].max().date())

    try:
        from scripts.reporting.build_position_context_daily import build_position_context
        _pc = build_position_context()
        (ROOT / "data" / "state" / "position_context_daily.json").write_text(
            json.dumps(_pc, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("position_context_daily.json refreshed (%d positions)", _pc.get("n_positions", 0))
    except Exception as exc:
        logger.warning("position_context_daily build skipped: %s", exc)

    try:
        index_boards_html = render_index_boards_html(load_index_boards())
        logger.info("Index boards loaded from FireAnt")
    except Exception as exc:
        logger.warning("Index boards failed: %s", exc)
        index_boards_html = (
            '<div class="slabel" id="pm-index">Index Boards</div>'
            f'<div class="index-strip"><div class="index-chart-card">'
            f'<div class="idx-meta">Index boards unavailable: {escape(str(exc))}</div></div></div>'
        )

    html = render_html(
        portfolio, regime, positions_mtime, positions_rev, quote_time,
        new_t1, holding_actions, all_tickers_list, daily_scan, scan_csv, pos_json,
        initial_quotes_json=initial_quotes_json,
        freeze_saved_at=freeze_label,
        ma_ctx_map=ma_ctx_map,
        ma_ctx_asof=ma_ctx_asof,
        ma_panel=ma_panel,
        ma_panel_end=ma_panel_end,
        positions_content_key=positions_content_key,
        index_boards_html=index_boards_html,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    logger.info("Dashboard written to %s", args.output)
    logger.info(
        "Portfolio: %d positions, invested %s, P&L %s (%+.2f%%), T1 candidates: %d",
        portfolio["n_positions"],
        _fmt_vnd(portfolio["total_mkt"]),
        _fmt_vnd(portfolio["total_pnl"]),
        portfolio["total_pnl_pct"],
        len(new_t1),
    )

    if args.serve:
        serve_dashboard(args.output, port=args.port, pos_path=pos_path)


if __name__ == "__main__":
    main()
