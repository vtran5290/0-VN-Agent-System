"""Compute per-symbol RS vs VNINDEX over correction leg."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from .anchor import CorrectionAnchor, detect_correction_anchor

REPO = Path(__file__).resolve().parents[3]
EX_VIN = frozenset({"VIC", "VHM", "VRE", "VPL"})
PANEL_PATH = REPO / "data" / "research" / "ema_cloud" / "ohlcv_panel_ext2012.parquet"
VNI_PATH = REPO / "data" / "fireant_ssot" / "ta_vnindex.parquet"
UNIVERSE_PATH = REPO / "config" / "universe_liquid_adv50_2b.txt"
ANCHOR_OVERRIDE = REPO / "config" / "rs_correction_anchor.txt"


def _load_universe() -> list[str]:
    if not UNIVERSE_PATH.is_file():
        return []
    return [
        x.strip().upper()
        for x in UNIVERSE_PATH.read_text(encoding="utf-8").splitlines()
        if x.strip() and not x.startswith("#")
    ]


def _read_anchor_override() -> Optional[str]:
    if not ANCHOR_OVERRIDE.is_file():
        return None
    for line in ANCHOR_OVERRIDE.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            return s
    return None


def _bucket(rs_pct: float) -> str:
    if rs_pct >= 3.0:
        return "leader_strong"
    if rs_pct >= 1.0:
        return "outperform"
    if rs_pct >= 0.0:
        return "relative_flat"
    return "underperform"


def compute_rs_correction_table(
    *,
    as_of: Optional[str] = None,
    anchor_date: Optional[str] = None,
    symbols: Optional[list[str]] = None,
) -> tuple[pd.DataFrame, dict[str, Any], list[str]]:
    warnings: list[str] = []
    vni = pd.read_parquet(VNI_PATH)
    override = anchor_date or _read_anchor_override()
    if override:
        anchor_req = pd.Timestamp(override)
        sub = vni.copy()
        sub["date"] = pd.to_datetime(sub["date"]).dt.normalize()
        sub = sub.sort_values("date")
        if as_of:
            sub = sub[sub["date"] <= pd.Timestamp(as_of)]
        avail = sub[sub["date"] <= anchor_req]
        if avail.empty:
            raise ValueError(f"no VNINDEX bar on/before anchor override {override}")
        peak_row = avail.iloc[-1]
        end_row = sub.iloc[-1]
        anchor = CorrectionAnchor(
            anchor_date=pd.Timestamp(peak_row["date"]).strftime("%Y-%m-%d"),
            anchor_close=float(peak_row["close"]),
            end_date=pd.Timestamp(end_row["date"]).strftime("%Y-%m-%d"),
            end_close=float(end_row["close"]),
            drawdown_pct=round((float(end_row["close"]) / float(peak_row["close"]) - 1) * 100, 2),
            lookback_bars=len(sub),
            detection_method="config_override",
        )
        warnings.append(f"anchor override: {override}")
    else:
        anchor = detect_correction_anchor(vni, as_of=as_of)

    panel = pd.read_parquet(
        PANEL_PATH,
        columns=["symbol", "date", "close", "volume"],
    )
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    universe = set(symbols) if symbols else set(_load_universe())
    if universe:
        panel = panel[panel["symbol"].isin(universe)]

    anchor_ts = pd.Timestamp(anchor.anchor_date)
    end_ts = pd.Timestamp(anchor.end_date)
    vni_ret = anchor.end_close / anchor.anchor_close - 1

    rows: list[dict[str, Any]] = []
    for sym, g in panel.groupby("symbol"):
        g = g.sort_values("date").set_index("date")
        a_idx = g.index[g.index <= anchor_ts]
        e_idx = g.index[g.index <= end_ts]
        if len(a_idx) == 0 or len(e_idx) == 0:
            continue
        da, de = a_idx[-1], e_idx[-1]
        p0, p1 = float(g.loc[da, "close"]), float(g.loc[de, "close"])
        if p0 <= 0:
            continue
        ret = p1 / p0 - 1
        rs = ret - vni_ret
        rs_line_chg = (p1 / anchor.end_close) / (p0 / anchor.anchor_close) - 1

        m = g.loc[:end_ts].reset_index().merge(
            vni[["date", "close"]].assign(date=pd.to_datetime(vni["date"]).dt.normalize()).rename(
                columns={"close": "vc"}
            ),
            on="date",
            how="inner",
        )
        rs20_end = np.nan
        rs20_anchor = np.nan
        if len(m) >= 21:
            rs20_end = m["close"].iloc[-1] / m["close"].iloc[-21] - 1 - (
                m["vc"].iloc[-1] / m["vc"].iloc[-21] - 1
            )
        ma = m[m["date"] <= da].tail(21)
        if len(ma) >= 21:
            rs20_anchor = ma["close"].iloc[-1] / ma["close"].iloc[-21] - 1 - (
                ma["vc"].iloc[-1] / ma["vc"].iloc[-21] - 1
            )
        rs_improving = (
            np.isfinite(rs20_end)
            and np.isfinite(rs20_anchor)
            and rs20_end > rs20_anchor + 0.01
        )
        seg = g.loc[da:de]
        peak = seg["close"].cummax()
        mdd = float((seg["close"] / peak - 1).min()) if len(seg) else np.nan

        rs20_end_pct = round(rs20_end * 100, 2) if np.isfinite(rs20_end) else None
        rs20_anchor_pct = round(rs20_anchor * 100, 2) if np.isfinite(rs20_anchor) else None
        rs20_delta_pp = None
        if rs20_end_pct is not None and rs20_anchor_pct is not None:
            rs20_delta_pp = round(rs20_end_pct - rs20_anchor_pct, 2)

        rows.append(
            {
                "symbol": sym,
                "anchor_date": da.strftime("%Y-%m-%d"),
                "end_date": de.strftime("%Y-%m-%d"),
                "close_anchor": round(p0, 2),
                "close_end": round(p1, 2),
                "ret_pct": round(ret * 100, 2),
                "vnindex_ret_pct": round(vni_ret * 100, 2),
                "rs_pct": round(rs * 100, 2),
                "rs_line_chg_pct": round(rs_line_chg * 100, 2),
                "rs20_end_pct": rs20_end_pct,
                "rs20_anchor_pct": rs20_anchor_pct,
                "rs20_delta_pp": rs20_delta_pp,
                "rs_improving_flag": bool(rs_improving),
                "mdd_since_anchor_pct": round(mdd * 100, 2) if np.isfinite(mdd) else None,
                "bucket": _bucket(rs * 100),
                "is_vin": sym in EX_VIN,
            }
        )

    df = pd.DataFrame(rows)
    meta: dict[str, Any] = {
        "source": "FireAnt",
        "method": "SSOT parquet (ema_cloud ohlcv_panel_ext2012 + ta_vnindex)",
        "benchmark": "VNINDEX native (ta_vnindex.parquet)",
        "universe": str(UNIVERSE_PATH.relative_to(REPO)),
        "anchor": {
            "anchor_date": anchor.anchor_date,
            "anchor_close": anchor.anchor_close,
            "end_date": anchor.end_date,
            "end_close": anchor.end_close,
            "vnindex_ret_pct": round(vni_ret * 100, 2),
            "drawdown_from_peak_pct": anchor.drawdown_pct,
            "lookback_bars": anchor.lookback_bars,
            "detection_method": anchor.detection_method,
        },
        "n_symbols": len(df),
        "n_outperform_rs_gt_0": int((df["rs_pct"] > 0).sum()) if not df.empty else 0,
        "n_leader_rs_ge_3": int((df["rs_pct"] >= 3).sum()) if not df.empty else 0,
        "safety_note": "RS correction lens is market context only and does not change final_action.",
    }
    return df, meta, warnings
