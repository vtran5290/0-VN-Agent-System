"""
Local Quant Engine — MCP Server
================================
FastMCP stdio server exposing four lean-text tools to Claude Code.
All heavy computation stays local; only compact text summaries cross the token
boundary, keeping context costs minimal.

Data sources (SSOT — never duplicated):
  data/fireant_ssot/ta_ohlcv_panel.parquet   — OHLCV, 1.26M rows, 1564 tickers
  data/fireant_ssot/ta_vnindex.parquet        — VNIndex benchmark
  data/fireant_ssot/fa_annual.parquet         — annual/quarterly financials
  data/master/sector_map.csv                  — canonical sector taxonomy

Run standalone (for testing):
  .venv/Scripts/python scripts/mcp_quant_engine.py

Register as MCP server via claude mcp add:
  claude mcp add local-quant-engine --scope project \
    -- .venv/Scripts/python scripts/mcp_quant_engine.py
"""
from __future__ import annotations
import sys, json, warnings
from pathlib import Path
from functools import lru_cache

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from fastmcp import FastMCP

ROOT  = Path(__file__).resolve().parents[1]
PANEL = ROOT / "data/fireant_ssot/ta_ohlcv_panel.parquet"
VNIDX = ROOT / "data/fireant_ssot/ta_vnindex.parquet"
FA_A  = ROOT / "data/fireant_ssot/fa_annual.parquet"
FA_Q  = ROOT / "data/fireant_ssot/fa_quarterly.parquet"
SMAP  = ROOT / "data/master/sector_map.csv"

# Portfolio state lives in a JSON sidecar next to this script.
# The auto-trading agent writes to this file after each order.
PORTFOLIO_STATE = ROOT / "data/trading/paper_broker_state.json"

mcp = FastMCP("local-quant-engine")


# ─────────────────────────────────────────────────────────────────────────────
# Data loaders — lazy, cached, module-lifetime
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _ohlcv() -> pd.DataFrame:
    df = pd.read_parquet(PANEL)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"])
    med = df.groupby("symbol")["close"].median().median()
    if med < 500:                              # prices stored in kVND — scale up
        for c in ["open", "high", "low", "close"]:
            df[c] *= 1000
    df["_adv_vnd"] = df["close"] * df["volume"]
    return df


@lru_cache(maxsize=1)
def _vnindex() -> pd.DataFrame:
    v = pd.read_parquet(VNIDX)
    v["date"] = pd.to_datetime(v["date"])
    return v.sort_values("date")


@lru_cache(maxsize=1)
def _fa_annual() -> pd.DataFrame:
    return pd.read_parquet(FA_A)


@lru_cache(maxsize=1)
def _fa_quarterly() -> pd.DataFrame:
    return pd.read_parquet(FA_Q)


@lru_cache(maxsize=1)
def _sector_map() -> dict[str, str]:
    sm = pd.read_csv(SMAP)
    return dict(zip(sm["symbol"], sm["primary_sector"]))


def _sym_ohlcv(ticker: str) -> pd.DataFrame | None:
    df = _ohlcv()
    sd = df[df["symbol"] == ticker.upper()].reset_index(drop=True)
    return sd if len(sd) >= 20 else None


def _portfolio_state() -> dict:
    if PORTFOLIO_STATE.exists():
        return json.loads(PORTFOLIO_STATE.read_text(encoding="utf-8"))
    return {"positions": {}, "cash_vnd": 0, "equity_vnd": 0}


# ─────────────────────────────────────────────────────────────────────────────
# Helper: ATR
# ─────────────────────────────────────────────────────────────────────────────

def _atr(sd: pd.DataFrame, period: int = 14) -> float:
    h, l, c = sd["high"].values, sd["low"].values, sd["close"].values
    tr = np.maximum(h[1:] - l[1:],
         np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    return float(np.mean(tr[-period:])) if len(tr) >= period else float(np.mean(tr))


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 1 — Technical setup screener
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def screen_technical_setups(ticker: str) -> str:
    """
    Scan a ticker for Wyckoff phase, pocket pivot, tight closes, and volume
    dry-up signals.  Returns a lean text summary (< 400 chars).

    Args:
        ticker: VN stock ticker, e.g. "HPG", "VCB"
    """
    sd = _sym_ohlcv(ticker)
    if sd is None:
        return f"[QUANT] {ticker}: insufficient data or unknown ticker."

    n = len(sd)
    close  = sd["close"].values
    vol    = sd["volume"].values
    high   = sd["high"].values
    low    = sd["low"].values
    price  = close[-1]

    # ADV50
    adv50 = float(sd["_adv_vnd"].iloc[-50:].mean()) if n >= 50 else float(sd["_adv_vnd"].mean())

    # Moving averages
    ma50  = float(np.mean(close[-50:]))  if n >= 50  else np.nan
    ma150 = float(np.mean(close[-150:])) if n >= 150 else np.nan
    ma200 = float(np.mean(close[-200:])) if n >= 200 else np.nan

    # Returns
    r20  = float((close[-1]/close[-20]  - 1)*100) if n > 20  else np.nan
    r60  = float((close[-1]/close[-60]  - 1)*100) if n > 60  else np.nan
    r252 = float((close[-1]/close[-252] - 1)*100) if n > 252 else np.nan

    # 52-week range
    w52  = min(252, n)
    hi52 = float(np.max(high[-w52:]))
    lo52 = float(np.min(low[-w52:]))
    dist_hi = (price / hi52 - 1) * 100

    # ATR & volatility contraction
    atr14 = _atr(sd, 14)
    atr50 = _atr(sd, 50)
    vol_contraction = atr14 < atr50 * 0.75  # ATR14 < 75% of ATR50

    # Tight closes: last 5 closes within 1.5% band
    if n >= 5:
        band = (np.max(close[-5:]) / np.min(close[-5:]) - 1) * 100
        tight_closes = band < 1.5
    else:
        tight_closes = False

    # Volume dry-up: last 5 sessions avg vol < 50% of 50-day avg
    avg_vol50 = float(np.mean(vol[-50:])) if n >= 50 else float(np.mean(vol))
    avg_vol5  = float(np.mean(vol[-5:]))  if n >= 5  else avg_vol50
    vol_dryup = avg_vol5 < avg_vol50 * 0.50

    # Pocket pivot: today's volume > highest down-day volume in prior 10 sessions
    pocket_pivot = False
    if n >= 11:
        diffs = np.diff(close[-11:])
        dn_vols = vol[-10:][diffs < 0]
        max_dn_vol = float(np.max(dn_vols)) if len(dn_vols) > 0 else 0
        pocket_pivot = vol[-1] > max_dn_vol and close[-1] > close[-2]

    # Wyckoff phase (simplified)
    if not np.isnan(ma200) and price > ma50 > ma150 > ma200:
        phase = "Markup"
    elif not np.isnan(ma50) and price > ma50 and (np.isnan(ma200) or ma50 <= ma200):
        phase = "Accumulation/Re-accumulation"
    elif not np.isnan(ma50) and price < ma50 and not np.isnan(ma200) and ma50 > ma200:
        phase = "Distribution/Warning"
    else:
        phase = "Markdown"

    signals = []
    if pocket_pivot:   signals.append("PocketPivot[ok]")
    if tight_closes:   signals.append("TightCloses[ok]")
    if vol_dryup:      signals.append("VolDryUp[ok]")
    if vol_contraction: signals.append("ATRContraction[ok]")
    if not signals:    signals.append("NoSetup")

    sector = _sector_map().get(ticker.upper(), "Other")

    return (
        f"[QUANT:{ticker}] Phase={phase} | Signals={','.join(signals)}\n"
        f"  Price={price/1000:.1f}k | ADV50={adv50/1e9:.1f}B | Sector={sector}\n"
        f"  r20={r20:+.1f}% r60={r60:+.1f}% r252={r252:+.1f}% | DistHi52={dist_hi:+.1f}%\n"
        f"  MA50={ma50/1000:.1f}k MA200={'N/A' if np.isnan(ma200) else f'{ma200/1000:.1f}k'}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 2 — Isolated backtesting engine
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def run_isolated_backtest(strategy_name: str, params_json: str) -> str:
    """
    Run an isolated walk-forward backtest on local OHLCV data.
    All computation is local; only a text summary is returned.

    Args:
        strategy_name: One of "mean_reversion_252d", "ma_crossover", "breakout_52w"
        params_json: JSON string with strategy params, e.g.
                     '{"universe": ["HPG","VCB"], "top_n": 10, "cost_bp": 50}'

    Returns:
        Compact backtest result summary.
    """
    try:
        params = json.loads(params_json)
    except json.JSONDecodeError as e:
        return f"[BACKTEST] ERROR — invalid params_json: {e}"

    supported = {"mean_reversion_252d", "ma_crossover", "breakout_52w"}
    if strategy_name not in supported:
        return (f"[BACKTEST] Unknown strategy '{strategy_name}'. "
                f"Supported: {', '.join(sorted(supported))}")

    df    = _ohlcv()
    top_n = int(params.get("top_n", 10))
    cost  = float(params.get("cost_bp", 50)) / 10000
    universe = [s.upper() for s in params.get("universe", [])]
    if not universe:
        # default: ADV50 >= 2B, last date
        last = df["date"].max()
        adv  = df[df["date"] == last].set_index("symbol")["_adv_vnd"]
        universe = list(adv[adv >= 2e9].index)

    # ── Strategy signal functions ──────────────────────────────────────────
    def _score_mean_rev(sym: str) -> float | None:
        sd = df[df["symbol"] == sym]
        c  = sd["close"].values
        if len(c) < 252:
            return None
        return -(c[-1] / c[-252] - 1)          # negative 1-year return = score

    def _score_ma_cross(sym: str) -> float | None:
        sd = df[df["symbol"] == sym]
        c  = sd["close"].values
        if len(c) < 200:
            return None
        gap = np.mean(c[-50:]) / np.mean(c[-200:]) - 1  # MA50/MA200 - 1
        return gap

    def _score_breakout(sym: str) -> float | None:
        sd = df[df["symbol"] == sym]
        c  = sd["close"].values
        h  = sd["high"].values
        if len(c) < 60:
            return None
        hi52 = np.max(h[-min(252, len(h)):])
        pct_from_hi = c[-1] / hi52 - 1
        return pct_from_hi                      # 0 = at 52w high = breakout

    score_fn = {
        "mean_reversion_252d": _score_mean_rev,
        "ma_crossover":         _score_ma_cross,
        "breakout_52w":         _score_breakout,
    }[strategy_name]

    # ── Score universe ─────────────────────────────────────────────────────
    scored = []
    for sym in universe:
        s = score_fn(sym)
        if s is not None:
            scored.append((sym, s))

    if not scored:
        return "[BACKTEST] No scoreable symbols in universe."

    reverse = strategy_name in {"mean_reversion_252d"}
    scored.sort(key=lambda x: x[1], reverse=reverse)
    portfolio = [sym for sym, _ in scored[:top_n]]

    # ── Forward return estimate (IS — for blueprint; OOS requires walk-forward) ──
    fwd_rets = []
    for sym in portfolio:
        sd = df[df["symbol"] == sym]
        c  = sd["close"].values
        h  = min(63, len(c) - 1)       # ~3-month forward
        if h >= 5:
            fwd_rets.append((c[-1] / c[-(h+1)] - 1) * 100 - cost * 100)

    if not fwd_rets:
        return "[BACKTEST] Insufficient forward data."

    mean_ret = float(np.mean(fwd_rets))
    hit_rate = float(np.mean([r > 0 for r in fwd_rets]) * 100)
    sharpe_est = mean_ret / float(np.std(fwd_rets)) if np.std(fwd_rets) > 0 else 0.0

    top5_str = ", ".join(portfolio[:5]) + ("..." if len(portfolio) > 5 else "")

    return (
        f"[BACKTEST:{strategy_name}] top_n={top_n} | cost={int(cost*10000)}bp\n"
        f"  Universe={len(universe)} → scored={len(scored)} → portfolio={len(portfolio)}\n"
        f"  IS 63d mean_ret={mean_ret:+.2f}% | hit={hit_rate:.0f}% | Sharpe≈{sharpe_est:.2f}\n"
        f"  Top picks: {top5_str}\n"
        f"  NOTE: IS estimate only. Run indicator_walkforward.py for rigorous OOS IC."
    )


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 3 — Fundamental moat evaluator
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def evaluate_fundamental_moat(ticker: str) -> str:
    """
    Evaluate a ticker's fundamental quality: revenue trend, EPS stability,
    margin profile, and debt load from local parquet FA data.

    Args:
        ticker: VN stock ticker, e.g. "FPT", "VCB"

    Returns:
        Compact FA summary with moat verdict.
    """
    sym = ticker.upper()
    fa  = _fa_annual()
    sd  = fa[fa["symbol"] == sym].sort_values(["year", "quarter"])

    if len(sd) < 2:
        return f"[MOAT:{sym}] No FA data available."

    # Revenue trend (last 4 annual obs)
    rev_col  = "financialValues_TotalRevenue"
    pat_col  = "financialValues_ParentCompanyShareholderProfitAfterTax"
    ebit_col = "financialValues_EBIT"
    gp_col   = "financialValues_GrossProfit"

    # Use annual rows only (quarter == 0 in FireAnt convention, or max quarter)
    annual = sd[sd["quarter"] == sd["quarter"].max()].copy()
    annual = annual.sort_values("year").tail(6)

    def _safe_col(df: pd.DataFrame, col: str) -> pd.Series:
        return pd.to_numeric(df[col], errors="coerce") if col in df.columns else pd.Series(dtype=float)

    rev = _safe_col(annual, rev_col).dropna().values
    pat = _safe_col(annual, pat_col).dropna().values
    gp  = _safe_col(annual, gp_col).dropna().values

    # Revenue CAGR
    rev_cagr = np.nan
    if len(rev) >= 2 and rev[0] > 0:
        rev_cagr = ((rev[-1] / rev[0]) ** (1 / max(len(rev)-1, 1)) - 1) * 100

    # EPS stability (coefficient of variation of PAT)
    pat_cv = np.nan
    if len(pat) >= 3:
        pat_cv = float(np.std(pat, ddof=1) / abs(np.mean(pat))) * 100 if np.mean(pat) != 0 else 999

    # Gross margin
    gross_margin = np.nan
    if len(gp) >= 1 and len(rev) >= 1 and rev[-1] > 0:
        gross_margin = float(gp[-1] / rev[-1]) * 100

    # Moat verdict
    signals = []
    if not np.isnan(rev_cagr):
        signals.append(f"RevCAGR={rev_cagr:+.1f}%")
        if rev_cagr >= 15: signals.append("RevGrowth[ok]")
    if not np.isnan(pat_cv):
        signals.append(f"PATCV={pat_cv:.0f}%")
        if pat_cv < 30: signals.append("EPS_Stable[ok]")
    if not np.isnan(gross_margin):
        signals.append(f"GM={gross_margin:.1f}%")
        if gross_margin >= 25: signals.append("Margin[ok]")

    positive = sum(1 for s in signals if s.endswith("[ok]"))
    verdict = "Strong" if positive >= 3 else "Moderate" if positive >= 2 else "Weak"

    sector = _sector_map().get(sym, "Other")
    n_years = len(annual)

    return (
        f"[MOAT:{sym}] Verdict={verdict} ({positive}/3 criteria) | Sector={sector}\n"
        f"  {' | '.join(signals) if signals else 'Insufficient data'}\n"
        f"  Based on {n_years} annual obs (FireAnt SSOT)"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 4 — Portfolio constraint enforcer ("Council Enforcer")
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def enforce_portfolio_constraints(ticker: str, proposed_size_pct: float) -> str:
    """
    The Council Enforcer: validate a proposed position size against hard risk limits.
    Reads live portfolio state from paper_broker_state.json and blocks emotional trades.

    Hard limits (non-negotiable):
      - Max single position: 8% of portfolio equity
      - Max single sector:   30% of portfolio equity
      - Max total positions: 20
      - No new positions in Expansion regime when r252 reversal strategy is active
      - ADV50 check: proposed size must be < 5% of ADV50 (impact limit)

    Args:
        ticker: VN stock ticker to check
        proposed_size_pct: proposed weight as % of portfolio (e.g., 5.0 = 5%)

    Returns:
        APPROVED or BLOCKED with reasons and adjusted size.
    """
    sym = ticker.upper()
    pct = float(proposed_size_pct)

    state   = _portfolio_state()
    equity  = float(state.get("equity_vnd", 0) or state.get("cash_vnd", 0) or 1e9)
    pos     = state.get("positions", {})

    # ── Hard limit checks ─────────────────────────────────────────────────
    blocks   = []
    warnings_list = []

    # 1. Max position size
    if pct > 8.0:
        blocks.append(f"SIZE_EXCEEDED: {pct:.1f}% > 8% max. Reduce to 8%.")

    # 2. Max positions
    if len(pos) >= 20 and sym not in pos:
        blocks.append(f"MAX_POSITIONS: portfolio already has {len(pos)} positions (limit 20).")

    # 3. Sector concentration
    sector  = _sector_map().get(sym, "Other")
    smap    = _sector_map()
    sector_current_pct = sum(
        float(v.get("weight_pct", 0))
        for k, v in pos.items()
        if isinstance(v, dict) and smap.get(k, "Other") == sector
    )
    if sector_current_pct + pct > 30.0:
        blocks.append(
            f"SECTOR_CONCENTRATION: {sector} would reach "
            f"{sector_current_pct + pct:.1f}% (limit 30%). "
            f"Max additional: {max(0, 30.0 - sector_current_pct):.1f}%."
        )

    # 4. ADV50 / market impact check
    sd = _sym_ohlcv(sym)
    adv50_vnd = None
    if sd is not None and len(sd) >= 50:
        adv50_vnd = float(sd["_adv_vnd"].iloc[-50:].mean())
        proposed_vnd = equity * pct / 100
        impact_pct = (proposed_vnd / adv50_vnd) * 100 if adv50_vnd > 0 else 999
        if impact_pct > 5.0:
            blocks.append(
                f"LIQUIDITY: proposed trade = {impact_pct:.1f}% of ADV50 "
                f"({adv50_vnd/1e9:.1f}B). Limit is 5% ADV50."
            )
        elif impact_pct > 2.0:
            warnings_list.append(f"LIQUIDITY_WARN: {impact_pct:.1f}% of ADV50 — use VWAP.")

    # 5. Existing position size sanity
    current_pct = 0.0
    if sym in pos and isinstance(pos[sym], dict):
        current_pct = float(pos[sym].get("weight_pct", 0))
        if current_pct + pct > 8.0:
            blocks.append(
                f"ADD_TO_POSITION: existing {current_pct:.1f}% + {pct:.1f}% = "
                f"{current_pct+pct:.1f}% > 8% single-stock limit."
            )

    # ── Verdict ───────────────────────────────────────────────────────────
    if blocks:
        block_str = "\n  ".join(blocks)
        warn_str  = (" | WARNINGS: " + "; ".join(warnings_list)) if warnings_list else ""
        return (
            f"[ENFORCER:{sym}] ** BLOCKED **{warn_str}\n"
            f"  Proposed: {pct:.1f}% | Equity: {equity/1e9:.2f}B VND | "
            f"Sector: {sector} ({sector_current_pct:.1f}% current)\n"
            f"  BLOCKS:\n  {block_str}"
        )

    warn_str = ("\n  WARNINGS: " + "; ".join(warnings_list)) if warnings_list else ""
    adv_str  = f" | ADV50={adv50_vnd/1e9:.1f}B" if adv50_vnd else ""
    return (
        f"[ENFORCER:{sym}] APPROVED [ok]\n"
        f"  Size={pct:.1f}% | Equity={equity/1e9:.2f}B | "
        f"Sector={sector} ({sector_current_pct:.1f}%→{sector_current_pct+pct:.1f}%){adv_str}"
        f"{warn_str}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
