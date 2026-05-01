# SStock Migration Audit (Vietnam liquidity / SBV indicators)

## Verified (from repo code)
1. Weekly report consumes Vietnam liquidity facts from `data/raw/manual_inputs.json` under:
   - `vietnam.omo_net`
   - `vietnam.interbank_on`
   - `vietnam.credit_growth_yoy`
   - `vietnam.fx_usd_vnd`
2. The file `scripts/update_manual_inputs.py` is the ingestion point that updates `data/raw/manual_inputs.json`.
   - It only fetches Vietnam liquidity when `--force-vn-liquidity` is enabled.
   - Default behavior (when `--force-vn-liquidity` is NOT set) preserves existing `manual_inputs.json` vietnam keys.
3. The SBV production path is `scripts/fetch_vietnam_liquidity.py` (web scrape + best-effort parsing).

## Verified (from live probing, auth required)
4. Endpoint probe:
   - `POST https://api-feature.sstock.vn/api/v1/chart/general-data-series` without auth returns HTTP `500`
   - Response stack mentions `better-auth` middleware, consistent with “requires session cookie / better-auth session”.

## What is still unverified / unknown
5. SStock request schema (required JSON body / series codes / exact series name strings) is not confirmed end-to-end in this repo environment.
   - The current parser is best-effort and matches by label keywords, then extracts latest point with `date/day` <= `asof`.
6. `credit_growth_yoy` availability from SStock is still not proven (may parse as null or may use different series label).

## Conclusion
7. SStock integration is added as Tier-B experimental behind env flags.
8. Default selection remains Tier-A (SBV) to avoid breaking weekly report reliability.
9. Shadow mode writes a comparison artifact so promotion can be decided using evidence.

