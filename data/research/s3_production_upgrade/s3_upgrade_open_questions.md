# S3 Upgrade — Open Questions

Date: 2026-05-17

---

1. **GK5+max60+top100 verification**: Run `pp_backtest/s3_combined_test.py` with GK5+max60+top100 config and persist `phase1_gk5_max60_top100_reproduction.csv`. If MAR ≥ 0.40, upgrade to REPRODUCED_CANDIDATE.

2. **OOS robustness with more data**: Phase 7 uses entry-year folds. Once 2026 data accumulates (post May), re-run to verify 2026 is positive.

3. **Paper-trade gate**: 3-month paper trading not yet started. Begin with Phase35 scan → S3_SHADOW outputs. Requires Phase35 code implementation in `portfolio_optimization_final_steps.py`.

4. **Regime + breadth combined config**: Best regime+breadth filter from Phase 2 should be formalized if it materially improves 2022 defense without reducing trade count below 3000.

5. **S3 with EX-VIN3 universe**: All S3 tests use "full" universe. Testing S3 on ex-VIN3 universe might improve MAR by removing VIN3 distortion. Pending test.

6. **Sector L4 breadth filter for S3**: Not tested in this research. Sector-level breadth may provide additional 2022 defense.
