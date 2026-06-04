"""RS C3 (RS line acceleration) display card — review-ranking context only.

RESEARCH ONLY — context lens. Does not set or override final_action.
Classification: REVIEW_RANKING_ONLY (v2, 2026-05-26)
OOS1/OOS2 IC significant (t>5). OOS3 2024+ IC near zero — display only.
"""
from __future__ import annotations

import html as _html
from pathlib import Path
from typing import Any, Optional

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
RS_PARQUET = REPO / "data" / "research" / "rs_rating" / "rs_rating_daily.parquet"
SCAN_DIR = REPO / "data/research/portfolio_optimization/missing_work"
SAFETY_NOTE = (
    "RS C3 is review-ranking context only and does not set or override final_action. "
    "IC near zero in OOS3 2024+. Use as sort/prioritization display only."
)
_MARKET_OFF_DATE = pd.Timestamp("2024-01-01")

_C3_TABLE_HEADERS = [
    "Symbol",
    "C3 Rating",
    "C3 Zone",
    "#Top50",
    "T2 Context",
    "Late Chase",
    "final_action",
    "EMA dist%",
]

# T2/add-on final_action values — T2 Context column is only shown for these rows
_T2_ACTIONS = frozenset({
    "T2",
    "ADD_T2",
    "NO_T2_BREADTH",
    "T2_BLOCKED",
    "T2_MANUAL_REVIEW",
    "REVIEW_ADD_T2",
    "HOLD_T2",
})


def _bucket(rating: Any) -> str:
    try:
        r = float(rating)
    except (TypeError, ValueError):
        return "UNKNOWN"
    if pd.isna(r):
        return "UNKNOWN"
    if r >= 90:
        return "EXTREME_RS"
    if r >= 70:
        return "LEADER_ZONE"
    if r >= 50:
        return "NEUTRAL"
    return "WEAK_RS"


def _fmt_pct(v: Any) -> str:
    """Format a value that is already stored as a percent (e.g. 2.12 → '+2.12%')."""
    if v is None:
        return "—"
    try:
        f = float(v)
        if pd.isna(f):
            return "—"
        return f"{f:+.2f}%"
    except (TypeError, ValueError):
        return str(v)


def _fmt_rating(v: Any) -> str:
    if v is None:
        return "—"
    try:
        f = float(v)
        if pd.isna(f):
            return "—"
        return f"{f:.0f}"
    except (TypeError, ValueError):
        return str(v)


def _fmt_rank(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"#{int(v)}"
    except (TypeError, ValueError):
        return "—"


def load_rs_c3_for_date(
    scan_date: Optional[str] = None,
    *,
    symbols: Optional[list[str]] = None,
) -> tuple[Optional[pd.DataFrame], list[str]]:
    """Load C3 ratings from rs_rating_daily.parquet for the nearest available date.

    Returns (DataFrame[date, symbol, rs_c3_rating, _rating_date], warnings).
    """
    warnings: list[str] = []
    if not RS_PARQUET.is_file():
        return None, [f"rs_rating_daily.parquet missing: {RS_PARQUET}"]

    try:
        df = pd.read_parquet(RS_PARQUET, columns=["date", "symbol", "rs_C3"])
    except Exception as exc:
        return None, [f"failed to read RS parquet: {exc}"]

    df["date"] = pd.to_datetime(df["date"])
    df = df.rename(columns={"rs_C3": "rs_c3_rating"})

    if scan_date:
        target = pd.Timestamp(scan_date)
        available = df["date"].drop_duplicates().sort_values()
        past = available[available <= target]
        if past.empty:
            return None, [f"no RS C3 data on or before {scan_date}"]
        use_date = past.iloc[-1]
        if use_date.date() < target.date():
            warnings.append(
                f"RS C3 using {use_date.date()} (nearest available before {scan_date})"
            )
    else:
        use_date = df["date"].max()

    out = df[df["date"] == use_date].dropna(subset=["rs_c3_rating"]).copy()
    out["_rating_date"] = str(use_date.date())

    if symbols:
        want = {s.upper() for s in symbols}
        out = out[out["symbol"].str.upper().isin(want)]

    return out.reset_index(drop=True), warnings


def _load_latest_scan_df() -> Optional[pd.DataFrame]:
    """Load the latest Phase36 scan CSV (best-effort; returns None if missing)."""
    candidates = [
        SCAN_DIR / "phase36_daily_scan_latest.csv",
        SCAN_DIR / "phase36_daily_scan_sample.csv",
        SCAN_DIR / "phase35_daily_scan_sample.csv",
    ]
    for p in candidates:
        if p.is_file():
            try:
                return pd.read_csv(p)
            except Exception:
                continue
    return None


def compute_c3_fields(
    c3_df: pd.DataFrame,
    scan_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Merge C3 ratings with scan context; compute derived display fields."""
    out = c3_df.copy()
    out["rs_c3_bucket"] = out["rs_c3_rating"].apply(_bucket)

    # Crosswalk final_action FIRST — T2 context depends on it
    out["final_action"] = "—"
    out["_ema_dist_fmt"] = None
    if scan_df is not None and not scan_df.empty:
        if "final_action" in scan_df.columns:
            fa_map = scan_df.set_index("symbol")["final_action"].to_dict()
            out["final_action"] = out["symbol"].map(fa_map).fillna("—")
        if "a3_ema_dist_pct" in scan_df.columns:
            dist_map = scan_df.set_index("symbol")["a3_ema_dist_pct"].to_dict()
            out["_ema_dist_fmt"] = out["symbol"].map(dist_map)

    # T2 context: only true when row is a T2/add-on action AND C3 >= 70
    out["rs_c3_t2_context"] = (
        out["final_action"].isin(_T2_ACTIONS) & (out["rs_c3_rating"] >= 70)
    )

    # Top-50 rank via adv50_B_VND from scan_df
    out["rs_c3_rank_in_top50"] = None
    if scan_df is not None and not scan_df.empty and "adv50_B_VND" in scan_df.columns:
        adv_top50 = scan_df.nlargest(50, "adv50_B_VND")
        top50_syms = set(adv_top50["symbol"].str.upper().tolist())
        top50_sub = out[out["symbol"].str.upper().isin(top50_syms)].copy()
        top50_sub = top50_sub.sort_values("rs_c3_rating", ascending=False).reset_index(drop=True)
        rank_map = {row["symbol"]: i + 1 for i, row in top50_sub.iterrows()}
        out["rs_c3_rank_in_top50"] = out["symbol"].map(rank_map)

    # Late-chase warning: C3>=90 AND a3_ema_dist_pct > 10 (column stores %, e.g. 10.5 = 10.5%)
    out["rs_c3_late_chase_warning"] = False
    if scan_df is not None and not scan_df.empty and "a3_ema_dist_pct" in scan_df.columns:
        ext_map = scan_df.set_index("symbol")["a3_ema_dist_pct"].to_dict()
        ema_dist = out["symbol"].map(ext_map).fillna(0.0)
        out["rs_c3_late_chase_warning"] = (out["rs_c3_rating"] >= 90) & (ema_dist > 10.0)

    # Market-off flag: date >= 2024-01-01 (OOS3 regime, IC near zero)
    rating_date_str = out["_rating_date"].iloc[0] if len(out) > 0 else "2000-01-01"
    market_off = pd.Timestamp(rating_date_str) >= _MARKET_OFF_DATE
    out["rs_c3_market_off"] = market_off

    return out


def _rows_from_df(c3_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert enriched DataFrame to records, dropping internal columns."""
    drop_cols = ["_rating_date", "date"]
    return c3_df.drop(columns=[c for c in drop_cols if c in c3_df.columns]).to_dict(
        orient="records"
    )


def _row_to_md_cells(r: dict[str, Any]) -> list[str]:
    late = "WARN" if r.get("rs_c3_late_chase_warning") else "—"
    t2ctx = "Y" if r.get("rs_c3_t2_context") else "—"
    return [
        str(r.get("symbol", "—")),
        _fmt_rating(r.get("rs_c3_rating")),
        str(r.get("rs_c3_bucket", "—")),
        _fmt_rank(r.get("rs_c3_rank_in_top50")),
        t2ctx,
        late,
        str(r.get("final_action", "—")),
        _fmt_pct(r.get("_ema_dist_fmt")),
    ]


def render_rs_c3_md(
    c3_rows: list[dict[str, Any]],
    *,
    max_rows: int = 15,
    market_off: bool = False,
    rating_date: Optional[str] = None,
    include_title: bool = True,
) -> str:
    lines: list[str] = []
    if include_title:
        lines.extend(["### RS C3 Context (RS line acceleration)", ""])
    if market_off:
        lines.append(
            "> **OOS3 regime active:** C3 IC near zero in 2024+. "
            "Use as sort/display only — hard filter not operative.\n"
        )
    if rating_date:
        lines.append(f"_Data as of: {rating_date}_\n")
    lines.extend([
        "| " + " | ".join(_C3_TABLE_HEADERS) + " |",
        "| " + " | ".join(["---"] * len(_C3_TABLE_HEADERS)) + " |",
    ])
    for r in c3_rows[:max_rows]:
        lines.append("| " + " | ".join(_row_to_md_cells(r)) + " |")
    lines.extend(["", f"_{SAFETY_NOTE}_", ""])
    return "\n".join(lines)


def render_rs_c3_html(
    c3_rows: list[dict[str, Any]],
    *,
    market_off: bool = False,
    rating_date: Optional[str] = None,
    max_rows: int = 20,
) -> str:
    esc = _html.escape
    parts: list[str] = [
        '<div class="subsection-title">RS C3 Context '
        '<span class="ctx-tag">REVIEW RANKING ONLY</span></div>'
    ]
    if market_off:
        parts.append(
            '<div class="ctx-safety">OOS3 2024+ regime — C3 IC near zero. '
            "Use as sort/display only. Hard filter not operative in current environment.</div>"
        )
    if rating_date:
        parts.append(f'<p class="meta">Data as of: {esc(str(rating_date))}</p>')

    th = "".join(f"<th>{esc(h)}</th>" for h in _C3_TABLE_HEADERS)
    tbody = ""
    for r in c3_rows[:max_rows]:
        bucket = str(r.get("rs_c3_bucket", "—"))
        late = bool(r.get("rs_c3_late_chase_warning"))
        t2ctx = bool(r.get("rs_c3_t2_context"))
        if bucket == "EXTREME_RS":
            # Amber — not automatically bullish; late-chase risk zone
            bkt_style = "color:#f0a030;font-weight:bold"
        elif bucket == "LEADER_ZONE":
            # Green — constructive sweet spot (70–89)
            bkt_style = "color:#5edd5e;"
        elif bucket == "NEUTRAL":
            bkt_style = "color:#7a8399;"
        else:
            # WEAK_RS / UNKNOWN — muted
            bkt_style = "color:#4a5168;"
        late_cell = "<span style='color:#f77;font-weight:bold'>WARN</span>" if late else "—"
        t2_cell = "<span style='color:#5edd5e;'>Y</span>" if t2ctx else "—"
        cells_html = "".join([
            f"<td>{esc(str(r.get('symbol', '—')))}</td>",
            f"<td style='text-align:right'>{_fmt_rating(r.get('rs_c3_rating'))}</td>",
            f"<td style='{bkt_style}'>{esc(bucket)}</td>",
            f"<td>{esc(_fmt_rank(r.get('rs_c3_rank_in_top50')))}</td>",
            f"<td>{t2_cell}</td>",
            f"<td>{late_cell}</td>",
            f"<td>{esc(str(r.get('final_action', '—')))}</td>",
            f"<td style='text-align:right'>{esc(_fmt_pct(r.get('_ema_dist_fmt')))}</td>",
        ])
        tbody += f"<tr>{cells_html}</tr>"

    parts.append(
        '<div class="scroll-table">'
        f"<table><thead><tr>{th}</tr></thead><tbody>{tbody}</tbody></table>"
        "</div>"
    )
    parts.append(f'<div class="ctx-safety">{esc(SAFETY_NOTE)}</div>')
    return "".join(parts)


def build_rs_c3_section_for_daily_scan(
    *,
    scan_date: Optional[str] = None,
    scan_df: Optional[pd.DataFrame] = None,
    max_rows: int = 15,
) -> tuple[str, list[str]]:
    """Build RS C3 compact section for daily_scan.md. Returns (markdown, warnings)."""
    symbols = scan_df["symbol"].tolist() if scan_df is not None and not scan_df.empty else None
    c3_df, warns = load_rs_c3_for_date(scan_date, symbols=symbols)

    if c3_df is None or c3_df.empty:
        return (
            "\n## RS C3 Context (RS line acceleration)\n\n"
            "_RS C3 data unavailable — run scripts/research/rs_rating_research.py._\n\n"
            f"_{SAFETY_NOTE}_\n",
            warns,
        )

    c3_df = compute_c3_fields(c3_df, scan_df=scan_df)
    market_off = bool(c3_df["rs_c3_market_off"].iloc[0])
    rating_date = str(c3_df["_rating_date"].iloc[0])

    c3_df = c3_df.sort_values(
        ["rs_c3_late_chase_warning", "rs_c3_rating"], ascending=[False, False]
    )
    rows = _rows_from_df(c3_df)

    md = (
        "\n## RS C3 Context (RS line acceleration)\n\n"
        "**FACTS** (context only; does not change final_action)\n\n"
        + render_rs_c3_md(
            rows,
            max_rows=max_rows,
            market_off=market_off,
            rating_date=rating_date,
            include_title=False,
        )
        + f"\n**SSOT:** `data/research/rs_rating/rs_rating_daily.parquet`"
        f" · **classification:** REVIEW_RANKING_ONLY\n"
    )
    return md, warns


def build_rs_c3_section_for_cloud_daily(
    *,
    scan_date: Optional[str] = None,
    scan_df: Optional[pd.DataFrame] = None,
    holdings: Optional[list[str]] = None,
) -> tuple[Optional[str], list[str]]:
    """Build RS C3 HTML block for cloud daily Section G. Returns (html|None, warnings)."""
    symbols: list[str] = []
    if scan_df is not None and not scan_df.empty:
        symbols = scan_df["symbol"].tolist()
    if holdings:
        sym_set = set(symbols)
        symbols = symbols + [h for h in holdings if h not in sym_set]

    c3_df, warns = load_rs_c3_for_date(scan_date, symbols=symbols or None)
    if c3_df is None or c3_df.empty:
        return None, warns

    c3_df = compute_c3_fields(c3_df, scan_df=scan_df)
    market_off = bool(c3_df["rs_c3_market_off"].iloc[0])
    rating_date = str(c3_df["_rating_date"].iloc[0])

    c3_df = c3_df.sort_values(
        ["rs_c3_late_chase_warning", "rs_c3_rating"], ascending=[False, False]
    )
    rows = _rows_from_df(c3_df)
    return render_rs_c3_html(rows, market_off=market_off, rating_date=rating_date), warns


def build_rs_c3_section_for_weekly(
    *,
    scan_date: Optional[str] = None,
    max_rows: int = 10,
) -> tuple[str, list[str]]:
    """Build RS C3 HTML card for weekly report (top LEADER/OUTPERFORM only)."""
    scan_df = _load_latest_scan_df()
    symbols = scan_df["symbol"].tolist() if scan_df is not None else None
    c3_df, warns = load_rs_c3_for_date(scan_date, symbols=symbols)

    if c3_df is None or c3_df.empty:
        return (
            '<div class="ctx-safety">'
            + _html.escape(
                "RS C3 data unavailable — run rs_rating_research.py. " + SAFETY_NOTE
            )
            + "</div>"
        ), warns

    c3_df = compute_c3_fields(c3_df, scan_df=scan_df)
    market_off = bool(c3_df["rs_c3_market_off"].iloc[0])
    rating_date = str(c3_df["_rating_date"].iloc[0])

    leaders = c3_df[c3_df["rs_c3_bucket"].isin(["EXTREME_RS", "LEADER_ZONE"])].sort_values(
        ["rs_c3_late_chase_warning", "rs_c3_rating"], ascending=[False, False]
    ).head(max_rows)
    rows = _rows_from_df(leaders)
    return render_rs_c3_html(rows, market_off=market_off, rating_date=rating_date, max_rows=max_rows), warns
