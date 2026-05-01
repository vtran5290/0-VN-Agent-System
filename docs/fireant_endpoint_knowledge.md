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

