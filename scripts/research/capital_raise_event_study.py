#!/usr/bin/env python3
"""
Vietnam equity capital-raise event study (descriptive, no look-ahead on fundamentals).

Data:
  - OHLCV: local panel (FireAnt-sourced) + FireAnt REST for VNINDEX gap-fill
  - Events: curated seed JSON + quarterly shares-outstanding change scan (FireAnt REST)
  - Fundamentals near event: FireAnt quarterly reports (point-in-time by report period)

Run: .venv\\Scripts\\python.exe scripts/research/capital_raise_event_study.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from src.data.fireant_client import get_client  # noqa: E402
from src.intake.fireant_historical import fetch_historical  # noqa: E402

OUT_DIR = _REPO / "data" / "research"
SEED_PATH = _REPO / "data" / "research" / "seeds" / "capital_raise_events_seed.json"
DERIVED_CACHE = OUT_DIR / "capital_raise_events_derived_cache.json"
_NAME_CACHE: dict[str, str] = {}
PANEL_PATH = _REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_full.parquet"
REPORT_DATE = date.today().strftime("%Y%m%d")

ADV_PRIMARY_VND = 2_000_000_000
PRICE_SCALE = 1000.0  # panel close is in thousands VND

REAL_ESTATE = {
    "VHM", "VIC", "KDH", "NLG", "DXG", "PDR", "DIG", "CEO", "NVL", "KHG",
    "AGG", "VPI", "HDG", "SCR", "QCG", "IJC", "NTL",
}
SECURITIES = {
    "SSI", "VCI", "HCM", "MBS", "SHS", "VND", "VIX", "FTS", "BSI", "CTS",
    "VDS", "ORS", "APG", "AGR",
}
BANKS = {
    "VCB", "BID", "CTG", "TCB", "MBB", "ACB", "VPB", "HDB", "STB", "VIB",
    "TPB", "OCB", "LPB", "SHB", "MSB", "EIB", "NAB", "SSB",
}
PRIORITY = REAL_ESTATE | SECURITIES | BANKS

EVENT_TYPE_MAP = {
    "rights_offering": "A_rights_offering",
    "private_placement": "B_private_placement",
    "stock_dividend": "C_stock_dividend",
    "esop": "D_esop",
    "conversion": "E_conversion",
    "mixed": "F_mixed",
    "unknown_capital_increase": "unknown_capital_increase",
}

# Columns included in multi-horizon summary CSVs / report tables
SUMMARY_RET_COLS = [
    "ret_pre_120_60",
    "ret_pre_60_20",
    "ret_pre_20_5",
    "ret_pre_5_1",
    "pre_runup_60d",
    "ret_pre_20_1",
    "ret_evt_m1_p1",
    "ret_evt_0",
    "ret_evt_0_3",
    "ret_evt_0_5",
    "post_return_20d",
    "post_return_60d",
    "ret_post_1_10",
    "ret_post_1_20",
    "ret_post_1_40",
    "ret_post_1_60",
    "ret_post_1_120",
    "ret_post_1_180",
    "excess_evt_0_20",
    "excess_return_60d",
    "excess_evt_0_120",
]

HORIZON_LABELS = {
    "ret_pre_120_60": "pre_T-120→T-60",
    "ret_pre_60_20": "pre_T-60→T-20",
    "ret_pre_20_5": "pre_T-20→T-5",
    "ret_pre_5_1": "pre_T-5→T-1",
    "pre_runup_60d": "pre_T-60→T-1",
    "ret_pre_20_1": "pre_T-20→T-1",
    "ret_evt_m1_p1": "evt_T-1→T+1",
    "ret_evt_0": "evt_T0",
    "ret_evt_0_3": "evt_T0→T+3",
    "ret_evt_0_5": "evt_T0→T+5",
    "post_return_20d": "post_T0→T+20",
    "post_return_60d": "post_T0→T+60",
    "ret_post_1_10": "post_T+1→T+10",
    "ret_post_1_20": "post_T+1→T+20",
    "ret_post_1_40": "post_T+1→T+40",
    "ret_post_1_60": "post_T+1→T+60",
    "ret_post_1_120": "post_T+1→T+120",
    "ret_post_1_180": "post_T+1→T+180",
    "excess_evt_0_20": "excess_T0→T+20",
    "excess_return_60d": "excess_T0→T+60",
    "excess_evt_0_120": "excess_T0→T+120",
}

# Multi-horizon summary buckets: phase → (display label, column name)
HORIZON_BUCKETS: list[tuple[str, str, str]] = [
    # Phase A: from public announcement (T0_announce)
    ("A_announce", "Pre T-60→T-1", "pre_runup_60d"),
    ("A_announce", "Pre T-20→T-1", "ret_pre_20_1"),
    ("A_announce", "Pre T-5→T-1", "ret_pre_5_1"),
    ("A_announce", "Event T-1→T+1", "ret_evt_m1_p1"),
    ("A_announce", "Event T0 day", "ret_evt_0"),
    ("A_announce", "T0→T+5", "ret_evt_0_5"),
    ("A_announce", "T0→T+10", "ret_post_1_10"),
    ("A_announce", "T0→T+20", "post_return_20d"),
    ("A_announce", "T0→T+40", "ret_post_1_40"),
    ("A_announce", "T0→T+60", "post_return_60d"),
    ("A_announce", "T0→T+120", "ret_post_1_120"),
    ("A_announce", "T0→T+180", "ret_post_1_180"),
    ("A_announce", "Excess vs VNINDEX T0→T+20", "excess_evt_0_20"),
    ("A_announce", "Excess vs VNINDEX T0→T+60", "excess_return_60d"),
    ("A_announce", "Excess vs VNINDEX T0→T+120", "excess_evt_0_120"),
    # Phase B: announcement → ex-right (rights / dated events)
    ("B_ann_to_exright", "T0→exright T-1", "ret_ann_to_ex_m1"),
    ("B_ann_to_exright", "Ex-right T-5→T-1", "ret_ex_m5_m1"),
    ("B_ann_to_exright", "Ex-right T0→T+1", "ret_ex_0_p1"),
    # Phase C: after ex-right
    ("C_after_exright", "Ex-right T+1→T+20", "ret_ex_p1_20"),
    ("C_after_exright", "Ex-right T+1→T+60", "ret_ex_p1_60"),
    # Phase D: result / completion announcement
    ("D_result", "Result T-5→T-1", "ret_res_m5_m1"),
    ("D_result", "Result T0→T+5", "ret_res_0_p5"),
    ("D_result", "Result T+1→T+20", "ret_res_p1_20"),
    ("D_result", "Result T+1→T+60", "ret_res_p1_60"),
]

RETURN_WINDOWS = {
    "pre_120_60": (-120, -60),
    "pre_60_20": (-60, -20),
    "pre_20_5": (-20, -5),
    "pre_5_1": (-5, -1),
    "pre_60_1": (-60, -1),
    "pre_20_1": (-20, -1),
    "evt_m1_p1": (-1, 1),
    "evt_0": (0, 0),
    "evt_0_3": (0, 3),
    "evt_0_5": (0, 5),
    "post_1_10": (1, 10),
    "post_1_20": (1, 20),
    "post_1_40": (1, 40),
    "post_1_60": (1, 60),
    "post_1_120": (1, 120),
    "post_1_180": (1, 180),
}


@dataclass
class EventRow:
    event_id: str
    ticker: str
    company_name: str = ""
    sector: str = "other"
    event_type: str = "unknown_capital_increase"
    T0_announce: str | None = None
    T0_board: str | None = None
    T0_record: str | None = None
    T0_exright: str | None = None
    T0_subscription_start: str | None = None
    T0_subscription_end: str | None = None
    T0_result: str | None = None
    pre_shares: float | None = None
    new_shares: float | None = None
    offering_price: float | None = None
    expected_proceeds: float | None = None
    actual_proceeds: float | None = None
    use_of_proceeds: str = "unclear"
    purpose_tag: str = "mixed_unknown"
    completion_status: str = "unknown"
    insider_participation: bool | None = None
    source: str = "derived_shares_outstanding"
    source_note: str = ""
    flags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


def _sector(sym: str) -> str:
    if sym in REAL_ESTATE:
        return "real_estate"
    if sym in SECURITIES:
        return "securities"
    if sym in BANKS:
        return "banks"
    return "other"


def _parse_date(s: str | None) -> pd.Timestamp | None:
    if not s:
        return None
    try:
        return pd.Timestamp(s).normalize()
    except Exception:
        return None


def load_panel() -> pd.DataFrame:
    df = pd.read_parquet(PANEL_PATH)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    if "value" not in df.columns or df["value"].isna().all():
        df["value"] = df["close"] * PRICE_SCALE * df["volume"]
    return df.sort_values(["symbol", "date"])


def load_vnindex(start: str, end: str, panel: pd.DataFrame) -> pd.DataFrame:
    sub = panel.loc[panel["symbol"] == "VNINDEX", ["date", "open", "high", "low", "close", "volume", "value"]]
    if len(sub) > 200:
        return sub.sort_values("date").reset_index(drop=True)
    rows = fetch_historical("VNINDEX", start, end)
    idx = pd.DataFrame(
        [{"date": pd.Timestamp(r.d), "open": r.o, "high": r.h, "low": r.l, "close": r.c, "volume": r.v or 0.0}
         for r in rows]
    )
    idx["value"] = idx["close"] * PRICE_SCALE * idx["volume"]
    return idx.sort_values("date").reset_index(drop=True)


def trading_align(dates: pd.DatetimeIndex, t0: pd.Timestamp, direction: str = "next") -> int | None:
    """Return index of trading day on/after (next) or on/before (prev) t0."""
    if direction == "next":
        pos = dates.searchsorted(t0, side="left")
        return int(pos) if pos < len(dates) else None
    pos = dates.searchsorted(t0, side="right") - 1
    return int(pos) if pos >= 0 else None


def window_return(close: np.ndarray, i0: int, i1: int) -> float | None:
    if i0 is None or i1 is None or i0 < 0 or i1 < 0 or i0 >= len(close) or i1 >= len(close):
        return None
    c0, c1 = close[i0], close[i1]
    if not np.isfinite(c0) or not np.isfinite(c1) or c0 <= 0:
        return None
    return float(c1 / c0 - 1.0)


def adv_n(values: np.ndarray, i: int, n: int) -> float | None:
    lo = max(0, i - n + 1)
    seg = values[lo : i + 1]
    seg = seg[np.isfinite(seg)]
    if len(seg) == 0:
        return None
    return float(np.mean(seg))


def max_drawdown(close: np.ndarray, i0: int, i1: int) -> float | None:
    if i0 is None or i1 is None or i0 > i1:
        return None
    seg = close[i0 : i1 + 1]
    seg = seg[np.isfinite(seg)]
    if len(seg) < 2:
        return None
    peak = np.maximum.accumulate(seg)
    dd = seg / peak - 1.0
    return float(np.min(dd))


def max_runup(close: np.ndarray, i0: int, i1: int) -> float | None:
    if i0 is None or i1 is None or i0 > i1:
        return None
    seg = close[i0 : i1 + 1]
    seg = seg[np.isfinite(seg)]
    if len(seg) < 2:
        return None
    trough = np.minimum.accumulate(seg)
    ru = seg / trough - 1.0
    return float(np.max(ru))


def classify_use(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ("nợ", "debt", "trái phiếu", "bond", "refinanc")):
        return "debt_repayment"
    if any(k in t for k in ("dự án", "project", "m&a", "acquisition", "đầu tư")):
        return "project_investment"
    if any(k in t for k in ("vốn tự có", "car", "basel", "margin", "tín dụng", "regulatory")):
        return "regulatory_capital"
    if any(k in t for k in ("cổ tức", "thưởng", "stock dividend", "bonus")):
        return "technical_stock_dividend"
    if any(k in t for k in ("vốn lưu động", "working capital")):
        return "working_capital"
    return "unclear"


def purpose_tag_from_use(use: str, leverage_high: bool | None) -> str:
    mapping = {
        "debt_repayment": "balance_sheet_repair",
        "project_investment": "growth_funding",
        "regulatory_capital": "regulatory_capital",
        "technical_stock_dividend": "technical_stock_dividend",
        "working_capital": "mixed_unknown",
    }
    tag = mapping.get(use, "mixed_unknown")
    if leverage_high and use == "debt_repayment":
        return "survival_refinancing"
    return tag


def market_regime_at(idx_row: pd.Series, vn: pd.DataFrame, t: pd.Timestamp) -> str:
    dates = vn["date"].values
    pos = trading_align(pd.DatetimeIndex(dates), t, "prev")
    if pos is None:
        return "unknown"
    sub = vn.iloc[: pos + 1]
    if len(sub) < 200:
        return "unknown"
    c = sub["close"].astype(float)
    ma50 = c.rolling(50).mean().iloc[-1]
    ma200 = c.rolling(200).mean().iloc[-1]
    close = c.iloc[-1]
    ret60 = close / c.iloc[-60] - 1 if len(c) >= 60 else np.nan
    if not np.isfinite(ma50) or not np.isfinite(ma200):
        return "unknown"
    above50 = close > ma50
    above200 = close > ma200
    if above50 and above200 and ret60 > 0.05:
        return "risk_on"
    if above50 and above200 and -0.02 <= ret60 <= 0.05:
        return "fragile_uptrend"
    if above50 and not above200:
        return "sideways_rotation"
    if above50 and ret60 > 0 and close / ma50 > 1.06:
        return "distribution_topping"
    if not above50:
        return "correction_risk_off"
    return "sideways_rotation"


def _is_equity_symbol(sym: str) -> bool:
    if sym in {"VNINDEX", "VN30", "HNX", "UPCOM"}:
        return False
    if sym.startswith(("FUE", "E1VF", "VN30F")):
        return False
    return True


def discover_from_shares(symbols: list[str], min_pct: float = 0.08) -> list[EventRow]:
    client = get_client()
    out: list[EventRow] = []
    for sym in symbols:
        if not _is_equity_symbol(sym):
            continue
        try:
            fq = client.get_fundamentals_quarterly(sym, n_quarters=48)
        except Exception:
            continue
        if fq.empty or "shares_outstanding" not in fq.columns:
            continue
        fq = fq.dropna(subset=["shares_outstanding"]).sort_values(["year", "quarter"])
        prev = None
        for _, row in fq.iterrows():
            sh = float(row["shares_outstanding"])
            if prev is not None and prev > 0:
                dil = sh / prev - 1.0
                if dil >= min_pct:
                    y, q = int(row["year"]), int(row["quarter"])
                    month = q * 3
                    q_end = pd.Timestamp(year=y, month=month, day=1) + pd.offsets.MonthEnd(0)
                    t_ann = (q_end - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
                    eid = f"{sym}_{y}Q{q}_shares_up"
                    out.append(
                        EventRow(
                            event_id=eid,
                            ticker=sym,
                            sector=_sector(sym),
                            event_type="unknown_capital_increase",
                            T0_announce=t_ann,
                            pre_shares=prev,
                            new_shares=sh - prev,
                            source="derived_shares_outstanding",
                            source_note=f"Shares +{dil:.1%} between quarters; T0_announce proxied",
                            flags=[
                                "derived_from_shares_outstanding_only",
                                "missing_offering_price",
                                "missing_exright_date",
                            ],
                        )
                    )
            prev = sh
        time.sleep(0.12)
    return out


def load_seed() -> list[EventRow]:
    if not SEED_PATH.exists():
        return []
    raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    rows: list[EventRow] = []
    for i, r in enumerate(raw):
        sym = r["ticker"].upper()
        et = r.get("event_type", "unknown_capital_increase")
        use = r.get("use_of_proceeds") or classify_use(r.get("source_note", ""))
        rows.append(
            EventRow(
                event_id=f"seed_{sym}_{i}",
                ticker=sym,
                sector=_sector(sym),
                event_type=et,
                T0_announce=r.get("T0_announce"),
                T0_board=r.get("T0_board"),
                T0_record=r.get("T0_record"),
                T0_exright=r.get("T0_exright"),
                T0_subscription_start=r.get("T0_subscription_start"),
                T0_subscription_end=r.get("T0_subscription_end"),
                T0_result=r.get("T0_result"),
                pre_shares=r.get("pre_shares"),
                new_shares=r.get("new_shares"),
                offering_price=r.get("offering_price"),
                expected_proceeds=r.get("expected_proceeds"),
                actual_proceeds=r.get("actual_proceeds"),
                use_of_proceeds=use,
                purpose_tag=r.get("purpose_tag") or purpose_tag_from_use(use, None),
                completion_status=r.get("completion_status", "unknown"),
                insider_participation=r.get("insider_participation"),
                source=r.get("source", "seed"),
                source_note=r.get("source_note", ""),
                flags=[] if r.get("T0_announce") else ["missing_event_date"],
            )
        )
    return rows


def dedupe_events(events: list[EventRow], window_days: int = 120) -> list[EventRow]:
    """Prefer seed over derived; collapse overlapping derived clusters per ticker-year."""
    seeds = [e for e in events if e.source != "derived_shares_outstanding"]
    derived = [e for e in events if e.source == "derived_shares_outstanding"]

    kept: list[EventRow] = list(seeds)
    seed_dates: dict[str, list[pd.Timestamp]] = {}
    for s in seeds:
        t = _parse_date(s.T0_announce)
        if t is not None:
            seed_dates.setdefault(s.ticker, []).append(t)

    derived_sorted = sorted(
        derived,
        key=lambda e: (e.ticker, -(e.new_shares or 0), e.T0_announce or ""),
    )
    derived_kept: list[EventRow] = []
    for e in derived_sorted:
        t = _parse_date(e.T0_announce)
        if t is None:
            continue
        if any(abs((t - sd).days) <= window_days for sd in seed_dates.get(e.ticker, [])):
            continue
        year = t.year
        if any(
            k.ticker == e.ticker
            and _parse_date(k.T0_announce) is not None
            and _parse_date(k.T0_announce).year == year
            for k in derived_kept
        ):
            continue
        derived_kept.append(e)

    return seeds + derived_kept


def attach_fundamentals(ev: EventRow, client) -> dict[str, Any]:
    t0 = _parse_date(ev.T0_announce)
    if t0 is None or not _is_equity_symbol(ev.ticker):
        return {}
    try:
        fq = client.get_fundamentals_quarterly(ev.ticker, n_quarters=12)
    except Exception:
        return {}
    if fq.empty:
        return {}
    fq = fq.copy()
    fq["period"] = pd.to_datetime(
        {"year": fq["year"].astype(int), "month": (fq["quarter"].astype(int) * 3), "day": 1}
    ) + pd.offsets.MonthEnd(0)
    eligible = fq[fq["period"] <= t0]
    if eligible.empty:
        eligible = fq.head(1)
    row = eligible.iloc[-1]
    out = {
        "fund_revenue": row.get("revenue"),
        "fund_net_income": row.get("net_income"),
        "fund_equity": row.get("equity"),
        "fund_total_debt": row.get("total_debt"),
        "fund_shares_outstanding": row.get("shares_outstanding"),
    }
    eq = row.get("equity")
    debt = row.get("total_debt")
    ni = row.get("net_income")
    if eq and eq > 0 and debt is not None:
        out["fund_debt_equity"] = debt / eq
    if eq and eq > 0 and ni is not None:
        out["fund_roe"] = ni / eq
    return out


def compute_event_returns(
    ev: EventRow,
    sym_df: pd.DataFrame,
    vn_df: pd.DataFrame,
    sector_frames: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    dates = sym_df["date"]
    di = pd.DatetimeIndex(dates)
    close = sym_df["close"].astype(float).values
    vals = sym_df["value"].astype(float).values

    t0d = _parse_date(ev.T0_announce)
    if t0d is None:
        return {"error": "missing T0_announce"}
    i0 = trading_align(di, t0d, "next")
    if i0 is None:
        return {"error": "T0 outside range"}

    out: dict[str, Any] = {"T0_trade_date": str(di[i0].date())}
    im1 = i0 - 1 if i0 > 0 else None

    for name, (a, b) in RETURN_WINDOWS.items():
        ia = i0 + a if a != 0 else i0
        ib = i0 + b if b != 0 else i0
        out[f"ret_{name}"] = window_return(close, ia, ib)

    # VNINDEX-relative for key windows
    vn_close = vn_df.set_index("date")["close"].astype(float)
    def idx_ret(offset_a: int, offset_b: int) -> float | None:
        da = di[i0 + offset_a] if i0 + offset_a < len(di) else None
        db = di[i0 + offset_b] if i0 + offset_b < len(di) else None
        if da is None or db is None:
            return None
        if da not in vn_close.index or db not in vn_close.index:
            return None
        c0, c1 = vn_close.loc[da], vn_close.loc[db]
        if c0 <= 0:
            return None
        return float(c1 / c0 - 1.0)

    for horizon in (20, 60, 120):
        sr = window_return(close, i0, i0 + horizon)
        ir = idx_ret(0, horizon)
        if sr is not None and ir is not None:
            out[f"excess_evt_0_{horizon}"] = sr - ir

    out["pre_runup_60d"] = window_return(close, i0 - 60, im1) if im1 is not None else None
    out["post_return_20d"] = window_return(close, i0, i0 + 20)
    out["post_return_60d"] = window_return(close, i0, i0 + 60)
    out["excess_return_60d"] = out.get("excess_evt_0_60")
    out["max_drawdown_60d"] = max_drawdown(close, i0, min(i0 + 60, len(close) - 1))
    out["max_runup_60d"] = max_runup(close, i0, min(i0 + 60, len(close) - 1))

    adv50 = adv_n(vals, im1, 50) if im1 is not None else None
    adv20_b = adv_n(vals, im1, 20) if im1 is not None else None
    adv60_b = adv_n(vals, im1, 60) if im1 is not None else None
    adv20_a = adv_n(vals, min(i0 + 20, len(vals) - 1), 20)
    out["adv50_T0_minus_1"] = adv50
    out["low_liquidity"] = adv50 is not None and adv50 < ADV_PRIMARY_VND
    if adv20_b and adv60_b and adv60_b > 0:
        out["volume_ratio_20_60_pre"] = adv20_b / adv60_b
    if adv20_a and adv60_b and adv60_b > 0:
        out["volume_expansion"] = adv20_a / adv60_b

    if im1 is not None and np.isfinite(close[im1]):
        sh = ev.pre_shares or out.get("fund_shares_outstanding")
        px_vnd = close[im1] * PRICE_SCALE
        if sh and sh > 0 and ev.expected_proceeds:
            out["event_size_pct_market_cap"] = ev.expected_proceeds / (px_vnd * sh)
        if ev.new_shares and ev.pre_shares and ev.pre_shares > 0:
            out["dilution_pct"] = ev.new_shares / ev.pre_shares
        if ev.offering_price and px_vnd > 0:
            out["discount_pct"] = ev.offering_price / px_vnd - 1.0

    # ex-right windows
    tex = _parse_date(ev.T0_exright)
    if tex is not None:
        iex = trading_align(di, tex, "next")
        if iex is not None:
            if iex > i0:
                out["ret_ann_to_ex_m1"] = window_return(close, i0, iex - 1)
            out["ret_ex_m5_m1"] = window_return(close, iex - 5, iex - 1)
            out["ret_ex_0_p1"] = window_return(close, iex, iex + 1)
            out["ret_ex_p1_20"] = window_return(close, iex + 1, iex + 20)
            out["ret_ex_p1_60"] = window_return(close, iex + 1, iex + 60)

    tres = _parse_date(ev.T0_result)
    if tres is not None:
        ires = trading_align(di, tres, "next")
        if ires is not None:
            out["ret_res_m5_m1"] = window_return(close, ires - 5, ires - 1)
            out["ret_res_0_p5"] = window_return(close, ires, ires + 5)
            out["ret_res_p1_20"] = window_return(close, ires + 1, ires + 20)
            out["ret_res_p1_60"] = window_return(close, ires + 1, ires + 60)

    # sector-relative (median peer return same window)
    sec = ev.sector
    peers = sector_frames.get(sec)
    if peers is not None and len(peers) > 5:
        peer_rets = []
        for psym, pdf in peers.items():
            if psym == ev.ticker:
                continue
            pdi = pd.DatetimeIndex(pdf["date"])
            pi0 = trading_align(pdi, di[i0], "next")
            if pi0 is None or pi0 + 60 >= len(pdf):
                continue
            pc = pdf["close"].astype(float).values
            pr = window_return(pc, pi0, pi0 + 60)
            if pr is not None:
                peer_rets.append(pr)
        if peer_rets and out.get("post_return_60d") is not None:
            out["sector_excess_60d"] = out["post_return_60d"] - float(np.median(peer_rets))

    out["market_regime"] = market_regime_at(sym_df.iloc[i0], vn_df, di[i0])
    return out


def enrich_ann_to_ex_from_panel(ret_df: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    """Fill ret_ann_to_ex_m1 when missing, using OHLCV panel."""
    out = ret_df.copy()
    if "ret_ann_to_ex_m1" not in out.columns:
        out["ret_ann_to_ex_m1"] = np.nan
    sym_groups = {s: g.reset_index(drop=True) for s, g in panel.groupby("symbol")}
    for idx, row in out.iterrows():
        if pd.notna(row.get("ret_ann_to_ex_m1")):
            continue
        tex, tann = _parse_date(row.get("T0_exright")), _parse_date(row.get("T0_announce"))
        if tex is None or tann is None:
            continue
        sdf = sym_groups.get(row["ticker"])
        if sdf is None:
            continue
        di = pd.DatetimeIndex(sdf["date"])
        close = sdf["close"].astype(float).values
        i0 = trading_align(di, tann, "next")
        iex = trading_align(di, tex, "next")
        if i0 is None or iex is None or iex <= i0:
            continue
        out.at[idx, "ret_ann_to_ex_m1"] = window_return(close, i0, iex - 1)
    return out


def build_horizon_summary(
    df: pd.DataFrame,
    sample_label: str,
    group_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Long-format median / hit-rate table by lifecycle phase and horizon."""
    group_cols = group_cols or ["sector"]
    rows: list[dict] = []
    for phase, label, col in HORIZON_BUCKETS:
        if col not in df.columns:
            continue
        valid = df[df[col].notna()]
        if valid.empty:
            continue
        for gcols in [[]] + [[c] for c in group_cols]:
            grouped = [("ALL", valid)] if not gcols else list(valid.groupby(gcols[0], dropna=False))
            for gkey, sub in grouped:
                s = sub[col].astype(float)
                row = {
                    "sample": sample_label,
                    "phase": phase,
                    "phase_name": {
                        "A_announce": "Quanh ngày công bố (T0)",
                        "B_ann_to_exright": "Từ công bố → ex-right",
                        "C_after_exright": "Sau ex-right",
                        "D_result": "Ngày công bố kết quả",
                    }.get(phase, phase),
                    "horizon": label,
                    "column": col,
                    "n": int(s.notna().sum()),
                    "median_return": float(s.median()),
                    "avg_return": float(s.mean()),
                    "hit_rate_gt_0": float((s > 0).mean()),
                }
                if gcols:
                    row[gcols[0]] = gkey
                rows.append(row)
    return pd.DataFrame(rows)


def write_horizon_summaries(primary: pd.DataFrame) -> Path:
    """Write combined horizon summary CSV + markdown snippet file."""
    parts = [
        build_horizon_summary(primary, "primary_all", ["sector"]),
        build_horizon_summary(primary, "primary_all", ["event_type"]),
    ]
    tier1 = primary[primary.get("analysis_tier") == "tier1_disclosed"]
    if len(tier1) > 0:
        parts.append(build_horizon_summary(tier1, "tier1_disclosed", ["event_type"]))
    rights = primary[primary["event_type"].isin(["rights_offering", "private_placement"])]
    if len(rights) > 0:
        parts.append(build_horizon_summary(rights, "rights_and_pp", ["event_type"]))

    long_df = pd.concat(parts, ignore_index=True)
    out_csv = OUT_DIR / "capital_raise_event_summary_horizons.csv"
    long_df.to_csv(out_csv, index=False)

    md_path = OUT_DIR / "capital_raise_event_summary_horizons.md"
    lines = [
        "# Capital raise — multi-horizon summary",
        "",
        f"*Generated {date.today().isoformat()} | Primary sample n={len(primary)}*",
        "",
        "Phases: **A** = T0 công bố | **B** = tới ex-right | **C** = sau ex-right | **D** = ngày kết quả.",
        "",
    ]
    for sample in long_df["sample"].unique():
        lines.append(f"## Sample: `{sample}`")
        lines.append("")
        sub = long_df[long_df["sample"] == sample]
        grp_col = "sector" if "sector" in sub.columns and sub["sector"].notna().any() else (
            "event_type" if "event_type" in sub.columns and sub["event_type"].notna().any() else None
        )
        if grp_col and sub[grp_col].notna().any() and (sub[grp_col] != "ALL").any():
            for gval in sorted(sub[grp_col].dropna().unique()):
                lines.append(f"### {grp_col}: {gval}")
                lines.append("")
                lines.append("| Phase | Horizon | n | Median | Hit>0 |")
                lines.append("|-------|---------|--:|-------:|------:|")
                gsub = sub[sub[grp_col] == gval]
                for _, r in gsub.iterrows():
                    lines.append(
                        f"| {r['phase_name']} | {r['horizon']} | {r['n']} | "
                        f"{r['median_return']:.2%} | {r['hit_rate_gt_0']:.1%} |"
                    )
                lines.append("")
        else:
            lines.append("| Phase | Horizon | n | Median | Hit>0 |")
            lines.append("|-------|---------|--:|-------:|------:|")
            overall = sub[sub.get("sector", "ALL") == "ALL"] if "sector" in sub.columns else sub
            if overall.empty:
                overall = sub.drop_duplicates(subset=["phase", "horizon"])
            for _, r in overall.iterrows():
                if grp_col and r.get(grp_col) not in (None, "ALL", np.nan):
                    continue
                lines.append(
                    f"| {r['phase_name']} | {r['horizon']} | {r['n']} | "
                    f"{r['median_return']:.2%} | {r['hit_rate_gt_0']:.1%} |"
                )
            lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return out_csv


def aggregate_summary(df: pd.DataFrame, group_col: str, ret_cols: list[str]) -> pd.DataFrame:
    rows = []
    for key, sub in df.groupby(group_col, dropna=False):
        row = {group_col: key, "count": len(sub)}
        for c in ret_cols:
            s = sub[c].dropna()
            row[f"median_{c}"] = s.median() if len(s) else np.nan
            row[f"avg_{c}"] = s.mean() if len(s) else np.nan
            row[f"hit_{c}"] = (s > 0).mean() if len(s) else np.nan
        ex = sub["excess_return_60d"].dropna()
        row["median_excess_60d"] = ex.median() if len(ex) else np.nan
        row["vnindex_outperform_60d_rate"] = (ex > 0).mean() if len(ex) else np.nan
        dd = sub["max_drawdown_60d"].dropna()
        row["median_max_drawdown_60d"] = dd.median() if len(dd) else np.nan
        vr = sub.get("volume_expansion", pd.Series(dtype=float)).dropna()
        row["median_volume_expansion"] = vr.median() if len(vr) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def build_report(
    clean: pd.DataFrame,
    merged: pd.DataFrame,
    limitations: list[str],
    disclosed: pd.DataFrame | None = None,
) -> str:
    primary = merged[~merged.get("low_liquidity", False).fillna(False)].copy()
    n_raw = len(merged)
    n_pri = len(primary)
    sec_tbl = primary.groupby("sector").size()
    typ_tbl = primary.groupby("event_type").size()
    use_tbl = primary.groupby("use_of_proceeds").size()
    lines = [
        "# Vietnam Equity Capital Raise Event Study",
        "",
        f"*Report date: {date.today().isoformat()}*",
        "",
        "## 1. Scope and methodology",
        "",
        "### Data sources",
        "- **source = FireAnt** | **method = REST API** (`restv2.fireant.vn`) for fundamentals; OHLCV panel built from FireAnt historical quotes.",
        "- **Events:** curated seed JSON + quarterly `shares_outstanding` change scan (derived).",
        "- **VNINDEX:** FireAnt historical quotes / panel.",
        "",
        "### Universe",
        f"- Panel symbols with OHLCV: {clean['ticker'].nunique()}.",
        f"- Priority sectors: Real Estate, Securities, Banks ({len(PRIORITY)} tickers in priority list).",
        f"- Primary liquidity filter: ADV50 ≥ VND {ADV_PRIMARY_VND/1e9:.0f}bn (trading value at T-1).",
        "",
        "### Event types",
        "Rights offering, private placement, stock dividend, ESOP, conversion, mixed, and derived share-count increases.",
        "",
        "### Event dates",
        "Primary anchor: **T0_announce**. Ex-right and result dates used when available. Calendar dates aligned to next trading day.",
        "",
        "### Return windows",
        "Standard pre/event/post windows per research brief; see `capital_raise_event_returns.csv` columns.",
        "",
        "### Adjustments and limitations",
    ]
    lines.extend([f"- {x}" for x in limitations])
    lines.extend(
        [
            "",
            "## 2. Dataset overview",
            "",
            f"- Raw / merged events: **{n_raw}**",
            f"- Primary-analysis events (liquidity pass): **{n_pri}**",
            "",
            "### Events by sector",
            "```",
            sec_tbl.to_string(),
            "```",
            "",
            "### Events by event type",
            "```",
            typ_tbl.to_string(),
            "```",
            "",
            "### Events by use of proceeds",
            "```",
            use_tbl.to_string(),
            "```",
            "",
        ]
    )
    if len(disclosed) > 0:
        lines.extend(
            [
                "### Disclosed events only (tier 1, n="
                f"{len(disclosed)})",
                f"- Median post T+60: **{disclosed['post_return_60d'].median():.2%}** | "
                f"VNINDEX excess: **{disclosed['excess_return_60d'].median():.2%}**",
                "",
            ]
        )
        ro = disclosed[disclosed["event_type"] == "rights_offering"]
        pp = disclosed[disclosed["event_type"] == "private_placement"]
        if len(ro) and len(pp):
            lines.append(
                f"- Rights (n={len(ro)}) median post60={ro['post_return_60d'].median():.2%} vs "
                f"Private placement (n={len(pp)})={pp['post_return_60d'].median():.2%}"
            )
        lines.append("")

    if n_pri > 0:
        lines.extend(
            [
                "## 3. Overall price behavior (primary sample)",
                "",
                f"- Median pre-event 60d return (T-60→T-1): **{primary['pre_runup_60d'].median():.2%}**",
                f"- Median post T+20 (T0→T+20): **{primary['post_return_20d'].median():.2%}**",
                f"- Median post T+60: **{primary['post_return_60d'].median():.2%}**",
                f"- Median VNINDEX-excess T+60: **{primary['excess_return_60d'].median():.2%}**",
                f"- Hit rate T+60 > 0: **{(primary['post_return_60d'] > 0).mean():.1%}**",
                f"- Outperform VNINDEX T+60: **{(primary['excess_return_60d'] > 0).mean():.1%}**",
                "",
                "## 4. By sector",
                "",
            ]
        )
        for sec in ["real_estate", "securities", "banks", "other"]:
            sub = primary[primary["sector"] == sec]
            if len(sub) == 0:
                continue
            lines.append(
                f"### {sec.replace('_', ' ').title()} (n={len(sub)}): "
                f"median pre60={sub['pre_runup_60d'].median():.2%}, "
                f"post20={sub['post_return_20d'].median():.2%}, "
                f"post60={sub['post_return_60d'].median():.2%}, "
                f"excess60={sub['excess_return_60d'].median():.2%}"
            )
        lines.extend(["", "## 5. By event type", ""])
        for et, sub in primary.groupby("event_type"):
            lines.append(
                f"- **{et}** (n={len(sub)}): median post60={sub['post_return_60d'].median():.2%}, "
                f"excess60={sub['excess_return_60d'].median():.2%}"
            )

    lines.extend(
        [
            "",
            "## 3b. Multi-horizon summary (announce → ex-right → after)",
            "",
            "Full tables: `data/research/capital_raise_event_summary_horizons.csv` and "
            "`data/research/capital_raise_event_summary_horizons.md`.",
            "",
            "Phases: **A** T0 công bố | **B** công bố→ex-right | **C** sau ex-right | **D** ngày kết quả.",
            "",
        ]
    )
    lines.extend(
        [
            "",
            "## 8. Case studies",
            "See `data/research/capital_raise_event_case_studies.csv` for top/bottom T+60 excess names.",
            "",
            "## 9. Observed empirical patterns",
            "",
            "In the historical sample, post-announcement returns are heterogeneous. "
            "Events with disclosed debt-repayment purpose and derived-only metadata should be interpreted separately. "
            "Results may be affected by market regime, incomplete event calendars, and unadjusted OHLCV around ex-right dates. "
            "**This does not imply causation.**",
            "",
            "## 10. Open questions",
            "",
        ]
    )
    lines.extend([f"- {x}" for x in limitations])
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-shares-scan", action="store_true", help="Use seed events only (faster)")
    ap.add_argument("--use-derived-cache", action="store_true", help="Load derived events from cache file")
    ap.add_argument("--priority-only-scan", action="store_true", help="Shares scan: priority tickers only")
    ap.add_argument("--max-symbols", type=int, default=0, help="Limit shares scan (0=all panel)")
    ap.add_argument(
        "--horizon-summary-only",
        action="store_true",
        help="Rebuild horizon summary CSV/MD from existing returns file (no API)",
    )
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.horizon_summary_only:
        ret_path = OUT_DIR / "capital_raise_event_returns.csv"
        if not ret_path.exists():
            print(f"Missing {ret_path}; run full study first.")
            sys.exit(1)
        ret_df = pd.read_csv(ret_path)
        panel = load_panel()
        ret_df = enrich_ann_to_ex_from_panel(ret_df, panel)
        primary = ret_df[
            ~ret_df.get("low_liquidity", False).fillna(False)
            & ret_df.get("post_return_60d").notna()
        ].copy()
        out = write_horizon_summaries(primary)
        print(f"Horizon summary written: {out}")
        print(f"Markdown: {OUT_DIR / 'capital_raise_event_summary_horizons.md'}")
        sys.exit(0)
    panel = load_panel()
    symbols = sorted(s for s in panel["symbol"].unique() if _is_equity_symbol(s))
    if args.max_symbols > 0:
        symbols = symbols[: args.max_symbols]

    start = panel["date"].min().strftime("%Y-%m-%d")
    end = panel["date"].max().strftime("%Y-%m-%d")
    vn = load_vnindex(start, end, panel)

    seed = load_seed()
    derived: list[EventRow] = []
    scan_syms = sorted(PRIORITY) if args.priority_only_scan else symbols
    if args.use_derived_cache and DERIVED_CACHE.exists():
        cached = json.loads(DERIVED_CACHE.read_text(encoding="utf-8"))
        derived = [EventRow(**{k: v for k, v in r.items() if k in EventRow.__dataclass_fields__}) for r in cached]
    elif not args.skip_shares_scan:
        derived = discover_from_shares(scan_syms)
        DERIVED_CACHE.write_text(
            json.dumps([{k: getattr(e, k) for k in e.__dataclass_fields__} for e in derived], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    events = dedupe_events(seed + derived)

    sym_groups = {s: g.reset_index(drop=True) for s, g in panel.groupby("symbol")}
    sector_frames: dict[str, dict[str, pd.DataFrame]] = {sec: {} for sec in ["real_estate", "securities", "banks", "other"]}
    for sym, df in sym_groups.items():
        sector_frames[_sector(sym)][sym] = df

    client = get_client()
    raw_rows: list[dict] = []
    ret_rows: list[dict] = []

    for ev in events:
        base = {k: getattr(ev, k) for k in ev.__dataclass_fields__ if k != "extra"}
        base["company_name"] = ""
        if ev.ticker not in _NAME_CACHE:
            try:
                info = client._get(f"https://restv2.fireant.vn/symbols/{ev.ticker}")
                _NAME_CACHE[ev.ticker] = info.get("name", "") if isinstance(info, dict) else ""
            except Exception:
                _NAME_CACHE[ev.ticker] = ""
        base["company_name"] = _NAME_CACHE.get(ev.ticker, "")
        fund = attach_fundamentals(ev, client)
        base.update(fund)
        raw_rows.append(base)

        sdf = sym_groups.get(ev.ticker)
        if sdf is None:
            continue
        r = compute_event_returns(ev, sdf, vn, sector_frames.get(ev.sector, {}))
        row = {**base, **r}
        ret_rows.append(row)

    raw_df = pd.DataFrame(raw_rows)
    ret_df = pd.DataFrame(ret_rows)

    if not ret_df.empty and "T0_announce" in ret_df.columns:
        ret_df["_t0"] = pd.to_datetime(ret_df["T0_announce"], errors="coerce")
        rep: list[bool] = []
        for i, row in ret_df.iterrows():
            t = row["_t0"]
            if pd.isna(t):
                rep.append(False)
                continue
            peers = ret_df[(ret_df["ticker"] == row["ticker"]) & (ret_df.index != i)]["_t0"].dropna()
            rep.append(((peers - t).abs() <= pd.Timedelta(days=365 * 3)).any())
        ret_df["repeated_issuance"] = rep
        ret_df = ret_df.drop(columns=["_t0"])

    clean_df = raw_df.copy()
    clean_df["event_type_std"] = clean_df["event_type"].map(lambda x: EVENT_TYPE_MAP.get(x, x))
    clean_df["primary_T0"] = clean_df["T0_announce"]
    clean_df["analysis_tier"] = np.where(
        clean_df["source"] != "derived_shares_outstanding",
        "tier1_disclosed",
        "tier2_derived_major_dilution",
    )
    ret_df = ret_df.merge(
        clean_df[["event_id", "analysis_tier"]],
        on="event_id",
        how="left",
        suffixes=("", "_c"),
    )

    raw_df.to_csv(OUT_DIR / "capital_raise_events_raw.csv", index=False)
    clean_df.to_csv(OUT_DIR / "capital_raise_events_clean.csv", index=False)
    ret_df.to_csv(OUT_DIR / "capital_raise_event_returns.csv", index=False)

    primary = ret_df[
        ~ret_df.get("low_liquidity", False).fillna(False)
        & ret_df.get("post_return_60d").notna()
    ].copy()
    disclosed = primary[primary.get("analysis_tier") == "tier1_disclosed"]
    ret_cols = ["pre_runup_60d", "post_return_20d", "post_return_60d", "ret_post_1_120", "excess_return_60d"]
    ret_cols = [c for c in ret_cols if c in primary.columns]

    aggregate_summary(primary, "sector", ret_cols).to_csv(
        OUT_DIR / "capital_raise_event_summary_by_sector.csv", index=False
    )
    aggregate_summary(primary, "event_type", ret_cols).to_csv(
        OUT_DIR / "capital_raise_event_summary_by_type.csv", index=False
    )
    aggregate_summary(primary, "use_of_proceeds", ret_cols).to_csv(
        OUT_DIR / "capital_raise_event_summary_by_use_of_proceeds.csv", index=False
    )
    if "market_regime" in primary.columns:
        aggregate_summary(primary, "market_regime", ret_cols).to_csv(
            OUT_DIR / "capital_raise_event_summary_by_regime.csv", index=False
        )

    # Case studies
    cs_parts = []
    if "excess_return_60d" in primary.columns:
        cs_parts.append(primary.nlargest(10, "excess_return_60d"))
        cs_parts.append(primary.nsmallest(10, "excess_return_60d"))
    if "pre_runup_60d" in primary.columns:
        cs_parts.append(primary.nlargest(10, "pre_runup_60d"))
    if "max_drawdown_60d" in primary.columns:
        cs_parts.append(primary.nsmallest(10, "max_drawdown_60d"))
    if cs_parts:
        pd.concat(cs_parts).drop_duplicates(subset=["event_id"]).to_csv(
            OUT_DIR / "capital_raise_event_case_studies.csv", index=False
        )

    horizon_csv = write_horizon_summaries(primary)

    limitations = [
        "FireAnt posts API only returns recent social posts — not used for historical event dates.",
        "FiinGroup/HOSE GetShareIssue API not available without separate license.",
        "Many events are inferred from quarterly shares_outstanding; T0_announce is proxied.",
        "OHLCV may not be dividend-adjusted; ex-right windows can conflate mechanical gaps.",
        "Seed dates for press-sourced events should be cross-checked against official disclosures.",
        "Survivorship: panel is current listed universe with history from 2018.",
    ]
    report = build_report(clean_df, ret_df, limitations, disclosed=disclosed)
    report_path = _REPO / "docs" / "research" / f"capital_raise_event_study_{REPORT_DATE}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    # Console summary
    print("=== Capital Raise Event Study ===")
    print(f"1. Raw events: {len(raw_df)}")
    print(f"2. Primary (ADV50>={ADV_PRIMARY_VND/1e9:.0f}bn): {len(primary)}")
    print("3. By sector:\n", primary.groupby("sector").size().to_string())
    print("4. By type:\n", primary.groupby("event_type").size().to_string())
    top = primary.groupby("ticker").size().sort_values(ascending=False).head(10)
    print("5. Top tickers:\n", top.to_string())
    for sec in ["real_estate", "securities", "banks"]:
        sub = primary[primary["sector"] == sec]
        if len(sub) == 0:
            continue
        print(f"6-8. {sec}: median pre60={sub['pre_runup_60d'].median():.2%} post20={sub['post_return_20d'].median():.2%} post60={sub['post_return_60d'].median():.2%} ex60={sub['excess_return_60d'].median():.2%}")
    print("9. Limitations: see report section 10")
    print("10. Files written:")
    for p in sorted(OUT_DIR.glob("capital_raise_event*.csv")) + [report_path, horizon_csv]:
        print(f"   {p}")
    print(f"   {OUT_DIR / 'capital_raise_event_summary_horizons.md'}")


if __name__ == "__main__":
    main()
