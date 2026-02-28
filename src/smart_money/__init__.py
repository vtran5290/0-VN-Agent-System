from __future__ import annotations

"""
Smart Money Dashboard (Layer 3.5 — Institutional Positioning).

This package works with JSON under data/smart_money/:
- extracted/: per-fund, per-month positioning (fund_extracted schema).
- monthly/: aggregated consensus + scores per month.

Parsing of PDFs/factsheets is done outside this repo; this package is
purely about aggregation, scoring and safe I/O around the JSON files.
"""

