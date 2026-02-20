# Runbook — Weekly Packet

## Core inputs (8 số tối thiểu — Pareto 20% → 80%)

MVP mỗi tuần chỉ cần điền **8 số** trong `data/raw/manual_inputs.json`:

| # | Nhóm    | Field                       | Mô tả ngắn                    |
|---|---------|-----------------------------|-------------------------------|
| 1 | Global  | `ust_2y`                    | UST 2Y                        |
| 2 | Global  | `ust_10y`                  | UST 10Y                       |
| 3 | Global  | `dxy`                      | DXY                           |
| 4 | Vietnam | `omo_net`                  | OMO net (bơm/hút ròng)       |
| 5 | Vietnam | `interbank_on`             | Interbank ON                  |
| 6 | Vietnam | `credit_growth_yoy`        | Credit growth YoY (hoặc YTD)  |
| 7 | Market  | `vnindex_level`            | VNIndex level                 |
| 8 | Market  | `distribution_days_rolling_20` | Distribution days rolling-20 |

Từ 8 số này đủ để:
- Facts section không "rỗng"
- Probability + allocation có logic hơn
- Execution layer bắt đầu dùng được

(Thêm nếu có: cpi_yoy, nfp, fed_tone, fx_usd_vnd. Regime: điền `overrides.global_liquidity`, `overrides.vn_liquidity` nếu chưa infer từ data.)

## Inputs (fill first)
- data/raw/manual_inputs.json
  - **Core 8:** ust_2y, ust_10y, dxy, omo_net, interbank_on, credit_growth_yoy, vnindex_level, distribution_days_rolling_20
  - Optional: cpi_yoy, nfp, fed_tone, fx_usd_vnd
  - overrides: global_liquidity, vn_liquidity

## Command
```bash
python -m src.report.weekly
```

## Claude tasks
- Update `data/raw/manual_inputs.json` with latest 8 core inputs
- Shift current file to `manual_inputs_prev.json` before updating new week
- Run: `python -m src.report.weekly`
- Summarize changes + decisions

## Output checks
- data/decision/weekly_report.md
- data/state/regime_state.json
- data/decision/allocation_plan.json

## Quality rules
- Facts-first
- Unknown if missing
- End with Signals + If X → do Y
