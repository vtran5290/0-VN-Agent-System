#!/usr/bin/env python3
"""
Probe FireAnt REST historical-quotes for optional query params (e.g. intraday resolution).

FACTS:
- Base: GET https://restv2.fireant.vn/symbols/{symbol}/historical-quotes
- Repo default params: startDate, endDate, offset, limit (see src/data/fireant_client.py)
- Official public OpenAPI for restv2 was not found at a stable URL from this repo.

Usage (PowerShell):
  $env:FIREANT_TOKEN="<jwt_without_Bearer_prefix>"
  python scripts/research/fireant_hist_quotes_probe.py --symbol VNM --start 2026-04-28 --end 2026-04-29

Try extra query keys (repeat --param):
  python scripts/research/fireant_hist_quotes_probe.py --symbol VNM --start 2026-04-28 --end 2026-04-29 --param resolution=60 --param type=1

Do NOT paste tokens into git, chat logs, or this file.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Tuple

import requests

RESTV2 = "https://restv2.fireant.vn"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://fireant.vn",
    "Referer": "https://fireant.vn/",
}


def parse_kv(s: str) -> Tuple[str, str]:
    if "=" not in s:
        raise ValueError(f"--param expects key=value, got: {s!r}")
    k, v = s.split("=", 1)
    return k.strip(), v.strip()


def summarize_json(data: Any, max_list: int = 3) -> str:
    if data is None:
        return "null"
    if isinstance(data, list):
        n = len(data)
        if n == 0:
            return "[] (empty)"
        first = data[0]
        keys = list(first.keys()) if isinstance(first, dict) else type(first).__name__
        sample_dates = []
        for i, row in enumerate(data[:max_list]):
            if isinstance(row, dict):
                d = row.get("date") or row.get("Date") or row.get("tradingDate") or row.get("time")
                sample_dates.append(str(d)[:32])
        return f"list len={n} first_keys={keys} sample_date/time={sample_dates}"
    if isinstance(data, dict):
        return f"dict keys={list(data.keys())[:30]}"
    return repr(data)[:400]


def main() -> int:
    p = argparse.ArgumentParser(description="Probe FireAnt historical-quotes query params")
    p.add_argument("--symbol", default="VNM")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument(
        "--param",
        action="append",
        default=[],
        help="Extra query key=value (repeatable), e.g. --param resolution=1",
    )
    args = p.parse_args()

    token = (os.environ.get("FIREANT_TOKEN") or "").strip()
    if not token:
        print("ERROR: Set FIREANT_TOKEN in the environment (raw JWT, no 'Bearer ' prefix).", file=sys.stderr)
        return 2

    headers = {**HEADERS, "Authorization": f"Bearer {token}"}
    params: Dict[str, Any] = {
        "startDate": args.start,
        "endDate": args.end,
        "offset": 0,
        "limit": args.limit,
    }
    for raw in args.param:
        k, v = parse_kv(raw)
        params[k] = v

    url = f"{RESTV2}/symbols/{args.symbol}/historical-quotes"
    print("GET", url)
    print("params:", json.dumps(params, ensure_ascii=False))

    try:
        r = requests.get(url, headers=headers, params=params, timeout=45)
    except requests.RequestException as e:
        print("REQUEST_FAILED:", e)
        return 1

    print("status:", r.status_code, "content-type:", r.headers.get("Content-Type", ""))
    if r.status_code != 200:
        print(r.text[:1200])
        return 1

    try:
        data = r.json()
    except json.JSONDecodeError:
        print("NON_JSON body (first 800 chars):", r.text[:800])
        return 1

    print("summary:", summarize_json(data))
    if isinstance(data, list) and data and isinstance(data[0], dict):
        print("first_row:", json.dumps(data[0], ensure_ascii=False, indent=2)[:2500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
