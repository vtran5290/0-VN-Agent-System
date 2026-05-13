# FireAnt Workflow

## When a task needs Vietnam market or company data

1. Determine the scope:
   - ohlcv
   - fundamentals
   - index
   - sector
   - discover
2. Use FireAnt first
3. Reuse existing token/client code
4. Attach standard headers
5. Pull only the minimum required data
6. Normalize the payload
7. Add warnings/errors/integrity flags
8. Continue analysis
9. Only fallback to another source if FireAnt fails or coverage is unavailable

## Token handling

- Prefer explicit token input
- Otherwise use FIREANT_TOKEN env var
- Token is raw JWT string
- Insert into Authorization header as `Bearer <token>`

## Heavy endpoint caution

For /symbols/all-financial-data:

- use timeout 180s
- retries 3
- backoff about 1.5

## Non-hallucination law

- Never invent bars
- Never invent line items
- Never invent coverage for unavailable logical indices
- Return empty structures + warnings/errors instead

## SSOT data location (project-wide)

- Use `data/fireant_ssot/` as the single source of truth for FireAnt data used by analysis/chat tasks.
- Canonical files:
  - `data/fireant_ssot/ta_ohlcv_panel.parquet`
  - `data/fireant_ssot/ta_vnindex.parquet`
  - `data/fireant_ssot/fa_quarterly.parquet`
  - `data/fireant_ssot/fa_annual.parquet`
  - `data/fireant_ssot/fa_symbol_coverage.csv`
  - `data/fireant_ssot/manifest.json`
- Rebuild SSOT after data refresh with:
  - `python scripts/build_fireant_ssot.py`
