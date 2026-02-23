roll:
	python -m src.intake.roll_week

daily:
	python -m src.report.daily

weekly:
	python -m src.report.weekly

ingest:
	python -m src.ingest.run

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
