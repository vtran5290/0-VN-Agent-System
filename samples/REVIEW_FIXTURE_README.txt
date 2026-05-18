REVIEW-ONLY: phase36_daily_scan_review_fixture.csv
================================================

This CSV is for 3rd-party AI review and pytest only.
It is NOT the live production scan SSOT (phase36_daily_scan_latest.csv).

Rows include:
- NVL: TRAIL_EXIT
- HDB: NO_T2_BREADTH
- GVR: TP1_PARTIAL
- ZX99: NEW_T1 (fixture-only; not FPT — avoids confusion with live market)
- ZX98: SKIP_LIQUIDITY (fixture-only; not AAA)
- S3X: S3_RESEARCH_ONLY (must stay out of default A3 watchlist)
- STB: intentionally absent (tests scan-missing / row-noscan)

Tests set PHASE36_DAILY_SCAN_PATH to this file via tests/conftest.py.
