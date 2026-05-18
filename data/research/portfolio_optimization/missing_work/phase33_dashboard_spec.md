# Phase35 Dashboard Specification

Generated: 2026-05-18

## Panel 1 — Data health / as-of
- panel_asof_date (from parquet max date)
- scan_date (as_of_date column)
- stale_warning if panel_asof < last trading session
- VNINDEX regime_bull
- pct_cloud_bull_a3 + breadth_zone
- pct_cloud_bull_s3 (EMA21/55 universe)

## Panel 2 — A3 production (ONLY real-capital SSOT)
- final_action counts
- NEW_T1 / NEW_T1_MANUAL_REVIEW_BREADTH / ADD_T2 / NO_T2_BREADTH / HOLD_T1_ONLY
- TP1_PARTIAL / TRAIL_EXIT / MAX_HOLD_EXIT
- SKIP_LIQUIDITY / SKIP_VNINDEX_BEAR
- a3_s3_lead_5d=True names (priority sort)
- Sort NEW_T1 rows by a3_rank_score DESC

## Panel 3 — S3 paper shadow (max_hold=60)
- Count s3_shadow_action=PAPER_S3_SHADOW
- s3_shadow_classification=PAPER_TRADE_SHADOW only
- s3_max_hold=60 / s3_max_hold_60_flag=True
- s3_no_real_order_flag must be 100% True
- REMINDER: separate paper ledger — not A3 P&L

## Panel 4 — S3 research monitor (GK5+top100)
- s3_gk5_top100_monitor=True count
- s3_research_monitor_action=PAPER_S3_RESEARCH_MONITOR
- NO REAL CAPITAL / NO DNSE

## Panel 5 — Legacy satellite (NOT production SSOT)
- B_cloud20_100 / B_cloud21_55 / C_GK_regime from daily_three_strategy_scan.md
- Label: satellite only — do not route live capital

## Panel 6 — Warnings
- duplicate position if symbol already held
- stale panel data
- liquidity WARN/CRITICAL
- breadth defense (<35%)
- S3 contamination risk if operator confuses shadow with A3
- missing broker reconciliation / ledger

