#!/usr/bin/env python3
"""
LEGACY: use `python -m src.trading.cli distribution-risk` for canonical distribution risk.
`dist_session_*` outputs are not SSOT — SSOT is distribution_risk_latest.json.

Per-session VNINDEX distribution monitor (full + ex-VIN + VIN basket).

Writes:
  - data/alerts/dist_session_latest.json
  - data/decision/dist_session_alert.md
  - data/alerts/dist_session_log.jsonl (append one record per run)

Usage:
  .venv\\Scripts\\python.exe scripts/monitor_vnindex_distribution_session.py
  .venv\\Scripts\\python.exe scripts/monitor_vnindex_distribution_session.py --fetch
  .venv\\Scripts\\python.exe scripts/monitor_vnindex_distribution_session.py --note "after close"
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.research.vnindex_dist_v2.dist_rule import add_dist_day

OUT_JSON = REPO / "data" / "alerts" / "dist_session_latest.json"
OUT_MD = REPO / "data" / "decision" / "dist_session_alert.md"
OUT_LOG = REPO / "data" / "alerts" / "dist_session_log.jsonl"
EX_SERIES = REPO / "data" / "research" / "vnindex_ex_vin_daily_series.csv"
VNI_SSOT = REPO / "data" / "fireant_ssot" / "ta_vnindex.parquet"
VIN_SYMS = ("VIC", "VHM", "VRE")

# Historical correction windows (for context labels only)
REF_WINDOWS = {
    "2023-08-09": ("2023-08-01", "2023-09-30"),
    "2024-03-04": ("2024-03-01", "2024-04-30"),
    "2024-06-07": ("2024-06-01", "2024-07-31"),
    "2024-09-10": ("2024-09-01", "2024-10-31"),
}


def _roll_dist(s: pd.Series, w: int) -> pd.Series:
    return s.fillna(0).rolling(w).sum()


def _load_vnindex(fetch: bool, end: str) -> pd.DataFrame:
    df = pd.read_parquet(VNI_SSOT)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    if not fetch:
        return df
    last = df["date"].max()
    if last >= pd.Timestamp(end):
        return df
    try:
        from src.intake.fireant_historical import fetch_historical

        start = (last - pd.Timedelta(days=5)).date().isoformat()
        rows = fetch_historical("VNINDEX", start, end)
        if rows:
            extra = pd.DataFrame(
                [
                    {
                        "date": pd.Timestamp(r.d),
                        "open": float(r.o),
                        "high": float(r.h),
                        "low": float(r.l),
                        "close": float(r.c),
                        "volume": float(r.v) if r.v is not None else np.nan,
                    }
                    for r in rows
                ]
            )
            df = pd.concat([df, extra], ignore_index=True)
            df = df.drop_duplicates(subset=["date"], keep="last").sort_values("date")
    except Exception as exc:
        print(f"WARN fetch VNINDEX failed: {exc}", file=sys.stderr)
    return df.reset_index(drop=True)


def _load_ex_vin(end: str, vni: pd.DataFrame, refresh: bool) -> pd.DataFrame | None:
    if EX_SERIES.exists() and not refresh:
        ex = pd.read_csv(EX_SERIES)
        ex["date"] = pd.to_datetime(ex["date"])
        if ex["date"].max() >= vni["date"].max() - pd.Timedelta(days=1):
            return ex.sort_values("date").reset_index(drop=True)
    try:
        from scripts.research.vnindex_low_dist_ex_vin import build_ex_vin_series

        ex = build_ex_vin_series(end, preloaded_vnindex=vni)
        EX_SERIES.parent.mkdir(parents=True, exist_ok=True)
        ex.to_csv(EX_SERIES, index=False)
        return ex
    except Exception as exc:
        print(f"WARN ex-VIN series build failed: {exc}", file=sys.stderr)
        if EX_SERIES.exists():
            ex = pd.read_csv(EX_SERIES)
            ex["date"] = pd.to_datetime(ex["date"])
            return ex.sort_values("date").reset_index(drop=True)
        return None


def _enrich(df: pd.DataFrame, close_col: str, vol_col: str) -> pd.DataFrame:
    out = add_dist_day(df, close_col, vol_col)
    c = out[close_col].astype(float)
    out["ma20"] = c.rolling(20, min_periods=20).mean()
    out["ma50"] = c.rolling(50, min_periods=50).mean()
    out["ma200"] = c.rolling(200, min_periods=200).mean()
    out["dist_10"] = _roll_dist(out["dist_day"], 10)
    out["dist_20"] = _roll_dist(out["dist_day"], 20)
    out["dist_50"] = _roll_dist(out["dist_day"], 50)
    out["ret_5d"] = c / c.shift(5) - 1
    out["ret_20d"] = c / c.shift(20) - 1
    return out


def _vin_returns(asof: pd.Timestamp) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for sym in VIN_SYMS:
        p = REPO / "data" / "stocks" / f"{sym}.csv"
        if not p.exists():
            out[sym] = {"status": "missing"}
            continue
        d = pd.read_csv(p, usecols=["date", "close"])
        d["date"] = pd.to_datetime(d["date"])
        d = d[d["date"] <= asof].sort_values("date")
        if d.empty:
            out[sym] = {"status": "empty"}
            continue
        c = d["close"].astype(float)
        r5 = float(c.iloc[-1] / c.iloc[-6] - 1) if len(d) >= 6 else float("nan")
        r20 = float(c.iloc[-1] / c.iloc[-21] - 1) if len(d) >= 21 else float("nan")
        out[sym] = {
            "ret_5d_pct": round(r5 * 100, 2) if np.isfinite(r5) else None,
            "ret_20d_pct": round(r20 * 100, 2) if np.isfinite(r20) else None,
        }
    return out


def _classify_alert(
    dist_10: int,
    dist_20: int,
    today_dist: bool,
    above_ma50: bool | None,
    dist_in_last_5: int,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if dist_20 >= 5 or (dist_20 >= 4 and not above_ma50):
        level = "RED"
        reasons.append(f"dist_20d={dist_20} (correction-zone vs 2023–2024 peaks)")
    elif dist_20 >= 4 or dist_10 >= 4 or (dist_in_last_5 >= 3 and above_ma50):
        level = "ORANGE"
        reasons.append(f"dist cluster: 10d={dist_10}, 20d={dist_20}, last5={dist_in_last_5}")
    elif dist_20 >= 3 or dist_10 >= 2 or today_dist:
        level = "YELLOW"
        if today_dist:
            reasons.append("today= distribution day")
        reasons.append(f"dist_10d={dist_10}, dist_20d={dist_20}")
    else:
        level = "GREEN"
        reasons.append("low distribution vs historical correction templates")

    if above_ma50 is False and dist_20 >= 3:
        level = max(level, "ORANGE", key=["GREEN", "YELLOW", "ORANGE", "RED"].index)
        reasons.append("below MA50 with elevated dist_20")

    return level, reasons


def _snapshot_row(df: pd.DataFrame, label: str, close_col: str, vol_col: str) -> dict[str, Any]:
    d = _enrich(df, close_col, vol_col)
    row = d.iloc[-1]
    c = float(row[close_col])
    dist_last5 = int(d["dist_day"].fillna(0).tail(5).sum())
    today_dist = bool(row["dist_day"] == 1)
    above_ma50 = bool(c > float(row["ma50"])) if pd.notna(row["ma50"]) else None
    d10, d20 = int(row["dist_10"]), int(row["dist_20"])
    level, reasons = _classify_alert(d10, d20, today_dist, above_ma50, dist_last5)
    last_dists = d.loc[d["dist_day"] == 1, "date"].tail(6).dt.strftime("%Y-%m-%d").tolist()
    snap: dict[str, Any] = {
        "label": label,
        "asof": str(row["date"].date()),
        "close": round(c, 2),
        "pct_1d": round(float(row["pct_change"]) * 100, 3) if pd.notna(row["pct_change"]) else None,
        "today_distribution_day": today_dist,
        "dist_10d": d10,
        "dist_20d": d20,
        "dist_50d": int(row["dist_50"]),
        "dist_in_last_5_sessions": dist_last5,
        "above_ma20": bool(c > float(row["ma20"])) if pd.notna(row["ma20"]) else None,
        "above_ma50": above_ma50,
        "above_ma200": bool(c > float(row["ma200"])) if pd.notna(row["ma200"]) else None,
        "ret_5d_pct": round(float(row["ret_5d"]) * 100, 2) if pd.notna(row["ret_5d"]) else None,
        "ret_20d_pct": round(float(row["ret_20d"]) * 100, 2) if pd.notna(row["ret_20d"]) else None,
        "last_distribution_dates": last_dists,
        "alert_level": level,
        "alert_reasons": reasons,
    }
    if "w_VIN" in row.index and pd.notna(row["w_VIN"]):
        snap["w_VIN_pct"] = round(float(row["w_VIN"]) * 100, 2)
    return snap


def _reference_table(vni: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    v = _enrich(vni, "close", "volume")
    for tag, (s, e) in REF_WINDOWS.items():
        w = v[(v["date"] >= pd.Timestamp(s)) & (v["date"] <= pd.Timestamp(e))]
        if w.empty:
            continue
        peak = float(w["close"].max())
        last_c = float(w["close"].iloc[-1])
        rows.append(
            {
                "label": tag,
                "max_dist_20d": int(w["dist_20"].max()),
                "dist_days_total": int(w["dist_day"].fillna(0).sum()),
                "dd_from_peak_pct": round((last_c / peak - 1) * 100, 2),
            }
        )
    cur = v[v["date"] >= pd.Timestamp("2026-03-01")]
    if not cur.empty:
        peak = float(cur["close"].max())
        last_c = float(cur["close"].iloc[-1])
        rows.append(
            {
                "label": "2026-YTD",
                "max_dist_20d": int(cur["dist_20"].max()),
                "dist_days_total": int(cur["dist_day"].fillna(0).sum()),
                "dd_from_peak_pct": round((last_c / peak - 1) * 100, 2),
            }
        )
    return rows


def _render_md(payload: dict[str, Any]) -> str:
    full = payload["full"]
    ex = payload.get("ex_vin")
    level = payload["composite_alert"]
    lines = [
        f"# Distribution session alert — {payload['run_at_utc'][:10]}",
        "",
        f"**Composite alert:** `{level}` — {payload.get('composite_summary', '')}",
        "",
        "## FACTS",
        f"- source = FireAnt (VNINDEX native; ex-VIN = proxy {list(VIN_SYMS)})",
        f"- method = O'Neil dist rule (-0.2% close vs prior + volume up); SSOT + optional `--fetch`",
        f"- asof bar = {full['asof']}",
        "",
        "### VNINDEX (full)",
        f"- close {full['close']} | 1d {full['pct_1d']}% | today_dist **{full['today_distribution_day']}**",
        f"- dist 10/20/50 = {full['dist_10d']}/{full['dist_20d']}/{full['dist_50d']} | last5 dist = {full['dist_in_last_5_sessions']}",
        f"- MA20/50/200 = {full['above_ma20']}/{full['above_ma50']}/{full['above_ma200']} | ret5/20 = {full['ret_5d_pct']}% / {full['ret_20d_pct']}%",
        f"- alert **{full['alert_level']}**: {', '.join(full['alert_reasons'])}",
        "",
    ]
    if ex:
        lines += [
            "### VNINDEX ex-VIN (proxy)",
            f"- close {ex['close']} | w_VIN {ex.get('w_VIN_pct', 'n/a')}% | today_dist **{ex['today_distribution_day']}**",
            f"- dist 10/20 = {ex['dist_10d']}/{ex['dist_20d']} | alert **{ex['alert_level']}**",
            "",
        ]
    vin = payload.get("vin_basket", {})
    if vin:
        lines.append("### VIN basket (native OHLCV)")
        for sym, m in vin.items():
            if m.get("status"):
                lines.append(f"- {sym}: {m['status']}")
            else:
                lines.append(f"- {sym}: 5d {m.get('ret_5d_pct')}% | 20d {m.get('ret_20d_pct')}%")
        lines.append("")

    lines += ["### Historical context (full VNINDEX)", "| window | max_dist_20 | dist_total | dd_from_peak |"]
    for r in payload.get("reference_windows", []):
        lines.append(
            f"| {r['label']} | {r['max_dist_20d']} | {r['dist_days_total']} | {r['dd_from_peak_pct']}% |"
        )
    lines += [
        "",
        "## INTERPRETATION",
        payload.get("interpretation", "(see alert levels)"),
        "",
        "## If X → do Y",
        "- If composite **RED** or dist_20≥5 or (dist_20≥4 and below MA50) → cut beta; no new chase entries.",
        "- If **ORANGE** → tighten stops; only leaders; watch for 3+ dist in 5 sessions.",
        "- If **YELLOW** + today_dist → do not add risk today; reassess tomorrow.",
        "- If **GREEN** → monitor only; not in 2023–2024 correction template yet.",
        "",
    ]
    if payload.get("user_note"):
        lines.append(f"_Note: {payload['user_note']}_")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Per-session VNINDEX distribution monitor")
    ap.add_argument("--end", default=None, help="YYYY-MM-DD (default: today)")
    ap.add_argument("--fetch", action="store_true", help="Try FireAnt for bars newer than SSOT")
    ap.add_argument("--refresh-ex-vin", action="store_true", help="Rebuild ex-VIN series CSV")
    ap.add_argument("--note", default="", help="Optional note stored in log")
    args = ap.parse_args()

    end = args.end or date.today().isoformat()
    vni = _load_vnindex(fetch=args.fetch, end=end)
    ex_raw = _load_ex_vin(end, vni, refresh=args.refresh_ex_vin or args.fetch)

    full = _snapshot_row(vni, "VNINDEX full", "close", "volume")
    ex_snap = None
    if ex_raw is not None:
        ex_snap = _snapshot_row(ex_raw, "VNINDEX ex-VIN", "close_ex_vin", "volume_ex_vin")

    levels = [full["alert_level"]]
    if ex_snap:
        levels.append(ex_snap["alert_level"])
    rank = {"GREEN": 0, "YELLOW": 1, "ORANGE": 2, "RED": 3}
    composite = max(levels, key=lambda x: rank[x])
    if composite == "RED":
        summary = "Distribution regime stressed — act defensive."
    elif composite == "ORANGE":
        summary = "Cluster building — reduce new risk."
    elif composite == "YELLOW":
        summary = "Early warning — today or 20d count elevated."
    else:
        summary = "Low distribution — not matching prior correction clusters."

    asof_ts = pd.Timestamp(full["asof"])
    interpretation = (
        f"Composite {composite}. Full dist20={full['dist_20d']} vs correction templates "
        f"(peaks 4–5). VIC/VHM/VRE used for big-hand read; ex-VIN proxy for breadth check."
    )

    payload: dict[str, Any] = {
        "run_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "FireAnt",
        "method": "REST (optional --fetch) + SSOT parquet; ex-VIN proxy",
        "composite_alert": composite,
        "composite_summary": summary,
        "full": full,
        "ex_vin": ex_snap,
        "vin_basket": _vin_returns(asof_ts),
        "reference_windows": _reference_table(vni),
        "interpretation": interpretation,
        "user_note": args.note or None,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(_render_md(payload), encoding="utf-8")

    with OUT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    print(
        "LEGACY: use python -m src.trading.cli distribution-risk for canonical distribution risk. "
        "dist_session_* is not SSOT."
    )
    print(f"Composite alert: {composite} — {summary}")
    print(f"Full: dist20={full['dist_20d']} today_dist={full['today_distribution_day']} MA50={full['above_ma50']}")
    if ex_snap:
        print(f"Ex-VIN: dist20={ex_snap['dist_20d']} alert={ex_snap['alert_level']}")
    print(f"Wrote: {OUT_JSON}")
    print(f"       {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
