# Sector L4 Final Findings (Updated 2026-05-16)

Supersedes: SECTOR_L4_FINAL_FINDINGS.md
Change: Decision reclassified SHADOW_RISK_CONTROL → DASHBOARD_WARNING_ONLY

---

## Coverage

- Total symbols: 273
- High confidence: 170
- Medium confidence: 32
- Unknown: 71

Note: 273 rows vs 272-symbol universe — likely one duplicate entry. Not blocking.

---

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

---

## Decision: DASHBOARD_WARNING_ONLY

**Previous wording (SUPERSEDED):** SHADOW_RISK_CONTROL

**Correct classification:** DASHBOARD_WARNING_ONLY

**Reasoning:**
- Best sector stress rule (l4_breadth<50%) improves MAR only 0.416 → 0.438 (+0.022). Not material.
- All max_N_per_l4 caps HURT MAR significantly (max_1: 0.197, max_2: 0.319).
- Complexity added by a hard sector cap is not justified by marginal MAR improvement.
- Sector L4 information is useful for operator awareness and concentration monitoring only.

**Ruled OUT as a trade filter:** Do not use sector L4 as an automatic entry block.

---

## Sector Concentration Dashboard Warning

Display in dashboard when:
- Any single L4 sector > 30% of active live positions → WARN operator
- Banking or Real Estate > 40% of active positions → elevated WARN

**Operator action:** Review concentration. May choose to skip additional entries in crowded sector.
This is operator judgment, not an automatic rule.

---

## Sector Risk Context

- Banking: largest sector in VN market. Multiple bank names in same cloud-breakout = cyclical cluster risk.
- Real Estate: high correlation within L4, especially during rate/policy cycles.
- Industrial Parks: often move together on FDI news cycles.
- Steel/Materials: commodity price driven, high beta to global risk.

These risks are visible in the dashboard; they do not trigger automatic trade blocks.
