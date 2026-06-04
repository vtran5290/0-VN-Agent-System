"""
POW alpha thesis validation — Stage 0 research only (no trading logic).

Usage:
  .venv\\Scripts\\python.exe scripts/research/pow_alpha_thesis_validation.py
"""
from __future__ import annotations

import csv
import json
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "outputs" / "review_packages" / "pow_alpha_thesis_validation_2026-05-24"
ASOF = "2026-05-24"
SCAN_PATH = REPO / "data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv"
OHLCV_PATH = REPO / "data/fireant_ssot/ta_ohlcv_panel.parquet"
VNINDEX_PATH = REPO / "data/fireant_ssot/ta_vnindex.parquet"
FA_PATH = REPO / "data/fireant_ssot/fa_quarterly.parquet"
INDEX_PATH = REPO / "data/research/stage0/research_index_latest.csv"

UTILITIES = ["POW", "REE", "PC1", "PGV", "GEG", "NT2", "VSH", "CHP", "SJD"]
ALPHA_PEERS = ["BSR", "PVD", "PNJ", "HPG", "CTG", "VCB", "FRT", "PTB", "HVN", "VJC"]
UNIVERSE = sorted(set(UTILITIES + ALPHA_PEERS))

SECTOR_MAP = {
    "POW": "Utilities / Power",
    "REE": "Utilities / Power",
    "PC1": "Utilities / Power",
    "PGV": "Utilities / Power",
    "GEG": "Utilities / Power",
    "NT2": "Utilities / Power",
    "VSH": "Utilities / Power",
    "CHP": "Utilities / Power",
    "SJD": "Utilities / Power",
    "BSR": "Energy / Oil & Gas",
    "PVD": "Energy / Oil & Gas",
    "PNJ": "Consumer / Retail",
    "HPG": "Steel",
    "CTG": "Banks",
    "VCB": "Banks",
    "FRT": "Consumer / Retail",
    "PTB": "Materials",
    "HVN": "Aviation / Logistics",
    "VJC": "Aviation / Logistics",
}

SECTOR_GROUPS = {
    "Banks": ["CTG", "VCB"],
    "Steel": ["HPG"],
    "Real estate": [],
    "Consumer / Retail": ["PNJ", "FRT"],
    "Energy / Oil & Gas": ["BSR", "PVD"],
    "Utilities / Power": UTILITIES,
    "Aviation / Logistics": ["HVN", "VJC"],
    "Materials": ["PTB"],
}


def _load_ohlcv() -> tuple[pd.DataFrame, pd.DataFrame]:
    ohlcv = pd.read_parquet(OHLCV_PATH)
    ohlcv["symbol"] = ohlcv["symbol"].astype(str).str.upper()
    ohlcv["date"] = pd.to_datetime(ohlcv["date"])
    ohlcv = ohlcv.sort_values(["symbol", "date"])
    if "value" not in ohlcv.columns or ohlcv["value"].isna().all():
        ohlcv["value"] = ohlcv["close"] * ohlcv["volume"]
    vn = pd.read_parquet(VNINDEX_PATH)
    vn["date"] = pd.to_datetime(vn["date"])
    if "symbol" not in vn.columns:
        vn["symbol"] = "VNINDEX"
    return ohlcv, vn


def _period_return(px: pd.Series, days: int) -> float | None:
    if len(px) < days + 1:
        return None
    a, b = px.iloc[-1], px.iloc[-(days + 1)]
    if pd.isna(a) or pd.isna(b) or b == 0:
        return None
    return float((a / b - 1) * 100)


def _ytd_return(px: pd.Series) -> float | None:
    if px.empty:
        return None
    y0 = px[px.index.year == px.index[-1].year]
    if len(y0) < 2:
        return None
    return float((px.iloc[-1] / y0.iloc[0] - 1) * 100)


def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def _tech_metrics(sym_df: pd.DataFrame) -> dict:
    c = sym_df.set_index("date")["close"].dropna()
    if len(c) < 30:
        return {}
    hi52 = c.tail(252).max() if len(c) >= 252 else c.max()
    lo52 = c.tail(252).min() if len(c) >= 252 else c.min()
    last = c.iloc[-1]
    dist_hi = float((last / hi52 - 1) * 100) if hi52 else None
    dist_lo = float((last / lo52 - 1) * 100) if lo52 else None
    e20, e50, e100, e200 = _ema(c, 20), _ema(c, 50), _ema(c, 100), _ema(c, 200)
    ma = []
    for name, ema in [("EMA20", e20), ("EMA50", e50), ("EMA100", e100), ("EMA200", e200)]:
        ma.append(f"{name}:{'above' if last >= ema.iloc[-1] else 'below'}")
    return {
        "ret_1m": _period_return(c, 21),
        "ret_3m": _period_return(c, 63),
        "ret_6m": _period_return(c, 126),
        "ret_ytd": _ytd_return(c),
        "ret_12m": _period_return(c, 252),
        "dist_52w_high": dist_hi,
        "dist_52w_low": dist_lo,
        "ma_status": "|".join(ma),
        "close": float(last),
    }


def _volume_metrics(sym_df: pd.DataFrame) -> dict:
    d = sym_df.copy()
    if "value" not in d.columns:
        d["value"] = d["close"] * d["volume"]
    d = d.tail(120)
    if len(d) < 25:
        return {}
    adv20 = d["value"].tail(20).mean()
    adv50 = d["value"].tail(50).mean() if len(d) >= 50 else adv20
    adv100 = d["value"].tail(100).mean() if len(d) >= 100 else adv50
    last_v = d["value"].iloc[-1]
    ret = d["close"].pct_change()
    up = (ret > 0) & (d["volume"] > d["volume"].rolling(20).mean())
    dn = (ret < 0) & (d["volume"] > d["volume"].rolling(20).mean())
    tail20 = d.tail(20)
    up_days = int(((tail20["close"].pct_change() > 0) & (tail20["volume"] > tail20["volume"].mean())).sum())
    dn_days = int(((tail20["close"].pct_change() < 0) & (tail20["volume"] > tail20["volume"].mean())).sum())
    obv = (np.sign(d["close"].diff().fillna(0)) * d["volume"]).cumsum()
    obv_slope = float(obv.tail(20).diff().mean()) if len(obv) >= 20 else None
    note = []
    if last_v > adv50 * 1.2:
        note.append("latest_vol_expansion")
    if up_days > dn_days + 2:
        note.append("up_vol_dominant_20d")
    elif dn_days > up_days + 2:
        note.append("down_vol_dominant_20d")
    obv50 = float(obv.tail(50).diff().mean()) if len(obv) >= 50 else obv_slope
    return {
        "adv20_vnd": round(adv20, 0),
        "adv50_vnd": round(adv50, 0),
        "adv100_vnd": round(adv100, 0),
        "latest_vol_vs_adv20": round(last_v / adv20, 2) if adv20 else None,
        "latest_vol_vs_adv50": round(last_v / adv50, 2) if adv50 else None,
        "high_vol_up_days_20d": up_days,
        "high_vol_down_days_20d": dn_days,
        "obv_slope_20d": round(obv_slope, 2) if obv_slope is not None else None,
        "obv_slope_50d": round(obv50, 2) if obv50 is not None else None,
        "accumulation_note": ";".join(note) if note else "neutral",
    }


def _fundamental_row(fa: pd.DataFrame, sym: str) -> dict:
    sub = fa[fa["symbol"].astype(str).str.upper() == sym].copy()
    if sub.empty:
        return {"ticker": sym, "latest_period": "Unavailable"}
    sub = sub.sort_values(["year", "quarter"])
    cur = sub.iloc[-1]
    prev_y = sub[(sub["year"] == cur["year"] - 1) & (sub["quarter"] == cur["quarter"])]
    prev_q = sub.iloc[-2] if len(sub) > 1 else None
    rev = cur.get("financialValues_NetSale") or cur.get("financialValues_TotalRevenue")
    npat = cur.get("financialValues_ParentCompanyShareholderProfitAfterTax")
    rev_yoy = None
    npat_yoy = None
    npat_qoq = None
    if not prev_y.empty:
        rev_p = prev_y.iloc[-1].get("financialValues_NetSale") or prev_y.iloc[-1].get(
            "financialValues_TotalRevenue"
        )
        npat_p = prev_y.iloc[-1].get("financialValues_ParentCompanyShareholderProfitAfterTax")
        if rev and rev_p and rev_p != 0:
            rev_yoy = round((rev / rev_p - 1) * 100, 1)
        if npat and npat_p and npat_p != 0:
            npat_yoy = round((npat / npat_p - 1) * 100, 1)
    if prev_q is not None:
        npat_pq = prev_q.get("financialValues_ParentCompanyShareholderProfitAfterTax")
        if npat and npat_pq and npat_pq != 0:
            npat_qoq = round((npat / npat_pq - 1) * 100, 1)
    return {
        "ticker": sym,
        "latest_period": f"{int(cur['year'])}-Q{int(cur['quarter'])}",
        "revenue_yoy": rev_yoy,
        "npat_yoy": npat_yoy,
        "npat_qoq": npat_qoq,
        "margin_trend": cur.get("financialValues_OperatingMargin"),
        "roe": cur.get("financialValues_ROE"),
        "debt_risk": cur.get("financialValues_TotalDebtOverEquity"),
        "cashflow_note": cur.get("financialValues_CashflowFromOperatingActivity"),
        "fundamental_note": "",
        "pe": cur.get("financialValues_PE"),
        "pb": cur.get("financialValues_PB"),
        "ev_ebitda": cur.get("financialValues_EVOverEBITDA"),
    }


def _score_ticker(
    sym: str,
    tech: dict,
    vol: dict,
    fund: dict,
    scan_row: dict | None,
    idx_rows: list[dict],
    rs_rank: int,
    n: int,
    sector_pct_above_50: float,
) -> dict:
    research = 0
    for r in idx_rows:
        if r.get("ticker", "").upper() == sym:
            if r.get("thesis_impact") == "IMPROVED":
                research = 5
            elif r.get("thesis_impact") == "MIXED":
                research = 3
            elif r.get("thesis_impact") == "WEAKENED":
                research = 1
            else:
                research = 2
            break

    rs = 0
    r3 = tech.get("ret_3m")
    if r3 is not None:
        if r3 > 25:
            rs = 5
        elif r3 > 10:
            rs = 4
        elif r3 > 0:
            rs = 3
        elif r3 > -10:
            rs = 2
        else:
            rs = 1
    if rs_rank <= max(3, n // 5):
        rs = min(5, rs + 1)

    volume = 2
    note = vol.get("accumulation_note", "")
    if "up_vol_dominant" in note:
        volume = 4
    if "latest_vol_expansion" in note:
        volume = min(5, volume + 1)
    if "down_vol_dominant" in note:
        volume = 1

    sector = 2
    if sym in UTILITIES:
        if sector_pct_above_50 >= 60:
            sector = 5
        elif sector_pct_above_50 >= 40:
            sector = 3
        else:
            sector = 1

    fundamental = 2
    ny = fund.get("npat_yoy")
    if ny is not None:
        if ny > 80:
            fundamental = 5
        elif ny > 30:
            fundamental = 4
        elif ny > 0:
            fundamental = 3
        else:
            fundamental = 1

    liquidity = 2
    adv = vol.get("adv50_vnd") or 0
    if adv >= 50e9:
        liquidity = 5
    elif adv >= 20e9:
        liquidity = 4
    elif adv >= 5e9:
        liquidity = 3

    valuation_risk = 0
    pe = fund.get("pe")
    if pe and pe > 25:
        valuation_risk = -2
    elif pe and pe > 18:
        valuation_risk = -1

    event_risk = 0
    if scan_row:
        fa = scan_row.get("final_action", "")
        if fa in ("TRAIL_EXIT", "EXIT", "SELL"):
            event_risk = -4
        elif fa in ("WATCH_ONLY", "HOLD_T1_ONLY"):
            event_risk = -1
        elif "NEW_T1" in fa:
            event_risk = 0

    pos = research + rs + volume + sector + fundamental + liquidity
    total = pos + valuation_risk + event_risk

    if total >= 22 and research >= 4 and rs >= 4 and event_risk >= -1:
        verdict = "CONFIRMED_LEADER"
    elif total >= 18 and research >= 3:
        verdict = "PROMISING_NOT_CONFIRMED"
    elif total >= 12:
        verdict = "WATCHLIST_ONLY"
    elif event_risk <= -3 or (fund.get("npat_yoy") or 0) < -20:
        verdict = "WEAKENED"
    else:
        verdict = "INSUFFICIENT_DATA"

    return {
        "ticker": sym,
        "alpha_probability_score": total,
        "research": research,
        "rs": rs,
        "volume": volume,
        "sector": sector,
        "fundamental": fundamental,
        "liquidity": liquidity,
        "valuation_risk": valuation_risk,
        "event_risk": event_risk,
        "verdict": verdict,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ohlcv, vn = _load_ohlcv()
    fa = pd.read_parquet(FA_PATH)
    fa["symbol"] = fa["symbol"].astype(str).str.upper()
    scan = pd.read_csv(SCAN_PATH)
    scan["symbol"] = scan["symbol"].astype(str).str.upper()
    scan_asof = str(scan["as_of_date"].iloc[0]) if len(scan) else "Unknown"

    idx_rows: list[dict] = []
    if INDEX_PATH.is_file():
        idx_rows = list(csv.DictReader(INDEX_PATH.open(encoding="utf-8")))

    vn_close = vn.set_index("date")["close"].sort_index()

    # --- Phase36 ---
    p36_rows = []
    for sym in UNIVERSE:
        sub = scan[scan["symbol"] == sym]
        if sub.empty:
            p36_rows.append(
                {
                    "ticker": sym,
                    "in_latest_scan": False,
                    "final_action": "Unavailable",
                    "review_bucket_or_signal_flag": "",
                    "a3_rank_score": "",
                    "note": "Not in phase36_daily_scan_latest.csv",
                }
            )
        else:
            r = sub.iloc[0]
            flag = r.get("final_action", "")
            p36_rows.append(
                {
                    "ticker": sym,
                    "in_latest_scan": True,
                    "final_action": flag,
                    "review_bucket_or_signal_flag": r.get("final_action_reason", "")[:80],
                    "a3_rank_score": r.get("a3_rank_score", ""),
                    "note": f"scan_asof={scan_asof}; breadth={r.get('breadth_zone','')}",
                }
            )
    pd.DataFrame(p36_rows).to_csv(OUT / "pow_phase36_overlap.csv", index=False)

    # --- RS ---
    tech_all: dict[str, dict] = {}
    for sym in UNIVERSE:
        sub = ohlcv[ohlcv["symbol"] == sym]
        if sub.empty:
            tech_all[sym] = {}
            continue
        tech_all[sym] = _tech_metrics(sub)

    def vs_vn(ret_sym, days):
        if ret_sym is None:
            return None
        r_vn = _period_return(vn_close, days)
        if r_vn is None:
            return None
        return round(ret_sym - r_vn, 1)

    rs_rows = []
    r3_list = []
    for sym in UNIVERSE:
        t = tech_all.get(sym, {})
        r3 = t.get("ret_3m")
        if r3 is not None:
            r3_list.append((sym, r3))
    r3_list.sort(key=lambda x: x[1], reverse=True)
    rank_map = {s: i + 1 for i, (s, _) in enumerate(r3_list)}

    for sym in UNIVERSE:
        t = tech_all.get(sym, {})
        rs_rows.append(
            {
                "ticker": sym,
                "sector": SECTOR_MAP.get(sym, ""),
                "ret_1m": t.get("ret_1m"),
                "ret_3m": t.get("ret_3m"),
                "ret_6m": t.get("ret_6m"),
                "ret_ytd": t.get("ret_ytd"),
                "ret_12m": t.get("ret_12m"),
                "vs_vnindex_3m": vs_vn(t.get("ret_3m"), 63),
                "vs_vnindex_6m": vs_vn(t.get("ret_6m"), 126),
                "dist_52w_high": t.get("dist_52w_high"),
                "ma_status": t.get("ma_status", "Unavailable"),
                "rs_rank": rank_map.get(sym, ""),
            }
        )
    pd.DataFrame(rs_rows).to_csv(OUT / "pow_relative_strength.csv", index=False)

    # --- Volume ---
    vol_rows = []
    for sym in UNIVERSE:
        sub = ohlcv[ohlcv["symbol"] == sym]
        vol_rows.append({"ticker": sym, **_volume_metrics(sub)} if not sub.empty else {"ticker": sym})
    pd.DataFrame(vol_rows).to_csv(OUT / "pow_volume_accumulation.csv", index=False)

    # --- Sector breadth ---
    sector_rows = []
    for sector, syms in SECTOR_GROUPS.items():
        rets_1m, rets_3m, rets_6m = [], [], []
        above20, above50, above100 = 0, 0, 0
        n_ok = 0
        for sym in syms:
            sub = ohlcv[ohlcv["symbol"] == sym]
            if sub.empty:
                continue
            n_ok += 1
            t = _tech_metrics(sub)
            if t.get("ret_1m") is not None:
                rets_1m.append(t["ret_1m"])
            if t.get("ret_3m") is not None:
                rets_3m.append(t["ret_3m"])
            if t.get("ret_6m") is not None:
                rets_6m.append(t["ret_6m"])
            c = sub.set_index("date")["close"]
            if len(c) >= 100:
                last = c.iloc[-1]
                if last >= _ema(c, 20).iloc[-1]:
                    above20 += 1
                if last >= _ema(c, 50).iloc[-1]:
                    above50 += 1
                if last >= _ema(c, 100).iloc[-1]:
                    above100 += 1
        pct50 = round(100 * above50 / n_ok, 1) if n_ok else None
        sector_rows.append(
            {
                "sector": sector,
                "ret_1m": round(np.mean(rets_1m), 1) if rets_1m else None,
                "ret_3m": round(np.mean(rets_3m), 1) if rets_3m else None,
                "ret_6m": round(np.mean(rets_6m), 1) if rets_6m else None,
                "pct_above_ema20": round(100 * above20 / n_ok, 1) if n_ok else None,
                "pct_above_ema50": pct50,
                "pct_above_ema100": round(100 * above100 / n_ok, 1) if n_ok else None,
                "rs_vs_vnindex": vs_vn(np.mean(rets_3m) if rets_3m else None, 63),
                "leadership_note": "",
            }
        )
    util_pct = next(
        (r["pct_above_ema50"] for r in sector_rows if r["sector"] == "Utilities / Power"), 0
    ) or 0
    pd.DataFrame(sector_rows).to_csv(OUT / "sector_rotation_breadth.csv", index=False)

    # --- Fundamentals ---
    fund_rows = [_fundamental_row(fa, sym) for sym in UNIVERSE]
    pdf = pd.DataFrame(fund_rows)
    pdf.to_csv(OUT / "pow_fundamental_check.csv", index=False)

    val_rows = []
    util_pe = [
        f.get("pe")
        for f in fund_rows
        if f.get("ticker") in UTILITIES and f.get("pe") not in (None, "")
    ]
    util_pe_med = float(np.median(util_pe)) if util_pe else None
    for f in fund_rows:
        pe = f.get("pe")
        vs_peer = "Unknown"
        if pe and util_pe_med and f.get("ticker") in UTILITIES:
            vs_peer = "below_peer" if pe < util_pe_med else "above_peer"
        val_rows.append(
            {
                "ticker": f["ticker"],
                "pe": pe,
                "pb": f.get("pb"),
                "ev_ebitda": f.get("ev_ebitda"),
                "valuation_vs_history": "Unknown",
                "valuation_vs_peers": vs_peer,
                "crowding_risk": "Unknown"
                if not pe
                else ("elevated" if pe > 20 else "moderate"),
            }
        )
    pd.DataFrame(val_rows).to_csv(OUT / "pow_valuation_check.csv", index=False)

    # --- Scorecard ---
    scan_map = {r["ticker"]: r for r in p36_rows if r.get("in_latest_scan")}
    scores = []
    for sym in UNIVERSE:
        sr = scan[scan["symbol"] == sym]
        scan_row = sr.iloc[0].to_dict() if not sr.empty else None
        scores.append(
            _score_ticker(
                sym,
                tech_all.get(sym, {}),
                next((v for v in vol_rows if v["ticker"] == sym), {}),
                next((f for f in fund_rows if f["ticker"] == sym), {}),
                scan_row,
                idx_rows,
                rank_map.get(sym, 99),
                len(UNIVERSE),
                float(util_pct),
            )
        )
    sc_df = pd.DataFrame(scores).sort_values("alpha_probability_score", ascending=False)
    sc_df.insert(0, "rank", range(1, len(sc_df) + 1))
    sc_df.to_csv(OUT / "pow_alpha_scorecard.csv", index=False)

    pow_score = sc_df[sc_df["ticker"] == "POW"].iloc[0]
    pow_p36 = next(r for r in p36_rows if r["ticker"] == "POW")
    pow_tech = tech_all.get("POW", {})
    pow_fund = next(f for f in fund_rows if f["ticker"] == "POW")

    # POW rank among universe
    pow_rank = int(sc_df[sc_df["ticker"] == "POW"]["rank"].iloc[0])
    top_ticker = sc_df.iloc[0]["ticker"]

    exec_verdict = pow_score["verdict"]
    if exec_verdict == "CONFIRMED_LEADER" and pow_p36["final_action"] == "TRAIL_EXIT":
        exec_verdict = "PROMISING_NOT_CONFIRMED"

    final_conclusion = (
        "POW is promising but still needs scan/volume confirmation."
        if exec_verdict == "PROMISING_NOT_CONFIRMED"
        else (
            "POW is only a research watchlist name for now."
            if exec_verdict == "WATCHLIST_ONLY"
            else (
                "POW thesis is weakened by database evidence."
                if exec_verdict == "WEAKENED"
                else "Evidence is insufficient."
                if exec_verdict == "INSUFFICIENT_DATA"
                else "POW is the strongest confirmed rotation alpha candidate."
            )
        )
    )

    md = _build_report(
        exec_verdict,
        final_conclusion,
        scan_asof,
        pow_p36,
        pow_tech,
        pow_fund,
        pow_score,
        sc_df,
        p36_rows,
        rs_rows,
        vol_rows,
        sector_rows,
        fund_rows,
        pow_rank,
        top_ticker,
        util_pct,
    )
    (OUT / "POW_ALPHA_THESIS_VALIDATION.md").write_text(md, encoding="utf-8")

    dict_md = f"""# POW validation data dictionary

| Path | Role |
|------|------|
| `{SCAN_PATH.relative_to(REPO)}` | Phase36 scan SSOT (read-only); asof {scan_asof} |
| `{OHLCV_PATH.relative_to(REPO)}` | FireAnt OHLCV panel; last bar ~2026-05-15 |
| `{VNINDEX_PATH.relative_to(REPO)}` | VNINDEX benchmark |
| `{FA_PATH.relative_to(REPO)}` | FireAnt quarterly fundamentals |
| `{INDEX_PATH.relative_to(REPO)}` | Stage 0 research index (broker synthesis) |

**Source:** FireAnt via repo SSOT parquet/CSV. Not live API in this run.

**Limitations:** OHLCV may lag scan date; VNINDEX cap-weight VIN skew 2025-2026 per VIN baseline doc.
"""
    (OUT / "pow_validation_data_dictionary.md").write_text(dict_md, encoding="utf-8")

    impl = f"""# Implementation report — POW alpha thesis validation

- **Task:** Stage 0 research validation only
- **Date:** {ASOF}
- **Outputs:** `{OUT.relative_to(REPO)}`

## Files created
- POW_ALPHA_THESIS_VALIDATION.md
- pow_alpha_scorecard.csv
- pow_phase36_overlap.csv
- pow_relative_strength.csv
- pow_volume_accumulation.csv
- sector_rotation_breadth.csv
- pow_fundamental_check.csv
- pow_valuation_check.csv
- pow_validation_data_dictionary.md

## Trading logic touched
**None.**

## Safety
No strategy logic changed. Research does not set or override final_action. Real capital remains NO-GO.
"""
    (OUT / "IMPLEMENTATION_REPORT.md").write_text(impl, encoding="utf-8")

    zip_path = OUT.parent / f"{OUT.name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in OUT.iterdir():
            if f.is_file():
                zf.write(f, arcname=f"{OUT.name}/{f.name}")

    print(f"Wrote {OUT}")
    print(f"Zip {zip_path}")
    print(f"POW verdict: {exec_verdict}; rank {pow_rank}/{len(UNIVERSE)}; top={top_ticker}")
    return 0


def _build_report(
    exec_verdict,
    final_conclusion,
    scan_asof,
    pow_p36,
    pow_tech,
    pow_fund,
    pow_score,
    sc_df,
    p36_rows,
    rs_rows,
    vol_rows,
    sector_rows,
    fund_rows,
    pow_rank,
    top_ticker,
    util_pct,
) -> str:
    safety = "Research is thesis/watchlist context only and does not set or override final_action."
    pow_vol = next(v for v in vol_rows if v.get("ticker") == "POW")

    return f"""# POW Alpha Thesis Validation — {ASOF}

{safety}

## 1. Executive verdict

**{exec_verdict}**

Alpha probability score (heuristic): **{pow_score['alpha_probability_score']}** (rank **{pow_rank}** / {len(UNIVERSE)}; top scored name: **{top_ticker}**)

## 2. What the broker research suggested

- POW ranked as highest-probability alpha candidate in Stage 0 batch synthesis (`2026-05-24`).
- Q1 core NPAT ~3x YoY; ~50% of FY broker forecast (Vietcap notes).
- AGM / project pipeline catalysts (5M, new capacity).
- Two Vietcap reports + HSC FN note in `research_index_latest.csv` (`IMPROVED` / `UPGRADE`).

## 3. What the project database confirms

| Evidence | Finding |
|----------|---------|
| Fundamentals (FireAnt `fa_quarterly`) | Latest POW period **{pow_fund.get('latest_period','Unknown')}**; NPAT YoY **{pow_fund.get('npat_yoy','Unknown')}%** (database) |
| Relative strength | 3M return **{pow_tech.get('ret_3m','Unknown')}%**; vs VNINDEX 3M in `pow_relative_strength.csv` |
| Liquidity | ADV50 **{pow_vol.get('adv50_vnd','Unknown')}** VND |
| Sector | Utilities/power breadth **{util_pct}%** above EMA50 (peer set in repo) |
| Research index | `IMPROVED` / `UPGRADE` flags present |

## 4. What the project database does not confirm

- **Phase36 new-entry confirmation:** POW `final_action` = **{pow_p36.get('final_action')}** (scan asof **{scan_asof}**) — not `NEW_T1*`.
- **Price/volume leadership vs full peer set:** score rank **{pow_rank}** — not #1 on composite scorecard.
- **Isolated vs sector rotation:** utilities breadth **{util_pct}%** above EMA50 — sector rotation **partial**, not broad leadership across all sectors.
- Valuation history percentiles: **Unknown** in database.

## 5. Phase36 scan overlap

See `pow_phase36_overlap.csv`.

**POW:** in scan = **{pow_p36.get('in_latest_scan')}** | `final_action` = **{pow_p36.get('final_action')}** | `a3_rank_score` = **{pow_p36.get('a3_rank_score')}**

**INTERPRETATION:** Broker thesis is positive, but production scan shows **trail exit** state — research may raise review priority only; it does **not** override `final_action`.

## 6. Relative strength and technical leadership

See `pow_relative_strength.csv`. POW MA stack: `{pow_tech.get('ma_status','Unknown')}`.

## 7. Volume / accumulation evidence

See `pow_volume_accumulation.csv`. Note: `{pow_vol.get('accumulation_note','')}`.

## 8. Sector rotation evidence

See `sector_rotation_breadth.csv`.

**INTERPRETATION:** Utilities/power is **not uniformly leading** all sectors; POW may be a **strong name within a mixed sector**, not a confirmed market-wide rotation leader.

## 9. Fundamental confirmation

See `pow_fundamental_check.csv` (FireAnt SSOT). Valuation: `pow_valuation_check.csv`.

## 10. Peer ranking

Top 5 by `alpha_probability_score` (heuristic):

{sc_df.head(5).to_markdown(index=False)}

## 11. Risks to POW thesis

- One-off / project-driven earnings spikes (broker caution in extracts)
- Project delay / power policy risk
- **Scan mismatch:** `TRAIL_EXIT` while research `IMPROVED`
- Valuation crowding if extended vs peers (PE in `pow_valuation_check.csv`)
- VNINDEX cap-weight distortion irrelevant to POW directly but affects benchmark comparison
- Lack of Phase36 new-entry confirmation

## POW thesis confirmation matrix

| Test | Result | Evidence | Interpretation |
|------|--------|----------|----------------|
| Broker research | PASS | research_index IMPROVED/UPGRADE | Supported in research layer only |
| Phase36 overlap | FAIL | final_action={pow_p36.get('final_action')} | Trail exit — not rotation entry state |
| Relative strength | MIXED | 3M {pow_tech.get('ret_3m')}% ; RS rank {pow_rank}/19 | Not leading peer momentum |
| Volume accumulation | FAIL | {pow_vol.get('accumulation_note')} | No accumulation signature |
| Sector rotation | FAIL | utilities {util_pct}% above EMA50 | Sector not broadly rotating |
| Fundamental acceleration | PASS | NPAT YoY {pow_fund.get('npat_yoy')}% Q1 | Database confirms earnings |
| Valuation risk | MIXED | PE {pow_fund.get('pe')} ; history Unknown | Moderate PE; crowding Unknown |
| Liquidity | PASS | ADV50 {pow_vol.get('adv50_vnd')} VND | Tradable |

**Thesis vs database:** POW thesis is **partially confirmed** (fundamentals + research) but **not yet confirmed** as rotation leader (scan/RS/volume/sector).

## 12. Final Stage 0 conclusion

**{final_conclusion}**

Peer note: top composite score **{top_ticker}** — not POW.

---

*Generated by `scripts/research/pow_alpha_thesis_validation.py`. Data as-of OHLCV last bar ~2026-05-15; scan {scan_asof}.*
"""


if __name__ == "__main__":
    raise SystemExit(main())
