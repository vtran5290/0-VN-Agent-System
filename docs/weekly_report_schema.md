# Weekly Report Schema v1.0

Formal schema for the VN Weekly Investment Report JSON. Used for validation, ingestion output, and dashboard consumption.

## Location

- **Schema file:** `schemas/weekly_report.schema.json`
- **Example payload:** `data/examples/weekly_report.example.json`

## Top-level sections

| Section | Required | Description |
|--------|----------|-------------|
| `metadata` | Yes | Report identity, freshness, confidence, warnings |
| `global_macro` | No | UST, DXY, CPI, NFP facts and deltas |
| `vietnam_liquidity` | No | OMO, interbank, credit, FX |
| `vietnam_policy` | No | Policy events and transmission |
| `research_intake` | No | Macro/sector/company/policy intake |
| `sectors_companies` | No | Earnings, broker notes, catalysts |
| `market_structure` | No | Levels, breadth, distribution |
| `regime_engine` | No | Current/suggested regime, mismatch |
| `probability_allocation` | No | Probabilities and allocation |
| `portfolio_structure` | No | Core gate, bucket allocation |
| `decision_layer` | No | Actions, risks, rules fired |
| `watchlist` | No | Posture, candidates, scores |
| `execution_monitoring` | No | Risk flags, sell/trim signals |
| `portfolio_health` | No | Summary, sector concentration |
| `council_status` | No | Council process status |
| `geo_layers` | No | e.g. geo_hormuz_energy_shock |
| `open_questions` | No | Array of strings |
| `monitoring_next_week` | No | Signals to monitor |
| `playbook_if_x_then_y` | No | If X → do Y rules |

## Market levels: report_snapshot vs latest_market vs wow_delta

Three separate concepts:

1. **report_snapshot** — Market level embedded in the report snapshot (from `market_snapshot_debug.json`). May be stale. Never labeled as current/latest.
2. **latest_market** — Freshest available close from `data/decision/latest_market_snapshot.json`. When this file exists and `asof_date` is after the report snapshot date, KPI uses these values. This is the current/latest level.
3. **wow_delta** — In `what_changed`; change metric only; never used to reconstruct level.

**KPI display:** `market_structure.levels` = latest_market when available, else report_snapshot (with stale badge). **levels** never derived from delta. Out-of-range values (e.g. 7600) are rejected. To show current level (e.g. 1696.24), add or update `data/decision/latest_market_snapshot.json` with `asof_date`, `vnindex_level`, and optionally `vn30_level`.

## Helper types

- **MetricSnapshot:** value, unit, date, source, stale
- **WeeklyDelta:** metric, delta, delta_bps, direction, source
- **PolicyEvent:** date, title, body, transmission
- **CompanyEvent:** ticker, event_type, description, date
- **RiskFlag:** risk_flag, distribution_days_rolling_20, dist_proxy_symbol
- **WatchlistCandidate:** ticker, regime_fit, total_score, notes
- **SourceRef:** name, url, retrieved_at, confidence, is_official
- **RegimeInput:** global_liquidity, vn_liquidity
- **GeoLayerState:** flexible object for geo layer payloads

## Backward compatibility

The current flat `weekly_report.json` (e.g. `asof_date`, `what_changed`, `actions`, `risks`, `geo_hormuz_energy_shock`) is mapped into this schema by the normalizer. Legacy keys are preserved under `metadata` or folded into the new sections; `decision_layer.top_actions` maps from `actions`, etc.

## Validation

- Run: `python -m scripts.utils.validation` (or tests) to validate a payload against `schemas/weekly_report.schema.json`.
- Required: only `metadata` and within it `asof_date`, `schema_version`. All other fields are optional for partial reports.

## Confidence and source coverage

- `metadata.data_confidence`: High | Medium | Low (derived from coverage and staleness).
- `metadata.source_coverage_score`: 0.0–1.0.
- Sections may include `sources[]` (SourceRef) for lineage.
