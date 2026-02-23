# Minervini Backtest (SEPA + VCP + Champion risk)

Engine spec: **Universe → Setup → Trigger → Risk → Exit → Sizing**, all OHLCV-based for backtest.

- **Book 1 (Stock Market Wizard):** Trend Template, VCP proxy, pivot breakout.
- **Book 2 (Think & Trade Like a Champion):** Risk-first, R-multiple sizing, sell rules.

## Structure

```
minervini_backtest/
  data/raw/          # One CSV per symbol: Date, Open, High, Low, Close, Volume
  data/curated/       # Parquet (after import)
  src/
    indicators.py     # MA, ATR, ATR%, Vol SMA, 52w high/low
    filters.py        # TT_Strict, TT_Lite
    setups.py         # VCP proxy (CS+VDU), 3-week tight
    triggers.py       # Breakout, retest (M4)
    risk.py           # Stop (pct/ATR), position_size_r
    exits.py         # Fail-fast, hard stop, time stop, trend break, climax, trailing MA
    engine.py        # Bar-by-bar engine, gates
    metrics.py       # PF, expectancy, MaxDD, CAGR, trade stats
  configs/
    M1.yaml .. M5.yaml
  scripts/
    import_csv_to_parquet.py
    report_compare_versions.py
  run.py
```

## Versions (M1–M8)

| Version | Filter   | Setup   | Trigger     | Exit                          |
|---------|----------|---------|------------|-------------------------------|
| M1      | TT_Lite  | VCP     | Break 20–60, Vol>1.5× | Hard stop + MA50 break        |
| M2      | TT_Strict| VCP strong | Break 30–80, Vol>1.8× | Fail-fast 3d + Time stop 15d + Hard |
| M3      | TT_Lite  | 3WT     | Break 15d   | Hard + Partial +2R + Trail MA20   |
| M4      | TT_Lite  | VCP     | Break + **retest** | Fail-fast + MA50              |
| M5      | TT_Lite  | VCP     | Same as M1  | Same; risk_pct 0.5% (Champion overlay) |
| M6      | TT_Lite  | VCP     | Break + **No-Chase** (Close ≤ pivot×1.015) | Hard + MA50 |
| M7      | TT_Lite  | VCP     | Same       | Stop = entry − 2×ATR only (volatility stop) |
| M8      | TT_Lite  | VCP     | Same       | Partial +1.5R + Trail MA20 (profit protection) |
| M9      | TT_Lite  | VCP     | Pivot = high of 15-bar tight range | Hard + MA50 |
| M10     | TT_Lite  | VCP     | Gap filter: TR>2.5×ATR → wait for day+1 above pivot | Hard + MA50 |
| M11     | TT_Lite  | VCP     | + Regime gate (VN30 vol/MA200)     | Hard + MA50 |

## Quick start

1. **Data:** Put CSV per symbol in `data/raw/` (columns: Date, Open, High, Low, Close, Volume), then:
   ```bash
   python minervini_backtest/scripts/import_csv_to_parquet.py
   ```
   Or use existing project data: copy/symlink or point `--raw` to a folder of CSVs.

2. **Run one config (e.g. M1):**
   ```bash
   cd "0. VN Agent System"
   python minervini_backtest/run.py --config M1
   ```

3. **Run all M1–M5 and compare:**
   ```bash
   python minervini_backtest/run.py
   ```
   Output: `minervini_backtest/minervini_backtest_results.csv`

4. **Report:**
   ```bash
   python minervini_backtest/scripts/report_compare_versions.py
   ```

5. **QA & research (see docs/QA_RESEARCH_PLAN.md):**
   - Data sanity: `python minervini_backtest/scripts/data_sanity.py`
   - Unit tests: `PYTHONPATH=minervini_backtest/src python -m pytest minervini_backtest/tests/test_engine_correctness.py -v`
   - Sensitivity (PF × fee × min_hold): `python minervini_backtest/scripts/sensitivity_fee_minhold.py --config M1 [--fetch]`
   - Gate attribution: `python minervini_backtest/scripts/gate_attribution.py [--fetch]`
   - Walk-forward (train/val/holdout): `python minervini_backtest/scripts/walk_forward.py [--fetch]`
   - Golden ledger (spot-check): `python minervini_backtest/run.py --golden MBB 2021` (or `--fetch --golden MBB 2021`)
   - **Decision Matrix** (realism fee 20/30, min_hold=3, pass/fail, Survivors/Gross-only/Noise): `python minervini_backtest/scripts/decision_matrix.py [--fetch]`
   - **Gate attribution waterfall** (2 universes, delta expectancy_r/PF/trades): `python minervini_backtest/scripts/gate_attribution.py --universe both [--fetch]`
   - **Deploy candidate** (M4 vs M3 @ realism): `python minervini_backtest/scripts/deploy_candidate_selection.py [--fetch]`
   - Failure modes & deploy logic: `minervini_backtest/docs/FAILURE_MODES_AND_DEPLOY.md`
   - **Core thesis & deploy framework** (T1/T2/T3, D1/D2/D3, iterate I1/I2/I3, two-tier): `minervini_backtest/docs/CORE_THESIS_AND_DEPLOY_FRAMEWORK.md`
   - **Deploy gates check:** `python minervini_backtest/scripts/deploy_gates_check.py` (sau khi có walk_forward_results + decision_matrix)
   - **Decision layer draft** từ outputs: `python minervini_backtest/scripts/decision_layer_from_outputs.py` → `decision_layer_draft.md`
   - **Playbook đóng vòng (1A+1B+1C → draft → D1/D2/D3 → iterate I2/I1/I3):** `minervini_backtest/docs/RUN_PLAYBOOK_CLOSED_LOOP.md`

## Output metrics

- **PF, Win rate, Avg win/loss, Expectancy/trade, MaxDD, CAGR**
- **Trade count / year, Median return per trade, Median hold**
- Optional sensitivity: PF vs fee (10/20/30/50 bps) and min_hold (0/3/5) via multiple runs and manual compare.

## Parameter grid (for sweep)

- TT: lite / strict  
- base_lookback: 20, 30, 40, 60, 80  
- vol_mult: 1.2, 1.5, 1.8  
- stop_pct: 3, 4, 5, 6, 8 (%)  
- ATR_k: 1.5, 2.0, 2.5  
- fail_fast_days: 2, 3, 5  
- time_stop_days: 10, 15, 20  
- take_partial: none / 1R / 2R  
- trail_ma: MA10 / MA20 / MA50  

Edit `configs/M*.yaml` or override in code to sweep.
