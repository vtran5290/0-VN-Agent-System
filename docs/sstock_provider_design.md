# SStock Provider Design (Tier-A SBV preserved, Tier-B experimental)

## Goal
Evaluate SStock (`sstock.vn` / `api-feature.sstock.vn`) as an alternative source for Vietnam liquidity indicators:
- `omo_net`
- `interbank_on`
- `credit_growth_yoy`
- `fx_usd_vnd`

without breaking the existing weekly-report workflow.

## Current production contract (Tier-A)
Weekly report rendering consumes:
- `data/raw/manual_inputs.json` → `vietnam.{omo_net, interbank_on, credit_growth_yoy, fx_usd_vnd}`

Tier-A is the existing SBV scraper:
- `scripts/fetch_vietnam_liquidity.py`

## New staged architecture
New code lives under:
- `src/macro/vietnam_liquidity/`

### Providers
1. Tier-A provider: `providers/sbv_provider.py`
   - Wraps existing SBV function `scripts.fetch_vietnam_liquidity.fetch_vietnam_liquidity()`
2. Tier-B provider: `providers/sstock_provider.py` (experimental)
   - Calls `POST https://api-feature.sstock.vn/api/v1/chart/general-data-series`
   - Requires auth (confirmed by unauthenticated probe returning HTTP 500 mentioning better-auth)
   - Parser is best-effort:
     - matches series items by label keywords
     - extracts latest point where `point_date <= asof`
     - normalizes numeric types:
       - `omo_net`, `fx_usd_vnd` -> `int`
       - `interbank_on`, `credit_growth_yoy` -> rounded to 2 decimals
     - auth-missing is handled as a graceful null result

### Adapter / merge rules (non-destructive)
Module: `src/macro/vietnam_liquidity/adapter.py`

Field-level policy:
- `existing` mode: chosen values always come from SBV (even if null)
- `auto` / `shadow` mode: chosen values come from SBV when present; otherwise fill missing fields from SStock (if parsed)

This preserves backward compatibility (no destructive overwrites with null).

## Feature flags / env vars
Used by `scripts/update_manual_inputs.py`:
- `VIETNAM_MACRO_PROVIDER`
  - `existing` (default): SBV only
  - `auto`: SBV primary + SStock fill-missing (experimental)
  - `sstock`: treated as `auto` for safety (SBV never overridden by null)
- `VIETNAM_MACRO_SSTOCK_SHADOW`:
  - when `true`, SStock is fetched and compared but chosen values still follow the non-destructive merge policy

Auth injection (no hardcoded secrets):
- `SSOCKT_COOKIE` / `SSTOCK_COOKIE`: full Cookie header value
- `SSOCKT_SESSION_TOKEN` / `SSTOCK_SESSION_TOKEN`: token injected into `better-auth.session-token=<token>`

## Provenance + evidence
During provider evaluation:
- `data/raw/manual_inputs.json` is enriched with:
  - `vietnam_provenance.{field} = {chosen_source, verification_status, series_name, ...}`
- Shadow mode writes:
  - `artifacts/sstock_shadow_compare.json`
  - `artifacts/sstock_shadow_compare.md`

These artifacts show per-field deltas and `status` for evidence-based promotion.

## Rollback / go-no-go
If SStock cannot be authenticated or parsing proves unreliable:
- keep Tier-A SBV as primary by setting:
  - `VIETNAM_MACRO_PROVIDER=existing`
  - `VIETNAM_MACRO_SSTOCK_SHADOW=false`

No other changes are required.

