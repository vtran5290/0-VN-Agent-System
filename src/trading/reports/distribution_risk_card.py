"""Read-only Distribution Risk Lens card for Cloud Daily Report."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

REPO = Path(__file__).resolve().parents[3]
LATEST_JSON = REPO / "data" / "research" / "market_risk" / "distribution_risk_latest.json"
SAFETY_NOTE = "Distribution Risk Lens is market context only and does not change final_action."


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
        f"<table><tbody>{tbody}</tbody></table>",
        f'<p class="footnote">{SAFETY_NOTE}</p>',
    ]
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
    lines = [
        "### VNINDEX Distribution Risk Lens",
        f"- Primary view: **{data.get('primary_view', '—')}**",
        f"- VNINDEX raw: **{raw.get('warning_state', '—')}** "
        f"(dist 10/25/50: {raw.get('dist_count_10d')}/{raw.get('dist_count_25d')}/{raw.get('dist_count_50d')})",
        f"- ex-VIN proxy: **{ex.get('warning_state', '—')}** "
        f"(dist 10/25/50: {ex.get('dist_count_10d')}/{ex.get('dist_count_25d')}/{ex.get('dist_count_50d')})",
        f"- VIN distortion flag: **{vin.get('distortion_flag', False)}**",
        f"- VIN group warning: **{vin.get('warning_state', '—')}**",
        f"- {SAFETY_NOTE}",
    ]
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
    lines = [
        "\n## VNINDEX Distribution Risk Lens\n",
        "**FACTS** (market context only; does not change final_action)\n",
        render_distribution_risk_md(data).replace("### VNINDEX Distribution Risk Lens\n", "").strip(),
        "",
        f"**As-of (lens):** {data.get('as_of_date', '—')} · "
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
