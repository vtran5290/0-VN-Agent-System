# Distribution session alert — 2026-05-17

**Composite alert:** `YELLOW` — Early warning — today or 20d count elevated.

## FACTS
- source = FireAnt (VNINDEX native; ex-VIN = proxy ['VIC', 'VHM', 'VRE'])
- method = O'Neil dist rule (-0.2% close vs prior + volume up); SSOT + optional `--fetch`
- asof bar = 2026-05-15

### VNINDEX (full)
- close 1921.6 | 1d -0.2% | today_dist **True**
- dist 10/20/50 = 2/3/8 | last5 dist = 2
- MA20/50/200 = True/True/True | ret5/20 = 0.33% / 8.22%
- alert **YELLOW**: today= distribution day, dist_10d=2, dist_20d=3

### VNINDEX ex-VIN (proxy)
- close 1269.36 | w_VIN 33.94% | today_dist **False**
- dist 10/20 = 1/2 | alert **GREEN**

### VIN basket (native OHLCV)
- VIC: 5d 0.88% | 20d 37.76%
- VHM: 5d -3.66% | 20d 22.58%
- VRE: 5d -5.29% | 20d 21.86%

### Historical context (full VNINDEX)
| window | max_dist_20 | dist_total | dd_from_peak |
| 2023-08-09 | 5 | 9 | -7.33% |
| 2024-03-04 | 5 | 9 | -6.25% |
| 2024-06-07 | 5 | 7 | -3.84% |
| 2024-09-10 | 6 | 9 | -2.15% |
| 2026-YTD | 7 | 9 | -0.2% |

## INTERPRETATION
Composite YELLOW. Full dist20=3 vs correction templates (peaks 4–5). VIC/VHM/VRE used for big-hand read; ex-VIN proxy for breadth check.

## If X → do Y
- If composite **RED** or dist_20≥5 or (dist_20≥4 and below MA50) → cut beta; no new chase entries.
- If **ORANGE** → tighten stops; only leaders; watch for 3+ dist in 5 sessions.
- If **YELLOW** + today_dist → do not add risk today; reassess tomorrow.
- If **GREEN** → monitor only; not in 2023–2024 correction template yet.

_Note: monitor setup baseline_