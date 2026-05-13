import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.data.fireant_client import get_client


DATA_PATH = Path("data/research/ema_cloud/ohlcv_panel_full.parquet")
OUT_DIR = Path("artifacts/composite_vn_screen")
SECTOR_L4_MAP_PATH = Path("data/research/level4_stock_scan_adv2b_all.csv")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False, min_periods=span).mean()


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def atr(df: pd.DataFrame, n: int) -> pd.Series:
    pc = df["close"].shift(1)
    tr = pd.concat(
        [
            (df["high"] - df["low"]).abs(),
            (df["high"] - pc).abs(),
            (df["low"] - pc).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(n, min_periods=n).mean()


def obv(df: pd.DataFrame) -> pd.Series:
    d = np.sign(df["close"].diff()).fillna(0.0)
    return (d * df["volume"]).cumsum()


def cmf(df: pd.DataFrame, n: int = 20) -> pd.Series:
    hl = (df["high"] - df["low"]).replace(0, np.nan)
    mfm = (((df["close"] - df["low"]) - (df["high"] - df["close"])) / hl).fillna(0.0)
    mfv = mfm * df["volume"]
    return mfv.rolling(n, min_periods=n).sum() / df["volume"].rolling(n, min_periods=n).sum()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0.0)
    dn = -d.clip(upper=0.0)
    rs = up.rolling(n, min_periods=n).mean() / dn.rolling(n, min_periods=n).mean().replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def lin_slope(y: pd.Series) -> float:
    z = y.dropna()
    if len(z) < 3:
        return np.nan
    x = np.arange(len(z))
    return float(np.polyfit(x, z.values, 1)[0])


def percentile_rank(series: pd.Series) -> pd.Series:
    return series.rank(pct=True) * 100


def resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    g = df.set_index("date").sort_index()
    w = pd.DataFrame(
        {
            "open": g["open"].resample("W-FRI").first(),
            "high": g["high"].resample("W-FRI").max(),
            "low": g["low"].resample("W-FRI").min(),
            "close": g["close"].resample("W-FRI").last(),
            "volume": g["volume"].resample("W-FRI").sum(),
            "trading_value": g["trading_value"].resample("W-FRI").sum(),
        }
    ).dropna(subset=["open", "high", "low", "close"])
    return w.reset_index()


def build_base_metrics(w: pd.DataFrame) -> dict:
    if len(w) < 20:
        return {}
    best = None
    for n in range(8, min(40, len(w)) + 1):
        s = w.tail(n)
        base_high = float(s["high"].max())
        base_low = float(s["low"].min())
        depth = (base_high - base_low) / base_high if base_high > 0 else np.nan
        pivot = base_high
        dist = s.iloc[-1]["close"] / pivot - 1 if pivot > 0 else np.nan
        score = 0
        if n >= 6:
            score += 1
        if depth < 0.15:
            score += 4
        elif depth < 0.25:
            score += 3
        elif depth < 0.35:
            score += 2
        if -0.10 <= dist <= 0.05:
            score += 4
        elif -0.15 <= dist <= 0.10:
            score += 2
        cand = {
            "n": n,
            "base_high": base_high,
            "base_low": base_low,
            "base_depth": depth,
            "pivot": pivot,
            "distance_to_pivot": dist,
            "fit_score": score,
        }
        if best is None or cand["fit_score"] > best["fit_score"]:
            best = cand
    return best or {}


def classify_stage(row: dict) -> str:
    if row["close"] > row["sma50"] > row["sma150"] > row["sma200"] and row["rs_pct"] >= 70 and row["near_52w"]:
        return "Stage 2 confirmed"
    if row["close"] > row["sma50"] and row["close"] > row["sma150"] and row["sma50"] > row["sma150"]:
        return "Stage 2 early"
    if row["close"] < row["sma200"]:
        return "Reject downtrend"
    return "Stage 1 / accumulation"


def classify_wyckoff(m: dict) -> str:
    if m.get("phase_e"):
        return "Phase E"
    if m.get("lps"):
        return "Phase D late"
    if m.get("sos"):
        return "Phase D early"
    if m.get("spring"):
        return "Phase C"
    if m.get("range"):
        return "Range"
    return "Unclear"


def refresh_panel_recent(df: pd.DataFrame, end_date: str, delay_s: float = 0.03) -> tuple[pd.DataFrame, dict]:
    client = get_client(timeout=45, cache_ttl=0)
    end_ts = pd.to_datetime(end_date)
    if pd.isna(end_ts):
        return df, {"attempted": False, "updated_symbols": 0, "appended_rows": 0, "errors": ["invalid_end_date"]}
    max_dt = pd.to_datetime(df["date"]).max()
    if max_dt >= end_ts:
        return df, {"attempted": False, "updated_symbols": 0, "appended_rows": 0, "errors": []}
    start_ts = max_dt + pd.Timedelta(days=1)
    additions = []
    updated = 0
    errors = []
    for sym in sorted(df["ticker"].astype(str).unique()):
        try:
            q = client.get_ohlcv(sym, start=start_ts.strftime("%Y-%m-%d"), end=end_ts.strftime("%Y-%m-%d"))
        except Exception as exc:
            errors.append(f"{sym}:{exc}")
            continue
        if q is None or q.empty:
            time.sleep(delay_s)
            continue
        q = q.copy()
        q["date"] = pd.to_datetime(q["date"])
        q = q[(q["date"] >= start_ts) & (q["date"] <= end_ts)]
        if q.empty:
            time.sleep(delay_s)
            continue
        q["ticker"] = sym
        q["value"] = pd.to_numeric(q.get("value"), errors="coerce")
        additions.append(q[["ticker", "date", "open", "high", "low", "close", "volume", "value"]])
        updated += 1
        time.sleep(delay_s)
    if not additions:
        return df, {"attempted": True, "updated_symbols": 0, "appended_rows": 0, "errors": errors}
    ext = pd.concat(additions, ignore_index=True).drop_duplicates(subset=["ticker", "date"], keep="last")
    merged = pd.concat([df, ext], ignore_index=True).drop_duplicates(subset=["ticker", "date"], keep="last")
    merged = merged.sort_values(["ticker", "date"]).reset_index(drop=True)
    return merged, {
        "attempted": True,
        "updated_symbols": int(updated),
        "appended_rows": int(len(ext)),
        "errors": errors,
    }


def attach_sector_l4(ranked: pd.DataFrame) -> pd.DataFrame:
    if not SECTOR_L4_MAP_PATH.exists() or ranked.empty:
        ranked["Sector L4"] = "Unknown"
        return ranked
    m = pd.read_csv(SECTOR_L4_MAP_PATH)
    keep = ["symbol", "exchange", "proxy_industryCode_l4", "proxy_industryName_l4", "date"]
    m = m[[c for c in keep if c in m.columns]].copy()
    if "date" in m.columns:
        m["date"] = pd.to_datetime(m["date"], errors="coerce")
        m = m.sort_values(["symbol", "date"]).drop_duplicates(subset=["symbol"], keep="last")
    else:
        m = m.drop_duplicates(subset=["symbol"], keep="last")
    m = m.rename(columns={"symbol": "Ticker", "exchange": "Exchange"})
    out = ranked.merge(m[["Ticker", "Exchange", "proxy_industryCode_l4", "proxy_industryName_l4"]], on="Ticker", how="left")
    ex_x = out["Exchange_x"].replace("Unknown", np.nan)
    out["Exchange"] = ex_x.fillna(out["Exchange_y"]).fillna("Unknown")
    out["Sector L4"] = (
        out["proxy_industryCode_l4"].fillna("").astype(str).str.replace(r"\.0$", "", regex=True)
        + " - "
        + out["proxy_industryName_l4"].fillna("Unknown")
    ).str.strip(" -")
    out.loc[out["Sector L4"] == "", "Sector L4"] = "Unknown"
    return out.drop(columns=["Exchange_x", "Exchange_y", "proxy_industryCode_l4", "proxy_industryName_l4"])


def run(refresh_end: str | None = None, no_refresh: bool = False, refresh_delay: float = 0.03) -> None:
    df = pd.read_parquet(DATA_PATH)
    df = df.rename(columns={"symbol": "ticker"}).copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker", "date"])
    refresh_meta = {"attempted": False, "updated_symbols": 0, "appended_rows": 0, "errors": []}
    if not no_refresh:
        tgt = refresh_end or pd.Timestamp.today().strftime("%Y-%m-%d")
        df, refresh_meta = refresh_panel_recent(df, end_date=tgt, delay_s=refresh_delay)
    as_of = df["date"].max()

    universe_close_median = float(df["close"].median())
    if 1 <= universe_close_median <= 300:
        price_unit = "thousand VND"
        px_mult = 1000.0
    elif 1000 <= universe_close_median <= 500000:
        price_unit = "VND"
        px_mult = 1.0
    else:
        price_unit = "uncertain"
        px_mult = 1.0

    df["close_vnd"] = df["close"] * px_mult
    df["reported_value"] = pd.to_numeric(df.get("value"), errors="coerce")
    computed = df["close_vnd"] * df["volume"]
    good_reported = df["reported_value"].notna() & (df["reported_value"] > 0)
    df["trading_value"] = np.where(good_reported, df["reported_value"], computed)

    initial_ticker_count = int(df["ticker"].nunique())

    basic_records = []
    warnings = []
    valid_tickers = []

    for t, g in df.groupby("ticker"):
        g = g.sort_values("date").copy()
        if len(g) < 250:
            basic_records.append({"ticker": t, "eligible": False, "reason": "insufficient_history"})
            continue
        last50 = g.tail(50)
        if len(last50) < 50:
            basic_records.append({"ticker": t, "eligible": False, "reason": "insufficient_adv50_window"})
            continue
        bad_50 = ((last50["volume"] <= 0) | (last50["trading_value"] <= 0) | last50["volume"].isna() | last50["trading_value"].isna()).mean()
        ratio = np.nan
        unit_flag = False
        cmp = g[good_reported.loc[g.index]].copy()
        if len(cmp) > 80:
            cv = (cmp["close_vnd"] * cmp["volume"]).replace(0, np.nan)
            rr = (cmp["reported_value"] / cv).replace([np.inf, -np.inf], np.nan).dropna()
            if len(rr) > 20:
                ratio = float(rr.median())
                near1 = 0.5 <= ratio <= 2.0
                suspicious_scales = any(lo <= ratio <= hi for lo, hi in [(5, 20), (50, 200), (500, 2000), (5e5, 2e6)])
                unit_flag = (not near1) and suspicious_scales
        adv50 = float(last50["trading_value"].mean())
        med250 = float(g.tail(250)["trading_value"].median())
        spike_flag = bool(med250 > 0 and adv50 > 100 * med250)
        unreliable = bad_50 > 0.10
        px_flag = bool(g["close_vnd"].iloc[-1] < 5000)
        if unit_flag:
            warnings.append({"ticker": t, "warning": "unit_sanity_fail", "ratio": ratio})
        if unreliable:
            warnings.append({"ticker": t, "warning": "liquidity data unreliable"})
        if spike_flag:
            warnings.append({"ticker": t, "warning": "possible data unit error"})
        eligible = (not unit_flag) and (not unreliable) and (adv50 >= 2_000_000_000)
        basic_records.append(
            {
                "ticker": t,
                "eligible": eligible,
                "reason": "ok" if eligible else "liquidity_or_unit_fail",
                "adv50": adv50,
                "bad_50_ratio": bad_50,
                "unit_ratio": ratio,
                "unit_flag": unit_flag,
                "spike_flag": spike_flag,
                "close_below_5000": px_flag,
            }
        )
        if eligible:
            valid_tickers.append(t)

    basic_df = pd.DataFrame(basic_records)
    sufficient_data_count = int((basic_df["reason"] != "insufficient_history").sum())
    liquidity_pass_count = int(basic_df["eligible"].sum())

    # First pass for momentum percentile (no VNINDEX/VN30 in panel).
    mom = []
    feats = {}
    for t in valid_tickers:
        g = df[df["ticker"] == t].sort_values("date").copy()
        close = g["close"]
        r3 = close.iloc[-1] / close.iloc[-63] - 1 if len(close) > 63 else np.nan
        r6 = close.iloc[-1] / close.iloc[-126] - 1 if len(close) > 126 else np.nan
        r12 = close.iloc[-1] / close.iloc[-252] - 1 if len(close) > 252 else np.nan
        raw = 0.4 * r3 + 0.3 * r6 + 0.3 * r12
        mom.append({"ticker": t, "mom_raw": raw})
        feats[t] = {"r3": r3, "r6": r6, "r12": r12}
    mom_df = pd.DataFrame(mom)
    mom_df["rs_pct"] = percentile_rank(mom_df["mom_raw"])
    rs_map = dict(zip(mom_df["ticker"], mom_df["rs_pct"]))

    rows = []
    rejected = []
    as_of_week_end = (as_of + pd.offsets.Week(weekday=4)).normalize()
    partial_week = bool(as_of < as_of_week_end)

    for t in valid_tickers:
        g = df[df["ticker"] == t].sort_values("date").copy()
        g = g[g["date"] <= as_of].copy()
        g["sma20"] = sma(g["close"], 20)
        g["sma50"] = sma(g["close"], 50)
        g["sma150"] = sma(g["close"], 150)
        g["sma200"] = sma(g["close"], 200)
        g["ema10"] = ema(g["close"], 10)
        g["ema20"] = ema(g["close"], 20)
        g["ema50"] = ema(g["close"], 50)
        g["atr14"] = atr(g, 14)
        g["atr_pct"] = g["atr14"] / g["close"]
        mid = g["sma20"]
        std20 = g["close"].rolling(20, min_periods=20).std()
        g["bb_width"] = ((mid + 2 * std20) - (mid - 2 * std20)) / mid
        g["obv"] = obv(g)
        g["obv_ma20"] = sma(g["obv"], 20)
        g["obv_ma50"] = sma(g["obv"], 50)
        g["cmf20"] = cmf(g, 20)
        g["rsi14"] = rsi(g["close"], 14)
        lo = g["rsi14"].rolling(14, min_periods=14).min()
        hi = g["rsi14"].rolling(14, min_periods=14).max()
        stoch = ((g["rsi14"] - lo) / (hi - lo).replace(0, np.nan)) * 100
        g["stoch_k"] = sma(stoch, 3)
        g["stoch_d"] = sma(g["stoch_k"], 3)
        macd = ema(g["close"], 12) - ema(g["close"], 26)
        signal = ema(macd, 9)
        g["macd_hist"] = macd - signal

        dd = (
            (g["close"] <= g["close"].shift(1) * (1 - 0.002))
            & (g["volume"] > g["volume"].shift(1))
        ).tail(25)
        dist_days = int(dd.sum())

        w = resample_weekly(g[["date", "open", "high", "low", "close", "volume", "trading_value"]])
        w["w_ema10"] = ema(w["close"], 10)
        w["w_ema20"] = ema(w["close"], 20)
        w["w_ema50"] = ema(w["close"], 50)
        w["w_sma30"] = sma(w["close"], 30)
        w["w_sma40"] = sma(w["close"], 40)
        w["w_sma10"] = sma(w["close"], 10)
        w["w_sma20"] = sma(w["close"], 20)
        w["w_atr14"] = atr(w.rename(columns={"date": "date"}), 14)
        w["w_atr_pct"] = w["w_atr14"] / w["close"]
        wmid = sma(w["close"], 20)
        wstd = w["close"].rolling(20, min_periods=20).std()
        w["w_bb_width"] = ((wmid + 2 * wstd) - (wmid - 2 * wstd)) / wmid
        w["obv"] = obv(w.rename(columns={"date": "date"}))
        w["obv_ma20"] = sma(w["obv"], 20)

        if len(w) < 25:
            rejected.append({"ticker": t, "reason": "insufficient weekly bars"})
            continue

        latest = g.iloc[-1]
        wl = w.iloc[-1]
        base = build_base_metrics(w)
        if not base:
            rejected.append({"ticker": t, "reason": "no_valid_base_window"})
            continue

        high_52w = float(g["high"].tail(252).max())
        low_52w = float(g["low"].tail(252).min())
        dist_high = latest["close"] / high_52w - 1 if high_52w > 0 else np.nan
        dist_low = latest["close"] / low_52w - 1 if low_52w > 0 else np.nan
        near_52w = bool(latest["close"] >= 0.85 * high_52w)

        atr_contr = float(w["w_atr_pct"].tail(4).mean() / w["w_atr_pct"].tail(20).mean()) if w["w_atr_pct"].tail(20).mean() > 0 else np.nan
        bb_pct = float((w["w_bb_width"].tail(52).rank(pct=True).iloc[-1] * 100)) if w["w_bb_width"].tail(52).notna().sum() >= 10 else np.nan
        c3 = w["close"].tail(3)
        c5 = w["close"].tail(5)
        r3w = float((c3.max() - c3.min()) / c3.mean()) if len(c3) == 3 and c3.mean() > 0 else np.nan
        r5w = float((c5.max() - c5.min()) / c5.mean()) if len(c5) == 5 and c5.mean() > 0 else np.nan
        vol_dry = float(w["volume"].tail(4).mean() / w["volume"].tail(20).mean()) if w["volume"].tail(20).mean() > 0 else np.nan

        # Wyckoff heuristics.
        rw = w.tail(min(100, len(w)))
        range_high = float(rw["high"].max())
        range_low = float(rw["low"].min())
        range_depth = (range_high - range_low) / range_high if range_high > 0 else np.nan
        range_valid = (len(rw) >= 12) and (0.15 <= range_depth <= 0.45)
        top_tests = int((rw["high"] >= range_high * 0.97).sum())
        bot_tests = int((rw["low"] <= range_low * 1.03).sum())
        range_flag = range_valid and (top_tests >= 2 and bot_tests >= 2)
        spring_idx = None
        spring = False
        if range_flag:
            for i in range(max(1, len(w) - 26), len(w)):
                row = w.iloc[i]
                if row["low"] < range_low * (1 - 0.01):
                    pos = (row["close"] - row["low"]) / max(1e-9, (row["high"] - row["low"]))
                    if (row["close"] > range_low) and (pos >= 0.5):
                        spring = True
                        spring_idx = i
        sos = False
        sos_idx = None
        avg20v = w["volume"].rolling(20, min_periods=20).mean()
        start_i = spring_idx + 1 if spring_idx is not None else max(1, len(w) - 12)
        for i in range(start_i, len(w)):
            row = w.iloc[i]
            ret = row["close"] / w.iloc[i - 1]["close"] - 1
            pos = (row["close"] - row["low"]) / max(1e-9, (row["high"] - row["low"]))
            if ret > 0.05 and row["volume"] > 1.2 * avg20v.iloc[i] and pos >= 0.65:
                if row["close"] >= (range_low + range_high) / 2:
                    sos = True
                    sos_idx = i
        lps = False
        if sos and sos_idx is not None and sos_idx < len(w) - 1:
            sos_high = w.iloc[sos_idx]["high"]
            sos_vol = w.iloc[sos_idx]["volume"]
            for i in range(sos_idx + 1, len(w)):
                row = w.iloc[i]
                depth = (sos_high - row["low"]) / sos_high
                hold = row["low"] > max(range_low, (range_low + range_high) / 2)
                if depth < 0.15 and row["volume"] < sos_vol and hold:
                    lps = True
        phase_e = bool(w.iloc[-1]["close"] > range_high and w.iloc[-1]["volume"] > 1.2 * avg20v.iloc[-1]) if range_flag and not np.isnan(avg20v.iloc[-1]) else False
        wy_phase = classify_wyckoff({"range": range_flag, "spring": spring, "sos": sos, "lps": lps, "phase_e": phase_e})

        up = w["close"] > w["close"].shift(1)
        dn = w["close"] < w["close"].shift(1)
        upvol = w.loc[up, "volume"].tail(20).mean()
        dnvol = w.loc[dn, "volume"].tail(20).mean()
        ud_ratio = float(upvol / dnvol) if (dnvol is not None and dnvol > 0 and not np.isnan(dnvol)) else np.nan
        obv_slope20w = lin_slope(w["obv"].tail(20))
        obv_status = "positive" if (w["obv"].iloc[-1] > w["obv_ma20"].iloc[-1] and obv_slope20w > 0) else "weak"

        breakout_vol_ratio = float(w["volume"].iloc[-1] / avg20v.iloc[-1]) if (not np.isnan(avg20v.iloc[-1]) and avg20v.iloc[-1] > 0) else np.nan
        stage = classify_stage(
            {
                "close": latest["close"],
                "sma50": latest["sma50"],
                "sma150": latest["sma150"],
                "sma200": latest["sma200"],
                "rs_pct": rs_map.get(t, np.nan),
                "near_52w": near_52w,
            }
        )

        # Scoring blocks.
        trend_score = 0
        if latest["close"] > latest["sma50"] and latest["close"] > latest["sma150"] and latest["close"] > latest["sma200"]:
            trend_score += 5
        if latest["sma50"] > latest["sma150"] > latest["sma200"] and wl["w_ema10"] >= wl["w_ema20"] >= wl["w_ema50"]:
            trend_score += 5
        if latest["sma200"] > g["sma200"].shift(20).iloc[-1]:
            trend_score += 3
        if latest["close"] >= 0.90 * high_52w:
            trend_score += 3
        elif latest["close"] >= 0.85 * high_52w:
            trend_score += 2
        rs_pct = float(rs_map.get(t, np.nan))
        if rs_pct >= 85:
            trend_score += 4
        elif rs_pct >= 70:
            trend_score += 3
        elif rs_pct >= 55:
            trend_score += 2

        base_score = 0
        if base["n"] >= 6:
            base_score += 4
        d = base["base_depth"]
        if d < 0.15:
            base_score += 4
        elif d < 0.25:
            base_score += 3
        elif d < 0.35:
            base_score += 2
        if (not np.isnan(atr_contr) and atr_contr < 0.75) or (not np.isnan(bb_pct) and bb_pct < 30):
            base_score += 2
        if (not np.isnan(atr_contr) and atr_contr < 0.60) or (not np.isnan(bb_pct) and bb_pct < 15):
            base_score += 2
        if (not np.isnan(r3w) and r3w < 0.05):
            base_score += 2
        if (not np.isnan(r5w) and r5w < 0.08):
            base_score += 2
        if not np.isnan(vol_dry) and vol_dry < 0.8:
            base_score += 4

        wyckoff_score = 0
        if range_flag:
            wyckoff_score += 4
        if spring:
            wyckoff_score += 5
        if sos:
            wyckoff_score += 4
        if lps:
            wyckoff_score += 4
        if wy_phase in ("Phase D late", "Phase E"):
            wyckoff_score += 3

        mf_score = 0
        if obv_status == "positive":
            mf_score += 5
        if obv_slope20w > 0:
            mf_score += 4
        cmf_last = latest["cmf20"]
        cmf_slope = lin_slope(g["cmf20"].tail(8))
        if cmf_last > 0.05:
            mf_score += 4
        elif cmf_last > -0.05:
            mf_score += 2
        elif cmf_slope > 0:
            mf_score += 1
        if not np.isnan(ud_ratio) and ud_ratio > 1.5:
            mf_score += 3
        elif not np.isnan(ud_ratio) and ud_ratio > 1.2:
            mf_score += 2
        if not np.isnan(breakout_vol_ratio) and breakout_vol_ratio > 1.5:
            mf_score += 4
        elif not np.isnan(breakout_vol_ratio) and breakout_vol_ratio >= 1.2:
            mf_score += 3
        elif not np.isnan(breakout_vol_ratio) and breakout_vol_ratio >= 1.0:
            mf_score += 1

        pivot = float(base["pivot"])
        close = float(latest["close"])
        dist_pivot = close / pivot - 1 if pivot > 0 else np.nan
        ema10_w = float(wl["w_ema10"])
        ema20_w = float(wl["w_ema20"])
        midpoint = (range_low + range_high) / 2
        nearest_support = float(max(min(pivot, close), ema10_w, ema20_w, midpoint))
        hard_stop = float(min(ema20_w, midpoint, range_low))
        if spring_idx is not None:
            hard_stop = float(min(hard_stop, w.iloc[spring_idx]["low"]))
        stop_distance = (close - hard_stop) / close if close > 0 else np.nan
        nearest_resistance = float(max(pivot, high_52w))
        upside = nearest_resistance / close - 1 if close > 0 else np.nan
        rr_proxy = upside / stop_distance if (stop_distance is not None and stop_distance > 0 and not np.isnan(stop_distance)) else np.nan
        extended = bool((close / latest["sma50"] - 1 > 0.20) or (w.iloc[-1]["close"] / ema10_w - 1 > 0.12) or (g["stoch_k"].iloc[-1] > 90 and dist_pivot > 0.10))

        entry_score = 0
        if -0.05 <= dist_pivot <= 0.03:
            entry_score += 4
        elif -0.10 <= dist_pivot <= 0.08:
            entry_score += 2
        if not extended:
            entry_score += 3
        if not np.isnan(stop_distance) and stop_distance <= 0.12:
            entry_score += 3
        elif not np.isnan(stop_distance) and stop_distance <= 0.15:
            entry_score += 2
        if not np.isnan(rr_proxy) and rr_proxy >= 2:
            entry_score += 3
        elif not np.isnan(rr_proxy) and rr_proxy >= 1.3:
            entry_score += 2
        if dist_days <= 2:
            entry_score += 2
        elif dist_days <= 4:
            entry_score += 1

        dq_score = 5
        if basic_df.set_index("ticker").loc[t, "spike_flag"]:
            dq_score -= 1
        if basic_df.set_index("ticker").loc[t, "bad_50_ratio"] > 0.05:
            dq_score -= 1
        dq_score = max(0, dq_score)

        total = trend_score + base_score + wyckoff_score + mf_score + entry_score + dq_score
        if total >= 85:
            cls = "A+ / Leader Candidate"
        elif total >= 75:
            cls = "A / Actionable Watchlist"
        elif total >= 65:
            cls = "B / Early Candidate"
        elif total >= 55:
            cls = "C / Low Priority"
        else:
            cls = "Reject"

        if stage == "Reject downtrend":
            cls = "Reject"
            total = min(total, 54)

        if total < 55:
            rejected.append({"ticker": t, "reason": "score_below_threshold"})
            continue

        key_reason = []
        if rs_pct >= 85:
            key_reason.append("RS percentile leader")
        if range_flag and (spring or sos or lps):
            key_reason.append("Wyckoff structure active")
        if base_score >= 14:
            key_reason.append("tight base contraction")
        if mf_score >= 14:
            key_reason.append("money flow confirmation")
        if not key_reason:
            key_reason.append("balanced setup")

        key_risk = []
        if extended:
            key_risk.append("extended")
        if cmf_last < -0.10:
            key_risk.append("CMF weak")
        if dist_days >= 5:
            key_risk.append("distribution risk")
        if not key_risk:
            key_risk.append("trigger not confirmed")

        rows.append(
            {
                "Ticker": t,
                "Exchange": "Unknown",
                "Latest Close": close,
                "ADV50 VND": float(basic_df.set_index("ticker").loc[t, "adv50"]),
                "Total Score": int(total),
                "Classification": cls,
                "Stage": stage,
                "Wyckoff Phase": wy_phase,
                "Trend Score": int(trend_score),
                "Base/Tightness Score": int(base_score),
                "Wyckoff Score": int(wyckoff_score),
                "Money Flow Score": int(mf_score),
                "Entry/Risk Score": int(entry_score),
                "Distance to Pivot %": float(dist_pivot * 100),
                "Pivot": pivot,
                "Nearest Support": nearest_support,
                "Hard Stop": hard_stop,
                "Stop Distance %": float(stop_distance * 100 if not np.isnan(stop_distance) else np.nan),
                "CMF20": float(cmf_last) if not np.isnan(cmf_last) else np.nan,
                "OBV Status": obv_status,
                "StochRSI K/D": f"{float(g['stoch_k'].iloc[-1]):.1f}/{float(g['stoch_d'].iloc[-1]):.1f}" if not np.isnan(g["stoch_k"].iloc[-1]) else "nan/nan",
                "Distribution Days 25D": dist_days,
                "Key Reason": "; ".join(key_reason),
                "Key Risk": "; ".join(key_risk),
                "extended_flag": extended,
                "rr_proxy": float(rr_proxy) if not np.isnan(rr_proxy) else np.nan,
                "breakout_vol_ratio": float(breakout_vol_ratio) if not np.isnan(breakout_vol_ratio) else np.nan,
                "close_below_5000_flag": bool(basic_df.set_index("ticker").loc[t, "close_below_5000"]),
                "partial_week": partial_week,
                "trigger_price": pivot,
            }
        )

    ranked = pd.DataFrame(rows).sort_values(["Total Score", "Trend Score", "Money Flow Score"], ascending=[False, False, False]).reset_index(drop=True)
    ranked = attach_sector_l4(ranked)
    ranked.insert(0, "Rank", np.arange(1, len(ranked) + 1))

    # Buckets.
    ready = ranked[(ranked["Distance to Pivot %"] >= -5) & (ranked["Distance to Pivot %"] <= 1) & (~ranked["extended_flag"])].head(20)
    pullback = ranked[(ranked["Wyckoff Phase"].isin(["Phase D late", "Phase E"])) & (ranked["Distance to Pivot %"] < 0) & (~ranked["extended_flag"])].head(20)
    early = ranked[(ranked["Wyckoff Phase"].isin(["Phase C", "Phase D early", "Range"])) & (ranked["Distance to Pivot %"] <= 0)].head(20)
    too_ext = ranked[ranked["extended_flag"]].head(20)

    summary = {
        "initial_ticker_count": initial_ticker_count,
        "sufficient_data_count": sufficient_data_count,
        "liquidity_pass_count": liquidity_pass_count,
        "price_unit_assumption": price_unit,
        "volume_unit_assumption": "shares",
        "number_of_unit_warnings": int((basic_df["unit_flag"] == True).sum()),
        "as_of_date": as_of.strftime("%Y-%m-%d"),
        "benchmark_status": "VNINDEX/VN30 not found in panel; used internal momentum percentile only",
        "partial_week": partial_week,
        "refresh_meta": refresh_meta,
    }

    unit_warning = basic_df[basic_df["unit_flag"] == True]["ticker"].tolist()
    warn_df = pd.DataFrame(warnings)
    rej_df = pd.DataFrame(rejected)

    basic_df.to_csv(OUT_DIR / "basic_filter_status.csv", index=False)
    ranked.to_csv(OUT_DIR / "ranked_table.csv", index=False)
    ready.to_csv(OUT_DIR / "bucket_ready_near_trigger.csv", index=False)
    pullback.to_csv(OUT_DIR / "bucket_lps_pullback.csv", index=False)
    early.to_csv(OUT_DIR / "bucket_early_wyckoff.csv", index=False)
    too_ext.to_csv(OUT_DIR / "bucket_too_extended.csv", index=False)
    warn_df.to_csv(OUT_DIR / "warnings.csv", index=False)
    rej_df.to_csv(OUT_DIR / "rejected.csv", index=False)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "unit_warning_tickers.json").write_text(json.dumps(unit_warning, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("ranked_count", len(ranked))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-end", default=None, help="Refresh OHLCV up to this date (YYYY-MM-DD).")
    ap.add_argument("--no-refresh", action="store_true", help="Skip FireAnt refresh and use local parquet only.")
    ap.add_argument("--refresh-delay", type=float, default=0.03, help="Delay between FireAnt symbol calls (sec).")
    args = ap.parse_args()
    run(refresh_end=args.refresh_end, no_refresh=args.no_refresh, refresh_delay=args.refresh_delay)
