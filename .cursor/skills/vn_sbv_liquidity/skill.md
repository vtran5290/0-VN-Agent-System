# Vietnam SBV Liquidity Fetch

Use this skill when the user asks to fetch Vietnam liquidity data, debug SBV scrape failures, or automate:
- `omo_net`
- `interbank_on`
- `credit_growth_yoy` (actually SBV YTD-vs-year-end metric)
- `fx_usd_vnd`

## Source policy (SBV only, HTML scrape)

- Source: `https://www.sbv.gov.vn`
- Method: static HTML (`requests` + `BeautifulSoup`)
- No API / no PDF fallback for these 4 fields.
- Known issue: SBV sometimes throttles automated requests (`ConnectTimeout`) while pages still open normally in browser.

## Endpoints + selector-first parsing

| Field | URL | Primary selector logic |
|---|---|---|
| `fx_usd_vnd` | `https://www.sbv.gov.vn/vi/t%E1%BB%B7-gi%C3%A1` | First table (`table.bi01-table`), row contains `Đô la Mỹ`, take rate cell and convert to int VND. |
| `interbank_on` | `https://www.sbv.gov.vn/vi/l%C3%A3i-su%E1%BA%A5t1` | Prefer second table (`tables[1]`) = interbank market table, row `Qua đêm`, parse `%` as float. |
| `credit_growth_yoy` | `https://www.sbv.gov.vn/vi/du-no-tin-dung-doi-voi-nen-kt-dttktt` | `div.credit-table-wrapper table`, row containing `TỔNG CỘNG`, read growth column. |
| `omo_net` | `https://www.sbv.gov.vn/vi/web/sbv_portal/nghi%E1%BB%87p-v%E1%BB%A5-th%E1%BB%8B-tr%C6%B0%E1%BB%9Dng-m%E1%BB%9F` | `table.ls01-table`, parse sections `Mua kỳ hạn` (+) vs `Bán/Hút` (-), sum detail rows by tenor. |

## Value semantics

- `fx_usd_vnd`: SBV central/reference USD/VND, integer (e.g. `25.113` -> `25113`).
- `interbank_on`: overnight interbank rate `%/year`.
- `credit_growth_yoy`: stored key name is historical; SBV table is **YTD vs year-end**, not pure YoY.
- `omo_net`: `omo_inject - omo_withdraw` (tỷ VND).

## Numeric normalization rules

- Vietnamese format: `10.000,00` -> `10000.0`.
- Dot = thousands separator, comma = decimal separator.
- Strip unit text (`VND`, `%`, etc.) before conversion.

## Recommended fetch config (anti-timeout)

Use these defaults for SBV requests:

```python
timeout = 30
retries = 3
retry_delay_sec = 5
headers = {
    "User-Agent": "Mozilla/5.0 (compatible; DataBot/1.0)",
    "Accept-Language": "vi-VN,vi;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}
```

Operational guidance:
- Prefer `requests.Session()` for connection reuse.
- Add short spacing between SBV calls (`sleep(2-3s)`) when running 4 endpoints in sequence.
- Treat `ConnectTimeout` as retriable before marking field missing.

## Parse workflow (per run)

1. Fetch all 4 SBV pages with retry policy.
2. Parse each field using selector-first logic above.
3. Return partial dict with `None` for failed fields (never hard fail whole pipeline).
4. Attach provenance:
   - source = `sbv`
   - method = `html_scrape`
   - verification status (`parsed`, `primary_missing`, `request_failed_or_missing`)
   - optional value_date/article_date where available.

## Repo integration commands

1. Fetch only SBV liquidity:
   ```bash
   python scripts/fetch_vietnam_liquidity.py
   ```

2. Merge into `manual_inputs` (allow overwrite SBV liquidity keys):
   ```bash
   python scripts/update_manual_inputs.py --asof YYYY-MM-DD --force-vn-liquidity
   ```

3. Full weekly refresh:
   ```bash
   python scripts/run_weekly_full_fetch.py --asof YYYY-MM-DD
   ```

## Debug checklist for SBV failures

- Confirm endpoint opens in browser manually.
- If browser works but script fails: classify as network throttling/timeout first, not parser break.
- Re-run with retry+timeout config before code changes.
- Validate parser selectors against current DOM:
  - fx: `table.bi01-table`
  - interbank: second table / `Qua đêm`
  - credit: `.credit-table-wrapper table` + `TỔNG CỘNG`
  - omo: `.ls01-table` + section context (`Mua`/`Bán`).
- Only call structure-broken when selectors truly missing.

## Current known status note (Apr 2026 pattern)

- SBV pages are accessible in browser; automation intermittently hits `ConnectTimeout`.
- This is usually transport-level instability, not endpoint deprecation.
- Keep parser stable and improve resilience first (timeout/retry/session/sleep), then reassess.
