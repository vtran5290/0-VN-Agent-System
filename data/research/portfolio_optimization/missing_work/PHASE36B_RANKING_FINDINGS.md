    # Phase36B — Ranking Tests

    Generated: 2026-05-17 | A3 baseline MAR=0.416, threshold=0.446

    ## MAR Acceptance Bar: +0.03 over baseline → need MAR ≥ 0.446

    ## Results (20-slot portfolio)

    | Variant | MAR | CAGR | MaxDD | Δ-MAR | Accept? |
    |---------|-----|------|-------|-------|---------|
    | ed_score_only | 0.4436 | 7.89% | -17.79% | 0.0276 | no |
| a3_rank_score | 0.3462 | 6.49% | -18.75% | -0.0698 | no |
| lead_11_20_flag | 0.3337 | 7.14% | -21.41% | -0.0823 | no |
| mom20 | 0.2674 | 6.57% | -24.57% | -0.1486 | no |
| baseline_ema_dist | 0.2629 | 5.82% | -22.12% | -0.1531 | no |

    ## Conclusion

    Best: ed_score_only|slots=20 MAR=0.4436 delta=0.0276

    CONSTRAINT: A3 production logic unchanged. Ranking is advisory only for operator
    when multiple NEW_T1 fire same day. It does not block any A3 signal.

    ## What This Means for Operations

    - If a3_rank_score improves MAR ≥ +0.03: adopt it as the NEW_T1 same-day sort order
    - If improvement < +0.03: keep ema_dist_at_entry as default sort
    - Regardless: a3_rank_score is already computed in Phase35 scan output
