"""Read-only Distribution Risk Lens card for Cloud Daily Report."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

REPO = Path(__file__).resolve().parents[3]
OUT_DIR = REPO / "data" / "research" / "market_risk"
LATEST_JSON = OUT_DIR / "distribution_risk_latest.json"
LATEST_HTML = OUT_DIR / "distribution_risk_latest.html"
LATEST_MD = OUT_DIR / "distribution_risk_latest.md"
SAFETY_NOTE = "Distribution Risk Lens is market context only and does not change final_action."
EX_VIN_PROXY_DISCLOSURE = (
    "ex-VIN proxy is derived and is NOT a native exchange index."
)
STALE_NEEDS_REVIEW_MSG = (
    "NEEDS_REVIEW: stale index view; probabilities may be caveated."
)
STALE_NEEDS_REVIEW_MD = STALE_NEEDS_REVIEW_MSG
STALE_NEEDS_REVIEW_HTML = (
    '<div class="warn-banner"><strong>NEEDS_REVIEW:</strong> stale index view; '
    "probabilities may be caveated.</div>"
)
LEGACY_DIST_SESSION_WARNING = (
    "LEGACY: use python -m src.trading.cli distribution-risk for canonical distribution risk. "
    "dist_session_* outputs are not SSOT."
)


def lens_needs_stale_review(data: dict[str, Any]) -> bool:
    """True when report_status=NEEDS_REVIEW or any view_freshness row is stale."""
    if data.get("report_status") == "NEEDS_REVIEW":
        return True
    rows = data.get("view_freshness") or []
    return any(bool(v.get("is_stale_for_as_of")) for v in rows)


def stale_needs_review_banner_html() -> str:
    return STALE_NEEDS_REVIEW_HTML


def stale_needs_review_line_md() -> str:
    return STALE_NEEDS_REVIEW_MD


def refresh_distribution_risk_for_reports(
    *,
    start: str = "2012-01-01",
    as_of: str | None = None,
) -> list[str]:
    """Regenerate distribution_risk_latest.json before daily reports (context only)."""
    from src.market.distribution_risk_lens.pipeline import run_distribution_risk_lens

    result = run_distribution_risk_lens(start=start, as_of=as_of)
    return list(result.get("warnings") or [])


def load_distribution_risk_latest(path: Optional[Path] = None) -> tuple[Optional[dict[str, Any]], list[str]]:
    p = path or LATEST_JSON
    if not p.is_file():
        return None, [f"distribution_risk_latest.json missing: {p}"]
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None, []
    except (json.JSONDecodeError, OSError) as exc:
        return None, [f"failed to read distribution risk JSON: {exc}"]


def render_view_freshness_html(data: dict[str, Any]) -> str:
    rows = data.get("view_freshness") or []
    if not rows:
        return ""
    trs = "".join(
        f"<tr><td>{v.get('index_view','—')}</td>"
        f"<td>{v.get('last_data_date','—')}</td>"
        f"<td>{v.get('requested_as_of_date','—')}</td>"
        f"<td>{'YES' if v.get('is_stale_for_as_of') else 'no'}</td></tr>"
        for v in rows
    )
    stale_banner = ""
    if any(v.get("is_stale_for_as_of") for v in rows):
        stale_banner = f'<p class="footnote">{STALE_NEEDS_REVIEW_MD}</p>'
    return (
        '<div class="subsection-title">Index view freshness</div>'
        "<table><thead><tr><th>View</th><th>Last data date</th>"
        "<th>Requested as-of</th><th>Stale</th></tr></thead>"
        f"<tbody>{trs}</tbody></table>{stale_banner}"
    )


def render_v13_breadth_staleness_md(data: dict[str, Any]) -> str:
    """Read-only v1.3 breadth staleness metadata (no probabilities or forecasts)."""
    v13 = data.get("v13_research") or {}
    if not v13.get("enabled"):
        return ""
    status = v13.get("breadth_status")
    if not status:
        return ""
    lines = [
        "#### v1.3 breadth staleness (read-only)",
        f"- Breadth status: **{status}**",
        f"- Breadth as-of: **{v13.get('breadth_as_of', '—')}**",
        f"- Index as-of: **{v13.get('index_as_of', '—')}**",
    ]
    lag = v13.get("breadth_lag_sessions")
    if lag is not None:
        lines.append(f"- Breadth lag (sessions): **{lag}**")
    lines.append(
        "- _Research context only; not used for final_action, OMS, A3/S3, or position sizing._"
    )
    return "\n".join(lines) + "\n"


def render_v13_breadth_staleness_html(data: dict[str, Any]) -> str:
    v13 = data.get("v13_research") or {}
    if not v13.get("enabled") or not v13.get("breadth_status"):
        return ""
    lag = v13.get("breadth_lag_sessions")
    lag_cell = f"<tr><th>Breadth lag (sessions)</th><td>{lag}</td></tr>" if lag is not None else ""
    return (
        '<div class="subsection-title">v1.3 breadth staleness (read-only)</div>'
        "<table><tbody>"
        f"<tr><th>Breadth status</th><td>{v13.get('breadth_status', '—')}</td></tr>"
        f"<tr><th>Breadth as-of</th><td>{v13.get('breadth_as_of', '—')}</td></tr>"
        f"<tr><th>Index as-of</th><td>{v13.get('index_as_of', '—')}</td></tr>"
        f"{lag_cell}"
        "</tbody></table>"
        '<p class="footnote">Research context only; not used for final_action, OMS, A3/S3, or sizing.</p>'
    )


def render_view_freshness_md(data: dict[str, Any]) -> str:
    rows = data.get("view_freshness") or []
    if not rows:
        return ""
    lines = [
        "#### Index view freshness",
        "| View | Last data date | Requested as-of | Stale |",
        "| --- | --- | --- | --- |",
    ]
    for v in rows:
        stale = "YES" if v.get("is_stale_for_as_of") else "no"
        lines.append(
            f"| {v.get('index_view', '—')} | {v.get('last_data_date', '—')} | "
            f"{v.get('requested_as_of_date', '—')} | {stale} |"
        )
    if any(v.get("is_stale_for_as_of") for v in rows):
        lines.append(f"\n{STALE_NEEDS_REVIEW_MD}")
    return "\n".join(lines) + "\n"


def render_distribution_risk_html(data: dict[str, Any]) -> str:
    primary = data.get("primary_view", "ex_vin_proxy")
    raw = data.get("vnindex_raw") or {}
    ex = data.get("ex_vin_proxy") or {}
    vin = data.get("vin_group") or {}
    cmp_ = data.get("comparison") or {}
    rows = [
        ("Primary view", str(primary)),
        ("VNINDEX raw warning", str(raw.get("warning_state", "—"))),
        ("ex-VIN proxy warning", str(ex.get("warning_state", "—"))),
        (
            "Raw dist 10d / 25d / 50d",
            f"{raw.get('dist_count_10d', '—')} / {raw.get('dist_count_25d', '—')} / {raw.get('dist_count_50d', '—')}",
        ),
        (
            "ex-VIN dist 10d / 25d / 50d",
            f"{ex.get('dist_count_10d', '—')} / {ex.get('dist_count_25d', '—')} / {ex.get('dist_count_50d', '—')}",
        ),
        ("VIN basket warning", str(vin.get("warning_state", "—"))),
        ("VIN distortion flag", str(vin.get("distortion_flag", False))),
        ("Raw vs ex-VIN disagreement", str(cmp_.get("raw_vs_ex_vin_warning_disagreement", False))),
    ]
    ex_probs = ex.get("probabilities") or {}
    if ex_probs:
        rows.append(("P(25D return < 0)", _fmt_with_base(ex_probs, "p_ret_neg_25d")))
        rows.append(("P(-5% correction within 25D)", _fmt_with_base(ex_probs, "p_correction_5pct_25d")))
        rows.append(("P(-10% correction within 75D)", _fmt_with_base(ex_probs, "p_correction_10pct_75d")))
        rows.append(
            (
                "Confidence / sample",
                f"{ex_probs.get('confidence', '—')} / {ex_probs.get('sample_size', '—')}",
            )
        )
    tbody = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows)
    html = [
        '<div class="subsection-title">VNINDEX Distribution Risk Lens</div>',
        render_view_freshness_html(data),
        render_v13_breadth_staleness_html(data),
        f"<table><tbody>{tbody}</tbody></table>",
        f'<p class="footnote">{SAFETY_NOTE}</p>',
    ]
    if lens_needs_stale_review(data) or any(
        w.startswith("PRIMARY_VIEW_STALE") for w in (data.get("load_warnings") or [])
    ):
        html.insert(1, STALE_NEEDS_REVIEW_HTML)
    if ex.get("is_proxy"):
        html.append(f'<p class="footnote"><strong>{EX_VIN_PROXY_DISCLOSURE}</strong></p>')
        if ex.get("note"):
            html.append(f'<p class="footnote">{ex["note"]}</p>')
    if vin.get("distortion_flag"):
        html.append(
            '<p class="footnote">VIN distortion: cap-weight VNINDEX may diverge from ex-VIN proxy — '
            "prefer ex-VIN view for broad participation.</p>"
        )
    ex_note = ex.get("methodology_note")
    if ex_note:
        html.append(f'<p class="footnote">{ex_note}</p>')
    vin_note = vin.get("note")
    if vin_note and vin.get("warning_state") == "UNKNOWN":
        html.append(f'<p class="footnote">{vin_note}</p>')
    return "".join(html)


def render_distribution_risk_md(data: dict[str, Any]) -> str:
    raw = data.get("vnindex_raw") or {}
    ex = data.get("ex_vin_proxy") or {}
    vin = data.get("vin_group") or {}
    freshness_block = render_view_freshness_md(data)
    lines = [
        "### VNINDEX Distribution Risk Lens",
        f"- Primary view: **{data.get('primary_view', '—')}**",
        f"- Lens report status: **{data.get('report_status', '—')}**",
    ]
    if freshness_block.strip():
        lines.append(freshness_block.rstrip())
    v13_block = render_v13_breadth_staleness_md(data)
    if v13_block.strip():
        lines.append(v13_block.rstrip())
    lines.extend([
        f"- VNINDEX raw: **{raw.get('warning_state', '—')}** "
        f"(dist 10/25/50: {raw.get('dist_count_10d')}/{raw.get('dist_count_25d')}/{raw.get('dist_count_50d')})",
        f"- ex-VIN proxy: **{ex.get('warning_state', '—')}** "
        f"(dist 10/25/50: {ex.get('dist_count_10d')}/{ex.get('dist_count_25d')}/{ex.get('dist_count_50d')})",
        f"- VIN distortion flag: **{vin.get('distortion_flag', False)}**",
        f"- VIN group warning: **{vin.get('warning_state', '—')}**",
        f"- {SAFETY_NOTE}",
    ])
    if ex.get("is_proxy"):
        lines.append(f"- **{EX_VIN_PROXY_DISCLOSURE}**")
        if ex.get("note"):
            lines.append(f"- _{ex['note']}_")
    if ex.get("methodology_note"):
        lines.append(f"- _{ex['methodology_note']}_")
    if vin.get("note") and vin.get("warning_state") == "UNKNOWN":
        lines.append(f"- _{vin['note']}_")
    ex_probs = ex.get("probabilities") or {}
    if ex_probs.get("p_ret_neg_25d") is not None:
        lines.append(f"- P(25D return < 0) ex-VIN: **{_fmt_with_base(ex_probs, 'p_ret_neg_25d')}**")
    if ex_probs.get("p_correction_5pct_25d") is not None:
        lines.append(
            f"- P(-5% correction within 25D) ex-VIN: **{_fmt_with_base(ex_probs, 'p_correction_5pct_25d')}**"
        )
    if ex_probs.get("p_correction_10pct_75d") is not None:
        lines.append(
            f"- P(-10% correction within 75D) ex-VIN: **{_fmt_with_base(ex_probs, 'p_correction_10pct_75d')}**"
        )
    cmp_ = data.get("comparison") or {}
    if cmp_.get("interpretation"):
        lines.append(f"- Comparison: {cmp_['interpretation']}")
    return "\n".join(lines) + "\n"


def build_distribution_risk_standalone_html(data: dict[str, Any]) -> str:
    """Full HTML page for distribution_risk_latest (no external assets)."""
    import html as html_mod

    from src.trading.reports.cloud_daily_report import CSS

    as_of = data.get("requested_as_of_date") or data.get("as_of_date") or "—"
    status = data.get("report_status", "—")
    method = data.get("method_version", "—")
    esc = html_mod.escape
    body = render_distribution_risk_html(data)
    cmp_ = data.get("comparison") or {}
    interp = cmp_.get("interpretation")
    interp_block = (
        f'<p class="footnote"><strong>Comparison:</strong> {esc(str(interp))}</p>'
        if interp
        else ""
    )
    warns = data.get("load_warnings") or []
    warn_block = ""
    if lens_needs_stale_review(data):
        warn_block = STALE_NEEDS_REVIEW_HTML
    if warns:
        items = "".join(f"<li>{esc(str(w))}</li>" for w in warns)
        warn_block += f'<div class="warn-banner"><ul class="action-list">{items}</ul></div>'
    return (
        f"<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>VNINDEX Distribution Risk — {esc(str(as_of))}</title>"
        f"<style>{CSS}</style></head><body><div class='container'>"
        f"<div class='card'><div class='section-title'>VNINDEX Distribution Risk Lens</div>"
        f"<p class='meta'>As-of: <strong>{esc(str(as_of))}</strong> · "
        f"Status: <strong>{esc(str(status))}</strong> · Method: {esc(str(method))}</p>"
        f"{warn_block}{body}{interp_block}</div></div></body></html>"
    )


def build_distribution_risk_standalone_md(data: dict[str, Any]) -> str:
    """Standalone markdown mirror of the lens card."""
    as_of = data.get("requested_as_of_date") or data.get("as_of_date") or "—"
    lines = [
        f"# VNINDEX Distribution Risk Lens — {as_of}",
        "",
        f"- Report status: **{data.get('report_status', '—')}**",
        f"- Method: `{data.get('method_version', '—')}`",
        "",
        render_distribution_risk_md(data).strip(),
        "",
    ]
    if lens_needs_stale_review(data):
        lines.append(f"- {STALE_NEEDS_REVIEW_MD}")
    for w in data.get("load_warnings") or []:
        lines.append(f"- WARN: {w}")
    lines.append(f"- {SAFETY_NOTE}")
    lines.append(
        "- Distribution Risk SSOT: `data/research/market_risk/distribution_risk_latest.json`"
    )
    return "\n".join(lines) + "\n"


def write_distribution_risk_latest_artifacts(data: dict[str, Any]) -> dict[str, str]:
    """Write HTML + MD alongside distribution_risk_latest.json."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html_path = LATEST_HTML
    md_path = LATEST_MD
    html_path.write_text(build_distribution_risk_standalone_html(data), encoding="utf-8")
    md_path.write_text(build_distribution_risk_standalone_md(data), encoding="utf-8")
    return {"html": str(html_path), "md": str(md_path)}


def build_distribution_risk_section_for_daily_scan(
    *,
    as_of: str | None = None,
    refresh: bool = True,
) -> tuple[str, list[str]]:
    """Markdown section for daily_scan.md; optionally refreshes SSOT JSON first."""
    warnings: list[str] = []
    if refresh:
        try:
            warnings.extend(refresh_distribution_risk_for_reports(as_of=as_of))
        except Exception as exc:
            return (
                "\n## VNINDEX Distribution Risk Lens\n\n"
                f"**WARN:** refresh failed: {exc}\n\n"
                f"_{SAFETY_NOTE}_\n",
                warnings + [str(exc)],
            )
    data, load_warns = load_distribution_risk_latest()
    warnings.extend(load_warns)
    if not data:
        return (
            "\n## VNINDEX Distribution Risk Lens\n\n"
            "_distribution_risk_latest.json missing — run distribution-risk CLI._\n\n"
            f"_{SAFETY_NOTE}_\n",
            warnings,
        )
    stale_note = ""
    if lens_needs_stale_review(data):
        stale_note = f"\n{STALE_NEEDS_REVIEW_MD}\n"
    lines = [
        "\n## VNINDEX Distribution Risk Lens\n",
        "**FACTS** (market context only; does not change final_action)\n",
        stale_note,
        render_distribution_risk_md(data).replace("### VNINDEX Distribution Risk Lens\n", "").strip(),
        "",
        f"**Requested as-of:** {data.get('requested_as_of_date', data.get('as_of_date', '—'))} · "
        f"**method:** {data.get('method_version', '—')}",
        "",
        f"_{SAFETY_NOTE}_\n",
    ]
    return "\n".join(lines), warnings


_PROB_TO_BASE_KEY = {
    "p_ret_neg_5d": "p_ret_neg_5d",
    "p_ret_neg_10d": "p_ret_neg_10d",
    "p_ret_neg_25d": "p_ret_neg_25d",
    "p_ret_neg_75d": "p_ret_neg_75d",
    "p_ret_neg_100d": "p_ret_neg_100d",
    "p_correction_5pct_25d": "p_correction_5pct_25d",
    "p_correction_10pct_75d": "p_correction_10pct_75d",
}


def _fmt_with_base(probs: dict, key: str) -> str:
    val = probs.get(key)
    if val is None:
        return "—"
    base_rates = probs.get("base_rates") or {}
    base = base_rates.get(_PROB_TO_BASE_KEY.get(key, ""))
    if base is not None:
        return f"{float(val):.1%} (base {float(base):.1%})"
    return f"{float(val):.1%}"
