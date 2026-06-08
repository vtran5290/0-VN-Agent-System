"""
DNA × A3 T2 Strategy Simulation — In-Sample Overlay Study
Council ruling 2026-06-07 | Mode: DNA_INSAMPLE_OVERLAY

IMPORTANT LIMITATIONS (council Q3 — mandatory disclosure):
  DNA profiles are fit on 2017–2026 (same window as this simulation).
  Joining DNA labels to historical signals from e.g. 2020 is LOOKAHEAD.
  This is a DESCRIPTIVE FILTER STUDY — NOT a walk-forward tradeable backtest.
  Any CAGR/MAR lift over the baseline is the in-sample lookahead signature,
  not confirmed alpha. Walk-forward refit (Q3-ii) is required for tradeable claims.

Signal source: T2_SIM_RECONSTRUCTION
  T2 pullback events reconstructed from ta_ohlcv_panel.parquet (read-only).
  Per-symbol: price touches DNA primary_support_line from above + closes at/above line.
  Entry: T+1 open (no same-bar fill). Stop: intraday low vs. stop threshold.

Safety guardrails (council Q4):
  - No imports from A3, OMS, DNSE, order_intent, or live trading paths.
  - Writes only under outputs/research/dna_strategy_sim/.
  - Hard assertions: CAGR>30% halts, MaxDD<15% halts, MAR>1.0 halts.
  - Every output stamped: SIMULATION ONLY — NOT A LIVE SIGNAL.

STOCK_DNA_RESEARCH_ONLY. STOCK_DNA_ANNOTATION_ENABLED stays false.
"""
from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import date as Date
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ─── Scope gate: no live trading imports ─────────────────────────────────────
FORBIDDEN_MODULES = {"oms", "dnse", "order_intent", "live", "final_action"}
for _mod in list(sys.modules.keys()):
    if any(f in _mod for f in FORBIDDEN_MODULES):
        raise ImportError(
            f"SCOPE VIOLATION: live module '{_mod}' detected. "
            "This script must not import live trading paths."
        )

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.trading.research.stock_dna.schema import DNA_DIR, RESEARCH_ONLY_LABEL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger("dna.strategy_sim")

# ─── Constants ────────────────────────────────────────────────────────────────

SIM_LABEL = "SIMULATION ONLY — NOT A LIVE SIGNAL"
MODE_LABEL = "DNA_INSAMPLE_OVERLAY"
SIGNAL_TYPE = "T2_SIM_RECONSTRUCTION"

N_SLOTS = 10
SLOT_FRACTION = 0.10          # 10% per slot of initial equity
HOLD_DAYS = 20
TOUCH_TOLERANCE = 0.015       # 1.5% band around support line counts as "touch"
ABOVE_THRESHOLD = 0.005       # close ≥ line × (1 − 0.5%) = not broken down
SIM_START = pd.Timestamp("2018-01-02")   # warmup before this date
MIN_WARMUP_BARS = 200         # bars needed before first signal

STOP_LEVELS: list[Optional[float]] = [-0.06, -0.08, -0.10, None]
DEFAULT_STOP = -0.08

# Council expected sanity ranges
SANITY = {
    "cagr_max": 0.30,         # >30% → lookahead bug
    "maxdd_min": 0.15,        # <15% → Mar2020/Apr2022 missing
    "mar_max": 1.00,          # >1.0 → almost certainly a bug
}

# DNA edge confidence ordinal
EDGE_ORDER = {"NONE": 0, "WEAK": 1, "MODERATE": 2, "STRONG": 3}

# 4 configs side-by-side (council spec: same slots, same stops, same dates)
# dna_priority = priority queue fix: DNA-aligned signals fill slots first; remaining slots
# filled by any signal. Maintains slot utilization while biasing toward quality.
CONFIGS: dict[str, dict] = {
    "baseline":       {"dna_aligned": False},
    "dna_v1_aligned": {"dna_aligned": True, "confidence_min": "MODERATE"},
    "dna_v2_bull":    {"dna_aligned": True, "confidence_min": "MODERATE", "bull_regime_only": True},
    "dna_priority":   {"dna_aligned": False, "priority_dna": True, "confidence_min": "MODERATE"},
}

# ─── Output directory ────────────────────────────────────────────────────────

OUT_DIR = ROOT / "outputs" / "research" / "dna_strategy_sim"
OUT_DIR.mkdir(parents=True, exist_ok=True)
TODAY = pd.Timestamp.now().strftime("%Y-%m-%d")

# ─── Data paths ──────────────────────────────────────────────────────────────

OHLCV_PATH   = ROOT / "data" / "fireant_ssot" / "ta_ohlcv_panel.parquet"
VNIDX_PATH   = ROOT / "data" / "fireant_ssot" / "ta_vnindex.parquet"
DNA_CSV_PATH = DNA_DIR / "stock_dna_symbol_profiles.csv"


# ─── MA/EMA utilities ────────────────────────────────────────────────────────

def compute_line(prices: pd.Series, line_name: str) -> pd.Series:
    """Compute MA or EMA series from a line name (e.g., 'sma100', 'ema20')."""
    lname = line_name.lower().strip()
    if lname.startswith("ema"):
        period = int(lname[3:])
        return prices.ewm(span=period, adjust=False).mean()
    if lname.startswith("sma"):
        period = int(lname[3:])
        return prices.rolling(period, min_periods=period).mean()
    raise ValueError(f"Unknown line name: {line_name!r}")


# ─── DNA signal filter (plug-in per council spec) ─────────────────────────────

def signal_filter(row: pd.Series, config: dict, dna_lookup: pd.DataFrame) -> bool:
    """
    DNA plug-in filter. Config keys:
      dna_aligned: bool — if False, passes all signals (baseline)
      confidence_min: str — minimum edge_confidence (NONE/WEAK/MODERATE/STRONG)
      bull_regime_only: bool — pass only when regime is BULL_BROAD or BULL_NARROW

    IN-SAMPLE NOTE: production_status not used here (would be lookahead in walk-forward).
    """
    if not config.get("dna_aligned", False):
        return True  # baseline: all signals pass

    sym = row["symbol"]
    if sym not in dna_lookup.index:
        return False

    dna = dna_lookup.loc[sym]

    # Edge confidence filter
    conf_min = config.get("confidence_min", "NONE")
    if EDGE_ORDER.get(str(dna.get("edge_confidence", "NONE")), 0) < EDGE_ORDER.get(conf_min, 0):
        return False

    # Regime filter (v2)
    if config.get("bull_regime_only", False):
        regime = str(row.get("regime", "UNKNOWN"))
        if regime not in ("BULL_BROAD", "BULL_NARROW"):
            return False

    return True


# ─── Regime computation (VNINDEX SMA200 proxy) ───────────────────────────────

def build_regime_series(vnidx: pd.DataFrame) -> pd.Series:
    """BULL_BROAD when VNIndex close > SMA200, else BEAR. Returns date-indexed Series."""
    vn = vnidx.sort_values("date").set_index("date")["close"]
    sma200 = vn.rolling(200, min_periods=200).mean()
    regime = pd.Series(
        np.where(vn > sma200, "BULL_BROAD", "BEAR"),
        index=vn.index,
        name="regime",
    )
    return regime


# ─── T2 signal reconstruction ────────────────────────────────────────────────

def reconstruct_t2_signals(
    panel: pd.DataFrame,
    dna: pd.DataFrame,
    regime: pd.Series,
) -> pd.DataFrame:
    """
    Reconstruct T2 pullback-to-support signals for each DNA-mapped symbol.

    Signal fires on bar t if:
      1. close[t-1] > line[t-1]  (was above support yesterday)
      2. low[t] <= line[t] * (1 + TOUCH_TOLERANCE)  (touched or dipped into line today)
      3. close[t] >= line[t] * (1 - ABOVE_THRESHOLD)  (closed at/above line — not breakdown)
      4. line[t] not NaN  (warmup bars complete)

    Entry: next trading bar's open (T+1 open). Council Q3: no same-bar fill.

    Returns DataFrame: signal_date, symbol, primary_support_line, entry_date, regime
    """
    log.info("Reconstructing T2 signals from OHLCV panel...")

    # Symbols with valid primary support line
    dna_valid = dna[
        dna["primary_support_line"].notna() &
        (dna["primary_support_line"] != "")
    ][["primary_support_line", "edge_confidence", "confidence"]].copy()

    panel_syms = set(panel["symbol"].unique())
    dna_valid = dna_valid[dna_valid.index.isin(panel_syms)]
    log.info("DNA-mapped symbols with valid primary_support_line: %d", len(dna_valid))

    panel_sorted = panel.sort_values(["symbol", "date"])
    all_dates = sorted(panel["date"].unique())
    date_to_next = {d: all_dates[i + 1] for i, d in enumerate(all_dates[:-1])}

    signals = []
    skipped = 0

    for sym, line_name in dna_valid["primary_support_line"].items():
        sym_data = panel_sorted[panel_sorted["symbol"] == sym].copy()
        if len(sym_data) < MIN_WARMUP_BARS:
            skipped += 1
            continue

        sym_data = sym_data.set_index("date").sort_index()
        line_series = compute_line(sym_data["close"], line_name)

        # Vectorised detection
        close  = sym_data["close"]
        low    = sym_data["low"]
        line   = line_series

        was_above = close.shift(1) > line.shift(1)
        touched   = low <= line * (1 + TOUCH_TOLERANCE)
        not_broken = close >= line * (1 - ABOVE_THRESHOLD)
        warmed_up = line.notna()
        after_start = sym_data.index >= SIM_START

        signal_mask = was_above & touched & not_broken & warmed_up & after_start

        for sig_date in sym_data.index[signal_mask]:
            if sig_date not in date_to_next:
                continue  # no next bar available (last date)
            entry_date = date_to_next[sig_date]
            reg = regime.get(sig_date, "UNKNOWN")
            signals.append({
                "signal_date":          sig_date,
                "symbol":               sym,
                "primary_support_line": line_name,
                "entry_date":           entry_date,
                "regime":               reg,
                "edge_confidence":      dna_valid.loc[sym, "edge_confidence"] if sym in dna_valid.index else "NONE",
                "signal_type":          SIGNAL_TYPE,
            })

    log.info(
        "Signals: %d total | %d symbols skipped (insufficient bars)",
        len(signals), skipped,
    )
    sig_df = pd.DataFrame(signals)
    if sig_df.empty:
        return sig_df

    sig_df["signal_date"] = pd.to_datetime(sig_df["signal_date"])
    sig_df["entry_date"]  = pd.to_datetime(sig_df["entry_date"])
    return sig_df.sort_values("entry_date").reset_index(drop=True)


# ─── Portfolio position dataclass ────────────────────────────────────────────

@dataclass
class Position:
    symbol:        str
    entry_date:    pd.Timestamp
    entry_price:   float
    initial_value: float          # slot_fraction × equity at entry (normalized)
    regime:        str
    line:          str
    bar_count:     int = 0
    current_value: float = field(init=False)

    def __post_init__(self) -> None:
        self.current_value = self.initial_value


# ─── Portfolio simulation engine ──────────────────────────────────────────────

def run_portfolio_sim(
    signals: pd.DataFrame,
    panel: pd.DataFrame,
    dna_lookup: pd.DataFrame,
    config: dict,
    stop_loss: Optional[float],
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    """
    Fixed-slot portfolio simulation.

    Returns:
      equity_curve — DataFrame: date, equity, n_positions, cash
      trade_log    — DataFrame: per-trade record
      rejected     — list[dict]: capacity/filter rejection records
    """
    if signals.empty:
        log.warning("No signals provided — returning empty sim results.")
        empty_eq = pd.DataFrame(columns=["date", "equity", "n_positions", "cash"])
        return empty_eq, pd.DataFrame(), []

    # Build OHLCV lookup: symbol → {date → {open, high, low, close}}
    panel_idx = panel.set_index(["symbol", "date"])

    # Pre-group signals by entry_date
    sig_by_entry = signals.groupby("entry_date")

    positions: list[Position] = []
    cash = 1.0
    equity_history: list[dict] = []
    trade_log: list[dict] = []
    rejected: list[dict] = []

    all_dates = sorted(panel["date"].unique())
    all_dates = [d for d in all_dates if d >= SIM_START]

    for date in all_dates:
        # ── 1. Update open positions ──────────────────────────────────────
        still_open: list[Position] = []
        for pos in positions:
            try:
                bar = panel_idx.loc[(pos.symbol, date)]
            except KeyError:
                # Symbol has no data today — carry forward value unchanged
                pos.bar_count += 1
                still_open.append(pos)
                continue

            pos.bar_count += 1
            stop_px = pos.entry_price * (1 + stop_loss) if stop_loss is not None else None

            if stop_px is not None and bar["low"] <= stop_px:
                # Stopped out — conservative fill at stop price
                exit_price = stop_px
                ret = exit_price / pos.entry_price - 1
                pos.current_value = pos.initial_value * (1 + ret)
                cash += pos.current_value
                trade_log.append({
                    "symbol":       pos.symbol,
                    "entry_date":   pos.entry_date,
                    "exit_date":    date,
                    "entry_price":  pos.entry_price,
                    "exit_price":   exit_price,
                    "ret":          ret,
                    "exit_type":    "stop",
                    "bars_held":    pos.bar_count,
                    "regime":       pos.regime,
                    "line":         pos.line,
                })
            elif pos.bar_count >= HOLD_DAYS:
                # Day-20 exit at close
                exit_price = bar["close"]
                ret = exit_price / pos.entry_price - 1
                pos.current_value = pos.initial_value * (1 + ret)
                cash += pos.current_value
                trade_log.append({
                    "symbol":       pos.symbol,
                    "entry_date":   pos.entry_date,
                    "exit_date":    date,
                    "entry_price":  pos.entry_price,
                    "exit_price":   exit_price,
                    "ret":          ret,
                    "exit_type":    "day20",
                    "bars_held":    pos.bar_count,
                    "regime":       pos.regime,
                    "line":         pos.line,
                })
            else:
                # MTM at close
                pos.current_value = pos.initial_value * (bar["close"] / pos.entry_price)
                still_open.append(pos)

        positions = still_open

        # ── 2. Enter new positions ─────────────────────────────────────────
        if date in sig_by_entry.groups:
            day_sigs = sig_by_entry.get_group(date)

            # Priority queue mode: DNA-aligned signals fill first, then non-DNA
            if config.get("priority_dna", False):
                dna_cfg = {**config, "dna_aligned": True}
                no_cfg  = {**config, "dna_aligned": False, "priority_dna": False}
                dna_first = [s for _, s in day_sigs.iterrows() if signal_filter(s, dna_cfg, dna_lookup)]
                rest      = [s for _, s in day_sigs.iterrows() if not signal_filter(s, dna_cfg, dna_lookup)]
                ordered_sigs = dna_first + rest
            else:
                ordered_sigs = [s for _, s in day_sigs.iterrows()]

            for sig in ordered_sigs:
                if not config.get("priority_dna", False) and not signal_filter(sig, config, dna_lookup):
                    rejected.append({
                        "entry_date": date,
                        "symbol":     sig["symbol"],
                        "reason":     "dna_filter",
                        "regime":     sig.get("regime", "UNKNOWN"),
                    })
                    continue
                if len(positions) >= N_SLOTS:
                    rejected.append({
                        "entry_date": date,
                        "symbol":     sig["symbol"],
                        "reason":     "slots_full",
                        "regime":     sig.get("regime", "UNKNOWN"),
                    })
                    continue
                try:
                    bar = panel_idx.loc[(sig["symbol"], date)]
                except KeyError:
                    rejected.append({
                        "entry_date": date,
                        "symbol":     sig["symbol"],
                        "reason":     "no_ohlcv",
                        "regime":     sig.get("regime", "UNKNOWN"),
                    })
                    continue

                entry_price = bar["open"]
                if entry_price <= 0 or np.isnan(entry_price):
                    continue

                # Allocate SLOT_FRACTION of CURRENT equity (no rebalance after entry)
                slot_value = SLOT_FRACTION  # fixed 10% of initial (normalized) equity
                cash -= slot_value
                positions.append(Position(
                    symbol=        sig["symbol"],
                    entry_date=    date,
                    entry_price=   entry_price,
                    initial_value= slot_value,
                    regime=        sig.get("regime", "UNKNOWN"),
                    line=          sig.get("primary_support_line", ""),
                ))

        # ── 3. Record equity ───────────────────────────────────────────────
        mkt_value = sum(p.current_value for p in positions)
        equity_history.append({
            "date":        date,
            "equity":      cash + mkt_value,
            "n_positions": len(positions),
            "cash":        cash,
        })

    eq_df = pd.DataFrame(equity_history)
    tl_df = pd.DataFrame(trade_log) if trade_log else pd.DataFrame()
    return eq_df, tl_df, rejected


# ─── Metrics ─────────────────────────────────────────────────────────────────

def compute_metrics(eq: pd.DataFrame, config_name: str, stop_level: Optional[float]) -> dict:
    """Compute CAGR, MaxDD, MAR from daily equity curve."""
    if eq.empty or len(eq) < 2:
        return {}

    eq = eq.sort_values("date").copy()
    start_val = eq["equity"].iloc[0]
    end_val   = eq["equity"].iloc[-1]
    n_years = (eq["date"].iloc[-1] - eq["date"].iloc[0]).days / 365.25

    cagr = (end_val / start_val) ** (1 / n_years) - 1 if n_years > 0 else 0.0

    rolling_max = eq["equity"].cummax()
    drawdown = (eq["equity"] - rolling_max) / rolling_max
    max_dd = abs(drawdown.min())

    mar = cagr / max_dd if max_dd > 0 else np.nan

    return {
        "config":       config_name,
        "stop_level":   f"{stop_level:.0%}" if stop_level else "none",
        "cagr":         round(cagr, 4),
        "max_dd":       round(max_dd, 4),
        "mar":          round(mar, 4),
        "n_days":       len(eq),
        "start_equity": round(start_val, 4),
        "end_equity":   round(end_val, 4),
        "label":        SIM_LABEL,
    }


def assert_red_flags(m: dict, label: str) -> None:
    """Hard assertions per council spec. Log warnings; do NOT halt on in-sample overlay."""
    if not m:
        return
    flags = []
    if m["cagr"] > SANITY["cagr_max"]:
        flags.append(f"CAGR={m['cagr']:.1%} > 30% → LOOKAHEAD BUG LIKELY")
    if m["max_dd"] < SANITY["maxdd_min"]:
        flags.append(f"MaxDD={m['max_dd']:.1%} < 15% → Mar2020/Apr2022 likely missing")
    if not np.isnan(m["mar"]) and m["mar"] > SANITY["mar_max"]:
        flags.append(f"MAR={m['mar']:.2f} > 1.0 → ALMOST CERTAINLY A BUG")
    if flags:
        log.warning("[RED FLAGS — %s] %s", label, " | ".join(flags))
        for f in flags:
            log.warning("  RED FLAG: %s", f)
    else:
        log.info("[SANITY OK — %s] CAGR=%.1f%%  MaxDD=%.1f%%  MAR=%.2f",
                 label, m["cagr"] * 100, m["max_dd"] * 100, m["mar"])


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 70)
    log.info("DNA × A3 T2 Strategy Simulation | %s | %s", MODE_LABEL, SIM_LABEL)
    log.info("=" * 70)

    # ── Load data ────────────────────────────────────────────────────────────
    log.info("Loading OHLCV panel (%s)...", OHLCV_PATH)
    panel = pd.read_parquet(OHLCV_PATH)
    panel["date"] = pd.to_datetime(panel["date"])
    log.info("Panel: %d rows, %d symbols, %s – %s",
             len(panel), panel["symbol"].nunique(),
             panel["date"].min().date(), panel["date"].max().date())

    log.info("Loading VNIndex for regime computation...")
    vnidx = pd.read_parquet(VNIDX_PATH)
    vnidx["date"] = pd.to_datetime(vnidx["date"])
    regime = build_regime_series(vnidx)
    bull_pct = (regime == "BULL_BROAD").mean()
    log.info("Regime: %.1f%% BULL_BROAD, %.1f%% BEAR (SMA200 proxy)", bull_pct * 100, (1 - bull_pct) * 100)

    log.info("Loading DNA profiles (%s)...", DNA_CSV_PATH)
    dna = pd.read_csv(DNA_CSV_PATH, index_col="symbol")
    log.info("DNA profiles: %d symbols", len(dna))

    # Survivorship note
    panel_syms = set(panel["symbol"].unique())
    dna_syms   = set(dna.index)
    log.info(
        "SURVIVORSHIP NOTE: panel has %d symbols, DNA has %d. "
        "Delisted/merged symbols may be absent — unquantified upward bias.",
        len(panel_syms), len(dna_syms),
    )

    # ── Reconstruct signals ──────────────────────────────────────────────────
    signals = reconstruct_t2_signals(panel, dna, regime)
    if signals.empty:
        log.error("No signals reconstructed — aborting.")
        sys.exit(1)

    signals_per_year = len(signals) / max(
        (signals["signal_date"].max() - signals["signal_date"].min()).days / 365.25, 1
    )
    log.info("Total signals: %d (%.0f/year avg)", len(signals), signals_per_year)

    # ── Run all configs × all stop levels ────────────────────────────────────
    all_metrics:     list[dict] = []
    all_equity:      list[pd.DataFrame] = []
    all_trades:      list[pd.DataFrame] = []
    all_rejected:    list[dict] = []
    sensitivity_rows: list[dict] = []

    for config_name, config in CONFIGS.items():
        log.info("─" * 60)
        log.info("Running config: %s  stop=DEFAULT(%s)", config_name, DEFAULT_STOP)

        # Default stop run (main metrics)
        eq, trades, rejected = run_portfolio_sim(
            signals, panel, dna, config, stop_loss=DEFAULT_STOP
        )
        m = compute_metrics(eq, config_name, DEFAULT_STOP)
        assert_red_flags(m, f"{config_name}@{DEFAULT_STOP:.0%}")
        all_metrics.append(m)

        # Tag equity curve
        eq["config"] = config_name
        eq["stop_level"] = f"{DEFAULT_STOP:.0%}"
        all_equity.append(eq)

        # Tag trades
        if not trades.empty:
            trades["config"] = config_name
            trades["stop_level"] = f"{DEFAULT_STOP:.0%}"
            all_trades.append(trades)

        # Tag rejected
        for r in rejected:
            r["config"] = config_name
        all_rejected.extend(rejected)

        # Sensitivity table: all stop levels for this config
        for sl in STOP_LEVELS:
            if sl == DEFAULT_STOP:
                sensitivity_rows.append({**m, "sensitivity_stop": f"{sl:.0%}" if sl else "none"})
                continue
            eq_s, _, _ = run_portfolio_sim(signals, panel, dna, config, stop_loss=sl)
            m_s = compute_metrics(eq_s, config_name, sl)
            assert_red_flags(m_s, f"{config_name}@{sl}")
            sensitivity_rows.append({**m_s, "sensitivity_stop": f"{sl:.0%}" if sl else "none"})

    # ── Write outputs ─────────────────────────────────────────────────────────

    # 1. Equity curve (all configs, default stop)
    eq_all = pd.concat(all_equity, ignore_index=True)
    eq_path = OUT_DIR / f"equity_curve_{TODAY}.csv"
    eq_all.to_csv(eq_path, index=False)
    log.info("Equity curve: %s (%d rows)", eq_path, len(eq_all))

    # 2. Metrics table
    metrics_df = pd.DataFrame(all_metrics)
    metrics_path = OUT_DIR / f"metrics_table_{TODAY}.csv"
    metrics_df.to_csv(metrics_path, index=False)
    log.info("Metrics table:\n%s", metrics_df[["config", "cagr", "max_dd", "mar"]].to_string(index=False))

    # 3. Sensitivity table
    sens_df = pd.DataFrame(sensitivity_rows)
    sens_path = OUT_DIR / f"sensitivity_table_{TODAY}.csv"
    sens_df.to_csv(sens_path, index=False)
    log.info("Sensitivity table: %s", sens_path)

    # 4. Trade log
    if all_trades:
        trades_all = pd.concat(all_trades, ignore_index=True)
        trades_path = OUT_DIR / f"trade_log_{TODAY}.csv"
        trades_all.to_csv(trades_path, index=False)
        log.info("Trade log: %s (%d trades)", trades_path, len(trades_all))

    # 5. Rejected signals (capacity diagnostic — council Q5)
    if all_rejected:
        rej_df = pd.DataFrame(all_rejected)
        rej_path = OUT_DIR / f"rejected_signals_{TODAY}.csv"
        rej_df.to_csv(rej_path, index=False)
        cap_rej = (rej_df["reason"] == "slots_full").sum()
        filt_rej = (rej_df["reason"] == "dna_filter").sum()
        log.info("Rejected: %d total | capacity=%d | filter=%d", len(rej_df), cap_rej, filt_rej)

    # 6. Lookahead audit (council Q5 addition)
    red_flag_results = {}
    for m in all_metrics:
        flags = []
        if m.get("cagr", 0) > SANITY["cagr_max"]:
            flags.append(f"CAGR {m['cagr']:.1%} > 30%")
        if m.get("max_dd", 1) < SANITY["maxdd_min"]:
            flags.append(f"MaxDD {m['max_dd']:.1%} < 15%")
        mar_val = m.get("mar", float("nan"))
        if not np.isnan(mar_val) and mar_val > SANITY["mar_max"]:
            flags.append(f"MAR {mar_val:.2f} > 1.0")
        red_flag_results[m["config"]] = flags if flags else ["PASS"]

    audit = {
        "mode":                     MODE_LABEL,
        "label":                    SIM_LABEL,
        "signal_type":              SIGNAL_TYPE,
        "generated":                TODAY,
        "lookahead_disclosure": (
            "DNA profiles are fit on 2017–2026 (same window as simulation). "
            "Joining DNA labels to historical signals is IN-SAMPLE LOOKAHEAD. "
            "This is a descriptive filter study, NOT a walk-forward tradeable backtest. "
            "Walk-forward refit is required before any tradeable claims."
        ),
        "entry_timing":             "T+1 open (next trading bar — no same-bar fill)",
        "stop_detection":           "Intraday low vs. stop_price = entry × (1 + stop_loss)",
        "production_status_used":   False,
        "warmup_bars":              MIN_WARMUP_BARS,
        "sim_start":                str(SIM_START.date()),
        "touch_tolerance_pct":      TOUCH_TOLERANCE,
        "n_slots":                  N_SLOTS,
        "slot_fraction":            SLOT_FRACTION,
        "hold_days":                HOLD_DAYS,
        "configs_run":              list(CONFIGS.keys()),
        "stop_levels_run":          [str(s) for s in STOP_LEVELS],
        "total_signals":            len(signals),
        "signals_per_year_avg":     round(signals_per_year, 1),
        "sanity_thresholds":        SANITY,
        "red_flag_results":         red_flag_results,
        "survivorship_note": (
            "Panel may exclude delisted/merged symbols. Unquantified upward bias. "
            "Walk-forward validation should use point-in-time universe."
        ),
    }
    audit_path = OUT_DIR / f"lookahead_audit_{TODAY}.json"
    audit_path.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    log.info("Lookahead audit: %s", audit_path)

    # 7. Run log (markdown)
    run_log_lines = [
        f"# DNA Strategy Sim — Run Log {TODAY}",
        "",
        f"> {SIM_LABEL}  |  Mode: `{MODE_LABEL}`",
        "",
        "## Lookahead Disclosure",
        "",
        audit["lookahead_disclosure"],
        "",
        "## Configs Run",
        "",
        "| Config | CAGR | MaxDD | MAR | Stop |",
        "|---|---|---|---|---|",
    ]
    for m in all_metrics:
        mar_str = f"{m['mar']:.2f}" if not np.isnan(m.get("mar", float("nan"))) else "—"
        run_log_lines.append(
            f"| {m['config']} | {m['cagr']:.1%} | {m['max_dd']:.1%} | {mar_str} | {m['stop_level']} |"
        )

    run_log_lines += [
        "",
        "## Expected Sanity Ranges (council spec)",
        "",
        "| Config | CAGR | MaxDD | MAR |",
        "|---|---|---|---|",
        "| Baseline | 8–14% | 25–35% | 0.30–0.45 |",
        "| DNA v1 | 12–18% | 22–30% | 0.45–0.65 |",
        "| DNA + BULL | 14–22% | 18–28% | 0.55–0.85 |",
        "",
        "> CAGR >30% → lookahead bug | MaxDD <15% → missing Mar2020/Apr2022 | MAR >1.0 → bug",
        "",
        "## Signals",
        f"- Total reconstructed: {len(signals)}",
        f"- Rate: {signals_per_year:.0f}/year avg",
        f"- Signal type: `{SIGNAL_TYPE}`",
        "",
        "## Red Flag Results",
        "",
    ]
    for cfg, flags in red_flag_results.items():
        run_log_lines.append(f"- **{cfg}:** {'; '.join(flags)}")

    run_log_lines += [
        "",
        "## Outputs",
        f"- `equity_curve_{TODAY}.csv`",
        f"- `metrics_table_{TODAY}.csv`",
        f"- `sensitivity_table_{TODAY}.csv`",
        f"- `trade_log_{TODAY}.csv`",
        f"- `rejected_signals_{TODAY}.csv`",
        f"- `lookahead_audit_{TODAY}.json`",
        "",
        "## Next Action for ChatGPT",
        "1. Review red flag results vs. expected sanity ranges.",
        "2. If CAGR and MAR fall within expected ranges: in-sample overlay is plausible.",
        "3. Decision required: fund walk-forward refit (Q3-ii) to convert this to a tradeable claim?",
        "4. If MaxDD <15%: investigate whether March 2020 / April 2022 drawdowns are captured.",
        "",
        f"> {RESEARCH_ONLY_LABEL}",
    ]

    log_path = OUT_DIR / f"run_log_{TODAY}.md"
    log_path.write_text("\n".join(run_log_lines), encoding="utf-8")
    log.info("Run log: %s", log_path)

    log.info("=" * 70)
    log.info("Done. %s", SIM_LABEL)
    log.info("Outputs → %s", OUT_DIR)
    log.info("=" * 70)


if __name__ == "__main__":
    main()
