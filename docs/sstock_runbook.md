# SStock Runbook (Vietnam liquidity evaluation)

## What this controls
Weekly ingestion point: `scripts/update_manual_inputs.py`

It updates `data/raw/manual_inputs.json` with Vietnam liquidity facts:
- `vietnam.omo_net`
- `vietnam.interbank_on`
- `vietnam.credit_growth_yoy`
- `vietnam.fx_usd_vnd`

SStock is experimental and is only fetched when enabled by env flags.

## Tier-A (SBV only) — default / rollback
Set:
- `VIETNAM_MACRO_PROVIDER=existing`
- `VIETNAM_MACRO_SSTOCK_SHADOW=false`

No SStock calls are attempted.

## Shadow evaluation (recommended)
1. Enable shadow mode:
   - `VIETNAM_MACRO_SSTOCK_SHADOW=true`
   - `VIETNAM_MACRO_PROVIDER=existing` (or leave it; shadow overrides chosen behavior)
2. Provide auth via env (do not hardcode secrets):
   - `SSOCKT_COOKIE` (preferred): `better-auth.session-token=...; ...`
     - OR
   - `SSOCKT_SESSION_TOKEN`: `<token>` injected as `better-auth.session-token=<token>`
3. Run the weekly full fetch (as-of your desired date):
   - `python scripts/run_weekly_full_fetch.py --asof <YYYY-MM-DD>`
4. Inspect evidence outputs:
   - `artifacts/sstock_shadow_compare.json`
   - `artifacts/sstock_shadow_compare.md`
   - Check `vietnam_provenance` inside `data/raw/manual_inputs.json` (if present)

## Promotion decision gate (go/no-go)
Only promote SStock to primary by setting:
- `VIETNAM_MACRO_PROVIDER=auto` or `sstock` (depending on your desired semantics)

But do not promote unless:
- weekly ingestion succeeds end-to-end
- auth works reliably (low stale/missing rate)
- no schema breaks downstream
- shadow comparison shows consistent matches for the fields required by the weekly report

## Known unverified parts
This repo cannot fully prove the SStock endpoint request schema without an authenticated session.
If SStock parsing or series mapping fails, fields will remain null and SBV remains safe due to the non-destructive merge policy.

