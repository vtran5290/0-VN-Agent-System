# Project Instructions

## Core Data Source Policy
For all Vietnam equity, index, sector, and company-data tasks, FireAnt is the default first source.

This applies to:
- OHLCV price history
- index or proxy history
- industry / sector history
- company metadata
- financial statements
- valuation metrics
- watchlist and screening data
- market breadth or factor inputs
- backtest data preparation

Do not ask the user where to get the data if FireAnt can provide it.

Only use another source if:
1. FireAnt does not cover the requested field or logical object
2. FireAnt fails after reasonable troubleshooting
3. The user explicitly requests a different source

When using another source, state clearly:
- why FireAnt was insufficient
- what fallback source was used
- any limitations or proxy issues

## FireAnt operating assumptions
FireAnt has two main surfaces:
- REST API at https://restv2.fireant.vn
- Web app at https://fireant.vn using the same REST base plus some additional JSON endpoints

Authentication:
- Use Bearer JWT
- Token is raw JWT string without the word "Bearer" inside it
- Prefer input token if provided
- Otherwise fallback to FIREANT_TOKEN from environment

## Standard FireAnt headers
Always attach:
- Authorization: Bearer <JWT>
- User-Agent: Mozilla/5.0
- Accept: application/json, text/plain, */*
- Origin: https://fireant.vn
- Referer: https://fireant.vn/

## Execution priority
When a task requires Vietnam market/company data:
1. Search the repo for existing FireAnt utilities
2. Reuse existing FireAnt client, token handling, and parsing code
3. Pull only the minimum required data
4. Normalize and validate data
5. Continue analysis
6. Only then consider fallback sources

## Data integrity law
Never invent data.
Missing values must remain null / NaN.
If an endpoint fails, return empty structure with an errors field.
Always include warnings and data-integrity flags where relevant.

## Output discipline
Whenever FireAnt data is used, state:
- source = FireAnt
- method = REST API or web-side endpoint
- symbols / logical names used
- date range used
- proxy logic used if applicable
- warnings or limitations

## EMA-cloud + price-level / VIN research baseline

For Vietnam **EMA-cloud + price-level**, breakout/retest studies, OOS folds, and regime overlays: follow **`docs/research/VIN_EMA_CLOUD_BASELINE.md`** and Cursor rule **`vin-ema-research-baseline`**.

Summary: run **full** vs **ex-VIN** (`VIC`, `VHM`, `VRE`); exclude **`VPL`** until ≥252 daily bars; flag **return-distribution** distortion from VIN; do not use cap-weight **VNINDEX** alone as broad market health in 2025–2026 without the documented caveat; prefer **breadth** proxies.

