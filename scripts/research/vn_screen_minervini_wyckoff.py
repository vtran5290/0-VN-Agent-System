"""
VN Stock Screener — Minervini/O'Neil + Wyckoff + Volume/Money Flow
Runs on: data/fireant_ssot/ta_ohlcv_panel.parquet + ta_vnindex.parquet
Output: prints structured report to stdout
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from pathlib import Path

# ── paths ────────────────────────────────────────────────────────────────────
BASE = Path(r"D:\V\0. VN Agent System")
OHLCV_PATH  = BASE / "data/fireant_ssot/ta_ohlcv_panel.parquet"
VNIDX_PATH  = BASE / "data/fireant_ssot/ta_vnindex.parquet"

# ── thresholds ────────────────────────────────────────────────────────────────
ADV50_MIN_VND = 2_000_000_000   # 2 billion VND
MIN_BARS      = 250
MIN_ADV50_BARS = 50

# ═══════════════════════════════════════════════════════════════════════════════
# 1. LOAD & UNIT SANITY
# ═══════════════════════════════════════════════════════════════════════════════

def load_panel():
    df = pd.read_parquet(OHLCV_PATH)
    df.columns = df.columns.str.lower().str.strip()
    if "symbol" in df.columns:
        df = df.rename(columns={"symbol": "ticker"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
    return df

def unit_check(df):
    """Determine price unit (VND vs thousand-VND) per universe."""
    med_close = df["close"].median()
    if 1 <= med_close <= 500:
        price_unit = "thousand_VND"
        df["close_vnd"] = df["close"] * 1000
        df["open_vnd"]  = df["open"]  * 1000
        df["high_vnd"]  = df["high"]  * 1000
        df["low_vnd"]   = df["low"]   * 1000
    elif 500 < med_close <= 500_000:
        price_unit = "VND"
        df["close_vnd"] = df["close"]
        df["open_vnd"]  = df["open"]
        df["high_vnd"]  = df["high"]
        df["low_vnd"]   = df["low"]
    else:
        price_unit = "UNKNOWN"
        df["close_vnd"] = df["close"]
        df["open_vnd"]  = df["open"]
        df["high_vnd"]  = df["high"]
        df["low_vnd"]   = df["low"]

    # Compute trading value
    if "value" in df.columns and df["value"].notna().mean() > 0.5:
        # Check ratio to infer unit of reported value
        sample = df[df["volume"] > 0].copy()
        sample["computed_val"] = sample["close_vnd"] * sample["volume"]
        sample = sample[sample["computed_val"] > 0]
        ratio = (sample["value"] / sample["computed_val"]).median()
        if 0.5 < ratio < 2.0:
            df["tv"] = df["value"]
            vol_unit = "shares; value in VND"
        elif 0.005 < ratio < 0.05:
            # value is in millions?
            df["tv"] = df["value"] * 1000
            vol_unit = "shares; value in thousand-VND (x1000 applied)"
        else:
            df["tv"] = df["close_vnd"] * df["volume"]
            vol_unit = f"computed (ratio={ratio:.2f}, fallback to close_vnd*volume)"
    else:
        df["tv"] = df["close_vnd"] * df["volume"]
        vol_unit = "computed (no reliable value column)"

    return df, price_unit, vol_unit


def filter_universe(df):
    """Keep tickers with >= MIN_BARS days and ADV50 >= 2B VND."""
    counts = df.groupby("ticker")["date"].count()
    ok_tickers = counts[counts >= MIN_BARS].index
    df = df[df["ticker"].isin(ok_tickers)].copy()
    sufficient_count = df["ticker"].nunique()

    as_of_date = df["date"].max()

    # ADV50 per ticker
    # For each ticker: take last 50 sessions tv
    def adv50_fn(g):
        last50 = g.nlargest(MIN_ADV50_BARS, "date")
        valid = last50["tv"].replace(0, np.nan).dropna()
        if len(valid) < MIN_ADV50_BARS * 0.9:
            return np.nan
        return valid.mean()

    adv_map = df.groupby("ticker").apply(adv50_fn)
    pass_tickers = adv_map[adv_map >= ADV50_MIN_VND].index
    df = df[df["ticker"].isin(pass_tickers)].copy()
    return df, sufficient_count, adv_map, as_of_date


# ═══════════════════════════════════════════════════════════════════════════════
# 2. INDICATORS (daily)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_indicators_daily(g):
    g = g.sort_values("date").copy()
    c = g["close_vnd"]
    h = g["high_vnd"]
    l = g["low_vnd"]
    v = g["volume"]
    tv = g["tv"]

    n = len(g)

    # Moving averages
    g["sma20"]  = c.rolling(20).mean()
    g["sma50"]  = c.rolling(50).mean()
    g["sma150"] = c.rolling(150).mean()
    g["sma200"] = c.rolling(200).mean()
    g["ema10"]  = c.ewm(span=10, adjust=False).mean()
    g["ema20"]  = c.ewm(span=20, adjust=False).mean()
    g["ema50"]  = c.ewm(span=50, adjust=False).mean()

    # SMA200 slope (vs 20d ago)
    g["sma200_20d_ago"] = g["sma200"].shift(20)

    # ATR14
    prev_close = c.shift(1)
    tr = pd.concat([
        h - l,
        (h - prev_close).abs(),
        (l - prev_close).abs()
    ], axis=1).max(axis=1)
    g["atr14"] = tr.rolling(14).mean()
    g["atr_pct"] = g["atr14"] / c

    # Bollinger Band
    g["bb_mid"]   = c.rolling(20).mean()
    g["bb_std"]   = c.rolling(20).std()
    g["bb_upper"] = g["bb_mid"] + 2 * g["bb_std"]
    g["bb_lower"] = g["bb_mid"] - 2 * g["bb_std"]
    g["bb_width"] = (g["bb_upper"] - g["bb_lower"]) / g["bb_mid"].replace(0, np.nan)

    # OBV
    direction = np.sign(c.diff().fillna(0))
    obv = (direction * v).cumsum()
    g["obv"] = obv
    g["obv_ma20"] = obv.rolling(20).mean()
    g["obv_ma50"] = obv.rolling(50).mean()

    # CMF20
    denom = (h - l).replace(0, np.nan)
    mfm = ((c - l) - (h - c)) / denom
    mfv = mfm * v
    g["cmf20"] = mfv.rolling(20).sum() / v.rolling(20).sum().replace(0, np.nan)

    # RSI14
    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta).clip(lower=0).rolling(14).mean()
    rs    = gain / loss.replace(0, np.nan)
    rsi   = 100 - (100 / (1 + rs))
    g["rsi14"] = rsi

    # StochRSI
    rsi_min14 = rsi.rolling(14).min()
    rsi_max14 = rsi.rolling(14).max()
    stoch_rsi = (rsi - rsi_min14) / (rsi_max14 - rsi_min14).replace(0, np.nan)
    g["stochrsi_k"] = stoch_rsi.rolling(3).mean() * 100
    g["stochrsi_d"] = g["stochrsi_k"].rolling(3).mean()

    # MACD
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal    = macd_line.ewm(span=9, adjust=False).mean()
    g["macd"]      = macd_line
    g["macd_sig"]  = signal
    g["macd_hist"] = macd_line - signal

    # Distribution days (last 25)
    ret = c.pct_change()
    dist_day = ((ret <= -0.002) & (v > v.shift(1))).astype(int)
    g["dist_days_25d"] = dist_day.rolling(25).sum()

    # 52-week high/low
    g["high_52w"] = h.rolling(252).max()
    g["low_52w"]  = l.rolling(252).min()

    return g


# ═══════════════════════════════════════════════════════════════════════════════
# 3. WEEKLY RESAMPLE
# ═══════════════════════════════════════════════════════════════════════════════

def to_weekly(g):
    g = g.set_index("date")
    w = g.resample("W").agg({
        "open_vnd":  "first",
        "high_vnd":  "max",
        "low_vnd":   "min",
        "close_vnd": "last",
        "volume":    "sum",
        "tv":        "sum",
    }).dropna(subset=["close_vnd"])
    w.index.name = "date"
    w = w.reset_index()

    c = w["close_vnd"]
    h = w["high_vnd"]
    l = w["low_vnd"]
    v = w["volume"]

    w["w_ema10"] = c.ewm(span=10, adjust=False).mean()
    w["w_ema20"] = c.ewm(span=20, adjust=False).mean()
    w["w_ema50"] = c.ewm(span=50, adjust=False).mean()
    w["w_sma30"] = c.rolling(30).mean()
    w["w_sma40"] = c.rolling(40).mean()

    # ATR weekly
    prev_close = c.shift(1)
    tr = pd.concat([
        h - l,
        (h - prev_close).abs(),
        (l - prev_close).abs()
    ], axis=1).max(axis=1)
    w["w_atr14"]  = tr.rolling(14).mean()
    w["w_atr_pct"] = w["w_atr14"] / c.replace(0, np.nan)

    # BB weekly
    w["w_bb_mid"]   = c.rolling(20).mean()
    w["w_bb_std"]   = c.rolling(20).std()
    w["w_bb_upper"] = w["w_bb_mid"] + 2 * w["w_bb_std"]
    w["w_bb_lower"] = w["w_bb_mid"] - 2 * w["w_bb_std"]
    w["w_bb_width"] = (w["w_bb_upper"] - w["w_bb_lower"]) / w["w_bb_mid"].replace(0, np.nan)

    # OBV weekly
    direction = np.sign(c.diff().fillna(0))
    obv_w = (direction * v).cumsum()
    w["w_obv"]      = obv_w
    w["w_obv_ma20"] = obv_w.rolling(20).mean()

    # CMF20 weekly
    denom = (h - l).replace(0, np.nan)
    mfm   = ((c - l) - (h - c)) / denom
    mfv   = mfm * v
    w["w_cmf20"] = mfv.rolling(20).sum() / v.rolling(20).sum().replace(0, np.nan)

    # Volume averages
    w["vol_avg4w"]  = v.rolling(4).mean()
    w["vol_avg20w"] = v.rolling(20).mean()
    w["tv_avg4w"]   = w["tv"].rolling(4).mean()
    w["tv_avg20w"]  = w["tv"].rolling(20).mean()

    # Close-position each bar = (close-low)/(high-low)
    w["close_pos"] = ((c - l) / (h - l).replace(0, np.nan)).clip(0, 1)

    return w


# ═══════════════════════════════════════════════════════════════════════════════
# 4. STAGE 2 / MINERVINI SCORING
# ═══════════════════════════════════════════════════════════════════════════════

def stage2_score(latest_d, latest_w, vnidx_row=None):
    """Returns (score_out_of_20, stage_label, detail_dict)."""
    score = 0
    det = {}

    c    = latest_d["close_vnd"]
    s50  = latest_d.get("sma50",  np.nan)
    s150 = latest_d.get("sma150", np.nan)
    s200 = latest_d.get("sma200", np.nan)
    s200_20d = latest_d.get("sma200_20d_ago", np.nan)
    h52  = latest_d.get("high_52w", np.nan)
    l52  = latest_d.get("low_52w",  np.nan)

    # close > SMA50/150/200 (5 pts)
    above_50  = pd.notna(s50)  and c > s50
    above_150 = pd.notna(s150) and c > s150
    above_200 = pd.notna(s200) and c > s200
    ma_pts = sum([above_50, above_150, above_200])
    pts = round(ma_pts / 3 * 5)
    score += pts
    det["above_MAs"] = f"{ma_pts}/3 → {pts}pts"

    # MA alignment (5 pts)
    align_pts = 0
    if pd.notna(s50) and pd.notna(s150) and s50 > s150:
        align_pts += 2
    if pd.notna(s150) and pd.notna(s200) and s150 > s200:
        align_pts += 2
    w_e10 = latest_w.get("w_ema10", np.nan) if latest_w is not None else np.nan
    w_e20 = latest_w.get("w_ema20", np.nan) if latest_w is not None else np.nan
    w_e50 = latest_w.get("w_ema50", np.nan) if latest_w is not None else np.nan
    if pd.notna(w_e10) and pd.notna(w_e20) and w_e10 >= w_e20:
        align_pts += 1
    score += min(align_pts, 5)
    det["MA_alignment"] = f"{min(align_pts,5)}/5"

    # SMA200 / W_EMA50 flatten/up (3 pts)
    sma200_up = pd.notna(s200) and pd.notna(s200_20d) and s200 >= s200_20d * 0.999
    if sma200_up:
        score += 3
        det["sma200_trend"] = "up/flat +3"
    else:
        det["sma200_trend"] = "down 0"

    # Near 52w high (3 pts)
    dist_hi = (c / h52 - 1) if pd.notna(h52) and h52 > 0 else -1
    if dist_hi >= -0.10:
        near_pts = 3
    elif dist_hi >= -0.20:
        near_pts = 2
    elif dist_hi >= -0.30:
        near_pts = 1
    else:
        near_pts = 0
    score += near_pts
    det["dist_52w_hi"] = f"{dist_hi:.1%} → {near_pts}/3pts"

    # RS (4 pts) — use momentum percentile placeholder (filled after universe ranking)
    det["rs_pct"] = "TBD"

    # Stage label
    if above_50 and above_150 and above_200 and pd.notna(s50) and pd.notna(s150) and s50 > s150 and sma200_up:
        stage = "Stage2"
    elif above_50 and above_150:
        stage = "Stage2_early"
    elif above_50:
        stage = "Stage1_recovery"
    else:
        stage = "Stage1_or_lower"

    return score, stage, det


# ═══════════════════════════════════════════════════════════════════════════════
# 5. BASE QUALITY / TIGHTNESS (weekly)
# ═══════════════════════════════════════════════════════════════════════════════

def base_quality_score(wdf):
    """
    Returns (score_out_of_20, base_info_dict)
    wdf: weekly DataFrame sorted ascending, full history
    """
    score = 0
    info = {}

    if len(wdf) < 8:
        return 0, {"error": "insufficient weekly bars"}

    c  = wdf["close_vnd"].values
    h  = wdf["high_vnd"].values
    l  = wdf["low_vnd"].values
    v  = wdf["volume"].values
    w_atr_pct = wdf["w_atr_pct"].values
    w_bb_width = wdf["w_bb_width"].values

    # Find best base window (8–40 weeks)
    best_depth = 9999
    best_n = 0
    best_pivot = np.nan
    best_base_low = np.nan

    for n in range(8, min(41, len(wdf)+1)):
        seg = wdf.iloc[-n:]
        bh = seg["high_vnd"].max()
        bl = seg["low_vnd"].min()
        depth = (bh - bl) / bh if bh > 0 else 9999
        if depth < best_depth:
            best_depth  = depth
            best_n      = n
            best_pivot  = bh
            best_base_low = bl

    curr_close = c[-1]
    dist_to_pivot = (curr_close / best_pivot - 1) if best_pivot > 0 else -9
    info["base_n_weeks"]   = best_n
    info["base_depth_pct"] = best_depth
    info["base_pivot"]     = best_pivot
    info["base_low"]       = best_base_low
    info["dist_to_pivot"]  = dist_to_pivot

    # Duration points (4)
    if best_n >= 20:   dur_pts = 4
    elif best_n >= 12: dur_pts = 3
    elif best_n >= 8:  dur_pts = 2
    else:              dur_pts = 0
    score += dur_pts

    # Depth points (4)
    if best_depth < 0.15:    dep_pts = 4
    elif best_depth < 0.25:  dep_pts = 3
    elif best_depth < 0.35:  dep_pts = 2
    elif best_depth < 0.45:  dep_pts = 1
    else:                    dep_pts = 0
    score += dep_pts

    # ATR contraction (4)
    atr_vals = w_atr_pct[~np.isnan(w_atr_pct)]
    if len(atr_vals) >= 20:
        atr_4w  = np.nanmean(atr_vals[-4:])
        atr_20w = np.nanmean(atr_vals[-20:])
        ratio = atr_4w / atr_20w if atr_20w > 0 else 9
        info["atr_contraction"] = ratio
        if ratio < 0.60:    atr_pts = 4
        elif ratio < 0.75:  atr_pts = 3
        elif ratio < 0.90:  atr_pts = 2
        else:               atr_pts = 0
    else:
        ratio = np.nan
        info["atr_contraction"] = np.nan
        atr_pts = 0
    score += atr_pts

    # BB width percentile (4)
    bb_vals = w_bb_width[~np.isnan(w_bb_width)]
    if len(bb_vals) >= 20:
        curr_bb = bb_vals[-1]
        hist_52 = bb_vals[-52:] if len(bb_vals) >= 52 else bb_vals
        pctile = (curr_bb > hist_52).mean() * 100  # lower = tighter
        info["bb_pctile"] = pctile
        if pctile < 15:    bb_pts = 4
        elif pctile < 30:  bb_pts = 3
        elif pctile < 50:  bb_pts = 2
        else:              bb_pts = 0
    else:
        info["bb_pctile"] = np.nan
        bb_pts = 0
    score += bb_pts

    # Close tightness (4)
    if len(c) >= 5:
        c3 = c[-3:]
        c5 = c[-5:]
        r3 = (c3.max() - c3.min()) / c3.mean() if c3.mean() > 0 else 9
        r5 = (c5.max() - c5.min()) / c5.mean() if c5.mean() > 0 else 9
        info["close_range_3w"] = r3
        info["close_range_5w"] = r5
        if r3 < 0.05 and r5 < 0.08:    tight_pts = 4
        elif r3 < 0.08 and r5 < 0.12:  tight_pts = 3
        elif r3 < 0.12:                 tight_pts = 2
        else:                           tight_pts = 0
    else:
        tight_pts = 0
    score += tight_pts

    # Volume dry-up (4)
    v_clean = v[v > 0]
    if len(v_clean) >= 20:
        v4w  = np.mean(v_clean[-4:])
        v20w = np.mean(v_clean[-20:])
        vdry = v4w / v20w if v20w > 0 else 9
        info["vol_dryup"] = vdry
        if vdry < 0.65:   dry_pts = 4
        elif vdry < 0.80: dry_pts = 3
        elif vdry < 0.95: dry_pts = 2
        else:             dry_pts = 0
    else:
        dry_pts = 0
    score += dry_pts

    info["score_out20"] = score
    return score, info


# ═══════════════════════════════════════════════════════════════════════════════
# 6. WYCKOFF DETECTION (weekly)
# ═══════════════════════════════════════════════════════════════════════════════

def wyckoff_score(wdf):
    """Returns (score_out_of_20, phase_label, wyckoff_dict)."""
    score = 0
    info = {}

    if len(wdf) < 20:
        return 0, "Insufficient", {}

    c  = wdf["close_vnd"].values
    h  = wdf["high_vnd"].values
    l  = wdf["low_vnd"].values
    v  = wdf["volume"].values
    obv = wdf["w_obv"].values
    obv_ma20 = wdf["w_obv_ma20"].values
    close_pos = wdf["close_pos"].values

    # ── detect trading range ──────────────────────────────────────────────────
    # Use last 100 weeks max
    window = min(100, len(wdf))
    seg_c = c[-window:]
    seg_h = h[-window:]
    seg_l = l[-window:]
    seg_v = v[-window:]

    range_high = np.nanpercentile(seg_h, 85)
    range_low  = np.nanpercentile(seg_l, 15)
    range_depth = (range_high - range_low) / range_high if range_high > 0 else 0

    info["range_high"] = range_high
    info["range_low"]  = range_low
    info["range_depth"] = range_depth

    # Is range valid?
    range_ok = (range_depth >= 0.12) and (window >= 12)

    # Trading range score (4)
    if range_ok and range_depth < 0.50:
        tr_pts = 4
    elif range_ok:
        tr_pts = 2
    else:
        tr_pts = 0
    score += tr_pts
    info["tr_pts"] = tr_pts

    # ── spring / shakeout ─────────────────────────────────────────────────────
    spring_idx = None
    spring_pts = 0
    best_spring_score = 0
    avg_vol20w = np.nanmean(seg_v[-20:]) if len(seg_v) >= 20 else np.nanmean(seg_v)

    for i in range(max(0, len(c)-60), len(c)-2):
        week_low  = l[i]
        week_cl   = c[i]
        week_v    = v[i]
        cp        = close_pos[i] if i < len(close_pos) else 0.5

        if week_low < range_low * 0.99:  # broke below range_low
            vol_ok = week_v >= avg_vol20w * 1.0
            cl_ok  = cp >= 0.40  # closed in upper half
            # Check no lower retest in subsequent 4 weeks
            future_lows = l[i+1:min(i+9, len(l))]
            no_retest = len(future_lows) == 0 or np.min(future_lows) >= week_low * 0.99
            sp_score = 0
            if cl_ok: sp_score += 3
            if vol_ok: sp_score += 1
            if no_retest: sp_score += 1
            if sp_score > best_spring_score:
                best_spring_score = sp_score
                spring_idx = i

    if spring_idx is not None:
        spring_pts = min(best_spring_score, 5)
        info["spring_week"] = str(wdf.iloc[spring_idx]["date"])[:10]
        info["spring_low"]  = l[spring_idx]
    else:
        info["spring_week"] = "None"
        info["spring_low"]  = np.nan

    score += spring_pts
    info["spring_pts"] = spring_pts

    # ── SOS detection ─────────────────────────────────────────────────────────
    sos_pts = 0
    sos_idx = None
    start_search = (spring_idx + 1) if spring_idx is not None else max(0, len(c)-40)

    for i in range(start_search, len(c)):
        wk_ret = (c[i] / c[i-1] - 1) if i > 0 and c[i-1] > 0 else 0
        cp     = close_pos[i] if i < len(close_pos) else 0.5
        wk_v   = v[i]
        if wk_ret > 0.05 and cp >= 0.65 and wk_v >= avg_vol20w * 1.2:
            sos_pts = 4
            sos_idx = i
            break
        elif wk_ret > 0.03 and cp >= 0.55:
            if sos_pts < 2:
                sos_pts = 2
                sos_idx = i

    score += sos_pts
    info["sos_pts"] = sos_pts
    if sos_idx is not None:
        info["sos_week"] = str(wdf.iloc[min(sos_idx, len(wdf)-1)]["date"])[:10]

    # ── LPS detection ─────────────────────────────────────────────────────────
    lps_pts = 0
    if sos_idx is not None and sos_idx < len(c) - 2:
        sos_high = h[sos_idx]
        for i in range(sos_idx+1, len(c)):
            pullback_pct = (c[i] / sos_high - 1) if sos_high > 0 else -1
            cp = close_pos[i] if i < len(close_pos) else 0
            wk_v = v[i]
            # LPS: modest pullback, vol lower than SOS, close position ok
            if -0.15 < pullback_pct < -0.01 and wk_v < v[sos_idx] * 0.85:
                lps_pts = 4
                info["lps_week"] = str(wdf.iloc[i]["date"])[:10]
                break
            elif -0.20 < pullback_pct < 0 and wk_v < avg_vol20w:
                if lps_pts < 2:
                    lps_pts = 2
    score += lps_pts
    info["lps_pts"] = lps_pts

    # ── Phase classification (3 pts) ──────────────────────────────────────────
    latest_close = c[-1]
    phase_pts = 0
    if latest_close >= range_high * 0.98:
        if sos_pts > 0 and lps_pts > 0:
            phase = "PhaseE"
            phase_pts = 3
        else:
            phase = "PhaseD_late"
            phase_pts = 2
    elif sos_pts >= 3 and lps_pts >= 2:
        phase = "PhaseD_late"
        phase_pts = 3
    elif sos_pts > 0 and spring_pts > 0:
        phase = "PhaseD_early"
        phase_pts = 2
    elif spring_pts > 0:
        phase = "PhaseC"
        phase_pts = 1
    elif range_ok:
        phase = "PhaseB"
        phase_pts = 0
    else:
        phase = "Unclear"
        phase_pts = 0

    score += phase_pts
    info["phase"] = phase
    info["phase_pts"] = phase_pts
    info["wyckoff_score"] = score

    return score, phase, info


# ═══════════════════════════════════════════════════════════════════════════════
# 7. VOLUME / MONEY FLOW SCORING (weekly)
# ═══════════════════════════════════════════════════════════════════════════════

def volume_mf_score(wdf, latest_d):
    score = 0
    info = {}

    c   = wdf["close_vnd"].values
    v   = wdf["volume"].values
    obv = wdf["w_obv"].values
    obv_ma20 = wdf["w_obv_ma20"].values
    cmf  = wdf["w_cmf20"].values

    avg_vol20w = np.nanmean(v[-20:]) if len(v) >= 20 else np.nanmean(v)

    # OBV trend (5)
    obv_above_ma = pd.notna(obv[-1]) and pd.notna(obv_ma20[-1]) and obv[-1] > obv_ma20[-1]
    if len(obv) >= 20:
        obv_slope = (obv[-1] - obv[-20]) / max(abs(obv[-20]), 1) if obv[-20] != 0 else 0
    else:
        obv_slope = 0
    obv_pts = 0
    if obv_above_ma: obv_pts += 3
    if obv_slope > 0: obv_pts += 2
    score += min(obv_pts, 5)
    info["obv_above_ma"] = obv_above_ma
    info["obv_slope_20w"] = obv_slope

    # OBV absorption (4)
    # OBV trending up while price sideways
    if len(c) >= 20 and len(obv) >= 20:
        price_chg = (c[-1] / c[-20] - 1) if c[-20] > 0 else 0
        obv_chg   = (obv[-1] / abs(obv[-20]) - 1) * np.sign(obv[-20]) if obv[-20] != 0 else 0
        absorption = obv_chg > 0.05 and abs(price_chg) < 0.10
        info["obv_absorption"] = absorption
        abs_pts = 4 if absorption else (2 if obv_chg > 0 and price_chg > 0 else 0)
    else:
        abs_pts = 0
    score += abs_pts

    # CMF (4)
    cmf_cur = cmf[-1] if len(cmf) > 0 and pd.notna(cmf[-1]) else 0
    cmf_improving = len(cmf) >= 8 and np.nanmean(cmf[-4:]) > np.nanmean(cmf[-8:-4])
    info["cmf20"] = cmf_cur
    if cmf_cur > 0.10:         cmf_pts = 4
    elif cmf_cur > 0.05:       cmf_pts = 3
    elif cmf_cur >= -0.05:     cmf_pts = 2 if cmf_improving else 1
    elif cmf_improving:        cmf_pts = 1
    else:                      cmf_pts = 0
    score += cmf_pts

    # Up/down volume ratio (3)
    if len(c) >= 20:
        up_mask   = np.diff(c[-20:]) > 0
        down_mask = np.diff(c[-20:]) < 0
        up_vol    = np.mean(v[-19:][up_mask])   if up_mask.sum()   > 0 else 0
        down_vol  = np.mean(v[-19:][down_mask]) if down_mask.sum() > 0 else 1
        ud_ratio  = up_vol / down_vol if down_vol > 0 else 1
        info["ud_ratio"] = ud_ratio
        if ud_ratio >= 1.5:   ud_pts = 3
        elif ud_ratio >= 1.2: ud_pts = 2
        elif ud_ratio >= 1.0: ud_pts = 1
        else:                  ud_pts = 0
    else:
        ud_pts = 0
    score += ud_pts

    # Breakout volume (4)
    if len(v) >= 2:
        last_v = v[-1]
        bvr = last_v / avg_vol20w if avg_vol20w > 0 else 0
        info["breakout_vol_ratio"] = bvr
        if bvr >= 1.5:   bv_pts = 4
        elif bvr >= 1.2: bv_pts = 3
        elif bvr >= 1.0: bv_pts = 2
        else:            bv_pts = 0
    else:
        bv_pts = 0
    score += bv_pts

    # Determine OBV status string
    if obv_above_ma and obv_slope > 0.02:
        obv_status = "Strong"
    elif obv_above_ma:
        obv_status = "OK"
    else:
        obv_status = "Weak"

    info["obv_status"] = obv_status
    info["vmf_score"] = score
    return score, info


# ═══════════════════════════════════════════════════════════════════════════════
# 8. ENTRY TIMING & RISK (daily + weekly)
# ═══════════════════════════════════════════════════════════════════════════════

def entry_risk_score(latest_d, latest_w, base_info, wyckoff_info):
    score = 0
    info = {}

    c    = latest_d["close_vnd"]
    s50  = latest_d.get("sma50",  np.nan)
    s200 = latest_d.get("sma200", np.nan)
    atr  = latest_d.get("atr14",  np.nan)
    srsi_k = latest_d.get("stochrsi_k", np.nan)
    dist_d = latest_d.get("dist_days_25d", 0)

    pivot = base_info.get("base_pivot", np.nan)
    dist_to_pivot = base_info.get("dist_to_pivot", np.nan)
    spring_low = wyckoff_info.get("spring_low", np.nan)

    # Pivot setup
    if pd.notna(dist_to_pivot):
        if -0.08 <= dist_to_pivot <= 0.05:
            piv_pts = 4
            entry_type = "Breakout_Candidate"
        elif 0.05 < dist_to_pivot <= 0.12:
            piv_pts = 2
            entry_type = "Confirmed_Breakout"
        elif dist_to_pivot > 0.12:
            piv_pts = 0
            entry_type = "Too_Extended"
        else:
            piv_pts = 2
            entry_type = "Below_Pivot"
    else:
        piv_pts = 1
        entry_type = "Unknown"
    score += piv_pts
    info["entry_type"] = entry_type

    # Not extended (3)
    extended = False
    if pd.notna(s50) and s50 > 0:
        gap_50 = c / s50 - 1
        if gap_50 > 0.20:
            extended = True
    if pd.notna(latest_w) and latest_w is not None:
        w_e10 = latest_w.get("w_ema10", np.nan)
        if pd.notna(w_e10) and w_e10 > 0:
            gap_we10 = c / w_e10 - 1
            if gap_we10 > 0.12:
                extended = True
    ext_pts = 0 if extended else 3
    score += ext_pts
    info["extended"] = extended

    # Stop distance (3)
    # Hard stop = max(spring_low, base_low, W_EMA20 - 1 ATR)
    w_e20 = latest_w.get("w_ema20", np.nan) if latest_w is not None else np.nan
    base_low = base_info.get("base_low", np.nan)
    candidates = [x for x in [spring_low, base_low] if pd.notna(x) and x > 0 and x < c]
    if pd.notna(w_e20) and pd.notna(atr):
        candidates.append(w_e20 - atr)
    hard_stop = max(candidates) if candidates else (c * 0.88)
    stop_dist = (c - hard_stop) / c if c > 0 else 0.20
    info["hard_stop"] = hard_stop
    info["stop_dist"] = stop_dist
    if stop_dist <= 0.08:   stop_pts = 3
    elif stop_dist <= 0.12: stop_pts = 2
    elif stop_dist <= 0.15: stop_pts = 1
    else:                   stop_pts = 0
    score += stop_pts

    # R/R (3)
    h52 = latest_d.get("high_52w", np.nan)
    nearest_res = h52 if pd.notna(h52) and h52 > c else (pivot * 1.10 if pd.notna(pivot) else np.nan)
    nearest_sup = hard_stop
    if pd.notna(nearest_res) and nearest_res > c:
        upside = nearest_res / c - 1
        rr = upside / stop_dist if stop_dist > 0 else 0
        info["rr_proxy"] = rr
        if rr >= 3.0:    rr_pts = 3
        elif rr >= 2.0:  rr_pts = 2
        elif rr >= 1.5:  rr_pts = 1
        else:            rr_pts = 0
    else:
        rr_pts = 1
        info["rr_proxy"] = np.nan
    score += rr_pts

    # Distribution days (2)
    dist_d = dist_d if pd.notna(dist_d) else 0
    if dist_d <= 2:   dd_pts = 2
    elif dist_d <= 4: dd_pts = 1
    else:             dd_pts = 0
    score += dd_pts

    info["entry_score"] = score
    info["nearest_support"] = nearest_sup
    info["nearest_resistance"] = nearest_res if pd.notna(nearest_res) else np.nan
    return score, info


# ═══════════════════════════════════════════════════════════════════════════════
# 9. DATA QUALITY SCORE (5 pts)
# ═══════════════════════════════════════════════════════════════════════════════

def data_quality_score(ticker_daily, adv50_val):
    score = 0
    n_bars = len(ticker_daily)

    # Unit/value sanity (2) — if we got here ADV50 is valid
    score += 2

    # Data length (1)
    if n_bars >= 500:
        score += 1
    elif n_bars >= 250:
        score += 0

    # ADV50 stable (1) — check no single-day spike dominating
    tv_vals = ticker_daily["tv"].tail(50).replace(0, np.nan).dropna()
    if len(tv_vals) >= 40:
        q95 = tv_vals.quantile(0.95)
        q50 = tv_vals.median()
        spike_ok = q95 < q50 * 10
        score += 1 if spike_ok else 0

    # No anomaly (1)
    close_ret = ticker_daily["close_vnd"].pct_change().abs()
    anomaly = (close_ret > 0.20).sum()
    score += 1 if anomaly <= 5 else 0

    return score


# ═══════════════════════════════════════════════════════════════════════════════
# 10. MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 80)
    print("VN STOCK SCREENER — Minervini/O'Neil + Wyckoff + Volume/Money Flow")
    print("=" * 80)

    # Load
    print("\n[1] Loading data...")
    df_raw = load_panel()
    initial_count = df_raw["ticker"].nunique()
    print(f"    Loaded {len(df_raw):,} rows, {initial_count} tickers.")

    df, price_unit, vol_unit = unit_check(df_raw)
    print(f"    Price unit assumption : {price_unit}")
    print(f"    Volume/value unit     : {vol_unit}")

    # Load VNINDEX
    vnidx = None
    if VNIDX_PATH.exists():
        try:
            vnidx = pd.read_parquet(VNIDX_PATH)
            vnidx.columns = vnidx.columns.str.lower()
            vnidx["date"] = pd.to_datetime(vnidx["date"])
            vnidx = vnidx.sort_values("date")
            print(f"    VNINDEX loaded: {len(vnidx)} rows, last={vnidx['date'].max().date()}")
        except Exception as e:
            print(f"    VNINDEX load failed: {e}")

    # Filter universe
    print("\n[2] Filtering universe...")
    df, suff_count, adv_map, as_of_date = filter_universe(df)
    liq_count = df["ticker"].nunique()
    print(f"    Initial tickers        : {initial_count}")
    print(f"    After >=250 bars       : {suff_count}")
    print(f"    After ADV50 >= 2B VND  : {liq_count}")
    print(f"    As-of date             : {as_of_date.date()}")

    # Compute daily indicators per ticker
    print("\n[3] Computing daily indicators...")
    daily_grps = {}
    for ticker, grp in df.groupby("ticker"):
        try:
            daily_grps[ticker] = compute_indicators_daily(grp.copy())
        except Exception:
            pass
    print(f"    Done: {len(daily_grps)} tickers.")

    # RS calculation vs VNINDEX
    rs_scores = {}
    if vnidx is not None:
        vnidx_c = vnidx.set_index("date")["close"]
        for ticker, g in daily_grps.items():
            g2 = g.set_index("date")["close_vnd"]
            # Align on common dates
            common = g2.index.intersection(vnidx_c.index)
            if len(common) < 63:
                rs_scores[ticker] = np.nan
                continue
            s_ret_3m  = g2.loc[common[-1]] / g2.loc[common[-63]] - 1 if len(common) >= 63 else np.nan
            s_ret_6m  = g2.loc[common[-1]] / g2.loc[common[-126]] - 1 if len(common) >= 126 else np.nan
            s_ret_12m = g2.loc[common[-1]] / g2.loc[common[-252]] - 1 if len(common) >= 252 else np.nan
            i_ret_3m  = vnidx_c.loc[common[-1]] / vnidx_c.loc[common[-63]] - 1 if len(common) >= 63 else np.nan
            i_ret_6m  = vnidx_c.loc[common[-1]] / vnidx_c.loc[common[-126]] - 1 if len(common) >= 126 else np.nan
            i_ret_12m = vnidx_c.loc[common[-1]] / vnidx_c.loc[common[-252]] - 1 if len(common) >= 252 else np.nan

            exc3  = (s_ret_3m  - i_ret_3m)  if pd.notna(s_ret_3m)  and pd.notna(i_ret_3m)  else 0
            exc6  = (s_ret_6m  - i_ret_6m)  if pd.notna(s_ret_6m)  and pd.notna(i_ret_6m)  else 0
            exc12 = (s_ret_12m - i_ret_12m) if pd.notna(s_ret_12m) and pd.notna(i_ret_12m) else 0
            rs_raw = 0.4 * exc3 + 0.3 * exc6 + 0.3 * exc12
            rs_scores[ticker] = rs_raw

        # Rank percentiles
        rs_series = pd.Series(rs_scores).dropna()
        rs_pctile = rs_series.rank(pct=True) * 100
        rs_scores_pctile = rs_pctile.to_dict()
    else:
        # Momentum-based RS
        mom_scores = {}
        for ticker, g in daily_grps.items():
            c_series = g["close_vnd"]
            if len(c_series) >= 63:
                mom = c_series.iloc[-1] / c_series.iloc[-63] - 1
                mom_scores[ticker] = mom
            else:
                mom_scores[ticker] = np.nan
        mom_series = pd.Series(mom_scores).dropna()
        rs_pctile  = mom_series.rank(pct=True) * 100
        rs_scores_pctile = rs_pctile.to_dict()
        print("    (No VNINDEX — using momentum percentile for RS)")

    # Weekly indicators
    print("\n[4] Computing weekly indicators...")
    weekly_grps = {}
    for ticker, g in daily_grps.items():
        try:
            weekly_grps[ticker] = to_weekly(g)
        except Exception:
            pass
    print(f"    Done: {len(weekly_grps)} tickers.")

    # Score each ticker
    print("\n[5] Scoring all tickers...")
    results = []

    for ticker in daily_grps:
        dg = daily_grps[ticker]
        wg = weekly_grps.get(ticker)
        if dg is None or len(dg) < 50:
            continue

        adv50_val = adv_map.get(ticker, np.nan)
        if pd.isna(adv50_val) or adv50_val < ADV50_MIN_VND:
            continue

        ld = dg.iloc[-1].to_dict()   # latest daily row
        lw = wg.iloc[-1].to_dict() if wg is not None and len(wg) > 0 else None

        # Exchange — try to get from data
        exch = ld.get("exchange", "")

        # Scores
        s2_score, stage, s2_det = stage2_score(ld, lw)
        rs_pct = rs_scores_pctile.get(ticker, 50.0)
        # Add RS points to trend score (4 pts)
        if rs_pct >= 85:   rs_pts = 4
        elif rs_pct >= 70: rs_pts = 3
        elif rs_pct >= 50: rs_pts = 1
        else:              rs_pts = 0
        trend_total = min(s2_score + rs_pts, 20)

        base_sc, base_info = base_quality_score(wg) if wg is not None else (0, {})
        wyck_sc, phase, wyck_info = wyckoff_score(wg) if wg is not None else (0, "NA", {})
        vmf_sc, vmf_info = volume_mf_score(wg, ld) if wg is not None else (0, {})
        entry_sc, entry_info = entry_risk_score(ld, lw, base_info, wyck_info)
        dq_sc = data_quality_score(dg, adv50_val)

        total = trend_total + base_sc + wyck_sc + vmf_sc + entry_sc + dq_sc

        # Classification
        if total >= 85:    cls = "A+ Leader"
        elif total >= 75:  cls = "A Watchlist"
        elif total >= 65:  cls = "B Early"
        elif total >= 55:  cls = "C Low"
        else:              cls = "Reject"

        # Key reason & risk
        dist_piv = base_info.get("dist_to_pivot", np.nan)
        cmf_val  = vmf_info.get("cmf20", np.nan)
        srsi_k   = ld.get("stochrsi_k", np.nan)
        srsi_d   = ld.get("stochrsi_d", np.nan)
        dist_d_val = ld.get("dist_days_25d", 0)

        key_reasons = []
        if stage in ("Stage2", "Stage2_early"): key_reasons.append(stage)
        if wyck_info.get("spring_pts", 0) >= 3: key_reasons.append("Spring")
        if vmf_info.get("obv_status") == "Strong": key_reasons.append("OBV↑")
        if pd.notna(cmf_val) and cmf_val > 0.05: key_reasons.append(f"CMF+{cmf_val:.2f}")
        if base_sc >= 15: key_reasons.append("TightBase")
        if phase in ("PhaseD_late", "PhaseE"): key_reasons.append(phase)

        key_risks = []
        if entry_info.get("extended"): key_risks.append("Extended")
        if pd.notna(cmf_val) and cmf_val < -0.10: key_risks.append("CMF-")
        if pd.notna(dist_d_val) and dist_d_val >= 4: key_risks.append(f"DistDays={int(dist_d_val)}")
        if pd.notna(srsi_k) and srsi_k > 85: key_risks.append(f"StochRSI={srsi_k:.0f}")
        if phase in ("PhaseB", "Unclear", "Insufficient"): key_risks.append("EarlyPhase")

        results.append({
            "Ticker":       ticker,
            "Exchange":     exch,
            "Close":        round(ld["close_vnd"], 0),
            "ADV50_B":      round(adv50_val / 1e9, 2),
            "Score":        total,
            "Class":        cls,
            "Stage":        stage,
            "Phase":        phase,
            "TrendSc":      trend_total,
            "BaseSc":       base_sc,
            "WyckSc":       wyck_sc,
            "VMFSc":        vmf_sc,
            "EntrySc":      entry_sc,
            "DQSc":         dq_sc,
            "DistPivot%":   round(dist_piv * 100, 1) if pd.notna(dist_piv) else np.nan,
            "Pivot":        round(base_info.get("base_pivot", np.nan), 0) if pd.notna(base_info.get("base_pivot", np.nan)) else np.nan,
            "Support":      round(entry_info.get("nearest_support", np.nan), 0) if pd.notna(entry_info.get("nearest_support", np.nan)) else np.nan,
            "HardStop":     round(entry_info.get("hard_stop", np.nan), 0) if pd.notna(entry_info.get("hard_stop", np.nan)) else np.nan,
            "StopDist%":    round(entry_info.get("stop_dist", np.nan) * 100, 1) if pd.notna(entry_info.get("stop_dist", np.nan)) else np.nan,
            "CMF20":        round(cmf_val, 3) if pd.notna(cmf_val) else np.nan,
            "OBV_Status":   vmf_info.get("obv_status", ""),
            "StochK":       round(srsi_k, 1) if pd.notna(srsi_k) else np.nan,
            "StochD":       round(srsi_d, 1) if pd.notna(srsi_d) else np.nan,
            "DistDays":     int(dist_d_val) if pd.notna(dist_d_val) else 0,
            "RS_Pct":       round(rs_pct, 1),
            "EntryType":    entry_info.get("entry_type", ""),
            "KeyReason":    "; ".join(key_reasons),
            "KeyRisk":      "; ".join(key_risks),
            "RR":           round(entry_info.get("rr_proxy", np.nan), 2) if pd.notna(entry_info.get("rr_proxy", np.nan)) else np.nan,
            # Internal refs for deep dive
            "_base_info":   base_info,
            "_wyck_info":   wyck_info,
            "_vmf_info":    vmf_info,
            "_entry_info":  entry_info,
            "_s2_det":      s2_det,
        })

    df_res = pd.DataFrame(results).sort_values("Score", ascending=False).reset_index(drop=True)
    df_res["Rank"] = df_res.index + 1
    print(f"    Scored {len(df_res)} tickers.")

    # ═══════════════════════════════════════════════════════════════════════════
    # OUTPUT
    # ═══════════════════════════════════════════════════════════════════════════

    sep = "─" * 80

    print(f"\n{'═'*80}")
    print("  PART 1 — DATA & UNIVERSE SUMMARY")
    print(f"{'═'*80}")
    print(f"  initial_ticker_count    : {initial_count}")
    print(f"  sufficient_data_count   : {suff_count}")
    print(f"  liquidity_pass_count    : {liq_count}")
    print(f"  price_unit_assumption   : {price_unit}")
    print(f"  volume_unit_assumption  : {vol_unit}")
    print(f"  as_of_date              : {as_of_date.date()}")

    print(f"\n{'═'*80}")
    print("  PART 2 — TOP 30 RANKED TABLE")
    print(f"{'═'*80}")
    top30 = df_res.head(30)
    display_cols = [
        "Rank","Ticker","Close","ADV50_B","Score","Class","Stage","Phase",
        "TrendSc","BaseSc","WyckSc","VMFSc","EntrySc",
        "DistPivot%","Pivot","Support","HardStop","StopDist%",
        "CMF20","OBV_Status","StochK","StochD","DistDays","RS_Pct","EntryType"
    ]
    print(top30[display_cols].to_string(index=False, max_colwidth=18))

    print(f"\n{'═'*80}")
    print("  KEY REASONS & RISKS — TOP 30")
    print(f"{'═'*80}")
    for _, row in top30.iterrows():
        print(f"  #{int(row['Rank']):>2} {row['Ticker']:<8} | Reason: {row['KeyReason']}")
        print(f"      {'':<8} | Risk  : {row['KeyRisk']}")

    # ── Actionable Buckets ───────────────────────────────────────────────────
    print(f"\n{'═'*80}")
    print("  PART 3 — ACTIONABLE BUCKETS")
    print(f"{'═'*80}")

    bucket_a = df_res[(df_res["EntryType"].isin(["Breakout_Candidate"])) &
                      (df_res["Score"] >= 65)].head(10)
    bucket_b = df_res[(df_res["EntryType"] == "Confirmed_Breakout") &
                      (df_res["Score"] >= 65) &
                      (~df_res["extended"].fillna(False) if "extended" in df_res.columns else True)].head(10)
    # Filter LPS: phase D/E, not too extended
    bucket_lps = df_res[(df_res["Phase"].isin(["PhaseD_late","PhaseE"])) &
                        (df_res["EntryType"].isin(["Breakout_Candidate","Below_Pivot","Confirmed_Breakout"])) &
                        (df_res["Score"] >= 65)].head(10)
    bucket_c = df_res[(df_res["WyckSc"] >= 8) &
                      (df_res["Phase"].isin(["PhaseC","PhaseD_early","PhaseB"])) &
                      (df_res["Score"] >= 55)].head(10)
    bucket_d = df_res[(df_res["EntryType"] == "Too_Extended") &
                      (df_res["Score"] >= 70)].head(10)

    def print_bucket(label, sub_df, cols=["Rank","Ticker","Score","Class","Stage","Phase","DistPivot%","Pivot","StopDist%","CMF20","StochK","EntryType"]):
        print(f"\n  ── {label} ──")
        if len(sub_df) == 0:
            print("  (none)")
        else:
            print(sub_df[cols].to_string(index=False))

    print_bucket("A — Ready / Near Trigger", bucket_a)
    print_bucket("B — LPS / Pullback Buy Candidates", bucket_lps)
    print_bucket("C — Early Wyckoff / Accumulation Watchlist", bucket_c)
    print_bucket("D — Too Extended But Strong", bucket_d)

    # ── Deep Dive Top 10 ─────────────────────────────────────────────────────
    print(f"\n{'═'*80}")
    print("  PART 4 — DEEP DIVE TOP 10")
    print(f"{'═'*80}")

    for i, row in df_res.head(10).iterrows():
        t = row["Ticker"]
        bi = row["_base_info"]
        wi = row["_wyck_info"]
        vi = row["_vmf_info"]
        ei = row["_entry_info"]
        s2 = row["_s2_det"]

        print(f"\n  /=== #{int(row['Rank'])} {t}  |  Score: {row['Score']}/100  |  {row['Class']}")
        print(f"  ||   Close: {row['Close']:,.0f} VND  |  ADV50: {row['ADV50_B']:.2f}B VND  |  RS%ile: {row['RS_Pct']:.0f}")
        print(f"  ||")
        atr_ctr = bi.get('atr_contraction', np.nan)
        atr_ctr_str = f"{atr_ctr:.2f}" if pd.notna(atr_ctr) else "—"
        cmf_v = vi.get('cmf20', np.nan)
        cmf_str = f"{cmf_v:.3f}" if pd.notna(cmf_v) else "—"
        ud_v = vi.get('ud_ratio', np.nan)
        ud_str = f"{ud_v:.2f}" if pd.notna(ud_v) else "—"
        print(f"  ||  Current Structure : {row['Stage']} / Wyckoff {row['Phase']}")
        print(f"  ||  Base              : {bi.get('base_n_weeks','?')}w | Depth {bi.get('base_depth_pct',0):.1%} | ATR-ctr {atr_ctr_str}")
        print(f"  ||  Spring            : {wi.get('spring_week','None')} | SOS: {wi.get('sos_week','None')} | LPS: {wi.get('lps_week','None')}")
        print(f"  ||  OBV Status        : {vi.get('obv_status','?')} | CMF20: {cmf_str} | U/D Vol: {ud_str}")
        print(f"  ||  StochRSI K/D      : {row['StochK']}/{row['StochD']}")
        print(f"  ||")
        dist_piv_str = f"{row['DistPivot%']:+.1f}%" if pd.notna(row['DistPivot%']) else "--"
        print(f"  ||  Pivot             : {row['Pivot']:,.0f}  (dist {dist_piv_str})")
        print(f"  ||  Nearest Support   : {row['Support']:,.0f}")
        print(f"  ||  Hard Stop         : {row['HardStop']:,.0f}  (stop dist {row['StopDist%']}%)")
        rr_str = f"{row['RR']:.1f}x" if pd.notna(row['RR']) else "--"
        print(f"  ||  R/R proxy         : {rr_str}")
        print(f"  ||")
        better = 'Pullback to support/LPS' if row['Phase'] in ('PhaseD_late','PhaseE') else 'Wait for breakout volume'
        print(f"  ||  Entry trigger     : {row['EntryType']} -- weekly close > {row['Pivot']:,.0f} w/ vol > 1.3x avg20w")
        print(f"  ||  Better entry      : {better}")
        print(f"  ||  Invalidation      : Break below {row['HardStop']:,.0f} on volume")
        print(f"  ||  Key Reason        : {row['KeyReason']}")
        key_risk_str = row['KeyRisk'] if row['KeyRisk'] else 'None flagged'
        print(f"  ++  Key Risk          : {key_risk_str}")

    # ── Final Recommendations ─────────────────────────────────────────────────
    print(f"\n{'═'*80}")
    print("  PART 6 — FINAL RECOMMENDATIONS")
    print(f"{'═'*80}")

    top5_watch = df_res.head(5)
    near_trigger = df_res[df_res["EntryType"] == "Breakout_Candidate"].head(5)
    extended_strong = df_res[df_res["EntryType"] == "Too_Extended"].head(5)

    print(f"\n  Top 5 — Overall Best Setups:")
    for _, r in top5_watch.iterrows():
        print(f"    {int(r['Rank']):>2}. {r['Ticker']:<8} Score={r['Score']} | {r['Class']} | {r['Stage']} | {r['Phase']}")

    print(f"\n  Top 5 — Nearest Trigger (Breakout Candidates):")
    if len(near_trigger) == 0:
        print("    (none in Breakout_Candidate bucket at current scores)")
    for _, r in near_trigger.iterrows():
        dist_str = f"{r['DistPivot%']:+.1f}%" if pd.notna(r['DistPivot%']) else "—"
        print(f"    {int(r['Rank']):>2}. {r['Ticker']:<8} Score={r['Score']} | Pivot={r['Pivot']:,.0f} | Dist={dist_str}")

    print(f"\n  Top 5 — Extended / Do Not Chase Yet:")
    if len(extended_strong) == 0:
        print("    (none flagged as Too_Extended)")
    for _, r in extended_strong.iterrows():
        print(f"    {int(r['Rank']):>2}. {r['Ticker']:<8} Score={r['Score']} | {r['Stage']} — Wait for base/pullback")

    print(f"\n{'═'*80}")
    print("  END OF REPORT")
    print(f"{'═'*80}\n")

    return df_res


if __name__ == "__main__":
    result_df = main()
