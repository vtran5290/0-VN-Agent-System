"""Markdown + HTML operator reports for intraday preview scan."""
from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.trading.config import REPO_ROOT


def _df_to_md(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "_none_"
    try:
        return df.to_markdown(index=False)
    except Exception:
        return df.to_string(index=False)


def _load_holdings(cfg: Dict[str, Any]) -> List[str]:
    p = cfg.get("holdings_path")
    if not p:
        return []
    path = REPO_ROOT / str(p) if not Path(str(p)).is_absolute() else Path(str(p))
    if not path.exists():
        return []
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
        col = "symbol" if "symbol" in df.columns else df.columns[0]
        return df[col].astype(str).str.upper().tolist()
    return [ln.strip().upper() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _load_eod_scan_for_delta() -> Optional[pd.DataFrame]:
    p = REPO_ROOT / "data/research/portfolio_optimization/missing_work/phase36_daily_scan_sample.csv"
    if not p.exists():
        return None
    try:
        return pd.read_csv(p)
    except Exception:
        return None


def _session_phase_label(scan_df: pd.DataFrame, meta: Dict[str, Any]) -> str:
    phase = meta.get("session_phase")
    if phase is None and not scan_df.empty and "session_phase" in scan_df.columns:
        phase = scan_df["session_phase"].iloc[0]
    return str(phase) if phase is not None else "n/a"


def _action_counts(scan_df: pd.DataFrame, col: str) -> Dict[str, int]:
    if scan_df.empty or col not in scan_df.columns:
        return {}
    return scan_df[col].value_counts().to_dict()


def write_intraday_report(
    scan_df: pd.DataFrame,
    meta: Dict[str, Any],
    quotes_df: pd.DataFrame,
    cfg: Dict[str, Any],
    mode: str,
    ts: datetime,
    out_dir: Path,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = (cfg.get("modes") or {}).get(mode, {}).get("output_prefix", "phase36_intraday_scan")
    stamp = ts.strftime("%Y%m%d_%H%M")
    path = out_dir / f"{prefix}_{stamp}.md"
    latest_md = out_dir / "phase36_intraday_scan_latest.md"

    vn = meta.get("vnindex") or {}
    cap = meta.get("capability") or {}
    lines: List[str] = [
        f"# Intraday preview scan ({mode})\n\n",
        "> **PREVIEW ONLY** — `final_action=INTRADAY_PREVIEW`; orders require EOD `phase36_daily_scan_sample.csv`.\n\n",
        "## 0. Executive summary\n\n",
        f"| Field | Value |\n|-------|-------|\n",
        f"| Generated | {ts.isoformat()} |\n",
        f"| Mode | {mode} |\n",
        f"| Session | {_session_phase_label(scan_df, meta)} |\n",
        f"| Active setups | {len(scan_df)} |\n",
        f"| Manual-review candidates | {int(scan_df['intraday_candidate'].sum()) if not scan_df.empty and 'intraday_candidate' in scan_df.columns else 0} |\n",
        f"| Scan status | {meta.get('status', 'unknown')} |\n",
        f"| Quote coverage | {meta.get('intraday_quote_coverage_pct', 0):.1%} |\n",
        f"| `auto_order_allowed` | **False** (always) |\n\n",
    ]
    if meta.get("status") in ("SOURCE_UNAVAILABLE", "NO_VALID_QUOTES"):
        lines.append(
            f"> **{meta.get('status')}** — no valid intraday scan; do not use prior `*_latest` rows for decisions.\n\n"
        )

    lines.append("## A. Data integrity\n\n")
    lines.append(f"- **source:** FireAnt (`{cap.get('recommended_method', 'unknown')}`)\n")
    lines.append(f"- **capability available:** {cap.get('available')}\n")
    lines.append(f"- **equity panel EOD max date:** {meta.get('eod_panel_asof_date', meta.get('panel_asof', 'unknown'))}\n")
    lines.append(f"- **scan panel as-of (with intraday bars):** {meta.get('panel_asof', 'unknown')}\n")
    lines.append(f"- **quotes fetched:** {meta.get('quotes_fetched', 0)} / {len(meta.get('symbols_requested', []))}\n")
    lines.append(f"- **intraday_quote_coverage_pct:** {meta.get('intraday_quote_coverage_pct', 0):.1%}\n")
    if not quotes_df.empty:
        stale = quotes_df.loc[quotes_df["is_stale"] == True, "symbol"].tolist()
        missing = sorted(set(meta.get("symbols_requested", [])) - set(quotes_df["symbol"].astype(str)))
        lines.append(f"- **stale quote symbols:** {stale or 'none'}\n")
        lines.append(f"- **missing quotes:** {missing or 'none'}\n")
    lines.append("\n")

    lines.append("## A2. VNINDEX intraday overlay\n\n")
    lines.append(f"- **overlay applied:** {vn.get('vnindex_overlay_applied', False)}\n")
    lines.append(f"- **VNINDEX quote quality:** {vn.get('vnindex_quote_quality', 'n/a')}\n")
    lines.append(f"- **EOD VNINDEX as-of:** {vn.get('vnindex_eod_asof_date', 'n/a')} close={vn.get('vnindex_eod_close', 'n/a')}\n")
    lines.append(f"- **EOD regime_bull (last EOD bar):** {vn.get('vnindex_eod_regime_bull', 'n/a')}\n")
    lines.append(f"- **Intraday VNINDEX close (IF_CLOSE_NOW):** {vn.get('vnindex_intraday_close', 'n/a')}\n")
    lines.append(f"- **Intraday regime_bull:** {vn.get('vnindex_intraday_regime_bull', 'n/a')}\n")
    if vn.get("vnindex_regime_changed"):
        lines.append("- **WARNING:** VNINDEX regime flag **changed** vs EOD — review SKIP_VNINDEX_BEAR / NEW_T1 gates.\n")
    lines.append("\n")

    lines.append("## A3. Macro (live panel breadth)\n\n")
    lines.append(f"- **breadth_source:** {meta.get('breadth_source', 'unknown')}\n")
    lines.append(f"- **pct_cloud_bull_a3:** {meta.get('last_breadth', 0):.1%}\n")
    lines.append(f"- **pct_cloud_bull_s3:** {meta.get('last_s3_breadth', 0):.1%}\n")
    lines.append(f"- **breadth_zone:** {meta.get('breadth_zone', 'unknown')}\n")
    lines.append(f"- **regime_bull (post-VNINDEX overlay):** {meta.get('regime_bull', 'unknown')}\n")
    lines.append("\n")

    lines.append("## B. Intraday A3 preview (`would_be_final_action` = IF_CLOSE_NOW)\n\n")
    if scan_df.empty:
        lines.append("_No scan rows._\n\n")
    elif "would_be_final_action" not in scan_df.columns:
        lines.append("_No actionable preview columns in scan output._\n\n")
    else:
        counts = _action_counts(scan_df, "would_be_final_action")
        lines.append("**Counts:** " + ", ".join(f"`{k}`={v}" for k, v in sorted(counts.items())) + "\n\n")
        priority_actions = (
            "NEW_T1",
            "NEW_T1_MANUAL_REVIEW_BREADTH",
            "ADD_T2",
            "WAIT_PB",
            "TP1_PARTIAL",
            "TRAIL_EXIT",
            "MAX_HOLD_EXIT",
            "SKIP_VNINDEX_BEAR",
            "SKIP_LIQUIDITY",
        )
        for action in priority_actions:
            sub = scan_df[scan_df["would_be_final_action"] == action]
            if len(sub) == 0:
                continue
            lines.append(f"### would_be `{action}` ({len(sub)})\n\n")
            cols = [
                "symbol", "close_kVND", "a3_rank_score", "breadth_zone", "regime_bull",
                "intraday_action_status", "intraday_data_quality",
            ]
            cols = [c for c in cols if c in sub.columns]
            show = sub.sort_values("a3_rank_score", ascending=False) if "a3_rank_score" in sub.columns else sub
            lines.append(_df_to_md(show[cols].head(20)))
            lines.append("\n\n")

    lines.append("## B2. Delta vs last EOD scan (if any)\n\n")
    eod_scan = _load_eod_scan_for_delta()
    if eod_scan is None or scan_df.empty or "would_be_final_action" not in scan_df.columns:
        lines.append("_EOD scan file not available or intraday empty._\n\n")
    else:
        merged = scan_df[["symbol", "would_be_final_action", "final_action"]].merge(
            eod_scan[["symbol", "final_action"]].rename(columns={"final_action": "eod_final_action"}),
            on="symbol",
            how="inner",
        )
        changed = merged[merged["would_be_final_action"] != merged["eod_final_action"]]
        lines.append(f"- Symbols in both: **{len(merged)}**; action changed IF_CLOSE_NOW: **{len(changed)}**\n\n")
        if len(changed):
            lines.append(_df_to_md(changed.head(25)))
            lines.append("\n\n")

    lines.append("## C. S3 paper-shadow preview\n\n")
    lines.append("- **NO REAL CAPITAL** — `s3_no_real_order_flag` must remain True.\n")
    if not scan_df.empty and "s3_shadow_action" in scan_df.columns:
        s3 = scan_df[scan_df["s3_shadow_action"] == "PAPER_S3_SHADOW"]
        lines.append(f"- `PAPER_S3_SHADOW` count: **{len(s3)}**\n\n")

    lines.append("## D. Volume projection\n\n")
    lines.append("- Projected volume is **not** used for official ADV50.\n")
    if not scan_df.empty and "volume_is_projected" in scan_df.columns:
        proj = scan_df[scan_df["volume_is_projected"] == True]
        lines.append(f"- Rows with projected volume flag: **{len(proj)}**\n\n")

    lines.append("## E. Operator actions\n\n")
    lines.append("1. Confirm EOD scan after market close.\n")
    lines.append("2. Use this file only for **pre-lunch / pre-ATC planning**.\n")
    lines.append("3. Any `MANUAL_REVIEW_REQUIRED` row still needs human sign-off.\n\n")
    if not scan_df.empty and "a3_rank_score" in scan_df.columns:
        top = scan_df[scan_df["intraday_candidate"] == True].sort_values("a3_rank_score", ascending=False).head(15)
        if len(top):
            lines.append("### Top manual-review (by `a3_rank_score`)\n\n")
            cols = ["symbol", "would_be_final_action", "a3_rank_score", "close_kVND", "intraday_action_status"]
            cols = [c for c in cols if c in top.columns]
            lines.append(_df_to_md(top[cols]))
            lines.append("\n")

    holdings = _load_holdings(cfg)
    lines.append("## F. Risk warnings\n\n")
    if holdings and not scan_df.empty and "would_be_final_action" in scan_df.columns:
        held = scan_df[scan_df["symbol"].isin(holdings)]
        new_in_held = held[held["would_be_final_action"].isin(["NEW_T1", "NEW_T1_MANUAL_REVIEW_BREADTH"])]
        lines.append(f"- **Holdings overlap:** {len(held)} held symbols in scan; "
                     f"{len(new_in_held)} would_be new T1 on holdings.\n")
    lines.append("- Intraday quotes may lag exchange tape (partial daily bar).\n")
    lines.append("- Do not confuse `would_be_final_action` with `final_action`.\n")
    lines.append("- VNINDEX/breadth use provisional closes on quoted universe + VNINDEX overlay.\n")

    text = "".join(lines)
    path.write_text(text, encoding="utf-8")
    latest_md.write_text(text, encoding="utf-8")
    write_intraday_html_dashboard(scan_df, meta, ts, mode, out_dir)
    return path


def write_intraday_html_dashboard(
    scan_df: pd.DataFrame,
    meta: Dict[str, Any],
    ts: datetime,
    mode: str,
    out_dir: Path,
) -> Path:
    """Simple static HTML dashboard (no JS deps)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    latest = out_dir / "phase36_intraday_scan_latest.html"
    vn = meta.get("vnindex") or {}

    def esc(x: Any) -> str:
        return html.escape(str(x if x is not None else ""))

    phase = meta.get("session_phase", "")
    n_candidates = (
        int(scan_df["intraday_candidate"].sum())
        if not scan_df.empty and "intraday_candidate" in scan_df.columns
        else 0
    )
    show_top = (
        phase not in ("CLOSED", "LUNCH_BREAK")
        and n_candidates > 0
        and meta.get("status") not in ("SOURCE_UNAVAILABLE", "NO_VALID_QUOTES")
    )
    rows_html = ""
    if show_top:
        cols = ["symbol", "would_be_final_action", "a3_rank_score", "close_kVND", "intraday_action_status", "breadth_zone"]
        cols = [c for c in cols if c in scan_df.columns]
        show = scan_df[scan_df["intraday_candidate"] == True].sort_values(
            "a3_rank_score", ascending=False
        ).head(40)
        header = "".join(f"<th>{esc(c)}</th>" for c in cols)
        body = ""
        for _, r in show.iterrows():
            body += "<tr>" + "".join(f"<td>{esc(r[c])}</td>" for c in cols) + "</tr>"
        rows_html = f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"
    else:
        rows_html = "<p>No manual-review candidates</p>"

    doc = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<title>Intraday preview {esc(mode)}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 1.5rem; background: #0f1419; color: #e7ecf3; }}
.warn {{ background: #3d2a00; border: 1px solid #c9a227; padding: 0.75rem; border-radius: 6px; }}
.card {{ background: #1a2332; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
table {{ border-collapse: collapse; width: 100%; font-size: 0.9rem; }}
th, td {{ border: 1px solid #334; padding: 0.35rem 0.5rem; text-align: left; }}
th {{ background: #243044; }}
.tag {{ color: #8ab4f8; }}
</style></head><body>
<h1>Phase36 intraday preview <span class="tag">({esc(mode)})</span></h1>
<div class="warn"><strong>PREVIEW ONLY</strong> — auto_order_allowed=False. OMS uses EOD scan only.</motion.div>
<div class="card">
<h2>Macro</h2>
<ul>
<li>status: <strong>{esc(meta.get('status'))}</strong></li>
<li>VNINDEX intraday close: <strong>{esc(vn.get('vnindex_intraday_close'))}</strong>
  (EOD {esc(vn.get('vnindex_eod_close'))})</li>
<li>regime_bull intraday: <strong>{esc(vn.get('vnindex_intraday_regime_bull'))}</strong>
  (EOD {esc(vn.get('vnindex_eod_regime_bull'))})</li>
<li>breadth A3: <strong>{meta.get('last_breadth', 0):.1%}</strong> zone=<strong>{esc(meta.get('breadth_zone'))}</strong></li>
<li>breadth source: {esc(meta.get('breadth_source'))}</li>
<li>quote coverage: {meta.get('intraday_quote_coverage_pct', 0):.1%}</li>
<li>session: {esc(meta.get('session_phase'))}</li>
<li>generated: {esc(ts.isoformat())}</li>
</ul>
</motion.div>
<div class="card">
<h2>Top candidates</h2>
{rows_html or '<p>No rows</p>'}
</div>
</body></html>"""
    # fix typo </motion.div> -> </motion.div> should be </motion.div> - I used wrong tag
    doc = doc.replace("</motion.div>", "</div>")
    latest.write_text(doc, encoding="utf-8")
    return latest
