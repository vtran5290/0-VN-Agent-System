"""
Render weekly_report.json (schema v1.0) to HTML.
Output: reports/latest/index.html and reports/archive/{asof_date}/index.html
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

from scripts.ingest.config import DATA_PROCESSED, REPO
from scripts.utils.io import read_json

REPORTS_LATEST = REPO / "reports" / "latest"
REPORTS_ARCHIVE = REPO / "reports" / "archive"
TEMPLATE_DIR = REPO / "templates"
TEMPLATE_NAME = "weekly_report.html.j2"


def _ensure_nested(d: Dict[str, Any], *keys: str) -> None:
    for k in keys:
        if k not in d or not isinstance(d.get(k), dict):
            d[k] = d.get(k) if isinstance(d.get(k), dict) else {}


def render_html(payload: Dict[str, Any], out_path: Path, base_css: str = "styles.css") -> None:
    """Render payload to HTML using Jinja2 template."""
    try:
        from jinja2 import Environment, FileSystemLoader
    except ImportError:
        # Fallback: minimal inline HTML without Jinja
        out_path.parent.mkdir(parents=True, exist_ok=True)
        html = _fallback_html(payload)
        out_path.write_text(html, encoding="utf-8")
        return
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    env.globals["base_css_path"] = base_css
    template = env.get_template(TEMPLATE_NAME)
    # Ensure nested dicts for template
    _ensure_nested(payload.get("global_macro", {}), "facts")
    _ensure_nested(payload.get("vietnam_liquidity", {}), "facts")
    _ensure_nested(payload.get("market_structure", {}), "levels", "distribution")
    _ensure_nested(payload.get("regime_engine", {}), "inputs")
    _ensure_nested(payload.get("execution_monitoring", {}), "risk_flags")
    _ensure_nested(payload.get("geo_layers", {}), "geo_hormuz_energy_shock")
    for section in ("global_macro", "vietnam_liquidity", "market_structure", "regime_engine", "decision_layer", "watchlist", "execution_monitoring", "portfolio_health", "geo_layers"):
        if section not in payload:
            payload[section] = {}
    if "metadata" not in payload:
        payload["metadata"] = {}
    # Template comparisons should not operate on Undefined values.
    payload["metadata"].setdefault("report_age_days", None)
    payload["metadata"].setdefault("generated_at", None)
    payload["metadata"].setdefault("warnings", [])
    payload.setdefault("open_questions", [])
    payload.setdefault("monitoring_next_week", [])
    payload.setdefault("playbook_if_x_then_y", [])
    html = template.render(
        metadata=payload["metadata"],
        global_macro=payload.get("global_macro", {}),
        vietnam_liquidity=payload.get("vietnam_liquidity", {}),
        market_structure=payload.get("market_structure", {}),
        regime_engine=payload.get("regime_engine", {}),
        probability_allocation=payload.get("probability_allocation", {}),
        decision_layer=payload.get("decision_layer", {}),
        downtrend_v2=payload.get("downtrend_v2", {}),
        watchlist=payload.get("watchlist", {}),
        execution_monitoring=payload.get("execution_monitoring", {}),
        portfolio_health=payload.get("portfolio_health", {}),
        geo_layers=payload.get("geo_layers", {}),
        open_questions=payload.get("open_questions", []),
        monitoring_next_week=payload.get("monitoring_next_week", []),
        playbook_if_x_then_y=payload.get("playbook_if_x_then_y", []),
        base_css_path=base_css,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")


def _fallback_html(payload: Dict[str, Any]) -> str:
    """Minimal HTML if Jinja2 not installed."""
    meta = payload.get("metadata", {})
    asof = meta.get("asof_date", "N/A")
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>VN Weekly Report — {asof}</title></head>
<body><h1>VN Weekly Report</h1><p>As-of: {asof}</p><p>Data confidence: {meta.get('data_confidence', 'N/A')}</p>
<p>Install jinja2 for full template rendering: pip install jinja2</p>
<pre>{payload}</pre></body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Render weekly report JSON to HTML")
    ap.add_argument("--input", type=Path, default=DATA_PROCESSED / "weekly_report.json", help="Input JSON path")
    ap.add_argument("--out", type=Path, help="Output HTML path (default: reports/latest/index.html)")
    args = ap.parse_args()
    inp = args.input if args.input.is_absolute() else REPO / args.input
    if not inp.exists():
        print(f"Input not found: {inp}")
        return 1
    payload = read_json(inp)
    if not payload:
        print("Empty or invalid JSON")
        return 1
    asof = (payload.get("metadata") or {}).get("asof_date") or "unknown"
    REPORTS_LATEST.mkdir(parents=True, exist_ok=True)
    out_latest = args.out or (REPORTS_LATEST / "index.html")
    if not out_latest.is_absolute():
        out_latest = REPO / out_latest
    render_html(payload, out_latest)
    print(f"Wrote {out_latest}")
    archive_dir = REPORTS_ARCHIVE / str(asof).replace("/", "-")
    archive_dir.mkdir(parents=True, exist_ok=True)
    render_html(payload, archive_dir / "index.html")
    print(f"Wrote {archive_dir / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
