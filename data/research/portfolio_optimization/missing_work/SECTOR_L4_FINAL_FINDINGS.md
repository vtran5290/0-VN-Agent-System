# Sector L4 Final Findings

As of: 2026-05-16

## Coverage

- Total symbols: 273
- High confidence: 170
- Medium confidence: 32
- Unknown: 71

## Stress Rule Tests (A3 DP at 5B/10%)

| Rule | MAR | MaxDD | CAGR | Avoided | Avoided Winners | Avoided Losers |
|------|-----|-------|------|---------|-----------------|----------------|
| no_entry_if_l4_breadth<30pct | 0.434 | -13.99% | 6.07% | 87 | 43 | 44 |
| no_entry_if_l4_breadth<40pct | 0.434 | -13.99% | 6.06% | 129 | 65 | 64 |
| no_entry_if_l4_breadth<50pct | 0.438 | -13.99% | 6.12% | 226 | 132 | 94 |
| max_1_per_l4 | 0.197 | -24.20% | 4.76% | 1110 | 0 | 0 |
| max_2_per_l4 | 0.319 | -18.34% | 5.84% | 363 | 0 | 0 |
| max_3_per_l4 | 0.304 | -19.73% | 6.00% | 126 | 0 | 0 |
| max_5_per_l4 | 0.303 | -19.73% | 5.97% | 9 | 0 | 0 |
| no_cap | 0.416 | -13.99% | 5.81% | 0 | 0 | 0 |

## Decision

**SHADOW_RISK_CONTROL**

- A3 DP baseline MAR = 0.416
- Best stress rule: no_entry_if_l4_breadth<50pct → MAR=0.438

## Sector Concentration Risk

- Banking: largest sector in VN market. Multiple bank names in same cloud-breakout = cyclical cluster risk.
- Real Estate: high correlation within L4, especially during rate/policy cycles.
- Rule recommendation: dashboard warning only. Track concentration; alert if >30% of active positions in same L4.
