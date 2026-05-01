"""
Download latest available fund PDFs (factsheets / monthly reports) into data/funds/latest/.

Does not invent URLs: only follows PDF links found on official pages or known CDN patterns.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

OUT_DIR = Path("data") / "funds" / "latest"
STATUS_JSON = Path("artifacts") / "fund_download_status_latest.json"
DEBUG_JSON = Path("artifacts") / "fund_download_debug_latest.json"

MIN_SIZE_BYTES = 50 * 1024
TIMEOUT_HTML = (12, 45)
TIMEOUT_PDF = (12, 120)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class DownloadResult:
    ok: bool
    reason: str
    url: Optional[str] = None
    path: Optional[str] = None
    size_bytes: Optional[int] = None


def _session(extra: Optional[dict[str, str]] = None) -> requests.Session:
    s = requests.Session()
    h = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
    }
    if extra:
        h.update(extra)
    s.headers.update(h)
    return s


def _is_pdf_header(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return f.read(8).startswith(b"%PDF-")
    except OSError:
        return False


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_pdf(s: requests.Session, url: str, out_path: Path) -> DownloadResult:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        sz = out_path.stat().st_size
        if sz >= MIN_SIZE_BYTES and _is_pdf_header(out_path):
            return DownloadResult(True, "already_present", url, str(out_path), sz)

    try:
        with s.get(url, stream=True, timeout=TIMEOUT_PDF) as r:
            if r.status_code != 200:
                return DownloadResult(False, f"http_{r.status_code}", url)
            ctype = (r.headers.get("Content-Type") or "").lower()
            if "pdf" not in ctype and not url.lower().endswith(".pdf"):
                return DownloadResult(False, f"not_pdf:{ctype}", url)
            tmp = out_path.with_suffix(out_path.suffix + ".part")
            total = 0
            with tmp.open("wb") as f:
                for chunk in r.iter_content(64 * 1024):
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)
                        if total > 200 * 1024 * 1024:
                            tmp.unlink(missing_ok=True)
                            return DownloadResult(False, "too_large", url)
            if total < MIN_SIZE_BYTES:
                tmp.unlink(missing_ok=True)
                return DownloadResult(False, f"too_small:{total}", url, size_bytes=total)
            if not _is_pdf_header(tmp):
                tmp.unlink(missing_ok=True)
                return DownloadResult(False, "invalid_pdf_header", url)
            tmp.replace(out_path)
            return DownloadResult(True, "downloaded", url, str(out_path), out_path.stat().st_size)
    except requests.RequestException as e:
        return DownloadResult(False, f"request:{type(e).__name__}", url)


def _fetch_html(s: requests.Session, url: str) -> tuple[Optional[str], Optional[str]]:
    try:
        r = s.get(url, timeout=TIMEOUT_HTML)
        if r.status_code != 200:
            return None, f"http_{r.status_code}"
        return r.text, None
    except requests.RequestException as e:
        return None, f"request:{type(e).__name__}"


def _iter_pdf_links(html: str, base: str) -> Iterable[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href or ".pdf" not in href.lower():
            continue
        yield urljoin(base, href), " ".join(a.get_text(" ", strip=True).split())


def _url_date_score(url: str) -> int:
    """Higher = more recent (best-effort from URL path)."""
    best = 0
    for m in re.finditer(r"(20\d{2})(\d{2})(\d{2})?", url):
        y, mo = m.group(1), m.group(2)
        d = m.group(3) or "01"
        try:
            val = int(y + mo + d)
            best = max(best, val)
        except ValueError:
            pass
    m2 = re.search(r"(20\d{2})-(\d{2})", url)
    if m2:
        try:
            best = max(best, int(m2.group(1) + m2.group(2) + "01"))
        except ValueError:
            pass
    return best


def _prefer_latest(urls: list[str]) -> Optional[str]:
    if not urls:
        return None
    return sorted(urls, key=lambda u: (_url_date_score(u), len(u)), reverse=True)[0]


def _scrape_all_pdfs(s: requests.Session, page_url: str) -> tuple[list[tuple[str, str]], list[str]]:
    html, err = _fetch_html(s, page_url)
    if html is None:
        return [], [err or "unknown"]
    return list(_iter_pdf_links(html, page_url)), []


def _vof_probe_latest_monthly_url(s: requests.Session) -> tuple[Optional[str], list[str]]:
    """Newest existing VOF-Monthly_YYYY-MM-final.pdf (site homepage often returns 403 to bots)."""
    from datetime import date

    errs: list[str] = []
    y, mo = date.today().year, date.today().month
    for _ in range(48):
        period = f"{y}-{mo:02d}"
        url = f"https://vof.vinacapital.com/wp-content/uploads/documents/VOF-Monthly_{period}-final.pdf"
        try:
            hr = s.head(url, allow_redirects=True, timeout=TIMEOUT_HTML)
            if hr.status_code == 200:
                return url, errs
            errs.append(f"{period}:http_{hr.status_code}")
        except requests.RequestException as e:
            errs.append(f"{period}:{type(e).__name__}")
        mo -= 1
        if mo < 1:
            mo = 12
            y -= 1
    return None, errs


def _vnh_investor_pdf_urls(urls: list[str]) -> list[str]:
    """Prefer VNH-branded investor PDFs (filename/path must reference VNH)."""
    good: list[str] = []
    for u in urls:
        low = u.lower()
        # Must look like a VNH document, not generic industry/library uploads
        if not any(
            tok in low
            for tok in (
                "vnh-",
                "_vnh",
                "vnh_",
                "vnhinvestor",
                "vnh-investor",
                "vietnam-holding",
                "vietnamholding-",
            )
        ):
            continue
        if any(
            b in low
            for b in (
                "tel_",
                "dynamcapital",
                "webinar",
                "carbon",
                "footprint",
                "executive-summary",
                "crib-sheet",
                "crib_sheet",
            )
        ):
            continue
        # Monthly / investor report wording (not one-pagers / legacy sheets)
        if not any(
            k in low
            for k in (
                "investor-report",
                "investor_report",
                "monthly",
                "vnh-update",
                "vnh_update",
                "investor-update",
                "investorupdate",
            )
        ):
            continue
        if not re.search(r"20(2[4-9]|3[0-9])", u):
            continue
        good.append(u)
    return good


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    Path("artifacts").mkdir(parents=True, exist_ok=True)

    status: dict[str, str] = {}
    debug: dict[str, dict] = {}

    def rec(key: str, st: str, **kw: object) -> None:
        status[key] = st
        debug[key] = {"state": st, **kw}

    # --- VEIL: direct latest month via S3 pattern unknown without probing; scrape documents ---
    print("== VEIL ==")
    s = _session()
    veil_pages = [
        "https://www.veil.uk/the-fund/",
        "https://www.veil.uk/news/category/funds/fund-performance/",
    ]
    veil_pdfs: list[str] = []
    errs: list[str] = []
    for p in veil_pages:
        links, e = _scrape_all_pdfs(s, p)
        veil_pdfs.extend([u for u, _ in links])
        errs.extend(e)
    veil_pdfs = list(dict.fromkeys(veil_pdfs))
    fs = [u for u in veil_pdfs if "factsheet" in u.lower() and "veil" in u.lower()]
    if not fs:
        fs = [u for u in veil_pdfs if "factsheet" in u.lower()]
    mr = [
        u
        for u in veil_pdfs
        if "veil" in u.lower() and ("veil_mr" in u.lower() or "_mr_" in u.lower() or "/mr" in u.lower())
    ]
    if not mr:
        mr = [u for u in veil_pdfs if "veil" in u.lower() and "monthly" in u.lower()]
    u_fs, u_mr = _prefer_latest(fs), _prefer_latest(mr)
    if u_fs:
        r = _download_pdf(s, u_fs, OUT_DIR / "VEIL_Factsheet_latest.pdf")
        if r.ok:
            rec("VEIL_Factsheet", "downloaded", url=u_fs, file=r.path, sha256=_sha256_file(Path(r.path)) if r.path else None)
        else:
            rec("VEIL_Factsheet", "missing", url=u_fs, error=r.reason, page_errors=errs)
    else:
        rec("VEIL_Factsheet", "missing", error="no_pdf_link", page_errors=errs)
    if u_mr:
        r = _download_pdf(s, u_mr, OUT_DIR / "VEIL_MonthlyReport_latest.pdf")
        if r.ok:
            rec("VEIL_MonthlyReport", "downloaded", url=u_mr, file=r.path, sha256=_sha256_file(Path(r.path)) if r.path else None)
        else:
            rec("VEIL_MonthlyReport", "missing", url=u_mr, error=r.reason)
    else:
        rec("VEIL_MonthlyReport", "missing", error="no_pdf_link")

    # --- VEF ---
    print("== VEF ==")
    vef_page = "https://www.dragoncapital.com/institutional/funds/vef/?fwp_vef_categories=monthly-report"
    links, e2 = _scrape_all_pdfs(s, vef_page)
    all_u = [u for u, _ in links]
    fs_u = [u for u in all_u if "vef" in u.lower() and "factsheet" in u.lower()]
    mr_u = [u for u in all_u if "vef" in u.lower() and ("_mr" in u.lower() or "monthly" in u.lower())]
    u1, u2 = _prefer_latest(fs_u), _prefer_latest(mr_u)
    if u1:
        r = _download_pdf(s, u1, OUT_DIR / "VEF_Factsheet_latest.pdf")
        rec("VEF_Factsheet", "downloaded" if r.ok else "missing", url=u1, file=r.path, error=None if r.ok else r.reason, scrape_errors=e2)
    else:
        rec("VEF_Factsheet", "missing", error="no_link", scrape_errors=e2)
    if u2:
        r = _download_pdf(s, u2, OUT_DIR / "VEF_MonthlyReport_latest.pdf")
        rec("VEF_MonthlyReport", "downloaded" if r.ok else "missing", url=u2, file=r.path, error=None if r.ok else r.reason)
    else:
        rec("VEF_MonthlyReport", "missing", error="no_link")

    # --- VOF (homepage often 403; probe known wp-content pattern month-by-month from today) ---
    print("== VOF ==")
    vof_page = "https://vof.vinacapital.com/"
    links, e3 = _scrape_all_pdfs(s, vof_page)
    monthly = [u for u, _ in links if "vof" in u.lower() and "monthly" in u.lower()]
    u = _prefer_latest(monthly) or _prefer_latest([u for u, _ in links if ".pdf" in u.lower()])
    probe_errs: list[str] = []
    if not u:
        u, probe_errs = _vof_probe_latest_monthly_url(s)
    if u:
        r = _download_pdf(s, u, OUT_DIR / "VOF_MonthlyReport_latest.pdf")
        rec(
            "VOF",
            "downloaded" if r.ok else "missing",
            url=u,
            file=r.path,
            error=None if r.ok else r.reason,
            homepage_scrape_errors=e3,
            monthly_probe_errors=probe_errs,
        )
    else:
        rec("VOF", "missing", error="no_pdf", scrape_errors=e3, monthly_probe_errors=probe_errs)

    # --- KIM UCITS / KDEF (factsheet): all PDFs on page, pick latest by URL date ---
    print("== KIMUCITS ==")
    kim_p = "https://koreainvestment.com.vn/en/kim-fund/kim-vietnam-growth-fund-ucits"
    links, ek = _scrape_all_pdfs(s, kim_p)
    pdfs = [u for u, _ in links]
    u_kim = _prefer_latest(pdfs)
    if u_kim:
        r = _download_pdf(s, u_kim, OUT_DIR / "KIMUCITS_Factsheet_latest.pdf")
        rec("KIMUCITS", "downloaded" if r.ok else "missing", url=u_kim, file=r.path, error=None if r.ok else r.reason, all_pdf_count=len(pdfs))
    else:
        rec(
            "KIMUCITS",
            "missing",
            error="no_pdf_in_static_html",
            hint="page_shell_js_rendered_try_browser",
            errors=ek,
        )

    print("== KDEF ==")
    kdef_p = "https://koreainvestment.com.vn/en/kim-fund/kdef-5778461"
    links, ek2 = _scrape_all_pdfs(s, kdef_p)
    pdfs2 = [u for u, _ in links]
    u_kdef = _prefer_latest(pdfs2)
    if u_kdef:
        r = _download_pdf(s, u_kdef, OUT_DIR / "KDEF_Factsheet_latest.pdf")
        rec("KDEF", "downloaded" if r.ok else "missing", url=u_kdef, file=r.path, error=None if r.ok else r.reason, all_pdf_count=len(pdfs2))
    else:
        rec(
            "KDEF",
            "missing",
            error="no_pdf_in_static_html",
            hint="page_shell_js_rendered_try_browser",
            errors=ek2,
        )

    # --- VinaCapital onshore: browser-like headers + EN pages ---
    print("== VinaCapital onshore ==")
    s_vc = _session(
        {
            "Referer": "https://vinacapital.com/",
            "Origin": "https://vinacapital.com",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Upgrade-Insecure-Requests": "1",
        }
    )
    vinacap = {
        "VMEEF": "https://vinacapital.com/en/investment-solutions/onshore-funds/vmeef/",
        "VESAF": "https://vinacapital.com/en/investment-solutions/onshore-funds/vesaf/",
        "VDEF": "https://vinacapital.com/en/investment-solutions/onshore-funds/vdef/",
        "VEOF": "https://vinacapital.com/en/investment-solutions/onshore-funds/veof/",
    }
    for fk, purl in vinacap.items():
        print(f"== {fk} ==")
        links, err = _scrape_all_pdfs(s_vc, purl)
        if err and not links:
            links2, err2 = _scrape_all_pdfs(s, purl.replace("/en/", "/vi/"))
            links, err = links2, err + err2
        pdfs_v = [u for u, _ in links]
        best = _prefer_latest(pdfs_v)
        if best:
            r = _download_pdf(s_vc, best, OUT_DIR / f"{fk}_MonthlyReport_latest.pdf")
            if not r.ok:
                r = _download_pdf(s, best, OUT_DIR / f"{fk}_MonthlyReport_latest.pdf")
            rec(fk, "downloaded" if r.ok else "missing", url=best, file=r.path, error=None if r.ok else r.reason, fetch_errors=err)
        else:
            rec(fk, "missing", error="no_pdf_or_403", fetch_errors=err, page=purl)

    # --- VNH ---
    print("== VNH ==")
    vnh_p = "https://www.vietnamholding.com/investors/library/"
    links, ev = _scrape_all_pdfs(s, vnh_p)
    cand = [u for u, _ in links if "pdf" in u.lower()]
    cand = _vnh_investor_pdf_urls(cand)
    if not cand:
        cand = [
            u
            for u, _ in links
            if "pdf" in u.lower()
            and "vnh" in u.lower()
            and any(
                k in u.lower()
                for k in ("monthly", "investor-report", "investor_report", "vnh-update", "vnh_update")
            )
            and not any(
                b in u.lower()
                for b in ("carbon", "footprint", "tel_", "dynamcapital", "crib-sheet", "webinar", "executive-summary")
            )
            and re.search(r"20(2[4-9]|3[0-9])", u)
        ]
    u_vnh = _prefer_latest(cand)
    if u_vnh:
        r = _download_pdf(s, u_vnh, OUT_DIR / "VNH_MonthlyReport_latest.pdf")
        rec("VNH", "downloaded" if r.ok else "missing", url=u_vnh, file=r.path, error=None if r.ok else r.reason)
    else:
        rec("VNH", "missing", error="no_pdf", errors=ev)

    # --- PYN ---
    rec("PYN", "missing", reason="no_public_monthly_pdf_typically_newsletter_only", page="https://www.pyn.fi/en/pyn-elite-fund/documents/")

    # Aggregate fund-level status for compatibility
    agg = {
        "VEIL": "downloaded"
        if status.get("VEIL_Factsheet") == "downloaded" or status.get("VEIL_MonthlyReport") == "downloaded"
        else "missing",
        "VEF": "downloaded"
        if status.get("VEF_Factsheet") == "downloaded" or status.get("VEF_MonthlyReport") == "downloaded"
        else "missing",
        "VOF": status.get("VOF", "missing"),
        "KIMUCITS": status.get("KIMUCITS", "missing"),
        "KDEF": status.get("KDEF", "missing"),
        "VMEEF": status.get("VMEEF", "missing"),
        "VESAF": status.get("VESAF", "missing"),
        "VDEF": status.get("VDEF", "missing"),
        "VEOF": status.get("VEOF", "missing"),
        "VNH": status.get("VNH", "missing"),
        "PYN": status.get("PYN", "missing"),
    }

    STATUS_JSON.write_text(json.dumps(agg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DEBUG_JSON.write_text(json.dumps(debug, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    n_ok = sum(1 for k, v in agg.items() if v == "downloaded")
    print(f"Summary: {n_ok}/10 funds have at least one latest file (PYN excluded). Files in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
