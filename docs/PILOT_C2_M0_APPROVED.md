# C2 m0 (Weekly 3WT, market_mode=0) — PILOT APPROVED

**Freeze chính thức.** Facts locked; Interpretation và Actions cho Operating Manual.

---

## 1. Facts (Locked)

### Signal spec
- **Entry:** Weekly 3-Weeks-Tight (3WT) breakout
- **Market filter:** None (market_mode=0)
- **Universe:** 80 liquid VN symbols (watchlist_80.txt)
- **Backtest:** 2012–2026, 3-split (train / validation / final), no peek
- **Final period:** 2025-01-01 → 2026-02-21
- **Trade-level (ledger full):** Signals 322; PF_trade 2.89; Top5 contribution 57.26% (< 60%); tail5 -8.61%

### Executed subset (K=5 portfolio)
| Metric | Value |
|--------|--------|
| Executed trades | 78 |
| PF_exec (RT30bps) | 1.474 |
| Median_ret_exec | -1.65% |
| EV_exec (RT30bps) | +1.08% |
| Exposure_tw (time-weighted) | 58.5% |
| Portfolio MDD | -11.49% |
| Portfolio CAGR | 12.62% |

### Stress test (executed subset)
| Scenario | PF_exec | EV_exec | Exposure_tw |
|----------|---------|---------|-------------|
| RT30bps (base) | 1.474 | +1.08% | 58.5% |
| RT40bps | 1.417 | +0.98% | 58.5% |
| RT60bps | 1.314 | +0.78% | 58.5% |

RT40 PASS theo pre-registered rule.

---

## 2. Interpretation (What the edge really is)

- Edge là **positive skew / tail-driven** breakout profile.
- Win rate thấp (33%), median âm (-1.65%).
- Alpha đến từ: avg win +10%, avg loss -3.4%. PF_exec 1.47 chứng minh deployable edge sau K-limit.
- Exposure_tw 58.5% → model không assume full utilization.
- **Quan trọng:** Model KHÔNG phải high hit-rate system. Model sống nhờ winner tail. Bỏ lỡ winner = giết edge.

---

## 3. Pilot rules (4 weeks)

- Max 5 concurrent positions
- 20% equity per slot
- No margin
- Weekly rebalance
- Take all signals subject to K-limit (no discretionary skip)

### Risk overlay (pre-committed)
- **Kill-switch:** Portfolio DD ≤ -8% từ peak → pause new entries
- **Review trigger:** PF_live < 1.2 sau 30 executed trades → pause + audit (no rule tweak)
- **Concentration alert:** Top5 rolling 6M > 60% → giảm size hoặc tạm dừng scale-up

---

## 4. Expectation calibration

- Exposure_tw 58.5% đã được tính trong sim (model không giả định full K=5 mọi tuần).
- Live CAGR có thể thấp hơn backtest do: miss fills, slippage thực tế, regime shift.
- **Kỳ vọng hợp lý cho pilot:** 7–9%/năm; không dùng 12.62% làm baseline.
- **Mục tiêu pilot:** Verify edge + verify execution discipline. Không chase CAGR tối đa.

---

## 5. Signals to monitor weekly

- PF_exec rolling
- EV_exec drift
- Top5 contribution rolling 6M
- Exposure_tw (58% expected)
- Real slippage vs 30 bps assumed
- Signal collision frequency

---

## 6. If X → Do Y

| If | Do |
|----|-----|
| Top5 > 60% | Reduce size / pause scale-up |
| DD < -8% | Stop new entries 4 weeks |
| PF_live < 1.2 | Pause + audit (no rule tweak) |
| RT40 equivalent cost | Still positive EV → continue |

---

## Verdict

Research phase complete. Model passes Final + Stress + IC governance. **Pilot authorized under controlled size.**
