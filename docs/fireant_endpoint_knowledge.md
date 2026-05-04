This is where your detailed knowledge lives in human-readable form.

# FireAnt Endpoint Knowledge

## High-level model
Two main surfaces:
- REST API: https://restv2.fireant.vn
- Web app: https://fireant.vn

The web app uses:
- the same REST base
- some extra JSON endpoints such as /industries and /industries/{code}/historical-stats

## Authentication
Use Bearer JWT.
Token is raw JWT string without "Bearer " inside the token itself.

## Minimal working headers
Authorization: Bearer <JWT>
User-Agent: Mozilla/5.0
Accept: application/json, text/plain, */*
Origin: https://fireant.vn
Referer: https://fireant.vn/

## Core endpoints

### Symbol search and metadata
GET /symbols/search
GET /symbols/{symbol}

### Historical OHLCV
GET /symbols/{symbol}/historical-quotes

Query parameters **confirmed in this repo’s client** today: `startDate`, `endDate`, `offset`, `limit` (see `src/data/fireant_client.py::get_ohlcv`). The client does **not** yet forward a separate REST resolution flag to the server; weekly bars are derived in Python from daily rows when `timeframe=W`.

#### Intraday / sub-daily (discovery — not SSOT until verified)

Public OpenAPI for `restv2.fireant.vn` was not available at a stable path from this workspace. Third-party snippets on the internet have referenced non-existent paths (e.g. `/symbols/{sym}/intraday`, `/stocks/{sym}/quotes`, `/symbols/{sym}/bars`) — probing those URLs returned **404** from this environment.

**Recommended way to find the real intraday contract**

1. Log in to [fireant.vn](https://fireant.vn), open a symbol, switch the chart to **1m / 5m / 15m** (or whatever FireAnt offers).
2. Open **DevTools → Network**, filter **XHR/fetch**, reload or change resolution.
3. Copy the **exact** request URL + query string + method. Prefer requests that return JSON arrays of OHLC-like objects.
4. Replay with `Authorization: Bearer <JWT>` and the same `Origin` / `Referer` / `User-Agent` as in this doc.
5. Run the repo probe helper (token **only** via env `FIREANT_TOKEN`):

   `python scripts/research/fireant_hist_quotes_probe.py --symbol NVL --start 2026-04-28 --end 2026-04-29 --param <key>=<value>`

   Repeat with candidate keys you saw in DevTools (examples people try elsewhere include `type`, `resolution`, `frequency`, `timeFrame` — **do not assume**; only use names you captured).

**Security:** never commit JWTs; never paste tokens into chat. If a token was exposed, **revoke/rotate** it in FireAnt account settings and set `FIREANT_TOKEN` locally or in `.env` (gitignored).

### Detailed financial statements
GET /symbols/{symbol}/full-financial-reports
- type=1 balance sheet
- type=2 income statement
- type=3/4 cash flow

### Compact all-company financials
GET /symbols/all-financial-data
- type=Q quarterly
- type=Y annual

### Industry / sector blocks
GET /industries
GET /industries/{industryCode}/historical-stats

### ICB
GET /icb
GET /icb/latest-index
GET /icb/{industryCode}/historical-index

## Recommended normalization
OHLCV normalized fields:
- date
- open
- high
- low
- close
- volume

## Recommended outputs
OHLCV:
{"symbol": ..., "rows": [...], "warnings": [...], "errors": [...]}

Fundamentals:
flattened or derived rows with clear field names

Index/sector:
{"logical_name": ..., "kind": ..., "proxy_symbol" or "industry_code": ..., "rows": [...]}

