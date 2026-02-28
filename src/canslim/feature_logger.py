"""
feature_logger.py
=================
Log CANSLIM features ra CSV theo ngày để:
  1. Audit / reproducibility
  2. Backtest dùng file-based inputs (tránh look-ahead bias)
  3. Distribution analysis trước khi chạy backtest lớn

Output: data/canslim_features/YYYY-MM-DD.csv
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_FEATURES_DIR = Path(__file__).parent.parent.parent / "data" / "canslim_features"


def log_features(
    df_screen: pd.DataFrame,
    date: str,
    output_dir: Optional[Path] = None,
) -> Path:
    """
    Lưu kết quả run_daily_screen() ra CSV với tên YYYY-MM-DD.csv.

    Args:
        df_screen: output của run_daily_screen()
        date: "YYYY-MM-DD" — ngày scan
        output_dir: thư mục lưu CSV (mặc định: data/canslim_features/)
    """
    out_dir = Path(output_dir or DEFAULT_FEATURES_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    required_cols = [
        "date", "symbol", "price", "pivot", "buy_zone", "breakout_vol_ratio",
        "q_eps_yoy", "q_sales_yoy", "sales_accel", "gross_margin", "margin_yoy",
        "eps_tier", "rs_rating", "market_status",
        "allow_buy", "size_suggestion", "reasons",
    ]

    df = df_screen.copy()

    # Chuẩn hoá tên cột nếu cần
    col_map = {
        "breakout_volume_ratio": "breakout_vol_ratio",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    if "date" not in df.columns:
        df.insert(0, "date", date)

    for col in required_cols:
        if col not in df.columns:
            df[col] = None

    out_path = out_dir / f"{date}.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info(f"Features saved: {out_path} ({len(df)} rows)")
    return out_path


def load_features(date: str, features_dir: Optional[Path] = None) -> pd.DataFrame:
    """Load feature CSV cho 1 ngày cụ thể."""
    out_dir = Path(features_dir or DEFAULT_FEATURES_DIR)
    path = out_dir / f"{date}.csv"
    if not path.exists():
        logger.warning(f"No features found for {date} at {path}")
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def load_feature_range(
    start: str,
    end: str,
    features_dir: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Load features cho khoảng ngày [start, end], concatenate thành 1 DataFrame.
    Dùng để phân tích distribution hoặc build backtest inputs.
    """
    out_dir = Path(features_dir or DEFAULT_FEATURES_DIR)
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")

    frames = []
    cur = start_dt
    while cur <= end_dt:
        date_str = cur.strftime("%Y-%m-%d")
        path = out_dir / f"{date_str}.csv"
        if path.exists():
            frames.append(pd.read_csv(path, encoding="utf-8-sig"))
        cur += timedelta(days=1)

    if not frames:
        logger.warning(f"No feature files found in [{start}, {end}]")
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    logger.info(f"Loaded {len(df)} rows from {len(frames)} feature files")
    return df


def sanity_check(df_features: pd.DataFrame) -> dict:
    """
    3 sanity checks quan trọng trước khi chạy backtest lớn.
    """
    if df_features.empty:
        return {"error": "empty dataframe"}

    total = len(df_features)

    has_eps_yoy = df_features["q_eps_yoy"].notna().sum() if "q_eps_yoy" in df_features.columns else 0
    has_sales_yoy = df_features["q_sales_yoy"].notna().sum() if "q_sales_yoy" in df_features.columns else 0
    completeness = {
        "total_rows": total,
        "eps_yoy_complete_pct": round(has_eps_yoy / total * 100, 1),
        "sales_yoy_complete_pct": round(has_sales_yoy / total * 100, 1),
    }

    margin_issues = 0
    if "gross_margin" in df_features.columns:
        gm = pd.to_numeric(df_features["gross_margin"], errors="coerce")
        margin_issues = ((gm < 0) | (gm > 1)).sum()
    stability = {"gross_margin_outliers": int(margin_issues)}

    # Buy signal & volume metrics
    allow_buy_pct = 0.0
    if "allow_buy" in df_features.columns:
        allow_buy_pct = df_features["allow_buy"].astype(bool).mean() * 100

    if "buy_zone" in df_features.columns:
        bz = df_features["buy_zone"]
    else:
        bz = pd.Series([None] * total)
    late_buy_pct = (bz == "late").mean() * 100 if total else 0.0

    volume_fail_pct = 0.0
    if "breakout_vol_ratio" in df_features.columns:
        r = pd.to_numeric(df_features["breakout_vol_ratio"], errors="coerce")
        volume_fail_pct = (r < 1.4).mean() * 100

    signals = {
        "allow_buy_pct": round(allow_buy_pct, 1),
        "late_buy_pct": round(late_buy_pct, 1),
        "volume_fail_pct": round(volume_fail_pct, 1),
    }

    result = {**completeness, **stability, **signals}

    print("\n=== CANSLIM Feature Sanity Check ===")
    print(f"  Total rows:             {total}")
    print(f"  EPS YoY complete:       {completeness['eps_yoy_complete_pct']}%")
    print(f"  Sales YoY complete:     {completeness['sales_yoy_complete_pct']}%")
    print(f"  Gross margin outliers:  {margin_issues}")
    print(f"  Allow buy signals:      {signals['allow_buy_pct']}%")
    print(f"  Late buy zone:          {signals['late_buy_pct']}%")
    print(f"  Volume filter failures: {signals['volume_fail_pct']}%")

    if completeness["eps_yoy_complete_pct"] < 60:
        print("  ⚠ EPS completeness <60% — nhiều mã thiếu data fundamentals")
    if margin_issues > total * 0.05:
        print("  ⚠ >5% gross_margin outliers — kiểm tra revenue/gross_profit parsing")
    if signals["allow_buy_pct"] > 20:
        print("  ⚠ >20% allow_buy — có thể market filter quá lỏng")
    if signals["allow_buy_pct"] < 1:
        print("  ⚠ <1% allow_buy — có thể threshold quá chặt hoặc market downtrend")

    return result

