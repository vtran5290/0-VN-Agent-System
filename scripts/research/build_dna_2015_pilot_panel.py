"""
DNA 2015 Pilot — Sandbox Panel Builder

Builds a sandbox OHLCV panel from minervini_backtest/data/raw/ CSVs for the
40 core symbols that had data before 2015. Uses this to test whether extending
the DNA research window from 2018-start to 2015-start changes tier assignments.

Council ruling 2026-06-06: pilot 40 symbols before committing to full-universe
backfill. Validate ADV units at the unit-convention crossover before conclusions.

UNIT CONVENTION NOTE:
  minervini_backtest prices are split-and-dividend adjusted, stored in full VND
  (not kVND). The DNA pipeline's features.py applies close × volume × 1000,
  assuming close is in kVND. For pre-2019 minervini data:
    - If close is in full VND → ×1000 inflates ADV by ~1000x
    - Pilot detects this by comparing median close at 2018-crossover
    - If needed, applies /1000 normalization to align with kVND convention

Outputs (all to sandbox — NEVER touches live SSOT):
  data/pilot_2015/
    ta_ohlcv_panel_pilot.parquet   — extended panel for 40 symbols
    pilot_symbol_list.csv          — symbols, date ranges, unit flags
    pilot_adv_unit_check.csv       — unit validation at 2018 crossover
    pilot_dna_profiles.csv         — DNA profiles from extended panel
    pilot_comparison.csv           — diff vs current DNA profiles for same 40 symbols

RESEARCH ONLY — does not modify live SSOT, A3, OMS, DNSE, or final_action.
STOCK_DNA_ANNOTATION_ENABLED stays false.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("dna_2015_pilot")

RESEARCH_ONLY_LABEL = "STOCK_DNA_RESEARCH_ONLY — NOT FOR PRODUCTION USE"

MINERVINI_DIR = ROOT / "minervini_backtest" / "data" / "raw"
PILOT_DIR     = ROOT / "data" / "pilot_2015"
DNA_PROFILES  = ROOT / "data" / "research" / "stock_dna" / "stock_dna_symbol_profiles.csv"
SSOT_PANEL    = ROOT / "data" / "fireant_ssot" / "ta_ohlcv_panel.parquet"

# Council-approved pilot list: symbols in DNA profiles with minervini data pre-2015
# Top 40 liquid compounders by earliest minervini date, with sector spread
PILOT_SYMBOLS = [
    # Banks / Financial
    "ACB", "MBB", "STB", "SHB", "EIB", "VCB", "SSI", "SHS", "HCM", "VIX",
    # Steel / Industry
    "HPG", "HSG", "NKG", "POM",
    # Energy / Oil
    "PVD", "PVS", "PVT", "PVC", "NT2",
    # Real estate
    "PDR", "KDH", "KBC", "NTL",
    # Consumer / Food
    "MSN", "PNJ", "SBT", "PAN",
    # Industrial / Infra
    "REE", "GMD", "FPT", "PLC",
    # Other
    "HAX", "AAA", "PTB", "VND", "VHC", "VCG", "VGS", "PHR", "PAC",
]

# Deduplicate (council brief had HPG twice)
PILOT_SYMBOLS = sorted(set(PILOT_SYMBOLS))


def _detect_unit(df: pd.DataFrame, symbol: str) -> str:
    """Detect if close prices are in full VND or kVND.

    Heuristic: if median close is > 500 for pre-2019 rows, assume full VND
    (most liquid VN stocks trade 5,000-200,000 VND; in kVND that would be 5-200).
    If median close < 500, likely already in kVND.
    """
    pre2019 = df[df["date"] < "2019-01-01"]
    if pre2019.empty:
        return "kVND_ASSUMED"
    med = pre2019["close"].median()
    if med > 500:
        return "FULL_VND_DIVIDE1000"
    return "kVND_OK"


def _normalize_to_kvnd(df: pd.DataFrame, unit_flag: str) -> pd.DataFrame:
    """Normalize close/open/high/low to kVND if full VND detected."""
    if unit_flag != "FULL_VND_DIVIDE1000":
        return df
    price_cols = [c for c in ["open", "high", "low", "close"] if c in df.columns]
    df = df.copy()
    # Only normalize pre-2019 rows (unit change happened around 2018-2019)
    mask = df["date"] < "2019-01-01"
    df.loc[mask, price_cols] = df.loc[mask, price_cols] / 1000.0
    logger.debug("Normalized %d pre-2019 rows from full VND to kVND", mask.sum())
    return df


def load_minervini_csv(symbol: str) -> pd.DataFrame | None:
    """Load minervini_backtest CSV for a symbol, return standardized DataFrame."""
    fp = MINERVINI_DIR / f"{symbol}.csv"
    if not fp.exists():
        return None
    try:
        df = pd.read_csv(fp)
        df.columns = [c.strip().lower() for c in df.columns]
        if "date" not in df.columns:
            return None
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date", "close"])
        df["symbol"] = symbol
        df["volume"] = pd.to_numeric(df.get("volume", 0), errors="coerce").fillna(0)
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["close"])
        df = df.sort_values("date").drop_duplicates(subset=["date"])
        return df[["symbol", "date", "open", "high", "low", "close", "volume"]]
    except Exception as e:
        logger.warning("Error loading %s: %s", symbol, e)
        return None


def build_pilot_panel() -> pd.DataFrame:
    """Build extended OHLCV panel for PILOT_SYMBOLS from minervini data."""
    PILOT_DIR.mkdir(parents=True, exist_ok=True)

    symbol_records = []
    parts = []

    for sym in PILOT_SYMBOLS:
        df = load_minervini_csv(sym)
        if df is None:
            logger.warning("No minervini data for %s — skipping", sym)
            symbol_records.append({
                "symbol": sym,
                "status": "MISSING",
                "min_date": None,
                "max_date": None,
                "n_rows": 0,
                "unit_flag": "N/A",
            })
            continue

        unit_flag = _detect_unit(df, sym)
        df = _normalize_to_kvnd(df, unit_flag)

        symbol_records.append({
            "symbol": sym,
            "status": "OK",
            "min_date": str(df["date"].min().date()),
            "max_date": str(df["date"].max().date()),
            "n_rows": len(df),
            "unit_flag": unit_flag,
        })
        parts.append(df)
        logger.info(
            "Loaded %s: %d rows %s→%s  unit=%s",
            sym, len(df),
            df["date"].min().date(), df["date"].max().date(),
            unit_flag,
        )

    if not parts:
        logger.error("No symbols loaded — check minervini_backtest/data/raw/")
        return pd.DataFrame()

    panel = pd.concat(parts, ignore_index=True)
    panel["date"] = pd.to_datetime(panel["date"])
    panel = panel.sort_values(["symbol", "date"]).drop_duplicates(
        subset=["symbol", "date"], keep="last"
    )
    # Add value column (consistent with build_fireant_ssot._standardize_ohlcv)
    panel["value"] = pd.to_numeric(panel["close"], errors="coerce") * pd.to_numeric(
        panel["volume"], errors="coerce"
    )

    # Save panel parquet to sandbox
    out_path = PILOT_DIR / "ta_ohlcv_panel_pilot.parquet"
    panel.to_parquet(out_path, index=False)

    # Save symbol list
    sym_df = pd.DataFrame(symbol_records)
    sym_df.to_csv(PILOT_DIR / "pilot_symbol_list.csv", index=False)

    logger.info(
        "Pilot panel saved: %s  (%d rows, %d symbols)",
        out_path, len(panel), panel["symbol"].nunique(),
    )
    logger.info(
        "Date range: %s → %s",
        panel["date"].min().date(), panel["date"].max().date(),
    )

    # Unit validation at 2018 crossover
    _run_unit_validation(panel)

    return panel


def _run_unit_validation(panel: pd.DataFrame) -> None:
    """Validate ADV unit at 2018 crossover vs current SSOT panel."""
    audit_rows = []

    if not SSOT_PANEL.exists():
        logger.warning("SSOT panel not found — skipping crossover validation")
        return

    ssot = pd.read_parquet(SSOT_PANEL, columns=["symbol", "date", "close", "volume"])
    ssot["date"] = pd.to_datetime(ssot["date"])

    for sym in PILOT_SYMBOLS:
        pilot_sub  = panel[panel["symbol"] == sym]
        ssot_sub   = ssot[ssot["symbol"] == sym]

        if pilot_sub.empty or ssot_sub.empty:
            continue

        # ADV30 from pilot (normalized) at 2018-06-01
        ref_date = pd.Timestamp("2018-06-01")
        p_window = pilot_sub[pilot_sub["date"] <= ref_date].tail(30)
        s_window = ssot_sub[ssot_sub["date"] <= ref_date].tail(30)

        if len(p_window) < 10:
            continue

        pilot_adv = float((p_window["close"] * p_window["volume"] * 1000).mean())
        ssot_adv  = float((s_window["close"] * s_window["volume"] * 1000).mean()) if len(s_window) >= 10 else None

        pilot_med_close = float(p_window["close"].median())
        ssot_med_close  = float(s_window["close"].median()) if len(s_window) >= 10 else None

        ratio = pilot_adv / ssot_adv if ssot_adv and ssot_adv > 0 else None

        audit_rows.append({
            "symbol": sym,
            "ref_date": str(ref_date.date()),
            "pilot_median_close_at_2018": pilot_med_close,
            "ssot_median_close_at_2018": ssot_med_close,
            "pilot_adv30_kvnd_x1000": pilot_adv,
            "ssot_adv30_kvnd_x1000": ssot_adv,
            "pilot_vs_ssot_ratio": ratio,
            "unit_ok": ratio is not None and 0.5 < ratio < 2.0,
        })

    if audit_rows:
        audit_df = pd.DataFrame(audit_rows)
        audit_df.to_csv(PILOT_DIR / "pilot_adv_unit_check.csv", index=False)
        ok = audit_df["unit_ok"].sum()
        total = len(audit_df)
        logger.info(
            "ADV unit crossover check: %d/%d symbols within 2x ratio at 2018-06-01",
            ok, total,
        )
        if ok < total * 0.8:
            logger.warning(
                "GATE FAIL: <80%% of symbols pass unit check. "
                "Review pilot_adv_unit_check.csv before feeding pilot data downstream."
            )
        else:
            logger.info("Unit check PASSED — pilot data consistent with SSOT at crossover.")
    else:
        logger.warning("No crossover comparison possible — no SSOT data for 2018 period")


def compare_with_current_profiles(panel: pd.DataFrame) -> None:
    """Compare pilot results against current DNA profiles for the same 40 symbols."""
    if not DNA_PROFILES.exists():
        logger.warning("Current DNA profiles not found — skipping comparison")
        return

    current = pd.read_csv(DNA_PROFILES)
    current_pilot = current[current["symbol"].isin(PILOT_SYMBOLS)].copy()

    pilot_profile_path = PILOT_DIR / "pilot_dna_profiles.csv"
    if not pilot_profile_path.exists():
        logger.warning(
            "Pilot DNA profiles not yet generated. Run the discovery pipeline with:\n"
            "  python scripts/research/run_stock_dna_discovery.py \\\n"
            "    --start 2015-01-01 \\\n"
            "    --data-dir data/pilot_2015 \\\n"
            "    --output-dir data/pilot_2015/dna_results"
        )
        return

    pilot = pd.read_csv(pilot_profile_path)

    merge_cols = [
        "symbol", "primary_support_line", "edge_confidence",
        "regime_obedience_bull", "confidence", "production_status",
    ]
    comp = current_pilot[merge_cols].merge(
        pilot[merge_cols], on="symbol", suffixes=("_2018start", "_2015start")
    )
    comp["primary_line_changed"] = (
        comp["primary_support_line_2018start"] != comp["primary_support_line_2015start"]
    )
    comp["edge_conf_changed"] = (
        comp["edge_confidence_2018start"] != comp["edge_confidence_2015start"]
    )
    comp["tier_changed"] = comp["primary_line_changed"] | comp["edge_conf_changed"]

    comp.to_csv(PILOT_DIR / "pilot_comparison.csv", index=False)

    logger.info(
        "Comparison: %d/%d symbols changed primary_support_line, "
        "%d changed edge_confidence",
        comp["primary_line_changed"].sum(),
        len(comp),
        comp["edge_conf_changed"].sum(),
    )


def main() -> None:
    logger.info("=" * 60)
    logger.info("DNA 2015 Pilot Panel Builder — %s", RESEARCH_ONLY_LABEL)
    logger.info("=" * 60)
    logger.info("Pilot symbols (%d): %s", len(PILOT_SYMBOLS), PILOT_SYMBOLS)
    logger.info("Source: %s", MINERVINI_DIR)
    logger.info("Sandbox output: %s", PILOT_DIR)
    logger.info("Live SSOT: NOT MODIFIED")

    panel = build_pilot_panel()
    if panel.empty:
        sys.exit(1)

    compare_with_current_profiles(panel)

    logger.info("-" * 60)
    logger.info("NEXT STEP: Run DNA discovery on pilot panel:")
    logger.info(
        "  python scripts/research/run_stock_dna_discovery.py"
        " --start 2015-01-01"
        " --output-dir data/pilot_2015/dna_results"
    )
    logger.info(
        "  Then copy pilot_dna_profiles.csv from the output and re-run this script."
    )
    logger.info("  GATE: ADV unit check must pass (>80%% symbols within 2x ratio) before conclusions.")
    logger.info("-" * 60)
    logger.info("Done. %s", RESEARCH_ONLY_LABEL)


if __name__ == "__main__":
    main()
