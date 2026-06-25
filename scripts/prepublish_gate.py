#!/usr/bin/env python3
"""
Prepublish Gate — Scan markdown/HTML files for banned content before public release.

Usage:
    python prepublish_gate.py file1.md file2.html [--strict]

Exit codes:
    0 = all files pass
    1 = blocked (banned content found)
"""

import argparse
import re
import sys


# Banned word list (case-insensitive, whole-word match)
BANNED_WORDS = {
    'buy', 'sell', 'hold', 'signal', 'alert', 'target price', 'allocation',
    'model portfolio', 'recommendation', 'top pick', 'watchlist', 'entry',
    'exit', 'stop loss', 'expected return', 'upside', 'overweight',
    'underweight', 'strong buy', 'buy rating', 'portfolio', 'paper trade',
    'paper_trade', 'fund-grade', 'fund grade', 'decision engine',
    'validated edge', 'blocks weak trades', 'avoid mistakes',
    'find winners', 'avoid losers'
}

# Pattern definitions
PATTERNS = {
    'ticker': r'\b([A-Z]{3})\b(?=\s+(?:is|forms|breaking|breakout|rally|surge|crash|drop|support|resistance)\b)',
    'filepath': r'(?:[DC]:\\|/home/|/root/|data/|src/|scripts/|\.env\b)',
    'credential': r'(?:sk-ant-|Bearer\s+|token=|password=|ANTHROPIC_API|FRED_API|FIREANT)',
    'personal_id': r'(?:vtran5290|LOLII|5\.47|lanphuong)',
    'nav_perf': r'(?:portfolio_nav|nav_history|positions\.csv|returned\s+[\d.]+%|win\s+rate)',
}

# Negation context words (if within 5 words before banned word, skip)
NEGATION_WORDS = {'not', 'no', 'never', 'không', 'dont', "don't", "doesn't"}


def check_negation_context(text, match_start, window=5):
    """Check if banned word is within negation context (5 words before)."""
    before_text = text[:match_start]
    words_before = before_text.split()[-window:]
    return any(word.lower().rstrip(',.!?;:') in NEGATION_WORDS for word in words_before)


def scan_file(filepath, strict=False):
    """
    Scan a file for banned content.
    Returns: list of (line_num, matched_term, context_snippet) tuples
    """
    findings = []

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"ERROR reading {filepath}: {e}", file=sys.stderr)
        return findings

    for line_num, line in enumerate(lines, 1):
        # Skip HTML/Markdown comment lines
        if line.strip().startswith(('<!--', '#')) and '<!--' in line:
            continue

        # 1. Check banned words
        for banned_word in BANNED_WORDS:
            pattern = r'\b' + re.escape(banned_word) + r'\b'
            for match in re.finditer(pattern, line, re.IGNORECASE):
                # Skip if negation context (unless --strict)
                if not strict and check_negation_context(line, match.start()):
                    continue

                context = line[max(0, match.start()-10):min(len(line), match.end()+10)].strip()
                findings.append((line_num, f"BANNED_WORD: {banned_word}", context))

        # 2. Check ticker patterns (directional language)
        for match in re.finditer(PATTERNS['ticker'], line, re.IGNORECASE):
            ticker = match.group(1)
            context = line[max(0, match.start()-10):min(len(line), match.end()+10)].strip()
            findings.append((line_num, f"TICKER_PATTERN: {ticker}", context))

        # 3. Check file paths
        if re.search(PATTERNS['filepath'], line):
            match = re.search(PATTERNS['filepath'], line)
            context = line[max(0, match.start()-10):min(len(line), match.end()+10)].strip()
            findings.append((line_num, "FILE_PATH", context))

        # 4. Check credentials
        if re.search(PATTERNS['credential'], line, re.IGNORECASE):
            match = re.search(PATTERNS['credential'], line, re.IGNORECASE)
            findings.append((line_num, "CREDENTIAL", "[REDACTED]"))

        # 5. Check personal identifiers
        if re.search(PATTERNS['personal_id'], line, re.IGNORECASE):
            match = re.search(PATTERNS['personal_id'], line, re.IGNORECASE)
            context = line[max(0, match.start()-10):min(len(line), match.end()+10)].strip()
            findings.append((line_num, "PERSONAL_ID", context))

        # 6. Check NAV/performance metrics
        if re.search(PATTERNS['nav_perf'], line, re.IGNORECASE):
            match = re.search(PATTERNS['nav_perf'], line, re.IGNORECASE)
            context = line[max(0, match.start()-10):min(len(line), match.end()+10)].strip()
            findings.append((line_num, "NAV_PERF", context))

    return findings


def main():
    parser = argparse.ArgumentParser(
        description='Scan markdown/HTML files for banned content before publishing.'
    )
    parser.add_argument('files', nargs='+', help='File(s) to scan')
    parser.add_argument('--strict', action='store_true',
                        help='Disable negation context exception (flag all banned words)')

    args = parser.parse_args()

    all_findings = []

    for filepath in args.files:
        findings = scan_file(filepath, strict=args.strict)
        for line_num, term, context in findings:
            all_findings.append((filepath, line_num, term, context))

    # Print results table
    if all_findings:
        print("\n" + "="*80)
        print("BLOCKED: Content issues found")
        print("="*80)
        print(f"{'File':<40} {'Line':<6} {'Issue':<20} {'Context':<40}")
        print("-"*80)
        for filepath, line_num, term, context in all_findings:
            fname = filepath.split('\\')[-1] if '\\' in filepath else filepath
            ctx_short = context[:37] + "..." if len(context) > 40 else context
            print(f"{fname:<40} {line_num:<6} {term:<20} {ctx_short:<40}")
        print("="*80)
        return 1
    else:
        print(f"✓ PASS — {len(args.files)} file(s) clean")
        return 0


if __name__ == '__main__':
    sys.exit(main())
