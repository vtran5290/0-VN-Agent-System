# Phase36 Decision Memo Summary

**Decision:** CONDITIONAL_NO_CHANGE  
**Production candidate:** A3 DP-first only  
**S3:** Paper-shadow / radar / support layer only

## Approved (low risk)

- Sort same-day A3 `NEW_T1` / `NEW_T1_MANUAL_REVIEW_BREADTH` by `a3_rank_score` DESC for operator review.
- Expose Phase36 lead buckets, `ed_score`, and context flags in daily scan CSV.

## Not approved for production

- S3-based production sizing (`lead_best_125x` — paper research only).
- S3-based T2 rule (`t2_only_if_good_lead` — track only).
- Tight trail 2.0×ATR (harmful in backtest).
- A3/S3 satellite real allocation.
- Any change that alters `final_action`, eligibility, or OMS routing.

## Execution SSOT

`final_action` in `phase35_daily_scan_sample.csv` (and phase36 alias) remains the only live-capital action source.
