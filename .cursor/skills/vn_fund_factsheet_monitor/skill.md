# Vietnam Fund Factsheet Monitor & Downloader

Use this skill when the user asks to check latest fund factsheets, download Vietnam fund reports, track publication status of VNH/VEIL/VEF/KIM/VinaCapital/VOF factsheets, or aggregate fund documents for the reporting engine.

You are a fund research assistant that tracks and downloads monthly factsheets/summaries for Vietnam-focused investment funds.

## Fund Registry

| # | Fund | Document Page | Notes |
|---|------|--------------|-------|
| 1 | Vietnam Holding (VNH) | https://www.vietnamholding.com/investors/library/ | Click "View All" under Monthly Reports |
| 2 | VEIL (Dragon Capital) | https://www.veil.uk/the-fund/#documents | Publishes both Factsheet + Monthly Report |
| 3 | VEF (Dragon Capital) | https://www.dragoncapital.com/institutional/funds/vef/?fwp_vef_categories=monthly-report | Publishes both Factsheet + Monthly Report |
| 4 | KIM Vietnam Growth Fund (UCITS) | https://koreainvestment.com.vn/en/kim-fund/kim-vietnam-growth-fund-ucits | Factsheet only, ~10th of following month |
| 5 | KIM Growth Dividend Equity Fund (KDEF) | https://koreainvestment.com.vn/en/kim-fund/kdef-5778461 | Factsheet only, onshore fund since Apr 2025 |
| 6 | PYN Elite Fund | https://www.pyn.fi/en/pyn-elite-fund/documents/ | ⚠️ No public factsheet — newsletter subscribers only |
| 7 | VINACAPITAL-VMEEF | https://vinacapital.com/vi/investment-solutions/onshore-funds/vmeef/ | "Báo cáo tháng", ~12th–15th of following month |
| 8 | VINACAPITAL-VESAF | https://vinacapital.com/vi/investment-solutions/onshore-funds/vesaf/ | "Báo cáo tháng", ~12th–15th of following month |
| 9 | VINACAPITAL-VDEF | https://vinacapital.com/vi/investment-solutions/onshore-funds/vdef/ | "Báo cáo tháng", ~12th–15th of following month |
| 10 | VINACAPITAL-VEOF | https://vinacapital.com/vi/investment-solutions/onshore-funds/veof/ | "Báo cáo tháng", ~12th–15th of following month |
| 11 | VOF (VinaCapital Vietnam Opportunity Fund) | https://vof.vinacapital.com/ | Direct PDF link on homepage |

## Known PDF URL Patterns (as of March 2026)

Use these patterns to construct or verify direct download links:

| Fund | URL Pattern | Example |
|------|------------|---------|
| VEIL Factsheet | `https://wp-veil-dragoncapital-2024.s3.eu-west-2.amazonaws.com/media/YYYY/MM/VEIL_Factsheet_YYYYMM.pdf` | `VEIL_Factsheet_202602.pdf` |
| VEIL Monthly Report | `https://wp-veil-dragoncapital-2024.s3.eu-west-2.amazonaws.com/media/YYYY/MM/VEIL_MR_YYYYMM.pdf` | `VEIL_MR_202602.pdf` |
| VEF Factsheet | `https://cdn.dragoncapital.com/media/YYYY/MM/[timestamp]/VEF_Factsheet_YYYYMM.pdf` | `VEF_Factsheet_202602.pdf` |
| VEF Monthly Report | `https://cdn.dragoncapital.com/media/YYYY/MM/[timestamp]/VEF_MR_YYYYMMDD.pdf` | `VEF_MR_20260228.pdf` |
| KIM UCITS Factsheet | `https://koreainvestment.com.vn/storage/sicav/[id].pdf` | Must scrape page for current link |
| KIM KDEF Factsheet | `https://koreainvestment.com.vn/storage/fund/[id].pdf` | Must scrape page for current link |
| VOF Monthly Report | `https://vof.vinacapital.com/wp-content/uploads/documents/VOF-Monthly_YYYY-MM-final.pdf` | `VOF-Monthly_2026-02-final.pdf` |
| VNH Monthly Report | `https://www.vietnamholding.com/media/[id]/vnh-investor-report-[month]-[year].pdf` | Must scrape page for link |
| VinaCapital funds | Scrape from fund page "Báo cáo tháng X YYYY" section | Must scrape page for link |

## Commands

### `check latest factsheets`

**Invoked by:** "check latest", "check status", "what's new", "update me", or any similar phrasing.

**Steps:**

1. Visit each fund's document page
2. Find the most recent factsheet, monthly report, or fund summary
3. Return a formatted status table:

```
╔══════════════════════╦═══════════════════════════════╦══════════════╦══════════╗
║ Fund                 ║ Document Type                 ║ Latest Period║ Status   ║
╠══════════════════════╬═══════════════════════════════╬══════════════╬══════════╣
║ VNH                  ║ Monthly Report                ║ Jan 2026     ║ ⚠️ -1mo  ║
║ VEIL                 ║ Factsheet + Monthly Report    ║ Feb 2026     ║ ✅       ║
║ VEF                  ║ Factsheet + Monthly Report    ║ Feb 2026     ║ ✅       ║
║ KIM UCITS            ║ Factsheet                     ║ Feb 2026     ║ ✅       ║
║ KIM KDEF             ║ Factsheet                     ║ Jan 2026     ║ ⚠️ -1mo  ║
║ PYN Elite            ║ N/A (newsletter only)         ║ N/A          ║ ℹ️       ║
║ VMEEF                ║ Báo cáo tháng                 ║ Jan 2026     ║ ⚠️ -1mo  ║
║ VESAF                ║ Báo cáo tháng                 ║ Jan 2026     ║ ⚠️ -1mo  ║
║ VDEF                 ║ Báo cáo tháng                 ║ Jan 2026     ║ ⚠️ -1mo  ║
║ VEOF                 ║ Báo cáo tháng                 ║ Jan 2026     ║ ⚠️ -1mo  ║
║ VOF                  ║ Monthly Report                ║ Feb 2026     ║ ✅       ║
╚══════════════════════╩═══════════════════════════════╩══════════════╩══════════╝
Summary: 4/11 funds have Feb 2026 | 6/11 funds still on Jan 2026 | 1 N/A
```

**Status legend:**

- ✅ = matches latest expected month
- ⚠️ -1mo = one month behind
- ⚠️ -2mo = two months behind (flag for attention)
- ℹ️ = no public document (newsletter/subscriber only)

---

### `download all [period] factsheets`

**Example invocations:**

- `download all feb-26 factsheets`
- `download all jan-26 reports`
- `download latest factsheets`
- `download available feb-26`

**Steps:**

1. Parse the target period (e.g. "feb-26" → February 2026, "latest" → most recent per fund)
2. For each fund, locate the PDF using known URL patterns first; fall back to scraping the page
3. Download available files with standardized names:

| Fund | Factsheet filename | Monthly Report filename |
|------|--------------------|------------------------|
| VNH | — | `VNH_MonthlyReport_[Mon-YY].pdf` |
| VEIL | `VEIL_Factsheet_[Mon-YY].pdf` | `VEIL_MonthlyReport_[Mon-YY].pdf` |
| VEF | `VEF_Factsheet_[Mon-YY].pdf` | `VEF_MonthlyReport_[Mon-YY].pdf` |
| KIM UCITS | `KIM_UCITS_Factsheet_[Mon-YY].pdf` | — |
| KIM KDEF | `KIM_KDEF_Factsheet_[Mon-YY].pdf` | — |
| PYN | *(skip — not public)* | — |
| VMEEF | `VMEEF_BaoCaoThang_[Mon-YY].pdf` | — |
| VESAF | `VESAF_BaoCaoThang_[Mon-YY].pdf` | — |
| VDEF | `VDEF_BaoCaoThang_[Mon-YY].pdf` | — |
| VEOF | `VEOF_BaoCaoThang_[Mon-YY].pdf` | — |
| VOF | — | `VOF_MonthlyReport_[Mon-YY].pdf` |

4. Report a download summary:

```
Download Summary — Feb 2026
────────────────────────────────────────────
✅ VEIL_Factsheet_Feb-26.pdf            downloaded
✅ VEIL_MonthlyReport_Feb-26.pdf        downloaded
✅ VEF_Factsheet_Feb-26.pdf             downloaded
✅ VEF_MonthlyReport_Feb-26.pdf         downloaded
✅ KIM_UCITS_Factsheet_Feb-26.pdf       downloaded
✅ VOF_MonthlyReport_Feb-26.pdf         downloaded
⚠️ VNH                                  Feb 2026 not yet available (latest: Jan 2026)
⚠️ KIM_KDEF                             Feb 2026 not yet available (latest: Jan 2026)
⚠️ VMEEF                                Feb 2026 not yet available (latest: Jan 2026)
⚠️ VESAF                                Feb 2026 not yet available (latest: Jan 2026)
⚠️ VDEF                                 Feb 2026 not yet available (latest: Jan 2026)
⚠️ VEOF                                 Feb 2026 not yet available (latest: Jan 2026)
ℹ️ PYN Elite                            No public factsheet (newsletter only)
────────────────────────────────────────────
Total: 6 files downloaded | 6 pending | 1 N/A
```

---

## Publication Schedule (expected timing each month)

| Fund | Typical publish date | Notes |
|------|---------------------|-------|
| VEIL | ~7th–10th of following month | Via dragoncapital.com |
| VEF | ~10th–14th of following month | Via dragoncapital.com |
| KIM UCITS | ~10th of following month | |
| KIM KDEF | ~10th–11th of following month | |
| VOF | ~10th–14th of following month | PDF linked directly on homepage |
| VNH | ~7th–14th of following month | |
| VinaCapital funds (4) | ~12th–15th of following month | |
| PYN Elite | N/A | Subscribers receive monthly newsletter |

## When to use

- User asks: "check latest factsheets", "download fund reports", "status VNH VEIL VEF", "tổng hợp báo cáo quỹ", or anything about Vietnam fund factsheets/monthly reports.
- Engine needs to aggregate fund reports: use this skill to know sources, URL patterns, and naming conventions.

## Failure handling

- If a document page is down or structure changed: note in status table, skip that fund in download summary.
- If direct URL pattern fails: fall back to scraping the document page for the current PDF link.
- PYN Elite: always report as N/A / newsletter only; do not attempt public download.
