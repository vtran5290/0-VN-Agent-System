# Institutional Accumulation Scan

**Layer:** Research / ranking (not execution).  
**Cadence:** Weekly or daily on demand; Smart Money monthly JSON = slow prior.  
**Data:** OHLCV from `data/stocks/` + benchmark `data/benchmark/VNINDEX.csv`; context from `data/smart_money/monthly/` or fallback priors.

---

## 1. Purpose

Hybrid scan combining:

- **Layer A — Smart Money context:** fund-report priors (consensus core, sectors, Vingroup distortion regime).
- **Layer B — Money flow:** CMF, OBV, Chaikin A/D, PVT, up/down volume, volume expansion quality (OHLCV only).
- **Layer C — Price structure:** RS vs VNINDEX, volatility contraction, pullback quality, close strength.
- **Layer D — Risk filters:** extension, distribution days, illiquidity, one-bar spikes, Vingroup distortion without flow confirmation.

April 2026 design context: fragile narrow leadership; avoid chasing headline-beta Vingroup moves without persistent accumulation.

---

## 2. Signal framework (v1.1)

| Block | Weight | Inputs |
|-------|--------|--------|
| Smart money context | 18% | Tags from monthly/priors; optional `n_funds` / `avg_weight` from monthly JSON |
| Money flow | 38% | **4 groups** (equal-weight): CMF; OBV/PVT; ADL; Participation (+ turnover accel) |
| Price structure | 28% | RS 20/60 vs VNINDEX, MA hold, vol contraction, pullback, close strength |
| Risk penalty | −16% cap | Extension, daily + weekly dist, VIN distortion flag, CMF conflict, illiquidity |

**Tiers:**

| Tier | Rule |
|------|------|
| Tier 1 | score ≥ 72, money_flow ≥ 55, risk ≤ 35 (all regimes) |
| Tier 2 | ≥ 58 normal / ≥ 52 fragile; or percentile ≥ 78th among liquid (floors apply) |
| Tier 3 | ≥ 42 normal / ≥ 38 fragile; or percentile ≥ 62nd; consensus-core floor in fragile regime |
| Reject | else / fails liquidity |

**Fragile regime** = `fragile_uptrend_narrow_leadership` in `regime_label`.

---

## 3. Indicators (OHLCV-only)

All computed on data **≤ scan_date** (no lookahead).

- **CMF(20)** daily and weekly (Friday week-end).
- **OBV** slope 20/50 (normalized linear slope).
- **Chaikin A/D line** slope 20; divergence flag vs price.
- **PVT** slope 20/50.
- **Up/down volume ratio** (20d): sum(vol on up close) / sum(vol on down close).
- **HV up/down count** (20d): days with vol > 1.5× vol MA20 on up vs down closes.
- **Turnover acceleration:** 5d avg value / 50d avg value − 1 (VND-scaled).
- **Weekly distribution weeks:** down week + rising volume in last 6 weekly bars.
- **RS vs VNINDEX** 20d and 60d relative returns.
- **Volatility contraction:** BB width 120d percentile ≤ 35 with CMF > 0.
- **Pullback quality:** 10d drawdown < 8% after 20d gain, down-volume < up-volume in pullback.
- **Distribution risk:** rolling 25d distribution-day count (O'Neil-style).
- **Vingroup distortion flag:** VIN symbol + strong RS + extension + (weekly CMF weak/missing OR daily/weekly CMF conflict OR OBV/ADL weak). Flag only — not auto-reject.

**Not implemented (marked UNAVAILABLE in output):** anchored VWAP, pocket pivot (optional future).

---

## 4. Smart money context source

1. `data/smart_money/monthly/smart_money_{YYYY-MM}.json` if present (`ticker_consensus`, `sector_consensus`, `regime_bias`, `flags`).
2. Else `data/smart_money/priors/apr2026_default_priors.json` (April 2026 composite).
3. Missing monthly → `context_source=fallback_priors`, note in report.

Tags (not buy signals): `consensus_core`, `consensus_second_ring`, `fund_commentary_mention`, `selective_fund_bet`, `outside_fund_disclosure`, `emerging_accumulation_candidate`, etc.

**Universe (important):** Scan runs on **all liquid** names in `data/stocks/` — NOT limited to fund holdings. Fund lists in `apr2026_default_priors.json` (`consensus_core`, `commentary_mentions`, …) are **context priors only**. Names with strong flow but no fund tag → `emerging_accumulation_candidate` (requires `score_risk_penalty ≤ 30`).

**Excluded vehicles:** ETF / open-fund tickers (sector `Quỹ mở`, symbol `E1VFVN30`) are dropped before candidate output — not ranked as accumulation names.

---

## 5. Outputs

| Path | Description |
|------|-------------|
| `outputs/scans/institutional_accumulation_{date}.csv` | Full ranked table |
| `outputs/scans/institutional_accumulation_{date}.json` | Same + metadata + sector summary |
| `outputs/scans/institutional_accumulation_{date}.md` | Research summary |
| `outputs/scans/institutional_accumulation_latest.csv` | Copy of latest run |
| `outputs/scans/institutional_accumulation_rejected_{date}.csv` | Near-miss rejections |

**Workflow contract:** Council / weekly reads **top Tier 1–2 tickers + compact metrics** only. Scan does not set `final_action` or orders.

---

## 6. Commands

```bash
# Default: latest date in VNINDEX benchmark
python -m src.scans.institutional_accumulation.run

# Explicit as-of
python -m src.scans.institutional_accumulation.run --as-of 2026-04-30

# Watchlist only, stricter liquidity
python -m src.scans.institutional_accumulation.run --as-of 2026-04-30 --watchlist config/watchlist.txt --min-adv20 5e9

# Validation spot-check
python -m src.scans.institutional_accumulation.run --validate-only --as-of 2026-04-30
```

Makefile: `make institutional-accumulation-scan`

**ChatGPT external review:** `make institutional-accumulation-chatgpt-zip` → attach zip + paste `docs/trading/CHATGPT_INSTITUTIONAL_ACCUMULATION_SCAN_REVIEW_PROMPT.md`

---

## 7. Caveats

- **Source:** Local CSV OHLCV (FireAnt-exported SSOT in repo); not live API unless refreshed separately.
- **Sector:** From `data/research/level4_stock_scan_adv2b_all.csv` when available; else `Unknown`.
- **Sector RS:** Sector index RS not computed unless sector benchmark series added — column omitted / null.
- **VIN baseline:** Dual universe reporting for aggregates not in single-name scan; VIN names flagged explicitly.
- **Proxies:** VNINDEX only for RS; cap-weight index may be Vingroup-skewed in 2025–2026.
- **Units:** `price_unit_mode` + `value_scale_factor` on each row; validation warns on ambiguous units.
- **Compact output:** `tier3_near_miss` (top 3) when Tier 1/2 empty — research only.

---

## 8. Validation checklist

1. Cross-section: sector concentration in top decile.
2. Score dominance: component correlation sanity.
3. Spot-check: MBB, CTG, MWG, HPG, GMD vs VIC, VHM.
4. Missing data: null metrics, not fabricated.
5. No-lookahead: slice `df[df.date <= scan_date]`.
