#!/usr/bin/env python3
"""Regime flash for social media: reads regime_state.json and weekly_report.md."""
import json, re, argparse, sys, io
from pathlib import Path

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def parse_report(path):
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()
    return {
        'vnindex_level': (m.group(1) if (m := re.search(r'vnindex_level=(\d+\.?\d*)', c)) else '[●]'),
        'distribution_days': (m.group(1) if (m := re.search(r'distribution_days_rolling_20=(\d+)', c)) else '[●]'),
        'breadth_zone': (m.group(1) if (m := re.search(r'Composite=(\w+)', c)) else '[●]'),
    }

def load_regime(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_values(regime, report, asof):
    return {
        'regime': regime.get('regime', '[●]'),
        'global_liq': regime.get('global_liquidity', '[●]'),
        'vn_liq': regime.get('vn_liquidity', '[●]'),
        'vnindex': report['vnindex_level'],
        'dist': report['distribution_days'],
        'breadth': report['breadth_zone'],
        'asof': asof,
    }

def format_x(v):
    return f"Regime {v['regime']} ({v['global_liq']}/{v['vn_liq']})\nVNINDEX {v['vnindex']} | Dist {v['dist']}/20\nBreadth: {v['breadth']}\nquantrac.substack.com"

def format_telegram(v):
    return f"🎯 Quan Trắc — Regime Flash | {v['asof']}\n\nRegime: {v['regime']} (Global: {v['global_liq']} / VN: {v['vn_liq']})\nVNINDEX: {v['vnindex']}\nDistribution days: {v['dist']}/20 sessions\nBreadth: {v['breadth']}\n\nObservation only. Not investment advice.\nquantrac.substack.com"

def format_tiktok(v):
    return f"Regime {v['regime']}\n━━━━━━━━\nGlobal: {v['global_liq']}\nVN: {v['vn_liq']}\n━━━━━━━━\nIndex: {v['vnindex']}\nDist: {v['dist']}/20\nBreadth: {v['breadth']}\n━━━━━━━━\nObservation only.\nquantrac.substack.com"

if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Extract regime flash from weekly report.')
    p.add_argument('--as-of', default=None, help='Override asof_date (YYYY-MM-DD).')
    p.add_argument('--format', choices=['x', 'telegram', 'tiktok'], default='telegram', help='Output format.')
    p.add_argument('--regime-state', default=None, help='Path to regime_state.json.')
    p.add_argument('--weekly-report', default=None, help='Path to weekly_report.md.')
    args = p.parse_args()

    regime_path = args.regime_state or Path(__file__).parent.parent / 'data/state/regime_state.json'
    report_path = args.weekly_report or Path(__file__).parent.parent / 'data/decision/weekly_report.md'

    try:
        regime = load_regime(regime_path)
        report = parse_report(report_path)
        asof = args.as_of or regime.get('asof_date', '[●]')
        values = get_values(regime, report, asof)
        formatters = {'x': format_x, 'telegram': format_telegram, 'tiktok': format_tiktok}
        print(formatters[args.format](values))
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        exit(1)
