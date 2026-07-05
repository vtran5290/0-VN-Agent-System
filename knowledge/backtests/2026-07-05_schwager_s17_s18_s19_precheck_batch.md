# S17 / S18 / S19 — Batch Degeneracy Pre-Check

**Date:** 2026-07-05
**Script:** `pp_backtest/cortex_schwager_s17_s18_s19_precheck_batch.py`
**OOS window:** 2020–2026

---

## S17 — FireAnt buy/sell flow data discovery

**Data discovery verdict:** PROCEED TO PRE-CHECK
**Pre-check verdict:** EXPRESSIBLE

| Q | Answer |
|---|--------|
| Q1 classification | FireAnt REST buyQuantity/sellQuantity — HOSE/HNX matched-order buy vs sell counts (not aggressor tick) |
| Q2 put-through | PARTIAL — putthroughVolume reported separately; buyQuantity/sellQuantity are deal-matched fields (verify HOSE spec) |
| Q3 coverage | OOS 2020-2026: 261/261 symbols with data; probe earliest {'VNM': '2012-01-03', 'ACB': '2012-01-03', 'AAA': '2012-01-03'} |
| Q4 survivorship | MEDIUM — delisted names may be absent from current FireAnt pull; OOS universe is trade-conditioned |
| Q5 rebuildable | YES on matched symbol-days; gaps exclude ticker-day from rolling windows |

- ratio_1d: n=4844, std=0.5127, pct_near_1.0=13.3%
- ratio_5d: n=4844, std=0.2769
- ratio_20d: n=4844, std=0.1961

---

## S18 — Sector breadth & persistence

**VERDICT (OOS diagnostic):** EXPRESSIBLE
- Sectors with ≥10 panel members: Agri, Consumer, Securities, Banks, Logistics, BDS, Oil_Gas, Steel
- IS qualifying sectors (activity proxy): 11
- OOS mean fire rate (k=1.0): 16.0%
- OOS mean fire rate (k=0.75): 22.8%
- IS mean continuation (up-days, k=1.0): 56.3%

---

## S19 — Co-sector cohort & VIN leader stability

**VERDICT:** EXPRESSIBLE
- Co-sector signal days (≥2 same sector, OOS): **1001**

| Sector | Leader stability (% days top RS = same symbol) |
|--------|-----------------------------------------------|
| Textile | 40.0% |
| Tech | 38.1% |
| Rubber | 33.3% |
| Steel | 33.3% |
| Agri | 20.5% |
| Logistics | 20.4% |
| Banks | 11.2% |
| Securities | 9.4% |
| Oil_Gas | 9.3% |
| Consumer | 6.4% |
| BDS | 4.1% |

### VIN check

- **VHM** (BDS): leader stability 4.1%
- **VRE** (BDS): leader stability 4.1%
- **VIC** (BDS): leader stability 4.1%
