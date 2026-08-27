"""Shared provenance, cross-report nav, inst-accum join, and position-context paths.

Display-only helpers for the 5-report VN trading suite. Does not touch signals or OMS.
"""
from __future__ import annotations

import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]

INST_ACCUM_COMPACT_PATH = REPO / "data" / "decision" / "institutional_accumulation_compact.json"
POSITION_CONTEXT_PATH = REPO / "data" / "state" / "position_context_daily.json"
# Produced by `03. Capital Investment/02_Stock_Research/_tools/street_corpus.py coverage`.
# Content-free by construction (ticker, 2 ints, 1 date, 1 enum) because the street corpus is
# Class-3 licensed and this suite is git-tracked + Drive-mirrored. Availability and staleness
# only — never a rating, target price, or broker view. FA-to-TA stays one-directional: this
# is display/advisory and must not reach signals, universe selection, or OMS.
STREET_COVERAGE_COMPACT_PATH = REPO / "data" / "decision" / "street_coverage_compact.json"

REPORT_SUITE: dict[str, dict[str, str]] = {
    "cloud_daily": {
        "label": "Cloud Daily",
        "path": "data/research/reports/cloud_daily_report_latest.html",
    },
    "portfolio_monitor": {
        "label": "Portfolio Monitor",
        "path": "reports/portfolio_monitor_latest.html",
    },
    "pm_regime": {
        "label": "PM Regime",
        "path": "reports/pm_regime_dashboard_latest.html",
    },
    "ema_research": {
        "label": "E&MA Research",
        "path": "data/research/reports/ema_research_latest.html",
    },
    "inst_accum": {
        "label": "Inst. Accumulation",
        "path": "outputs/scans/institutional_accumulation_operator_summary_latest.html",
    },
    "tollbooth": {
        "label": "Tollbooth 10Y",
        "path": "reports/tollbooth_tracker_latest.html",
    },
}

PERMISSION_PRECEDENCE_CLOUD = (
    "This matrix is the <strong>binding</strong> trading-permission source; "
    "pm_regime_dashboard Trading Logic flags are advisory PM overlay only."
)

PERMISSION_PRECEDENCE_PM = (
    "Trading Logic flags here are <strong>advisory PM overlay only</strong>. "
    "Binding permission matrix: "
    '<a href="../data/research/reports/cloud_daily_report_latest.html#section-cio">'
    "Cloud Daily CIO Cockpit</a>."
)

SUITE_NAV_CSS = """
/* Suite-wide mobile table behaviour: below 900px every table becomes its own horizontal
   scroll container, so wide tables never force the page to scroll sideways. Scoped to a
   media query so desktop keeps sticky <th> (display:block would detach it there). */
@media (max-width: 900px) { table { display: block; overflow-x: auto; } }
.suite-provenance { background: var(--panel, #13161b); border: 1px solid var(--border, #252a35); border-radius: 6px; padding: 10px 14px; margin: 8px 0 10px; font-size: 12px; }
.suite-provenance .sp-title { font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--dim, #7a8399); margin-bottom: 6px; }
.suite-provenance .sp-row { color: var(--dim, #7a8399); margin: 2px 0; line-height: 1.5; }
.suite-provenance .sp-row strong { color: var(--text, #d8dde8); font-weight: 600; }
.suite-provenance .sp-badge { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 9px; font-weight: 700; letter-spacing: 0.04em; margin-left: 4px; vertical-align: middle; }
.suite-provenance .sp-frozen { background: #1e2a38; color: #4a9eff; border: 1px solid #2d3f57; }
.suite-provenance .sp-live { background: #3a2800; color: #f0a030; border: 1px solid #6a4e00; }
.suite-provenance .sp-snapshot { background: #1a1a3a; color: #a8b4ff; border: 1px solid #3a4080; }
.suite-provenance .sp-mixed { background: #1a2a1a; color: #00c896; border: 1px solid #2d6a2d; }
.suite-nav { background: var(--panel, #13161b); border-radius: 6px; padding: 6px 12px; margin: 6px 0 10px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; font-size: 11px; }
.suite-nav .suite-nav-label { color: #4a6888; font-weight: 700; font-size: 0.72rem; letter-spacing: 0.04em; }
.suite-nav a { color: #4a9eff; text-decoration: none; padding: 2px 8px; border-radius: 3px; border: 1px solid var(--border, #252a35); transition: background 0.1s; }
.suite-nav a:hover { background: #1e3050; }
.suite-nav a.suite-nav-current { border-color: #00c896; color: #00c896; }
.suite-nav .suite-nav-ts { color: var(--muted, #4a5168); font-size: 10px; font-family: "IBM Plex Mono", monospace; }
.perm-precedence-note { font-size: 11px; color: #7aa8d0; margin: 4px 0 8px; line-height: 1.45; }
.inst-accum-cell { font-size: 11px; line-height: 1.4; }
.inst-accum-score { font-family: "IBM Plex Mono", monospace; font-weight: 600; color: #8ab4f8; }
.inst-accum-bucket { font-size: 10px; color: var(--dim, #7a8399); }
.inst-accum-research-tag { display: inline-block; font-size: 9px; font-weight: 700; letter-spacing: 0.04em; color: #6a9cc8; border: 1px solid #1e3650; border-radius: 3px; padding: 0 4px; margin-right: 4px; }
"""


def _esc(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


def _relative_href(from_html_path: str, to_repo_path: str) -> str:
    """Relative URL from one report HTML file to another in the repo."""
    from_abs = (REPO / from_html_path).parent.resolve()
    target_abs = (REPO / to_repo_path).resolve()
    try:
        rel = os.path.relpath(target_abs, from_abs)
        return rel.replace("\\", "/")
    except ValueError:
        return to_repo_path.replace("\\", "/")


def report_file_mtime(repo_path: str) -> str:
    p = REPO / repo_path
    if not p.is_file():
        return "missing"
    ts = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    return ts.strftime("%Y-%m-%d %H:%M UTC")


def render_suite_nav(current_report_id: str) -> str:
    """Cross-report link strip with sibling generated-at timestamps.

    The current page's own timestamp is deliberately omitted: its mtime changes on every
    write, so rendering it here would make an otherwise-idempotent in-place inject
    non-deterministic (see build_vn_structural_signals.py --inject idempotency contract,
    guarded by test_laban_engine.test_10). The current page's generated-at is already shown
    in the provenance header directly above this strip.
    """
    current = REPORT_SUITE[current_report_id]
    from_path = current["path"]
    links: list[str] = []
    for rid, meta in REPORT_SUITE.items():
        href = _relative_href(from_path, meta["path"])
        cls = " suite-nav-current" if rid == current_report_id else ""
        if rid == current_report_id:
            links.append(
                f'<a href="{_esc(href)}" class="{cls.strip()}">{_esc(meta["label"])}</a>'
            )
        else:
            ts = report_file_mtime(meta["path"])
            links.append(
                f'<a href="{_esc(href)}" class="{cls.strip()}">{_esc(meta["label"])}'
                f' <span class="suite-nav-ts">{_esc(ts)}</span></a>'
            )
    return (
        '<div class="suite-nav">'
        '<span class="suite-nav-label">REPORT SUITE:</span> '
        + " ".join(links)
        + "</div>"
    )


def render_provenance_header(
    *,
    title: str,
    generated_at: str,
    data_as_of: str,
    data_mode: str,
    universe_scope: str,
    source_files: list[str],
) -> str:
    """Provenance block: generated-at, data-as-of, FROZEN/LIVE badge, universe, sources."""
    mode_upper = data_mode.upper()
    badge_cls = {
        "FROZEN": "sp-frozen",
        "LIVE": "sp-live",
        "MIXED": "sp-mixed",
        "SNAPSHOT": "sp-snapshot",
    }.get(mode_upper, "sp-frozen")
    sources = ", ".join(_esc(str(s).replace("\\", "/")) for s in source_files) if source_files else "—"
    snapshot_note = (
        " <span style='font-size:10px;color:var(--dim,#7a8399)'>"
        "(static at generation; no client refresh)</span>"
        if mode_upper == "SNAPSHOT" else ""
    )
    return (
        '<div class="suite-provenance">'
        f'<div class="sp-title">{_esc(title)}</div>'
        f'<div class="sp-row">Generated: <strong>{_esc(generated_at)}</strong></div>'
        f'<div class="sp-row">Data as-of: <strong>{_esc(data_as_of)}</strong>'
        f' <span class="sp-badge {badge_cls}">{_esc(mode_upper)}</span>{snapshot_note}</div>'
        f'<div class="sp-row">Universe: <strong>{_esc(universe_scope)}</strong></div>'
        f'<div class="sp-row">Sources: <span style="font-family:IBM Plex Mono,monospace;font-size:11px">{sources}</span></div>'
        "</div>"
    )


def load_institutional_accumulation_compact(
    path: Path | None = None,
) -> dict[str, Any]:
    p = path or INST_ACCUM_COMPACT_PATH
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def build_inst_accum_ticker_index(compact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map ticker → tier2_focus_list or tier3_near_miss record (display-only)."""
    out: dict[str, dict[str, Any]] = {}
    for row in compact.get("tier2_focus_list") or []:
        if isinstance(row, dict):
            tk = str(row.get("ticker", "")).upper()
            if tk:
                out[tk] = {**row, "_tier": "tier2"}
    for row in compact.get("tier3_near_miss") or []:
        if isinstance(row, dict):
            tk = str(row.get("ticker", "")).upper()
            if tk:
                out[tk] = {**row, "_tier": "tier3"}
    for tk in compact.get("tier1_tickers") or []:
        sym = str(tk).upper()
        if sym and sym not in out:
            out[sym] = {"ticker": sym, "_tier": "tier1"}
    return out


def render_inst_accum_cell(ticker: str, index: dict[str, dict[str, Any]]) -> str:
    """Compact inst-accum evidence cell — research_prioritization_only, no badge reuse."""
    rec = index.get(str(ticker).upper())
    if not rec:
        return "<span style='color:#3a5570'>—</span>"
    score = rec.get("institutional_accumulation_score")
    bucket = rec.get("fund_context_bucket", "")
    tier = rec.get("_tier", "")
    score_str = f"{float(score):.1f}" if score is not None else "—"
    summary = (
        '<span class="inst-accum-research-tag">IA</span>'
        f'<span class="inst-accum-score">{_esc(score_str)}</span>'
    )
    if bucket:
        summary += f' <span class="inst-accum-bucket">{_esc(bucket)}</span>'
    if tier:
        summary += f' <span class="inst-accum-bucket">({_esc(tier)})</span>'

    driver = rec.get("primary_driver")
    note = rec.get("operator_note")
    if not driver and not note:
        return f'<div class="inst-accum-cell">{summary}</div>'

    detail_parts: list[str] = []
    if driver:
        detail_parts.append(f"<div><strong>Driver:</strong> {_esc(driver)}</div>")
    if note:
        detail_parts.append(f"<div><strong>Note:</strong> {_esc(note)}</div>")
    card = (
        '<div class="inst-accum-cell" style="font-size:11px;color:#8b9eb8;margin-top:4px">'
        + "".join(detail_parts)
        + '<div style="font-size:10px;color:#4a5168;margin-top:4px">'
        "institutional_accumulation_compact.json · research_prioritization_only</div></div>"
    )
    return f"<details class='ma-det'><summary>{summary}</summary>{card}</details>"


_STREET_FRESH_STYLE: dict[str, tuple[str, str]] = {
    # enum -> (dot colour, tooltip verb).  Thresholds owned upstream by street_corpus.py;
    # this map only paints what the contract already decided — do not re-derive ages here.
    "fresh": ("#00c896", "under 30d"),
    "aging": ("#f0a030", "30-90d"),
    "stale": ("#f05050", "90d+ or undated"),
}


def load_street_coverage_compact(path: Path | None = None) -> dict[str, Any]:
    """Load the content-free street-coverage contract. Absent file is a normal state."""
    p = path or STREET_COVERAGE_COMPACT_PATH
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def build_street_coverage_index(compact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map ticker -> {houses, reports, latest, fresh}. Display-only."""
    out: dict[str, dict[str, Any]] = {}
    for tk, rec in (compact.get("tickers") or {}).items():
        if isinstance(rec, dict):
            sym = str(tk).upper()
            if sym:
                out[sym] = rec
    return out


def render_street_coverage_cell(ticker: str, index: dict[str, dict[str, Any]]) -> str:
    """Coverage availability cell: freshness dot + house count. No broker view, by contract.

    Renders `--` when a ticker has no street coverage. That is deliberately the same glyph
    as 'no data' elsewhere in the suite: absence of coverage is not a negative signal about
    the name, and must not read as one.
    """
    rec = index.get(str(ticker).upper())
    if not rec:
        return "<span style='color:#3a5570'>&mdash;</span>"
    fresh = str(rec.get("fresh", "stale"))
    colour, age_hint = _STREET_FRESH_STYLE.get(fresh, _STREET_FRESH_STYLE["stale"])
    houses = rec.get("houses", 0)
    reports = rec.get("reports", 0)
    latest = str(rec.get("latest") or "undated")
    tip = (
        f"{houses} house(s), {reports} report(s), latest {latest} ({age_hint}). "
        "Availability only - advisory, does not feed signals/universe/OMS."
    )
    return (
        f'<span title="{html.escape(tip, quote=True)}" '
        'style="font-family:IBM Plex Mono,monospace;font-size:11px;white-space:nowrap">'
        f'<span style="color:{colour}">&#9679;</span> '
        f'<span style="color:#8b9eb8">{int(houses)}h</span>'
        "</span>"
    )


def load_position_context(path: Path | None = None) -> dict[str, Any]:
    p = path or POSITION_CONTEXT_PATH
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def position_context_by_symbol(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = payload.get("positions") or []
    out: dict[str, dict[str, Any]] = {}
    for rec in records:
        if isinstance(rec, dict):
            sym = str(rec.get("symbol", "")).upper()
            if sym:
                out[sym] = rec
    return out


# ---------------------------------------------------------------------------
# Structural TA (file-backed advisory) — mirror inst-accum triad pattern
# Data: data/processed/ta_structural_support.json (CLI --output wrapper).
# Display-only; never feeds OMS / final_action.
# ---------------------------------------------------------------------------

TA_STRUCTURAL_SUPPORT_PATH = REPO / "data" / "processed" / "ta_structural_support.json"
STRUCTURAL_TA_STALE_DAYS = 7  # match weekly_lean_sections domain convention

# Colorblind-safe tokens shared with lean `.sta-badge-*` (templates/styles.css)
_STA_INFO = "#1d4ed8"
_STA_WARN = "#b45309"

STRUCTURAL_TA_CSS = f"""
.sta-suite-wrap {{ margin: 10px 0 14px; }}
.sta-suite-card {{
  background: var(--panel, #13161b); border: 1px solid var(--border, #252a35);
  border-radius: 6px; padding: 10px 12px; margin: 8px 0; font-size: 12px;
}}
.sta-suite-card .sta-head {{
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-content: space-between;
  margin-bottom: 6px;
}}
.sta-suite-card .sta-tk {{ font-weight: 700; font-family: IBM Plex Mono, monospace; color: var(--accent, #00c896); }}
.sta-suite-tag {{
  display: inline-block; background: #0f1e2e; color: #6a9cc8; border: 1px solid #1e3650;
  border-radius: 3px; padding: 0 6px; font-size: 9px; font-weight: 700;
  text-transform: uppercase; letter-spacing: .04em;
}}
.sta-badge {{
  display: inline-flex; align-items: center; gap: 4px; font-size: 10px;
  padding: 2px 8px; border-radius: 4px; font-weight: 600;
}}
.sta-badge-info {{
  background: rgba(29, 78, 216, 0.14); color: {_STA_INFO}; border: 1px solid rgba(29, 78, 216, 0.35);
}}
.sta-badge-warning {{
  background: rgba(180, 83, 9, 0.14); color: {_STA_WARN}; border: 1px solid rgba(180, 83, 9, 0.4);
}}
.sta-badge-missing {{
  background: rgba(122, 131, 153, 0.12); color: #7a8399; border: 1px solid rgba(122, 131, 153, 0.35);
}}
.sta-suite-meta {{ color: var(--dim, #7a8399); font-size: 11px; line-height: 1.45; }}
.sta-suite-compact {{
  font-size: 11px; padding: 6px 10px; border: 1px solid var(--border, #252a35);
  border-radius: 4px; background: rgba(255,255,255,.02); margin: 6px 0;
}}
.sta-suite-summary {{
  border-left: 3px solid {_STA_INFO}; padding: 8px 12px; margin: 8px 0 12px;
  background: rgba(29, 78, 216, 0.06); border-radius: 0 4px 4px 0; font-size: 12px;
}}
"""


def _parse_generated_at(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def structural_ta_file_meta(compact: dict[str, Any]) -> dict[str, Any]:
    """Return {status: missing|stale|ok, note, age_days, generated_at, source}."""
    if not compact:
        return {
            "status": "missing",
            "note": "Structural TA not generated this cycle.",
            "age_days": None,
            "generated_at": None,
            "source": None,
            "stale_threshold_days": STRUCTURAL_TA_STALE_DAYS,
        }
    generated_at = compact.get("generated_at")
    parsed = _parse_generated_at(generated_at)
    age_days = None
    status = "ok"
    note = None
    if parsed is None:
        status = "stale"
        note = "Structural TA missing generated_at — treated as stale."
    else:
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_days = (now.date() - parsed.astimezone(timezone.utc).date()).days
        if age_days > STRUCTURAL_TA_STALE_DAYS:
            status = "stale"
            note = (
                f"Structural TA is {age_days}d old "
                f"(threshold {STRUCTURAL_TA_STALE_DAYS}d)."
            )
    return {
        "status": status,
        "note": note,
        "age_days": age_days,
        "generated_at": generated_at,
        "source": compact.get("source") or "vn_ta_fireant_cli",
        "schema_version": compact.get("schema_version"),
        "stale_threshold_days": STRUCTURAL_TA_STALE_DAYS,
    }


def load_structural_ta_compact(path: Path | None = None) -> dict[str, Any]:
    """Load ta_structural_support.json wrapper. Absent/malformed → {{}}."""
    p = path or TA_STRUCTURAL_SUPPORT_PATH
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def build_structural_ta_index(compact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map ticker → normalized assessment (reuse lean normalizer — one shape)."""
    # Lazy import avoids circular imports at module load; lean already owns normalize.
    from scripts.ingest.weekly_lean_sections import _normalize_structural_ticker

    out: dict[str, dict[str, Any]] = {}
    results = compact.get("results") if isinstance(compact.get("results"), list) else []
    for item in results:
        row = _normalize_structural_ticker(item)
        tk = str(row.get("ticker") or "").upper()
        if tk and tk != "UNKNOWN":
            out[tk] = row
    return out


def render_structural_ta_card(
    ticker: str,
    index: dict[str, dict[str, Any]],
    *,
    file_meta: dict[str, Any] | None = None,
) -> str:
    """Full advisory card for one ticker (Cloud Daily / Portfolio Monitor)."""
    meta = file_meta or {"status": "ok"}
    file_status = str(meta.get("status") or "ok")
    if file_status == "missing":
        return (
            f'<div class="sta-suite-card" data-sta-ticker="{_esc(ticker)}">'
            f'<div class="sta-head"><span class="sta-tk">{_esc(str(ticker).upper())}</span>'
            f'<span class="sta-suite-tag">ADVISORY — not a signal input</span></div>'
            f'<span class="sta-badge sta-badge-missing">⚠ missing</span> '
            f'<span class="sta-suite-meta">Structural TA not generated this cycle.</span></div>'
        )
    if file_status == "stale":
        stale_banner = (
            f'<div class="sta-suite-meta" style="margin-bottom:6px">'
            f'<span class="sta-badge sta-badge-warning">⚠ stale</span> '
            f'{_esc(meta.get("note") or "Structural TA snapshot is stale.")}</div>'
        )
    else:
        stale_banner = ""

    rec = index.get(str(ticker).upper())
    if not rec:
        return (
            f'<div class="sta-suite-card" data-sta-ticker="{_esc(ticker)}">'
            f'{stale_banner}'
            f'<div class="sta-head"><span class="sta-tk">{_esc(str(ticker).upper())}</span>'
            f'<span class="sta-suite-tag">ADVISORY — not a signal input</span></div>'
            f'<span class="sta-suite-meta">No Structural TA row for this ticker.</span></div>'
        )

    tone = rec.get("status_tone") or "info"
    badge_cls = "sta-badge-warning" if tone == "warning" else "sta-badge-info"
    if rec.get("error"):
        badge_cls = "sta-badge-warning"
    glyph = rec.get("status_glyph") or "•"
    label = rec.get("status_label") or "under_test"
    score = rec.get("score")
    score_s = "—" if score is None else str(score)
    cls = rec.get("classification") or rec.get("verdict") or "—"
    mf = rec.get("money_flow") if isinstance(rec.get("money_flow"), dict) else {}
    mf_line = mf.get("summary") if mf.get("available") else "Weekly OBV/CMF n/a"
    err = rec.get("error")
    err_html = (
        f'<div class="sta-suite-meta"><span class="sta-badge sta-badge-warning">✗ error</span> {_esc(err)}</div>'
        if err
        else ""
    )
    return (
        f'<div class="sta-suite-card" data-sta-ticker="{_esc(rec.get("ticker"))}">'
        f"{stale_banner}"
        f'<div class="sta-head">'
        f'<span><span class="sta-tk">{_esc(rec.get("ticker"))}</span>'
        f' · score {_esc(score_s)} · {_esc(cls)}</span>'
        f'<span class="sta-suite-tag">ADVISORY — not a signal input</span></div>'
        f'<span class="sta-badge {badge_cls}">{_esc(glyph)} {_esc(label)}</span> '
        f'<span class="sta-suite-meta">{_esc(mf_line)}</span>'
        f"{err_html}</div>"
    )


def render_structural_ta_compact_row(
    ticker: str,
    index: dict[str, dict[str, Any]],
    *,
    file_meta: dict[str, Any] | None = None,
) -> str:
    """Compact one-line context (Inst. Accumulation)."""
    meta = file_meta or {"status": "ok"}
    if str(meta.get("status")) == "missing":
        return (
            '<div class="sta-suite-compact">'
            '<span class="sta-suite-tag">ADVISORY — not a signal input</span> '
            '<span class="sta-badge sta-badge-missing">⚠ missing</span> Structural TA n/a</div>'
        )
    rec = index.get(str(ticker).upper())
    if not rec:
        return ""
    tone = rec.get("status_tone") or "info"
    badge_cls = "sta-badge-warning" if tone == "warning" or rec.get("error") else "sta-badge-info"
    score = rec.get("score")
    score_s = "—" if score is None else str(score)
    return (
        f'<div class="sta-suite-compact" data-sta-ticker="{_esc(rec.get("ticker"))}">'
        f'<span class="sta-suite-tag">ADVISORY — not a signal input</span> '
        f'<strong class="sta-tk">{_esc(rec.get("ticker"))}</strong> '
        f'score {_esc(score_s)} · {_esc(rec.get("classification") or rec.get("verdict") or "—")} '
        f'<span class="sta-badge {badge_cls}">{_esc(rec.get("status_glyph") or "•")} '
        f'{_esc(rec.get("status_label") or "under_test")}</span></div>'
    )


def render_structural_ta_summary(
    index: dict[str, dict[str, Any]],
    *,
    file_meta: dict[str, Any] | None = None,
) -> str:
    """Index-level rollup only (PM Regime) — no per-ticker cards."""
    meta = file_meta or {"status": "ok"}
    file_status = str(meta.get("status") or "ok")
    advisory = '<span class="sta-suite-tag">ADVISORY — not a signal input</span>'
    if file_status == "missing":
        return (
            f'<div class="sta-suite-summary" id="structural-ta-summary">{advisory} '
            f'<span class="sta-badge sta-badge-missing">⚠ missing</span> '
            f'Structural TA not generated this cycle.</div>'
        )
    n = len(index)
    strong = sum(
        1
        for r in index.values()
        if "Strong" in str(r.get("classification") or "") or (isinstance(r.get("score"), (int, float)) and r["score"] >= 70)
    )
    failed = sum(1 for r in index.values() if r.get("status_label") == "failed" or r.get("error"))
    under = sum(1 for r in index.values() if r.get("status_label") == "under_test")
    held = sum(1 for r in index.values() if r.get("status_label") == "held")
    stale_note = ""
    if file_status == "stale":
        stale_note = (
            f' <span class="sta-badge sta-badge-warning">⚠ stale</span> '
            f'{_esc(meta.get("note") or "")}'
        )
    return (
        f'<div class="sta-suite-summary" id="structural-ta-summary">{advisory}{stale_note}<br>'
        f'<strong>Structural TA rollup:</strong> {n} ticker(s) scored · '
        f'{strong} strong support · {held} held · {under} under test · {failed} failed/error. '
        f'<span class="sta-suite-meta">Source {_esc(meta.get("source"))} · '
        f'generated {_esc(meta.get("generated_at") or "—")} · text only, no chart</span></div>'
    )


def render_structural_ta_cards_section(
    tickers: list[str],
    index: dict[str, dict[str, Any]],
    *,
    file_meta: dict[str, Any] | None = None,
    section_id: str = "structural-ta",
    title: str = "Structural TA (advisory)",
) -> str:
    """Section wrapper with full cards for the given ticker list (deduped, order preserved)."""
    meta = file_meta or structural_ta_file_meta({})
    seen: set[str] = set()
    ordered: list[str] = []
    for t in tickers:
        sym = str(t or "").upper()
        if sym and sym not in seen:
            seen.add(sym)
            ordered.append(sym)
    cards = [render_structural_ta_card(t, index, file_meta=meta) for t in ordered]
    if not cards and meta.get("status") == "missing":
        cards = [
            '<div class="sta-suite-card">'
            '<span class="sta-suite-tag">ADVISORY — not a signal input</span> '
            '<span class="sta-badge sta-badge-missing">⚠ missing</span> '
            "Structural TA not generated this cycle.</div>"
        ]
    if not cards:
        return ""
    return (
        f'<div class="sta-suite-wrap" id="{_esc(section_id)}">'
        f'<div class="section-title" style="margin:0 0 6px;font-size:11px;letter-spacing:.06em;'
        f'text-transform:uppercase;color:var(--dim,#7a8399)">{_esc(title)} '
        f'<span class="sta-suite-tag">ADVISORY — not a signal input</span></div>'
        + "".join(cards)
        + "</div>"
    )


# Pages already inject SUITE_NAV_CSS — fold Structural TA styles into that bundle.
SUITE_NAV_CSS = SUITE_NAV_CSS + "\n" + STRUCTURAL_TA_CSS
