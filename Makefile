roll:
	python -m src.intake.roll_week

daily:
	python -m src.report.daily

weekly:
	python -m src.report.weekly --render

# VN Weekly Investment Report Engine v1.0 — full cycle: ingestion (weekly + normalize) → validate → render
weekly-report:
	python -m scripts.run_full_weekly_cycle

ingest:
	python -m src.ingest.run

# Data ingestion (FRED + VN market + dist days → manual_inputs.json). Requires FRED_API_KEY in .env or env.
ingestion:
	python -m scripts.run_ingestion --all

CONSENSUS_PACK ?= data/raw/consensus_pack.json
RESEARCH_PACK ?= data/raw/research_engine_pack.json

consensus-apply:
	python -m src.intake.apply_consensus_pack --pack "$(CONSENSUS_PACK)"

consensus-apply-dry-run:
	python -m src.intake.apply_consensus_pack --pack "$(CONSENSUS_PACK)" --dry-run

research-pack-apply:
	python -m src.intake.apply_research_engine_pack --pack "$(RESEARCH_PACK)"

research-pack-apply-strict:
	python -m src.intake.apply_research_engine_pack --pack "$(RESEARCH_PACK)" --strict-drift-guard

bond-snapshot-apply:
	python -m scripts.apply_bond_monetary_snapshot

smart-money-weekly-diff:
	python -m src.smart_money.weekly_diff

# Earnings & Council artifacts (see docs/EARNINGS_INTAKE_SPEC.md)
earnings-heatmap-apply:
	python -m scripts.earnings_heatmap_apply
earnings-quality-flags:
	python -m scripts.earnings_quality_flags
council-packet-v2:
	python -m scripts.build_council_packet_v2

# Book Test Ladder — validation 2023-2024 (see docs/BOOK_TEST_LADDER.md)
# C1/C2 default = market-mode 2 (Book). Ablation: m0=no filter, m1=trend only, m2=trend+dist stop-buy
book-c1-val:
	python -m pp_backtest.run_weekly --watchlist config/watchlist_80.txt --start 2023-01-01 --end 2024-12-31
book-c1-val-m0:
	python -m pp_backtest.run_weekly --watchlist config/watchlist_80.txt --market-mode 0 --start 2023-01-01 --end 2024-12-31
book-c1-val-m1:
	python -m pp_backtest.run_weekly --watchlist config/watchlist_80.txt --market-mode 1 --start 2023-01-01 --end 2024-12-31
book-c1-val-m2:
	python -m pp_backtest.run_weekly --watchlist config/watchlist_80.txt --market-mode 2 --start 2023-01-01 --end 2024-12-31
book-c2-val:
	python -m pp_backtest.run_weekly --watchlist config/watchlist_80.txt --entry-3wt --no-entry-weekly-pp --start 2023-01-01 --end 2024-12-31
book-c2-val-m0:
	python -m pp_backtest.run_weekly --watchlist config/watchlist_80.txt --entry-3wt --no-entry-weekly-pp --market-mode 0 --start 2023-01-01 --end 2024-12-31
book-c2-val-m1:
	python -m pp_backtest.run_weekly --watchlist config/watchlist_80.txt --entry-3wt --no-entry-weekly-pp --market-mode 1 --start 2023-01-01 --end 2024-12-31
book-c2-val-m2:
	python -m pp_backtest.run_weekly --watchlist config/watchlist_80.txt --entry-3wt --no-entry-weekly-pp --market-mode 2 --start 2023-01-01 --end 2024-12-31
book-b1a-val:
	python -m pp_backtest.run --no-gate --book-regime --entry-bgu --exit-fixed-bars 10 --watchlist config/watchlist_80.txt --start 2023-01-01 --end 2024-12-31
# Final untouched 2025-2026 (run once when model locked)
book-c1-final:
	python -m pp_backtest.run_weekly --watchlist config/watchlist_80.txt --start 2025-01-01 --end 2026-02-21
book-c2-final:
	python -m pp_backtest.run_weekly --watchlist config/watchlist_80.txt --entry-3wt --no-entry-weekly-pp --start 2025-01-01 --end 2026-02-21
book-b1a-final:
	python -m pp_backtest.run --no-gate --book-regime --entry-bgu --exit-fixed-bars 10 --watchlist config/watchlist_80.txt --start 2025-01-01 --end 2026-02-21

# Council OS v1 — weekly council cycle + monthly audit cadence
council-weekly:
	python -m src.report.weekly
	python -m src.report.council_secretary --mode weekly
	python -c "from pathlib import Path; p=Path('data/decision/council_output.json'); print(f'Council input pack ready. Save council output to: {p.resolve()}'); print('Use: prompts/council/orchestrator.md then prompts/council/constraint_enforcer.md')"

council-secretary-weekly:
	python -m src.report.council_secretary --mode weekly

council-audit-monthly:
	python -m src.report.council_secretary --mode monthly
	-python -m pp_backtest.portfolio_exec_stats pp_backtest/pp_weekly_ledger.csv --stress
	python -c "from pathlib import Path; d=Path('decision_log'); m=Path('data/decision/council_audit_monthly.md'); print(f'Monthly audit input: {d.resolve()}'); print(f'Secretary audit note: {m.resolve()}'); print('Use: prompts/council/secretary.md to finalize process improvements')"

# Trade Postmortem Layer — review executed trades, diagnostics, masters, lessons (see docs/TRADE_REVIEW_LAYER.md)
trade-review-monthly:
	python -m src.review.cli run-monthly

# Council Performance Review (CPR v1.0) — weekly + monthly
review:
	python -m src.review.run

monthly-review:
	python -m src.review.monthly --lookback-weeks 8

# Sanitize & compact — clear cache, optionally convert FireAnt financials CSV→Parquet (see docs/MAINTENANCE.md)
sanitize:
	-rd /s /q data\cache\fireant 2>nul || true
	python scripts/compact_fireant_financials_to_parquet.py 2>nul || echo "No financials CSV to compact."

# MCP orchestration layer (see docs/MCP_ARCHITECTURE.md)
mcp-smoke:
	python scripts/mcp_smoke.py

mcp-test:
	python -m pytest tests/test_mcp_orchestration.py -q

mcp-status:
	python scripts/mcp_status.py

mcp-risk-smoke:
	python scripts/mcp_risk_smoke.py

mcp-paper-smoke:
	python scripts/mcp_paper_smoke.py

mcp-live-guard:
	python scripts/mcp_live_guard.py
