# Weekly-Style Brief Spec — Institutional Accumulation Scan (Research Only)

Claude Code (or human analyst) produces **`institutional_accumulation_weekly_brief_{as_of}.md`** in the same spirit as `data/decision/weekly_report.md`, but **scoped to accumulation scan only**.

**HTML:** `institutional_accumulation_weekly_brief_{as_of}.html` is **auto-regenerated from the `.md` file** on every full scan run, or after manual MD edits via:

```powershell
python -m src.scans.institutional_accumulation.run --sync-weekly-html --as-of YYYY-MM-DD
```

**Not** a substitute for the full macro weekly packet. **No** order instructions.

---

## Required section order

### Header

- As-of date, methodology version (`v1.1`), scan row count, regime label from priors/context  
- `universe_policy.mode` and safety line: *research ranking only; does not set final_action*

### Global Macro + Fed (brief)

- 3–5 bullets: only what matters for **VN liquidity / risk appetite** and scan regime tag  
- If data not in zip → **Unknown** + what would confirm  
- Separate FACTS vs INTERPRETATION

### Vietnam Policy + Liquidity (brief)

- OMO / interbank / credit / FX if available in repo context; else Unknown  
- Transmission: rates → credit → FX → equity flow sentiment (1 short paragraph)

### Market internals (scan-derived)

- Tier counts: Tier1 / Tier2 / Tier3 / Reject  
- Top sectors in Tier1+2 (from `sector_summary` or CSV aggregate)  
- **Emerging accumulation** count + top 5 tickers (outside fund disclosure tags)  
- **Vingroup note:** cap-weight VNINDEX caveat 2025–2026; VIN distortion flags count  
- Breadth proxy if in validation outputs; else state unavailable

### Sectors & Companies (accumulation lens)

**FACTS table** — minimum columns:

| ticker | tier | score | score_money_flow | fund_context_bucket | emerging | vingroup_distortion |

Include:

- All `consensus_core` + `consensus_second_ring` from priors (even if Reject)  
- Top 10 by score from `top80` excerpt  
- Any `emerging_accumulation_candidate` in Tier2+ not already listed  

**INTERPRETATION:** 2–4 bullets on consensus vs emerging tension (e.g. banks weak CMF vs retail/emerging strong flow).

### Decision layer (research only)

- **Top 3 research actions** (e.g. deepen diligence on X, monitor Y tier change, validate Z flow)  
- **Top 3 methodology risks** (redundancy, unit scale, tier empty, VIN skew)  
- **Watchlist updates** — names to add to human watchlist file (symbols only from scan output)

### Validation & data integrity

- `execution_leakage_check`, `money_flow_redundancy` summary, `price_unit_mode`  
- Limitations: no sector RS, no pocket pivot, local CSV only unless stated

### End (mandatory)

1. **Signals to monitor next week** (bullet list)  
2. **If X happens → do Y** (conditional playbook, research steps only)

---

## Style rules

- Bullet-heavy; quantify tiers/scores/percentiles  
- Never present proxy index as native  
- Never invent fund holdings not in priors/monthly JSON  
- Do not recommend buy/sell/size
