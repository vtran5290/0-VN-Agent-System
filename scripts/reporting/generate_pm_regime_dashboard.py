"""
PM Regime Dashboard Generator
Reads data/raw/pm_dashboard_data.json (manually-curated content) and optionally
merges live macro fields from data/raw/manual_inputs.json + data/state/regime_state.json,
then renders the full dark-theme HTML to reports/pm_regime_dashboard_latest.html.

Usage:
  python scripts/reporting/generate_pm_regime_dashboard.py
  python scripts/reporting/generate_pm_regime_dashboard.py --output reports/pm_regime_dashboard_latest.html
  python scripts/reporting/generate_pm_regime_dashboard.py --data data/raw/pm_dashboard_data.json

Edit data/raw/pm_dashboard_data.json to update regime verdict, KPIs, tickers, events, risks,
and forward triggers. Re-run this script to regenerate the HTML.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.trading.reports.report_suite_common import (
    SUITE_NAV_CSS,
    PERMISSION_PRECEDENCE_PM,
    render_provenance_header,
    render_suite_nav,
)

GEOPOLITICAL_PULSE  = ROOT / "data" / "features" / "geopolitics" / "geopolitical_pulse.json"
REGIME_STATE_PATH   = ROOT / "data" / "state" / "regime_state.json"
BREADTH_C1_PATH     = ROOT / "data" / "research" / "regime" / "breadth_c1_series.parquet"
_GEO_ROUTING_FOOTER = (
    '<p class="footnote meta" style="margin-top:10px;font-size:11px;color:var(--muted);font-style:italic">'
    "SYSTEM ROUTING: Reporting only — does not feed signals, sizing, or final_action"
    "</p>"
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
logger = logging.getLogger("pm_dashboard")

# ── CSS ───────────────────────────────────────────────────────────────────────

_CSS = """
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
  background: var(--bg);
  color: var(--text);
  font-family: "IBM Plex Sans", Inter, system-ui, -apple-system, sans-serif;
  font-size: 13px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
  letter-spacing: -0.01em;
}
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.10); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.18); }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; } }
.page { flex: 1; min-width: 0; max-width: 1200px; margin: 0 auto; padding: 32px 24px 48px; }

/* HEADER */
.hdr { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 28px; border-bottom: 1px solid var(--border); padding-bottom: 14px; }
.hdr-title { font-size: 15px; font-weight: 700; letter-spacing: .02em; }
.hdr-meta { font-size: 11px; color: var(--muted); }

/* SECTION LABEL */
.slabel { font-size: 10px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); margin-bottom: 10px; }

/* S1 REGIME VERDICT */
.verdict {
  background: var(--s1);
  border: 1px solid var(--border);
  border-left: 4px solid var(--a);
  border-radius: 8px;
  padding: 14px 18px;
  margin-bottom: 20px;
}
.verdict-note { font-size: 11px; color: var(--muted); line-height: 1.55; margin-top: 10px; padding-top: 8px; border-top: 1px solid var(--border); }
.pills { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 0; }
.pill { font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 20px; letter-spacing: .02em; }
.pill-g { background: var(--gb); color: var(--g); border: 1px solid rgba(0,200,150,.25); }
.pill-a { background: var(--ab); color: var(--a); border: 1px solid rgba(245,158,11,.25); }
.pill-r { background: var(--rb); color: var(--r); border: 1px solid rgba(244,63,94,.25); }
.pill-b { background: var(--bb); color: var(--b); border: 1px solid rgba(59,130,246,.25); }

.inval {
  background: rgba(244,63,94,.05);
  border: 1px solid rgba(244,63,94,.2);
  border-radius: 5px;
  padding: 0;
  margin-top: 8px;
}
.inval > summary {
  list-style: none; cursor: pointer;
  font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: .1em;
  color: var(--r); padding: 8px 12px;
}
.inval > summary::-webkit-details-marker { display: none; }
.inval > summary::before { content: "▸ "; }
.inval[open] > summary::before { content: "▾ "; }
.inval-list { padding: 0 12px 10px; }
.inval-list ul { margin: 0; padding-left: 14px; font-size: 11px; line-height: 1.9; }
.inval-list ul li { color: var(--muted); }
.inval-list ul li strong { color: var(--r); }

/* Evidence tags */
.tag { display: inline-block; font-size: 8px; font-weight: 700; padding: 1px 4px; border-radius: 2px; text-transform: uppercase; letter-spacing: .04em; vertical-align: middle; margin-right: 2px; }
.tag-f { background: var(--gb); color: var(--g); border: 1px solid rgba(0,200,150,.2); }
.tag-s { background: var(--bb); color: var(--b); border: 1px solid rgba(59,130,246,.2); }
.tag-e { background: var(--pb); color: var(--p); border: 1px solid rgba(168,85,247,.2); }
.tag-a { background: var(--ab); color: var(--a); border: 1px solid rgba(245,158,11,.2); }

/* S2 PULSE STRIP */
.pulse { display: grid; grid-template-columns: repeat(8, 1fr); gap: 8px; margin-bottom: 24px; }
@media (max-width: 900px) { .pulse { grid-template-columns: repeat(4, 1fr); } }
.kpi { background: var(--s1); border: 1px solid var(--border); border-radius: 6px; padding: 12px 14px; }
.kpi-label { font-size: 10px; color: var(--muted); font-weight: 600; letter-spacing: .06em; text-transform: uppercase; margin-bottom: 5px; }
.kpi-val { font-size: 18px; font-weight: 700; line-height: 1.1; }
.kpi-sub { font-size: 10px; margin-top: 3px; }
.kpi.ok   { border-top: 2px solid var(--g); }
.kpi.warn { border-top: 2px solid var(--a); }
.kpi.bad  { border-top: 2px solid var(--r); }
.up   { color: var(--g); }
.down { color: var(--r); }
.flat { color: var(--a); }
.dim  { color: var(--muted); }

/* S3 EVENTS */
.moves { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 24px; }
@media (max-width: 700px) { .moves { grid-template-columns: 1fr; } }
.move-card { background: var(--s1); border: 1px solid var(--border); border-radius: 6px; padding: 12px 14px; display: flex; align-items: flex-start; gap: 12px; }
.move-glyph { font-size: 18px; flex-shrink: 0; width: 28px; text-align: center; margin-top: 1px; }
.move-body { flex: 1; }
.move-who { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 2px; }
.move-what { font-size: 12px; color: var(--text); line-height: 1.4; }
.move-tag { font-size: 10px; color: var(--muted); margin-top: 3px; }
.date-warn { display: inline-block; margin-top: 3px; padding: 1px 6px; background: var(--ab); border: 1px solid rgba(245,158,11,.3); border-radius: 3px; font-size: 9px; color: var(--a); font-weight: 600; }

/* S3.5 RISK STRIP */
.risk-strip {
  background: var(--s1);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 18px;
  margin-bottom: 16px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
@media (max-width: 700px) { .risk-strip { grid-template-columns: 1fr; } }
.risk-col-title { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 8px; }
.risk-row { display: flex; align-items: flex-start; gap: 8px; padding: 5px 0; border-bottom: 1px solid rgba(37,42,69,.5); }
.risk-row:last-child { border-bottom: none; }
.risk-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; margin-top: 4px; }
.dot-r { background: var(--r); }
.dot-a { background: var(--a); }
.risk-body { flex: 1; }
.risk-title { font-size: 11px; font-weight: 600; }
.risk-sub   { font-size: 10px; color: var(--muted); margin-top: 1px; }

/* S4 POSITIONING BOARD */
.board { background: var(--s1); border: 1px solid var(--border); border-radius: 8px; overflow-x: auto; margin-bottom: 24px; }
.board table { width: 100%; min-width: 900px; border-collapse: collapse; }
.board th {
  background: var(--s2);
  color: var(--muted);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .08em;
  padding: 8px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.board td { padding: 8px 12px; border-bottom: 1px solid rgba(37,42,69,.6); vertical-align: top; font-size: 12px; }
.board tr:last-child td { border-bottom: none; }
.bucket-header td { font-size: 10px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; padding: 6px 12px; color: var(--muted); }
.bucket-core  .bucket-header td { background: rgba(0,200,150,.06); color: var(--g); }
.bucket-watch .bucket-header td { background: rgba(245,158,11,.06); color: var(--a); }
.bucket-cat   .bucket-header td { background: rgba(59,130,246,.06); color: var(--b); }
.bucket-avoid .bucket-header td { background: rgba(244,63,94,.06);  color: var(--r); }
.bucket-core  tr:not(.bucket-header) td:first-child { border-left: 3px solid var(--g); }
.bucket-watch tr:not(.bucket-header) td:first-child { border-left: 3px solid var(--a); }
.bucket-cat   tr:not(.bucket-header) td:first-child { border-left: 3px solid var(--b); }
.bucket-avoid tr:not(.bucket-header) td:first-child { border-left: 3px solid var(--r); }

.tk          { font-weight: 700; font-size: 13px; }
.thesis      { color: var(--muted); font-size: 11px; }
.price-col   { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.trigger-col { color: var(--muted); font-size: 11px; min-width: 160px; }
.inval-col   { color: var(--r);     font-size: 11px; min-width: 160px; }
.date-col    { color: var(--b);     font-size: 11px; min-width: 110px; font-weight: 600; white-space: nowrap; }
.flow-col    { text-align: center; font-size: 13px; white-space: nowrap; }
.prev        { font-size: 10px; color: var(--faint); margin-left: 3px; }

/* S5 FORWARD TRIGGERS */
.triggers { display: flex; flex-direction: column; }
.trigger-item { display: flex; align-items: center; gap: 16px; padding: 11px 0; border-bottom: 1px solid var(--border); }
.trigger-item:last-child { border-bottom: none; }
.trigger-date { width: 80px; flex-shrink: 0; font-size: 11px; font-weight: 700; color: var(--a); font-variant-numeric: tabular-nums; }
.trigger-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; background: var(--faint); }
.trigger-dot.hot { background: var(--a); box-shadow: 0 0 6px var(--a); }
.trigger-text { flex: 1; font-size: 12px; }
.trigger-text strong { color: var(--text); }
.trigger-text span { color: var(--muted); }

/* REGIME HERO (component 1 + 5) */
.regime-hero {
  background: var(--s1);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 18px 22px;
  margin-bottom: 14px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 20px;
  align-items: center;
}
.rc-block { text-align: center; min-width: 72px; }
.rc-num { font-size: 52px; font-weight: 700; line-height: 1; font-family: "IBM Plex Mono", monospace; font-variant-numeric: tabular-nums; }
.rc-label { font-size: 9px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); margin-top: 4px; }
.regime-hero-main { flex: 1; }
.regime-name { font-size: 20px; font-weight: 700; letter-spacing: .02em; margin-bottom: 3px; }
.regime-asof { font-size: 10px; color: var(--muted); }
.regime-dot-wrap { display: flex; align-items: center; gap: 6px; }
.regime-dot {
  width: 12px; height: 12px; border-radius: 50%;
  background: currentColor;
  animation: regime-pulse 2.4s ease-in-out infinite;
}
@keyframes regime-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: .2; }
}
.regime-hero.ok  .rc-num,
.regime-hero.ok  .regime-dot,
.regime-hero.ok  .regime-name  { color: var(--g); }
.regime-hero.warn .rc-num,
.regime-hero.warn .regime-dot,
.regime-hero.warn .regime-name { color: var(--a); }
.regime-hero.bad  .rc-num,
.regime-hero.bad  .regime-dot,
.regime-hero.bad  .regime-name { color: var(--r); }
.regime-hero.conflict .rc-num,
.regime-hero.conflict .regime-dot,
.regime-hero.conflict .regime-name { color: #ffa500; }

/* SPARKLINES (component 4 — renders when history[] present in KPI) */
.kpi-spark-wrap { margin-top: 6px; height: 30px; }
.kpi-spark { width: 100%; height: 30px; display: block; color: var(--muted); }
.kpi.ok   .kpi-spark { color: var(--g); opacity: .7; }
.kpi.warn .kpi-spark { color: var(--a); opacity: .7; }
.kpi.bad  .kpi-spark { color: var(--r); opacity: .7; }

/* FOOTER */
.footer { margin-top: 36px; padding-top: 14px; border-top: 1px solid var(--border); font-size: 10px; color: var(--muted); line-height: 1.7; }

/* MONETARY POLICY PANEL */
.mp-panel { background: var(--s1); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 24px; overflow: hidden; }
.mp-header { background: var(--s2); border-bottom: 1px solid var(--border); padding: 7px 18px; display: flex; justify-content: space-between; align-items: center; }
.mp-header-title { font-size: 10px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); }
.mp-header-asof { font-size: 10px; color: var(--faint); }
.mp-row { display: grid; grid-template-columns: 72px 1fr; border-bottom: 1px solid rgba(37,42,69,.7); }
.mp-row:last-child { border-bottom: none; }
.mp-bank { padding: 10px 12px; display: flex; align-items: center; border-right: 1px solid rgba(37,42,69,.7); background: rgba(255,255,255,.018); }
.mp-bank-label { font-size: 10px; font-weight: 700; letter-spacing: .09em; text-transform: uppercase; color: var(--muted); }
.mp-content { padding: 9px 16px 10px; }
.mp-stance-row { display: flex; align-items: center; gap: 10px; margin-bottom: 7px; }
.mp-inds { display: flex; flex-wrap: wrap; gap: 3px 18px; margin-bottom: 5px; }
.mp-ind { font-size: 11px; white-space: nowrap; }
.mp-ind-label { color: var(--muted); }
.mp-ind-val { font-weight: 600; }
.mp-note { font-size: 10px; color: var(--faint); margin-top: 3px; }
.mp-regime-row { padding: 7px 18px; font-size: 11px; font-weight: 600; color: var(--b); background: rgba(59,130,246,.05); border-top: 1px solid rgba(59,130,246,.15); }
""".strip() + "\n" + SUITE_NAV_CSS.strip() + """
.layout { display: flex; min-height: 100vh; }
.sidebar { width: 158px; position: sticky; top: 0; height: 100vh; overflow-y: auto; overscroll-behavior: contain; border-right: 1px solid var(--border); background: var(--panel, var(--s1)); padding: 12px 0; flex-shrink: 0; }
.sidebar-logo { padding: 8px 12px 10px; font-size: 9px; color: var(--muted); text-transform: uppercase; letter-spacing: .1em; border-bottom: 1px solid var(--border); margin-bottom: 8px; font-weight: 700; }
.sidebar h3 { margin: 10px 12px 3px; font-size: 8px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; }
.sidebar a { display: block; margin: 1px 6px; padding: 5px 8px; color: var(--dim, var(--muted)); text-decoration: none; font-size: 11px; border-radius: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sidebar a:hover, .sidebar a.active { background: #1e2330; color: var(--text); }
@media (max-width: 860px) { .sidebar { display: none; } }
"""


# ── HTML renderers ─────────────────────────────────────────────────────────────

def _render_pills(pills: list[dict]) -> str:
    parts = []
    for p in pills:
        c = p.get("color", "a")
        parts.append(f'<span class="pill pill-{c}">{escape(p["text"])}</span>')
    return "\n      ".join(parts)


def _render_invalidation(conditions: list[dict]) -> str:
    items = []
    for c in conditions:
        items.append(
            f'<li><strong>{escape(c["trigger"])}</strong> → {escape(c["consequence"])}</li>'
        )
    return "\n        ".join(items)


def _compute_regime_hero(path: Path) -> tuple[str, str, str, str, str]:
    """Return (days_str, regime_label, css_class, asof_str, conflict_note) from regime_state.json."""
    try:
        state = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        reg_raw = str(state.get("regime") or "UNKNOWN").upper()
        asof_str = str(state.get("asof_date") or "")
        days_str = "—"
        if asof_str:
            try:
                delta = (date.today() - date.fromisoformat(asof_str[:10])).days
                days_str = str(delta)
            except ValueError:
                pass
        # market_direction field drives the hero label (separate from liquidity quadrant code).
        # Liquidity quadrant codes A/B/C/D are NOT market-direction vocabulary — never show them as BULL/BEAR.
        mkt_dir = str(state.get("market_direction") or "").upper()
        _dir_map = {
            "BULL":    ("BULL",    "ok"),
            "NEUTRAL": ("NEUTRAL", "warn"),
            "DEFENSE": ("DEFENSE", "bad"),
            "BEAR":    ("BEAR",    "bad"),
        }
        # Fallback: if market_direction absent, use legacy regime code mapping (non-directional labels)
        _legacy_map = {
            "B":       ("LIQ-B",   "warn"),   # tight-global / easing-VN — NOT a direction word
            "N":       ("NEUTRAL", "warn"),
            "NEUTRAL": ("NEUTRAL", "warn"),
            "BEAR":    ("BEAR",    "bad"),
            "BULL":    ("BULL",    "ok"),      # only if explicitly stored as direction
        }
        if mkt_dir and mkt_dir in _dir_map:
            reg_label, css_class = _dir_map[mkt_dir]
        else:
            reg_label, css_class = _legacy_map.get(reg_raw, (reg_raw, "warn"))
        # Regime conflict: liquidity-direction vs breadth disagree
        conflict_note = ""
        if state.get("regime_conflict"):
            conflict_note = state.get("regime_conflict_note", "regime conflict — check breadth vs liquidity")
            # In conflict mode, show the market-direction label but flag it — keep CSS consistent
            if css_class == "ok":
                css_class = "conflict"
        return days_str, reg_label, css_class, asof_str or "UNKNOWN", conflict_note
    except Exception:
        return "—", "UNKNOWN", "warn", "UNKNOWN", ""


def _render_sparkline_svg(history: list[float]) -> str:
    """60×30 SVG sparkline. Zero-anchored normalization per Fable spec."""
    vals = [v for v in history if v is not None]
    if len(vals) < 2:
        return ""
    n = len(vals)
    lo = min(min(vals), 0.0)
    hi = max(max(vals), 0.0)
    span = hi - lo or 1.0
    W, H, pad = 60, 30, 3

    def _x(i: int) -> str:
        return f"{pad + (i / (n - 1)) * (W - 2 * pad):.1f}"

    def _y(v: float) -> str:
        return f"{H - pad - ((v - lo) / span) * (H - 2 * pad):.1f}"

    pts = " ".join(f"{_x(i)},{_y(v)}" for i, v in enumerate(vals))
    zero_y = _y(0.0)
    zero_line = (
        f'<line x1="{pad}" y1="{zero_y}" x2="{W - pad}" y2="{zero_y}"'
        f' stroke="rgba(255,255,255,.12)" stroke-width="1" stroke-dasharray="2 2"/>'
    )
    return (
        f'<svg class="kpi-spark" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        f'{zero_line}'
        f'<polyline points="{pts}" fill="none" stroke="currentColor"'
        f' stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>'
        f'</svg>'
    )


def _render_regime_hero(days_str: str, reg_label: str, css_class: str, asof_str: str, conflict_note: str = "") -> str:
    """Component 1+5: merged regime hero block with duration counter + animated pulse dot."""
    conflict_html = ""
    if conflict_note:
        conflict_html = (
            f'\n  <div style="margin-top:6px;font-size:10px;padding:4px 8px;'
            f'background:rgba(255,165,0,.12);border-left:3px solid #ffa500;border-radius:3px;'
            f'color:#ffa500;font-style:italic">⚠ REGIME CONFLICT: {escape(conflict_note)}</div>'
        )
    return (
        f'<div class="regime-hero {escape(css_class)}">\n'
        f'  <div class="rc-block">\n'
        f'    <div class="rc-num">{escape(days_str)}</div>\n'
        f'    <div class="rc-label">days</div>\n'
        f'  </div>\n'
        f'  <div class="regime-hero-main">\n'
        f'    <div class="regime-name">{escape(reg_label)}</div>\n'
        f'    <div class="regime-asof">state as-of {escape(asof_str)}</div>\n'
        f'  </div>\n'
        f'  <div class="regime-dot-wrap">\n'
        f'    <div class="regime-dot" aria-hidden="true"></div>\n'
        f'  </div>\n'
        f'{conflict_html}'
        f'</div>'
    )


def _render_kpi(k: dict) -> str:
    val_class = k.get("value_class", "")
    sub_class = k.get("sub_class", "dim")
    val_span = f'<span class="{val_class}">{escape(k["value"])}</span>' if val_class else escape(k["value"])
    spark_html = ""
    if k.get("history"):
        try:
            svg = _render_sparkline_svg([float(v) for v in k["history"]])
            if svg:
                spark_html = f'\n  <div class="kpi-spark-wrap">{svg}</div>'
        except (TypeError, ValueError):
            pass
    return (
        f'<div class="kpi {k["status"]}">\n'
        f'  <div class="kpi-label">{escape(k["label"])}</div>\n'
        f'  <div class="kpi-val">{val_span}</div>\n'
        f'  <div class="kpi-sub {sub_class}">{escape(k["sub"])}</div>'
        f'{spark_html}\n'
        f'</div>'
    )


def _render_event(ev: dict) -> str:
    glyph_color = ev.get("glyph_color", "a")
    who_tags_html = "".join(
        f'<span class="tag tag-{t["type"]}">{escape(t["text"])}</span>'
        for t in ev.get("who_tags", [])
    )
    date_warn_html = ""
    if ev.get("date_warn"):
        date_warn_html = f'\n        <div class="date-warn">{ev["date_warn"]}</div>'
    return (
        f'<div class="move-card">\n'
        f'  <div class="move-glyph" style="color:var(--{glyph_color})">{ev["glyph"]}</div>\n'
        f'  <div class="move-body">\n'
        f'    <div class="move-who">{escape(ev["who"])} {who_tags_html}</div>\n'
        f'    <div class="move-what">{ev["what"]}</div>\n'
        f'    <div class="move-tag">{escape(ev["note"])}</div>'
        f'{date_warn_html}\n'
        f'  </div>\n'
        f'</div>'
    )


def _render_risk_rows(risks: list[dict], dot_class: str) -> str:
    rows = []
    for r in risks:
        rows.append(
            f'<div class="risk-row">\n'
            f'  <div class="risk-dot {dot_class}"></div>\n'
            f'  <div class="risk-body">\n'
            f'    <div class="risk-title">{escape(r["title"])}</div>\n'
            f'    <div class="risk-sub">{r["sub"]}</div>\n'
            f'  </div>\n'
            f'</div>'
        )
    return "\n      ".join(rows)


def _render_ticker_row(t: dict, bucket_id: str) -> str:
    chg_class = t.get("chg_class", "")
    if chg_class == "prev":
        chg_html = f'<span class="prev">{escape(t["chg"])}</span>'
    elif chg_class:
        chg_html = f'<span class="{chg_class}">{escape(t["chg"])}</span>'
    else:
        chg_html = escape(t["chg"])

    flow_class = t.get("flow_class", "dim")
    return (
        f'<tr>\n'
        f'  <td><span class="tk">{escape(t["ticker"])}</span></td>\n'
        f'  <td><span class="thesis">{escape(t["thesis"])}</span></td>\n'
        f'  <td class="price-col">{escape(t["price"])} {chg_html}</td>\n'
        f'  <td class="flow-col {chg_class if chg_class != "prev" else "dim"}">{"▲" if chg_class == "up" else ("▼" if chg_class == "down" else "—")}</td>\n'
        f'  <td class="trigger-col">{escape(t["trigger"])}</td>\n'
        f'  <td class="inval-col">{escape(t["invalidation"])}</td>\n'
        f'  <td class="date-col">{escape(t["event_date"])}</td>\n'
        f'  <td class="flow-col {flow_class}">{escape(t["flow"])}</td>\n'
        f'</tr>'
    )


def _render_bucket(b: dict) -> str:
    bid = b["id"]
    header_row = f'<tr class="bucket-header"><td colspan="8">▸ {escape(b["label"])}</td></tr>'
    rows = "\n        ".join(_render_ticker_row(t, bid) for t in b["tickers"])
    return (
        f'<tbody class="bucket-{bid}">\n'
        f'  {header_row}\n'
        f'  {rows}\n'
        f'</tbody>'
    )


def _render_forward_trigger(tr_: dict) -> str:
    hot_class = " hot" if tr_.get("hot") else ""
    return (
        f'<div class="trigger-item">\n'
        f'  <div class="trigger-date">{escape(tr_["date"])}</div>\n'
        f'  <div class="trigger-dot{hot_class}"></div>\n'
        f'  <div class="trigger-text"><strong>{escape(tr_["title"])}</strong> <span>{tr_["body"]}</span></div>\n'
        f'</div>'
    )


# ── Monetary policy panel ─────────────────────────────────────────────────────

def _render_monetary_policy(mp: dict) -> str:
    def _inds_html(inds: list) -> str:
        parts = []
        for ind in inds:
            delta_html = ""
            if ind.get("delta"):
                dc = ind.get("delta_class", "dim")
                delta_html = f' <span class="{dc}">{escape(ind["delta"])}</span>'
            parts.append(
                f'<span class="mp-ind">'
                f'<span class="mp-ind-label">{escape(ind["label"])}:</span> '
                f'<span class="mp-ind-val">{escape(ind["value"])}</span>'
                f'{delta_html}'
                f'</span>'
            )
        return "\n          ".join(parts)

    fed = mp["fed"]
    sbv = mp["sbv"]
    fed_note = f'<div class="mp-note">{escape(fed["note"])}</div>' if fed.get("note") else ""
    sbv_note = f'<div class="mp-note">{escape(sbv["note"])}</div>' if sbv.get("note") else ""

    return (
        f'<div class="mp-panel">\n'
        f'  <div class="mp-header">\n'
        f'    <div class="mp-header-title">Monetary Policy Stance</div>\n'
        f'    <div class="mp-header-asof">as-of: {escape(mp["asof"])}</div>\n'
        f'  </div>\n'
        f'  <div class="mp-row">\n'
        f'    <div class="mp-bank"><div class="mp-bank-label">FED</div></div>\n'
        f'    <div class="mp-content">\n'
        f'      <div class="mp-stance-row"><span class="pill pill-{escape(fed["stance_color"])}">{escape(fed["stance"])}</span></div>\n'
        f'      <div class="mp-inds">{_inds_html(fed["indicators"])}</div>\n'
        f'      {fed_note}\n'
        f'    </div>\n'
        f'  </div>\n'
        f'  <div class="mp-row">\n'
        f'    <div class="mp-bank"><div class="mp-bank-label">SBV</div></div>\n'
        f'    <div class="mp-content">\n'
        f'      <div class="mp-stance-row"><span class="pill pill-{escape(sbv["stance_color"])}">{escape(sbv["stance"])}</span></div>\n'
        f'      <div class="mp-inds">{_inds_html(sbv["indicators"])}</div>\n'
        f'      {sbv_note}\n'
        f'    </div>\n'
        f'  </div>\n'
        f'  <div class="mp-regime-row">&#8635; {escape(mp["regime_summary"])}</div>\n'
        f'</div>'
    )


# ── Rate Pivot Monitor ────────────────────────────────────────────────────────

RATE_PIVOT_MONITOR_PATH = ROOT / "data" / "research" / "rate_pivot_monitor.json"

def _load_rate_pivot_monitor() -> dict:
    if not RATE_PIVOT_MONITOR_PATH.exists():
        return {}
    try:
        return json.loads(RATE_PIVOT_MONITOR_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _render_fx_transmission(contract: dict) -> str:
    """Full primary FX→reserve→deposit transmission panel (advisory / non-scoring)."""
    state = contract.get("current_state") or {}
    state_id = state.get("id")
    state_label = str(state.get("label") or "UNKNOWN")
    status = str(state.get("status") or "UNKNOWN / STALE")
    conf = str(state.get("confirmation_status") or "NOT_CONFIRMED").replace("_", " ")
    headline = str(contract.get("headline") or "FX–LIQUIDITY TRANSMISSION")
    as_of = str(contract.get("as_of") or "Unknown")
    ehash = str(contract.get("evidence_hash") or "")
    integrity = str(contract.get("integrity_status") or "UNKNOWN")

    ladder_labels = {
        0: "FX PRESSURE",
        1: "FX PRESSURE EASING",
        2: "RESERVE-REBUILD SETUP",
        3: "RESERVE REBUILD / LIQUIDITY TRANSMISSION CONFIRMED",
        4: "DEPOSIT-RATE PIVOT CONFIRMED",
    }
    ladder_html = ""
    for sid, lab in ladder_labels.items():
        active = state_id == sid
        bg = "rgba(59,130,246,.12)" if active else "rgba(255,255,255,.02)"
        border = "1px solid var(--b)" if active else "1px solid var(--border)"
        weight = "800" if active else "500"
        mark = f"STATE {sid}" if active else str(sid)
        ladder_html += (
            f'<div style="flex:1;min-width:110px;padding:6px 8px;background:{bg};'
            f'border:{border};border-radius:4px;font-size:9px;">'
            f'<div style="font-weight:{weight};color:{"var(--b)" if active else "var(--muted)"}">'
            f'{escape(mark)}</div>'
            f'<div style="color:var(--muted);margin-top:2px;line-height:1.35">{escape(lab)}</div>'
            f'</div>'
        )

    def _ev_group(title: str, rows: list) -> str:
        if not rows:
            return (
                f'<div style="font-size:10px;margin-bottom:6px"><strong>{escape(title)}</strong>'
                f'<div style="color:var(--muted);font-size:9px">—</div></div>'
            )
        items = ""
        for row in rows:
            items += (
                f'<div style="padding:4px 0;border-bottom:1px solid var(--border);font-size:9px;line-height:1.4">'
                f'<span style="font-weight:700;color:var(--muted)">{escape(str(row.get("status") or ""))}</span>'
                f' · {escape(str(row.get("label") or row.get("variable_id") or ""))}'
                f' · <span style="color:var(--faint)">{escape(str(row.get("claim_class") or ""))}'
                f'/{escape(str(row.get("source_quality") or ""))}'
                f'/{escape(str(row.get("freshness") or ""))}</span>'
                f'<div style="color:var(--muted)">{escape(str(row.get("notes") or "")[:160])}</div>'
                f'</div>'
            )
        return (
            f'<div style="margin-bottom:8px"><div style="font-size:10px;font-weight:700;'
            f'text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:4px">'
            f'{escape(title)}</div>{items}</div>'
        )

    el = contract.get("evidence_ladder") or {}
    channels = contract.get("channels") or {}
    checklist = contract.get("confirmation_checklist") or []
    falsifiers = contract.get("falsifiers") or []
    hist = contract.get("historical_context") or {}
    impl = contract.get("implications") or {}
    reg = contract.get("regulatory_funding_relief") or {}
    deposit = contract.get("deposit_thesis") or {}

    checklist_html = "".join(
        f'<div style="font-size:9px;padding:2px 0">'
        f'<strong style="color:var(--muted)">{escape(str(r.get("status") or ""))}</strong>'
        f' · {escape(str(r.get("label") or ""))}</div>'
        for r in checklist
    )
    if not checklist_html:
        checklist_html = '<div style="font-size:9px;color:var(--muted)">—</div>'
    falsifier_html = "".join(
        f'<li style="margin:2px 0">{escape(str(f))}</li>' for f in falsifiers
    )

    def _bullets(items: list) -> str:
        return "".join(f'<li>{escape(str(x))}</li>' for x in (items or []))

    hist_notes = hist.get("notes") or []
    if isinstance(hist_notes, str):
        hist_notes = [hist_notes]
    hist_html = "".join(f'<li>{escape(str(n))}</li>' for n in hist_notes)

    state_disp = f"STATE {state_id}" if isinstance(state_id, int) else "UNKNOWN"
    return (
        f'<div style="background:rgba(59,130,246,.05);border:1px solid rgba(59,130,246,.28);'
        f'border-radius:6px;padding:12px 14px;margin-bottom:10px;">'
        f'<div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;'
        f'align-items:flex-start;margin-bottom:8px">'
        f'<div>'
        f'<div style="font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;'
        f'letter-spacing:.08em">FX → Reserve → Deposit Transmission</div>'
        f'<div style="font-size:13px;font-weight:800;color:var(--b);margin-top:3px">'
        f'{escape(headline)}</div>'
        f'<div style="font-size:10px;color:var(--muted);margin-top:3px">'
        f'{escape(state_disp)} · {escape(state_label)} · {escape(status)} · '
        f'<strong>NOT CONFIRMED</strong> ({escape(conf)})</div>'
        f'</div>'
        f'<div style="font-size:9px;color:var(--muted);text-align:right">'
        f'as-of {escape(as_of)}<br>integrity {escape(integrity)}'
        f'<br><span style="color:var(--faint)">scoring: NONE</span></div>'
        f'</div>'
        f'<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px">{ladder_html}</div>'
        f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));'
        f'gap:8px;margin-bottom:10px">'
        f'{_ev_group("OBSERVATION", el.get("observation") or [])}'
        f'{_ev_group("INFERENCE", el.get("inference") or [])}'
        f'{_ev_group("CONFIRMATION", el.get("confirmation") or [])}'
        f'</div>'
        f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px">'
        f'{_ev_group("FX", channels.get("fx") or [])}'
        f'{_ev_group("External flows", channels.get("external_flows") or [])}'
        f'{_ev_group("Reserve / VND liquidity", channels.get("reserve_liquidity") or [])}'
        f'{_ev_group("Bank funding", channels.get("bank_funding") or [])}'
        f'</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:10px 0">'
        f'<div style="padding:8px;border:1px solid var(--border);border-radius:4px;background:rgba(255,255,255,.02)">'
        f'<div style="font-size:10px;font-weight:700;color:var(--a)">Regulatory funding relief</div>'
        f'<div style="font-size:9px;color:var(--muted);margin-top:4px;line-height:1.45">'
        f'{escape(str(reg.get("status") or "UNKNOWN"))} · '
        f'{escape(str(reg.get("source_quality") or ""))} · '
        f'{escape(str(reg.get("confirmation_status") or ""))}<br>'
        f'{escape(str(reg.get("notes") or "")[:280])}</div></div>'
        f'<div style="padding:8px;border:1px solid var(--border);border-radius:4px;background:rgba(255,255,255,.02)">'
        f'<div style="font-size:10px;font-weight:700;color:var(--b)">Actual monetary liquidity creation</div>'
        f'<div style="font-size:9px;color:var(--muted);margin-top:4px;line-height:1.45">'
        f'SBV buys FX → pays VND → interbank liquidity improves. '
        f'Regulatory LDR relief is not a substitute for this channel. '
        f'Current confirmation: UNKNOWN / NOT CONFIRMED.</div></div>'
        f'</div>'
        f'<div style="font-size:10px;font-weight:700;color:var(--muted);margin-bottom:4px">'
        f'Deposit thesis</div>'
        f'<div style="font-size:9px;color:var(--muted);margin-bottom:8px">'
        f'{escape(str(deposit.get("headline") or ""))} · '
        f'{escape(str(deposit.get("claim_class") or ""))} · '
        f'{escape(str(deposit.get("evidence_state") or ""))} · upgrade '
        f'{escape(str(deposit.get("upgrade") or "NONE"))}</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">'
        f'<div><div style="font-size:10px;font-weight:700;letter-spacing:.06em;color:var(--muted)">'
        f'CHECKLIST</div>{checklist_html}</div>'
        f'<div><div style="font-size:10px;font-weight:700;letter-spacing:.06em;color:var(--r)">'
        f'FALSIFIERS</div><ul style="font-size:9px;color:var(--muted);margin:4px 0 0 14px;'
        f'padding:0">{falsifier_html}</ul></div>'
        f'</div>'
        f'<div style="margin-top:10px;font-size:10px;font-weight:700;color:var(--muted)">Implications</div>'
        f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:6px;'
        f'font-size:9px;color:var(--muted)">'
        f'<div><strong>1st</strong><ul style="margin:2px 0 0 14px">{_bullets(impl.get("first_order"))}</ul></div>'
        f'<div><strong>2nd</strong><ul style="margin:2px 0 0 14px">{_bullets(impl.get("second_order"))}</ul></div>'
        f'<div><strong>3rd</strong><ul style="margin:2px 0 0 14px">{_bullets(impl.get("third_order"))}</ul></div>'
        f'<div><strong>4th / residual</strong><ul style="margin:2px 0 0 14px">'
        f'{_bullets(impl.get("fourth_order_residual_risk"))}</ul></div>'
        f'</div>'
        f'<div style="font-size:9px;color:var(--muted);margin-top:6px">'
        f'{escape(str(impl.get("equity_display") or ""))}</div>'
        f'<details style="margin-top:8px"><summary style="font-size:9px;color:var(--muted);'
        f'cursor:pointer;font-weight:700">Historical context (commentary only)</summary>'
        f'<ul style="font-size:9px;color:var(--muted);margin:6px 0 0 14px">{hist_html}</ul>'
        f'<div style="font-size:9px;color:var(--faint);margin-top:4px">'
        f'use: {escape(str(hist.get("use") or "supporting commentary only"))}</div></details>'
        f'<details style="margin-top:6px"><summary style="font-size:9px;color:var(--faint);'
        f'cursor:pointer">Audit · evidence_hash</summary>'
        f'<code style="font-size:9px;word-break:break-all">{escape(ehash)}</code></details>'
        f'</div>'
    )


def _render_rate_pivot_monitor(data: dict) -> str:
    if not data:
        return ""
    from html import escape
    meta = data.get("_meta", {})
    criteria = data.get("criteria", [])
    scenarios = data.get("scenario_matrix", {})
    beneficiaries = data.get("beneficiary_sectors_on_confirmed_pivot", [])
    as_of = meta.get("as_of", "")
    overall = meta.get("overall_status", "")
    overall_note = meta.get("overall_status_note", "")

    sc = {"CONFIRMED": "var(--g)", "APPROACHING": "var(--b)", "WATCH": "var(--a)", "BLOCKING": "var(--r)", "FAIL": "var(--r)", "PASS": "var(--g)", "EARLY": "var(--a)", "MIXED": "var(--a)", "IMPROVING": "var(--g)", "GATED": "var(--r)"}
    si = {"CONFIRMED": "✓", "APPROACHING": "→", "WATCH": "◎", "BLOCKING": "✕", "FAIL": "✕", "PASS": "✓"}

    # ── V2 primary view ──────────────────────────────────────────────────────
    v2 = data.get("council_v2_framework", {})
    v2_html = ""
    if v2:
        v2_cur = v2.get("current_v2_assessment", {})
        v2_status = v2_cur.get("v2_status", "")
        g1_raw = v2_cur.get("G1_fx", "")
        g2_raw = v2_cur.get("G2_inflation", "")
        p1_raw = v2_cur.get("P1_omo", "")
        p2_raw = v2_cur.get("P2_deposit", "")
        p3_raw = v2_cur.get("P3_disinflation", "")
        watches = v2_cur.get("watch_triggers", [])

        def _row(label, val, tier):
            key = val.split()[0] if val else ""
            col = sc.get(key, "var(--muted)")
            icon = si.get(key, "◎")
            tier_col = "rgba(59,130,246,.15)" if tier == "gate" else "rgba(168,85,247,.10)"
            tier_label = "GATE" if tier == "gate" else "SIGNAL"
            tier_text_col = "#60a5fa" if tier == "gate" else "#a78bfa"
            return (
                f'<div style="display:flex;gap:8px;align-items:flex-start;padding:6px 8px;'
                f'background:{tier_col};border-radius:4px;margin-bottom:4px;">'
                f'<span style="color:{col};font-weight:800;font-size:13px;min-width:16px">{icon}</span>'
                f'<div style="flex:1;min-width:0">'
                f'<div style="font-size:10px;font-weight:700;color:{col}">{escape(label)}</div>'
                f'<div style="font-size:9px;color:var(--muted);margin-top:1px">{escape(val)}</div>'
                f'</div>'
                f'<span style="font-size:8px;font-weight:700;color:{tier_text_col};'
                f'background:{tier_col};padding:1px 4px;border-radius:2px;white-space:nowrap">{tier_label}</span>'
                f'</div>'
            )

        gates_html = (
            _row("G1 · FX Veto  (USD/VND + foreign flow + trade)", g1_raw, "gate") +
            _row("G2 · Inflation Permission  (core CPI 3m momentum)", g2_raw, "gate")
        )
        signals_html = (
            f'<div style="font-size:9px;color:var(--muted);padding:4px 0 4px 4px;font-style:italic">'
            f'Signals scored only when BOTH gates pass</div>' +
            _row("P1 · OMO / Interbank Momentum  (45%)", p1_raw, "signal") +
            _row("P2 · Deposit Rate Diffusion  (35%)", p2_raw, "signal") +
            _row("P3 · Disinflation Momentum  (20%)", p3_raw, "signal")
        )

        binding = ""
        g1_fails = "FAIL" in g1_raw.upper()
        g2_fails = "FAIL" in g2_raw.upper()
        if g1_fails:
            binding = "G1 FX permission is binding — V2 score remains gated."
        elif g2_fails:
            binding = "G2 inflation permission is binding — V2 score remains gated despite G1 FX passing."
        status_col = sc.get(v2_status.split()[0] if v2_status else "", "var(--muted)")
        watch_items = "".join(
            f'<div style="font-size:9px;color:var(--muted);padding:1px 0">→ {escape(w)}</div>'
            for w in watches[:4]
        )

        v2_html = (
            f'<div style="background:rgba(255,255,255,.02);border:1px solid var(--border);'
            f'border-radius:6px;padding:10px 12px;margin-bottom:8px;">'
            # header
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
            f'<div style="font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.08em">'
            f'Rate Pivot · V2 Framework</div>'
            f'<div style="font-size:9px;color:{status_col};font-weight:700">{escape(v2_status[:40] if v2_status else "")}</div>'
            f'</div>'
            # gates + signals
            f'{gates_html}'
            f'{signals_html}'
            # binding constraint callout
            + (f'<div style="margin-top:6px;padding:4px 8px;background:rgba(244,63,94,.08);'
               f'border-left:3px solid var(--r);border-radius:2px;font-size:10px;color:var(--r)">'
               f'{escape(binding)}</div>' if binding else "")
            # watch triggers
            + (f'<div style="margin-top:8px;padding:6px 8px;background:rgba(245,158,11,.06);'
               f'border-radius:4px;"><div style="font-size:9px;font-weight:700;color:#f59e0b;'
               f'margin-bottom:3px">WATCH FOR</div>{watch_items}</div>' if watches else "")
            # stats note
            + f'<div style="margin-top:6px;font-size:9px;color:var(--muted);font-style:italic">'
            + f'⚠ V1 C1-C8 was concurrent classifier (r=0.563), not predictor. V2 uses leading derivatives only.</div>'
            + f'</div>'
        )

    # ── Beneficiary sectors (on confirmed pivot) ─────────────────────────────
    bene_html = " &nbsp;·&nbsp; ".join(
        f'<span style="color:var(--g)">#{b["rank"]}</span> {escape(b["sector"])} '
        f'<span style="color:var(--muted)">({escape(b["examples"])})</span>'
        for b in beneficiaries[:4]
    )
    bene_section = (
        f'<div style="font-size:10px;color:var(--muted);margin-bottom:8px">'
        f'<strong>Sectors on confirmed pivot:</strong> {bene_html}</div>'
    ) if bene_html else ""

    # ── Scenario matrix ───────────────────────────────────────────────────────
    scen_html = ""
    for key, label, col in [("bull_case", "Bull", "var(--g)"), ("base_case", "Base", "var(--a)"), ("bear_case", "Bear", "var(--r)")]:
        s = scenarios.get(key, {})
        if s:
            scen_html += (
                f'<div style="flex:1;min-width:130px;padding:5px 7px;background:rgba(255,255,255,.03);'
                f'border-left:3px solid {col};border-radius:3px;font-size:10px;">'
                f'<div style="font-weight:700;color:{col}">{label} · {escape(s.get("label",""))}</div>'
                f'<div style="color:var(--muted);margin-top:1px">{escape(s.get("probability",""))} · {escape(s.get("expected_move",""))}</div>'
                f'</div>'
            )
    scen_section = (
        f'<div style="font-size:10px;font-weight:600;color:var(--muted);text-transform:uppercase;'
        f'letter-spacing:.05em;margin-bottom:5px">Scenario Matrix</div>'
        f'<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px">{scen_html}</div>'
    ) if scen_html else ""

    # ── Old C1-C8 detail (collapsible) ────────────────────────────────────────
    rows_html = ""
    for c in criteria:
        st = c.get("status", "WATCH")
        col = sc.get(st, "var(--muted)")
        icon = si.get(st, "?")
        pruned = c.get("id", "") in ("C1", "C4", "C7", "C8")
        opacity = "opacity:0.45;" if pruned else ""
        rows_html += (
            f'<div style="display:flex;gap:6px;align-items:flex-start;padding:4px 0;'
            f'border-bottom:1px solid var(--border);{opacity}">'
            f'<span style="color:{col};font-weight:700;min-width:14px;font-size:12px">{icon}</span>'
            f'<div style="flex:1;min-width:0">'
            f'<div style="font-size:10px;font-weight:600">'
            f'<span style="color:{col}">[{st}]</span> {escape(c.get("id",""))} · {escape(c.get("name",""))}'
            + (f' <span style="font-size:8px;color:var(--muted)">[V2: pruned]</span>' if pruned else "")
            + f'</div>'
            f'<div style="font-size:9px;color:var(--muted);margin-top:1px">'
            f'<strong>Now:</strong> {escape(str(c.get("current_value",""))[:80])}'
            f'</div>'
            f'</div>'
            f'</div>\n'
        )
    detail_section = (
        f'<details style="margin-top:8px;">'
        f'<summary style="font-size:9px;color:var(--muted);cursor:pointer;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:.06em;padding:4px 0">'
        f'▸ V1 C1–C8 detail (4 pruned, kept for reference)</summary>'
        f'<div style="margin-top:6px">{rows_html}</div>'
        f'</details>'
    )

    # ── Crash EWS block ──────────────────────────────────────────────────────
    crash_ews = data.get("crash_ews", {})
    ews_html = ""
    if crash_ews:
        cur = crash_ews.get("current_2026_q2", {})
        ews_score = cur.get("score", "?")
        ews_status = cur.get("status", "")
        ews_char = cur.get("character", "")
        ews_trigger = cur.get("trigger_for_red", "")
        ews_reentry = cur.get("re_entry_signal", "")
        ews_note = cur.get("vs_2022", "")
        ews_col_map = {"GREEN": "var(--g)", "WATCH": "var(--a)", "AMBER": "#f97316", "RED": "var(--r)"}
        ews_col = ews_col_map.get(ews_status, "var(--muted)")
        design_rule = crash_ews.get("_meta", {}).get("design_rule", "")
        ews_html = (
            f'<div style="margin-top:8px;padding:8px 10px;background:rgba(239,68,68,.06);'
            f'border:1px solid rgba(239,68,68,.25);border-radius:5px;">'
            f'<div style="font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;'
            f'letter-spacing:.05em;margin-bottom:5px">Crash EWS · 3-Layer Vulnerability</div>'
            f'<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:5px">'
            f'<span style="font-size:18px;font-weight:800;color:{ews_col}">{ews_score}/4</span>'
            f'<span style="font-size:12px;font-weight:700;color:{ews_col}">{escape(ews_status)}</span>'
            f'<span style="font-size:10px;color:var(--muted)">{escape(ews_char)}</span>'
            f'</div>'
            f'<div style="font-size:10px;color:var(--muted);line-height:1.5;margin-bottom:3px">'
            f'<strong style="color:var(--r)">→ RED trigger:</strong> {escape(ews_trigger)}</div>'
            f'<div style="font-size:10px;color:var(--muted);line-height:1.5;margin-bottom:3px">'
            f'<strong style="color:var(--g)">Re-entry:</strong> {escape(ews_reentry)}</div>'
            f'<div style="font-size:9px;color:var(--muted);font-style:italic">{escape(ews_note)}</div>'
            f'</div>'
        )
        if design_rule:
            ews_html += (
                f'<div style="margin-top:3px;font-size:9px;color:var(--muted);padding:3px 8px;'
                f'border-left:2px solid var(--muted);font-style:italic">'
                f'⚠ {escape(design_rule)}</div>'
            )

    # ── Layer 2 CBFS + Margin block ──────────────────────────────────────────
    l2 = data.get("layer2_vulnerability", {})
    l2_html = ""
    if l2:
        cbfs = l2.get("cbfs", {})
        margin = l2.get("margin_debt", {})
        combined = l2.get("combined_l2_verdict", {})
        cbfs_status = cbfs.get("current_status", "")
        margin_status = margin.get("current_status", "")
        margin_val = margin.get("current_value_t", "?")
        margin_note = margin.get("current_note", "")
        cbfs_note = cbfs.get("current_notes", "")
        combined_level = combined.get("combined_level", "")
        combined_2026 = combined.get("current_2026", "")
        col_map = {"GREEN": "var(--g)", "WATCH": "var(--a)", "AMBER": "#f97316", "RED": "var(--r)"}
        cbfs_col = col_map.get(cbfs_status, "var(--muted)")
        margin_col = col_map.get(margin_status, "var(--muted)")
        combined_col = col_map.get(combined_level, "var(--muted)")
        l2_html = (
            f'<div style="margin-top:8px;padding:8px 10px;background:rgba(255,255,255,.02);'
            f'border:1px solid var(--border);border-radius:5px;">'
            f'<div style="font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;'
            f'letter-spacing:.05em;margin-bottom:5px">Layer 2 · Financial-System Vulnerability</div>'
            f'<div style="display:flex;gap:12px;flex-wrap:wrap;font-size:10px;">'
            f'<div><span style="color:var(--muted)">CBFS bonds: </span>'
            f'<span style="font-weight:700;color:{cbfs_col}">{escape(cbfs_status)}</span>'
            f'<div style="font-size:9px;color:var(--muted);max-width:200px">{escape(cbfs_note[:100])}…</div></div>'
            f'<div><span style="color:var(--muted)">Margin debt: </span>'
            f'<span style="font-weight:700;color:{margin_col}">{escape(margin_status)}</span>'
            f' <span style="color:var(--muted)">~{escape(str(margin_val))}T</span>'
            f'<div style="font-size:9px;color:var(--muted);max-width:220px">{escape(margin_note[:120])}…</div></div>'
            f'<div><span style="color:var(--muted)">Combined: </span>'
            f'<span style="font-weight:700;color:{combined_col}">{escape(combined_level)}</span>'
            f'<div style="font-size:9px;color:var(--muted);max-width:200px">{escape(combined_2026[:100])}…</div></div>'
            f'</div>'
            f'</div>'
        )

    # ── Assemble ─────────────────────────────────────────────────────────────
    from scripts.reporting.rate_pivot_transmission import normalize_transmission_contract

    tx_contract = normalize_transmission_contract(data)
    tx_html = _render_fx_transmission(tx_contract)

    return (
        f'<div style="background:rgba(255,255,255,.01);border:1px solid var(--border);'
        f'border-radius:6px;padding:12px 14px;">'
        f'{tx_html}'
        f'<div style="font-size:11px;color:var(--muted);margin-bottom:8px;line-height:1.5">'
        f'<strong style="color:var(--a)">{escape(overall)}</strong>'
        + (f' · <span style="font-size:10px">{escape(overall_note[:120])}</span>' if overall_note else "")
        + f'</div>'
        f'{v2_html}'
        f'{scen_section}'
        f'{bene_section}'
        f'{detail_section}'
        f'{l2_html}'
        f'{ews_html}'
        f'<div style="font-size:9px;color:var(--muted);margin-top:6px;font-style:italic">'
        f'as-of {escape(as_of)}</div>'
        f'</div>'
    )


def _render_dxy_cycle_panel() -> str:
    """DXY 20-year annual cycle panel — compact, Chart.js bar charts.
    Opus council review 2026-07-12: data quality PASS, cycle phases validated.
    2005-2014 returns derived from year-end closing prices (training knowledge);
    2015-2025 cross-verified 3 independent sources ±0.1pp.
    """
    return '''<div class="card" style="margin-bottom:12px">
<div style="font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:8px">
  DXY Annual Cycle (2005–2025)
  <span style="font-size:9px;font-weight:400;text-transform:none;letter-spacing:0;margin-left:8px;color:var(--a)">
    Late-stage topping structure — G1 FX veto ~5.5pts from open (&lt;95.5 monthly close)
  </span>
</div>

<div style="font-size:9px;color:var(--muted);margin-bottom:6px;display:flex;flex-wrap:wrap;gap:8px;align-items:center">
  <span><span style="display:inline-block;width:8px;height:8px;border-radius:1px;background:#8b8a84;margin-right:3px"></span>Secular bear 2005–07</span>
  <span><span style="display:inline-block;width:8px;height:8px;border-radius:1px;background:#c98500;margin-right:3px"></span>GFC rebound 2008</span>
  <span><span style="display:inline-block;width:8px;height:8px;border-radius:1px;background:#4a3aa7;margin-right:3px"></span>QE range 2009–13</span>
  <span><span style="display:inline-block;width:8px;height:8px;border-radius:1px;background:#185fa5;margin-right:3px"></span>Secular bull 2014–22</span>
  <span><span style="display:inline-block;width:8px;height:8px;border-radius:1px;background:#d03b3b;margin-right:3px"></span>Post-peak topping 2023–25</span>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:8px">
  <div>
    <div style="font-size:9px;color:var(--muted);margin-bottom:4px">Annual returns by phase</div>
    <div style="position:relative;height:160px"><canvas id="dxy-annual-chart"></canvas></div>
    <div style="font-size:8px;color:var(--muted);margin-top:3px;font-style:italic">2005–14: derived from year-end closes (training knowledge). 2015–25: 3-source verified.</div>
  </div>
  <div>
    <div style="font-size:9px;color:var(--muted);margin-bottom:4px">Monthly seasonality avg 2005–2024</div>
    <div style="position:relative;height:160px"><canvas id="dxy-season-chart"></canvas></div>
    <div style="font-size:8px;color:var(--muted);margin-top:3px">■ 20yr: <span style="color:#c98500">May +0.72%</span> (12/20), <span style="color:#c98500">Sep +0.67%</span> (12/20) strongest. <span style="color:#c98500">Nov +0.45%</span> (13/20) hi win-rate. Current: Jul −0.54% (9/20 — seasonal headwind).</div>
  </div>
</div>

<div style="display:flex;flex-wrap:wrap;gap:6px;font-size:9px;border-top:1px solid var(--border,#e0e0e0);padding-top:6px">
  <span style="padding:2px 7px;border-radius:3px;background:#fce4e4;color:#a32d2d;font-weight:600">&gt;110 HARD BLOCK</span>
  <span style="padding:2px 7px;border-radius:3px;background:#fff3e0;color:#854f0b;font-weight:600">105–110 BLOCK</span>
  <span style="padding:2px 7px;border-radius:3px;background:#e3f0fc;color:#185fa5;font-weight:700;outline:1px solid #185fa5">~101 WATCH ← now</span>
  <span style="padding:2px 7px;border-radius:3px;background:#e6f5ee;color:#0f6e56;font-weight:600">96–98 PARTIAL OPEN</span>
  <span style="padding:2px 7px;border-radius:3px;background:#d6f0e2;color:#0a5c3a;font-weight:700">&lt;95.5 G1 OPENS</span>
  <span style="padding:2px 7px;border-radius:3px;background:#c9ecd9;color:#084d2e;font-weight:600">90–92 STRONG OPEN</span>
</div>

<script>
(function() {
  var phases = {
    "2005":"#8b8a84","2006":"#8b8a84","2007":"#8b8a84",
    "2008":"#c98500",
    "2009":"#4a3aa7","2010":"#4a3aa7","2011":"#4a3aa7","2012":"#4a3aa7","2013":"#4a3aa7",
    "2014":"#185fa5","2015":"#185fa5","2016":"#185fa5","2017":"#185fa5","2018":"#185fa5",
    "2019":"#185fa5","2020":"#185fa5","2021":"#185fa5","2022":"#185fa5",
    "2023":"#d03b3b","2024":"#d03b3b","2025":"#d03b3b"
  };
  var annual = [
    ["2005",11.9],["2006",-8.1],["2007",-8.0],["2008",5.5],
    ["2009",-3.7],["2010",1.4],["2011",1.5],["2012",-0.5],["2013",0.3],
    ["2014",12.8],["2015",9.3],["2016",3.7],["2017",-9.9],["2018",4.4],
    ["2019",0.5],["2020",-6.7],["2021",6.4],["2022",8.2],
    ["2023",-2.1],["2024",7.0],["2025",-9.4]
  ];
  var isDark = document.body.classList.contains("dark") ||
    window.matchMedia("(prefers-color-scheme:dark)").matches;
  var gridC = isDark ? "#2c2c2a" : "#e8e7e0";
  var tickC = isDark ? "#898781" : "#6b6a65";

  if (window.Chart) {
    new Chart(document.getElementById("dxy-annual-chart"), {
      type:"bar",
      data:{
        labels:annual.map(d=>d[0]),
        datasets:[{
          data:annual.map(d=>d[1]),
          backgroundColor:annual.map(d=>phases[d[0]]),
          borderRadius:{topLeft:2,topRight:2,bottomLeft:2,bottomRight:2},
          borderSkipped:false,
          barThickness:10
        }]
      },
      options:{
        responsive:true,maintainAspectRatio:false,
        plugins:{legend:{display:false},tooltip:{callbacks:{label:function(c){return (c.parsed.y>0?"+":"")+c.parsed.y.toFixed(1)+"%";}}}},
        scales:{
          x:{grid:{display:false},ticks:{color:tickC,font:{size:7},maxRotation:45,autoSkip:false}},
          y:{grid:{color:gridC},border:{display:false},ticks:{color:tickC,font:{size:8},callback:function(v){return (v>0?"+":"")+v+"%";}}}
        }
      }
    });

    var seas = [["Jan",0.58],["Feb",0.24],["Mar",-0.16],["Apr",-0.40],["May",0.72],
                ["Jun",0.01],["Jul",-0.54],["Aug",0.18],["Sep",0.67],["Oct",0.51],["Nov",0.45],["Dec",-0.51]];
    new Chart(document.getElementById("dxy-season-chart"), {
      type:"bar",
      data:{
        labels:seas.map(d=>d[0]),
        datasets:[{
          data:seas.map(d=>d[1]),
          backgroundColor:seas.map(function(d,i){
            if(i===8||i===9) return "#c98500";
            if(i===6) return "rgba(24,95,165,0.4)";
            return d[1]>=0?"#185fa5":"#d03b3b";
          }),
          borderRadius:{topLeft:2,topRight:2,bottomLeft:2,bottomRight:2},
          borderSkipped:false,
          barThickness:16
        }]
      },
      options:{
        responsive:true,maintainAspectRatio:false,
        plugins:{legend:{display:false},tooltip:{callbacks:{label:function(c){return (c.parsed.y>0?"+":"")+c.parsed.y.toFixed(2)+"%";}}}},
        scales:{
          x:{grid:{display:false},ticks:{color:tickC,font:{size:8}}},
          y:{grid:{color:gridC},border:{display:false},ticks:{color:tickC,font:{size:8},callback:function(v){return (v>0?"+":"")+v.toFixed(1)+"%";}}}
        }
      }
    });
  }
})();
</script>
</div>'''


def _load_geopolitical_pulse() -> dict:
    if not GEOPOLITICAL_PULSE.exists():
        return {}
    try:
        with open(GEOPOLITICAL_PULSE, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    routing = data.get("routing", {})
    if routing.get("strategy_signal") or routing.get("oms_signal") or not routing.get("reporting_only", False):
        logger.warning("geopolitical_pulse.json routing flags invalid — refusing file")
        return {}
    return data


def _render_sector_impact_matrix(geo: dict) -> str:
    matrix = geo.get("sector_impact_matrix") or []
    if not matrix:
        return f"""
  <div class="slabel" id="geo-sector-matrix">Sector Impact Matrix <span class="tag tag-a" style="vertical-align:middle">Context</span></div>
  <div class="board" style="padding:14px 18px">
    <p class="footnote meta" style="margin:0;font-size:11px;color:var(--muted)">[●] no current geopolitical pulse</p>
    {_GEO_ROUTING_FOOTER}
  </div>
"""
    rows_html = []
    for row in matrix:
        if not isinstance(row, dict):
            continue
        rows_html.append(
            "<tr>"
            f"<td>{escape(str(row.get('theme', '')))}</td>"
            f"<td>{escape(str(row.get('beneficiaries', '')))}</td>"
            f"<td>{escape(str(row.get('losers', '')))}</td>"
            f"<td class=\"mono\" style=\"font-family:'IBM Plex Mono',monospace\">{escape(str(row.get('symbols', '')))}</td>"
            "</tr>"
        )
    asof = escape(str(geo.get("asof", "UNKNOWN")))
    return f"""
  <div class="slabel" id="geo-sector-matrix">Sector Impact Matrix <span class="tag tag-a" style="vertical-align:middle">Context</span> <span style="font-size:9px;color:var(--muted);font-weight:400;text-transform:none;letter-spacing:0">as-of {asof}</span></div>
  <div class="board">
    <table>
      <thead>
        <tr>
          <th>Theme</th>
          <th>Beneficiaries</th>
          <th>Losers</th>
          <th>Symbols</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows_html)}
      </tbody>
    </table>
  </div>
  {_GEO_ROUTING_FOOTER}
"""


def _portfolio_tilt_compact_html() -> str:
    """Compact held-sector tilt strip when position file is available."""
    try:
        from src.trading.overlays.propagation_display import (
            build_portfolio_tilt_summary_html,
            is_sector_annotation_enabled,
        )
        if not is_sector_annotation_enabled():
            return ""
        pos_path = ROOT / "data" / "raw" / "current_positions_derived.json"
        if not pos_path.is_file():
            return ""
        raw = json.loads(pos_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return ""
        positions = []
        for row in raw:
            sym = str(row.get("ticker") or row.get("symbol") or "").upper()
            lots = row.get("lots") or 0
            ep = row.get("entry_price") or 0
            try:
                mkt = float(lots) * float(ep)
            except (TypeError, ValueError):
                mkt = 0.0
            if sym:
                positions.append({"symbol": sym, "mkt_value_vnd": mkt})
        return build_portfolio_tilt_summary_html(
            positions, None, compact=True, include_empty_sectors=False, show_caption=False,
        )
    except Exception:
        return ""


def _sector_leadership_tile_html() -> str:
    try:
        from src.trading.overlays.propagation_display import (
            is_sector_annotation_enabled,
            load_sector_leadership_for_display,
            sector_leadership_rows,
        )
        if not is_sector_annotation_enabled():
            return ""
        payload = load_sector_leadership_for_display()
        dates = (payload or {}).get("dates") or {}
        if not dates:
            return ""
        day = dates[max(dates.keys())]
        rows = sector_leadership_rows(day)
        if not rows:
            return ""
        body = "".join(
            f'<div class="kpi"><div class="kpi-lbl">{escape(r["sector"])}</div>'
            f'<div class="kpi-val">#{r["rank"]} {escape(str(r["bucket"]))}</div></div>'
            for r in rows[:11]
        )
        return (
            '<div class="slabel">Sector Leadership Map <span class="tag tag-f" style="vertical-align:middle">D3 display</span></div>'
            f'<div class="pulse">{body}</div>'
            '<p class="footnote meta" style="margin:6px 0 14px;font-size:11px;color:var(--muted);">'
            'Leading sectors → 1.25× size, lagging → 0.75× (D3, monotonic MAR 0.535).</p>'
        )
    except Exception:
        return ""


def _cash_plus_tile_html() -> str:
    try:
        from src.trading.overlays.propagation_display import build_cash_plus_tile_html
        tile = build_cash_plus_tile_html()
        if not tile:
            return ""
        return (
            '<div class="slabel">Idle Cash Yield <span class="tag tag-f" style="vertical-align:middle">D4 display</span></div>'
            f'<div class="pulse">{tile}</div>'
        )
    except Exception:
        return ""


def _load_breadth_c1() -> dict | None:
    """Load latest Breadth-C1 reading. Returns dict with value, signal, meaning, action."""
    try:
        import pandas as pd
        df = pd.read_parquet(BREADTH_C1_PATH)
        if df.empty:
            return None
        latest = df.iloc[-1]
        pct = float(latest["breadth_pct"])
        signal = str(latest["regime_b1"])  # BULL or BEAR
        asof = str(latest["date"])[:10]

        # Thresholds: BULL > 45% (hysteresis up), BEAR < 40% (hysteresis down)
        if pct >= 45:
            value_class = "up"
            meaning = f"{pct:.1f}% of stocks above EMA50 — broad participation"
            action = "Conditions support new entries at normal size"
        elif pct >= 40:
            value_class = "warn"
            meaning = f"{pct:.1f}% of stocks above EMA50 — borderline breadth"
            action = "Reduce new entry size; hold existing positions"
        elif pct >= 30:
            value_class = "down"
            meaning = f"{pct:.1f}% of stocks above EMA50 — market is narrowing"
            action = "No new entries; defend existing; watch exits"
        else:
            value_class = "down"
            meaning = f"{pct:.1f}% of stocks above EMA50 — thin, few leaders"
            action = "Avoid new entries; prioritise exit discipline"

        return {
            "label": "Breadth C1",
            "value": f"{pct:.1f}%  [{signal}]",
            "value_class": value_class,
            "sub": f"{meaning} → {action}",
            "sub_class": "dim",
            "status": "ok" if pct >= 45 else ("warn" if pct >= 35 else "alert"),
            "asof": asof,
        }
    except Exception:
        return None


def build_html(data: dict) -> str:
    meta    = data["meta"]
    regime  = data["regime"]
    pulse   = data["pulse"]
    events  = data["events"]
    risks   = data["risks"]
    action  = data["action_bar"]
    triggers = data["forward_triggers"]
    footer  = data["footer"]

    pills_html       = _render_pills(regime["pills"])
    inval_html       = _render_invalidation(regime["invalidation_conditions"])

    # Breadth C1 — inject as first KPI tile (meaning + action always shown)
    _breadth = _load_breadth_c1()
    _all_kpis = ([_breadth] if _breadth else []) + list(pulse["kpis"])
    kpis_html = "\n    ".join(_render_kpi(k) for k in _all_kpis)

    # Breadth context line for regime verdict section — includes forward trigger levels
    _breadth_verdict_line = ""
    if _breadth:
        _bc = "var(--r)" if "alert" in _breadth["status"] else ("var(--a)" if "warn" in _breadth["status"] else "var(--g)")
        try:
            _b_pct = float(_breadth["value"].split("%")[0].strip())
        except Exception:
            _b_pct = None
        if _b_pct is not None and _b_pct < 40:
            _watch = "Watch: &gt;40% re-opens T2 · &gt;45% re-opens full T1 sizing"
        elif _b_pct is not None and _b_pct < 45:
            _watch = "Watch: &gt;45% to re-open full T1 · drop below 40% blocks T2"
        else:
            _watch = "Normal sizing supported · watch for drop below 40% (T2 block)"
        _breadth_verdict_line = (
            f'<div style="margin-top:8px;font-size:11px;padding:6px 10px;'
            f'background:rgba(255,255,255,.03);border-left:3px solid {_bc};border-radius:3px">'
            f'<span style="color:{_bc};font-weight:600">Breadth C1 {_breadth["asof"]}:</span> '
            f'{escape(_breadth["sub"])}'
            f' &nbsp;·&nbsp; <span style="color:var(--muted);font-style:italic">{_watch}</span>'
            f'</div>'
        )
    events_html      = "\n    ".join(_render_event(e) for e in events)
    high_risks_html  = _render_risk_rows(risks["high"],   "dot-r")
    med_risks_html   = _render_risk_rows(risks["medium"], "dot-a")
    buckets_html     = "\n      ".join(_render_bucket(b) for b in action["buckets"])
    price_date       = escape(action.get("price_date", ""))
    triggers_html    = "\n      ".join(_render_forward_trigger(t) for t in triggers)

    # Component 1+5: Regime hero (duration counter + animated pulse dot)
    _days, _reg_label, _css_cls, _asof, _conflict_note = _compute_regime_hero(REGIME_STATE_PATH)
    regime_hero_html = _render_regime_hero(_days, _reg_label, _css_cls, _asof, _conflict_note)

    mp_html = _render_monetary_policy(data["monetary_policy"]) if data.get("monetary_policy") else ""
    _pivot_data = _load_rate_pivot_monitor()
    pivot_monitor_html = _render_rate_pivot_monitor(_pivot_data)
    from scripts.reporting.rate_pivot_transmission import normalize_transmission_contract
    _tx = normalize_transmission_contract(_pivot_data)
    _tx_state = (_tx.get("current_state") or {})
    _tx_id = _tx_state.get("id")
    _tx_conf = str(_tx_state.get("confirmation_status") or "NOT_CONFIRMED").replace("_", " ")
    if isinstance(_tx_id, int):
        fx_liq_badge = (
            f'<div style="margin:8px 0 12px;padding:6px 10px;border:1px solid rgba(59,130,246,.35);'
            f'border-radius:4px;background:rgba(59,130,246,.06);font-size:11px;color:var(--b);'
            f'font-weight:700">FX → Liquidity: STATE {_tx_id} · {_tx_conf}</div>'
        )
    else:
        fx_liq_badge = (
            '<div style="margin:8px 0 12px;padding:6px 10px;border:1px solid var(--border);'
            'border-radius:4px;background:rgba(255,255,255,.02);font-size:11px;color:var(--muted);'
            'font-weight:700">FX → Liquidity: UNKNOWN / STALE · NOT CONFIRMED</div>'
        )
    dxy_cycle_html = _render_dxy_cycle_panel()
    sector_tile_html = _sector_leadership_tile_html()
    cash_tile_html = _cash_plus_tile_html()
    portfolio_tilt_html = _portfolio_tilt_compact_html()
    geo = _load_geopolitical_pulse()
    sector_impact_html = _render_sector_impact_matrix(geo)

    report_controls_css = ""
    sys_controls_html = ""
    sys_controls_js = ""
    live_mode_js = ""
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
        live_mode_js = build_live_mode_js("pm_regime")
    except Exception:
        pass

    generated_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    prov_html = render_provenance_header(
        title="PM Vietnam Regime Dashboard",
        generated_at=generated_ts,
        data_as_of=str(meta.get("data_date") or meta.get("prices_date") or "—"),
        data_mode="FROZEN",
        universe_scope="PM thesis tickers + macro pulse (manually curated dashboard data)",
        source_files=["data/raw/pm_dashboard_data.json", "data/state/regime_state.json"],
    )
    suite_nav_html = render_suite_nav("pm_regime")
    perm_note_html = f'<p class="perm-precedence-note">{PERMISSION_PRECEDENCE_PM}</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PM Vietnam — Regime Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
{_CSS}
{report_controls_css}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
</head>
<body>
<div class="layout">
<aside class="sidebar">
  <div class="sidebar-logo">PM Regime</div>
  <h3>Policy</h3>
  <a href="#pmr-monetary">Monetary Policy</a>
  <a href="#pmr-pivot">Rate Pivot Monitor</a>
  <a href="#pmr-dxy">DXY Cycle</a>
  <h3>Regime</h3>
  <a href="#pmr-regime">Regime Verdict</a>
  <a href="#pmr-pulse">Macro Pulse</a>
  <h3>Risk &amp; Action</h3>
  <a href="#pmr-events">Events</a>
  <a href="#pmr-risk">Risk Dashboard</a>
  <a href="#pmr-action">Action Bar</a>
  <a href="#pmr-triggers">Triggers</a>
</aside>
<div class="page">

  {prov_html}
  {suite_nav_html}

  <!-- HEADER -->
  <div class="hdr">
    <div class="hdr-title">PM · Vietnam Regime Dashboard</div>
    <div class="hdr-meta">Data: {escape(meta["data_date"])} · Prices: {escape(meta["prices_date"])} · Updated: {escape(meta["updated_date"])} · <span style="color:var(--b)">Council conditions applied: {escape(meta["council_conditions_date"])}</span></div>
  </div>

  {sys_controls_html}
  {perm_note_html}

  <!-- S0 · MONETARY POLICY STANCE -->
  <div class="slabel" id="pmr-monetary">Monetary Policy Stance <span class="tag tag-f" style="vertical-align:middle">Fact</span></div>
  {mp_html}

  <!-- S0.5 · RATE PIVOT MONITOR -->
  <div class="slabel" id="pmr-pivot">Rate Pivot Monitor <span style="font-size:9px;color:var(--a);font-weight:400;text-transform:none;letter-spacing:0">When do VN funding costs ease enough to re-open equity participation?</span></div>
  {pivot_monitor_html}

  <!-- S0.6 · DXY ANNUAL CYCLE (G1 FX veto context) -->
  <div class="slabel" id="pmr-dxy">DXY Annual Cycle <span style="font-size:9px;color:var(--muted);font-weight:400;text-transform:none;letter-spacing:0">20yr history · G1 FX veto context · Opus council reviewed 2026-07-12</span></div>
  {dxy_cycle_html}

  <!-- S1 · REGIME HERO (duration counter + pulse dot) -->
  {regime_hero_html}

  <!-- S1 · REGIME VERDICT -->
  <div class="slabel" id="pmr-regime">Regime</div>
  <div class="verdict">
    <div class="pills">
      {pills_html}
    </div>
    <div class="verdict-note">{escape(regime["verdict_text"])}</div>
    {_breadth_verdict_line}
    <details class="inval">
      <summary>⚠ Thesis Invalidation — any one flips the regime verdict</summary>
      <div class="inval-list"><ul>
        {inval_html}
      </ul></div>
    </details>
  </div>

  <!-- S2 · PULSE STRIP -->
  <div class="slabel" id="pmr-pulse">Macro &amp; Market Pulse <span class="tag tag-f" style="vertical-align:middle">All: Fact</span></div>
  {fx_liq_badge}
  <div class="pulse">
    {kpis_html}
  </div>
  {sector_tile_html}
  {cash_tile_html}
  {portfolio_tilt_html}

  <!-- S3 · EVENTS -->
  <div class="slabel" id="pmr-events">Events</div>
  <div class="moves">
    {events_html}
  </div>

  <!-- S3.5 · RISK DASHBOARD -->
  <div class="slabel" id="pmr-risk">Risk Dashboard <span style="font-size:9px;color:var(--b);font-weight:400;text-transform:none;letter-spacing:0">[above Action Bar — council hierarchy]</span></div>
  <div class="risk-strip">
    <div>
      <div class="risk-col-title" style="color:var(--r)">● High</div>
      {high_risks_html}
    </div>
    <div>
      <div class="risk-col-title" style="color:var(--a)">● Medium</div>
      {med_risks_html}
    </div>
  </div>

  <!-- S4 · ACTION BAR -->
  <div class="slabel" id="pmr-action">Action Bar <span style="font-size:9px;color:var(--b);font-weight:400;text-transform:none;letter-spacing:0">[trigger · invalidation · event date added per council Condition 4]</span></div>
  <div class="board">
    <table>
      <thead>
        <tr>
          <th style="width:80px">Ticker</th>
          <th style="min-width:130px">Thesis</th>
          <th style="width:120px;text-align:right">Price · {price_date}</th>
          <th style="width:45px;text-align:center">Chg%</th>
          <th style="min-width:160px;color:var(--g)">▲ Trigger Level</th>
          <th style="min-width:160px;color:var(--r)">✕ Invalidation</th>
          <th style="min-width:110px;color:var(--b)">📅 Event Date</th>
          <th style="width:55px;text-align:center">Flow</th>
        </tr>
      </thead>
      {buckets_html}
    </table>
  </div>

  {sector_impact_html}

  <!-- S5 · FORWARD TRIGGERS -->
  <div class="slabel" id="pmr-triggers">Forward Triggers</div>
  <div style="background:var(--s1);border:1px solid var(--border);border-radius:8px;padding:6px 18px 10px;">
    <div class="triggers">
      {triggers_html}
    </div>
  </div>

  <!-- FOOTER -->
  <div class="footer">
    {escape(footer["sources"])} &nbsp;|&nbsp;
    {escape(footer["prev_note"])} &nbsp;|&nbsp;
    <strong style="color:var(--b)">Council conditions applied {escape(meta["council_conditions_date"])}:</strong>
    <span style="color:var(--b)">{escape(footer["council_conditions_text"])}</span> &nbsp;|&nbsp;
    Council-reviewed by {escape(footer["council_reviewer"])} &nbsp;|&nbsp; Not financial advice. &nbsp;|&nbsp;
    <span style="color:var(--faint)">Generated: {generated_ts}</span>
  </div>

</div>
</div>
{sys_controls_js}
{live_mode_js}
</body>
</html>"""


# ── Entry point ────────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="PM Regime Dashboard Generator")
    parser.add_argument(
        "--data",
        default=str(ROOT / "data" / "raw" / "pm_dashboard_data.json"),
        help="Path to pm_dashboard_data.json",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "reports" / "pm_regime_dashboard_latest.html"),
        help="Output HTML path",
    )
    args = parser.parse_args()

    data_path   = Path(args.data)
    output_path = Path(args.output)

    if not data_path.exists():
        logger.error("Data file not found: %s", data_path)
        sys.exit(1)

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    logger.info("Building PM Regime Dashboard from: %s", data_path)
    html = build_html(data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Dashboard written: %s", output_path)


if __name__ == "__main__":
    main()
