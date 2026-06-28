# Diversity Breadth — Gate B Summary

**Label:** RESEARCH_ONLY_NOT_PRODUCTION

## Verdict
- **Gate B:** FAIL
- Signal criterion (r>0.15 OR hit>55%): NO
- Rolling stability (>50% of 36m windows with r>0.15): NO

## Test 1 — Correlation (spread vs next-month VNINDEX)
- n=168, r=-0.05795137124929914, p=0.45557381112830836

## Test 2 — Hit rate (spread vs median → next-month sign)
- n=168, hit_rate=0.5059523809523809, median_spread=0.0013188815850740734

## Test 3 — Rolling stability
- windows=133, min_r=-0.38163542599339706, max_r=0.12326461579928295, pct_r>0.15=0.0

## Test 4 — Regime conditional
- Historical bull/neutral/bear from data/regime_log_2012_now.csv market_status (regime_state.json is current snapshot only).
- **bull:** n=28, r=0.5073152767994968, hit_rate=0.6785714285714286
- **neutral:** n=138, r=-0.14420287879571841, hit_rate=0.463768115942029
- **bear:** n=0, r=None, hit_rate=None

## ex-VIN variant
- n=168, r=-0.07412812672392037, hit_rate=0.5059523809523809

## Limitations
- VN100 membership approximated by top-N ADV at each rebalance (no PIT reconstitution log).
- OHLCV panel uses raw close for ADV; value column = close*volume*1000 VND turnover.
- VNINDEX used as VN100 proxy for forward return test (native VN100 series not loaded).
- No transaction costs; RESEARCH_ONLY predictive signal test.
