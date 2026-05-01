from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader


TARGET_PERIOD = "2026-02"
TARGET_YEAR = 2026
TARGET_MONTH = 2

OUT_DIR = Path("data") / "funds" / TARGET_PERIOD
STATUS_JSON_PATH = Path("artifacts") / "fund_download_status_2026_02.json"
DEBUG_JSON_PATH = Path("artifacts") / "fund_download_debug_2026_02.json"

MIN_SIZE_BYTES = 50 * 1024

TIMEOUT_HTML = (10, 35)  # (connect, read)
TIMEOUT_PDF = (10, 90)  # (connect, read)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class DownloadResult:
    ok: bool
    reason: str
    url: Optional[str] = None
    path: Optional[str] = None
    size_bytes: Optional[int] = None
    sha256: Optional[str] = None


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        }
    )
    return s


def _safe_filename_component(s: str) -> str:
    s = s.strip()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^A-Za-z0-9_\-]+", "", s)
    return s


def _is_pdf_header(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            head = f.read(8)
        return head.startswith(b"%PDF-")
    except Exception:
        return False


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_pdf(s: requests.Session, url: str, out_path: Path) -> DownloadResult:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Avoid re-download if already valid
    if out_path.exists():
        size = out_path.stat().st_size
        if size >= MIN_SIZE_BYTES and _is_pdf_header(out_path):
            return DownloadResult(
                ok=True,
                reason="already_present",
                url=url,
                path=str(out_path),
                size_bytes=size,
                sha256=_sha256_file(out_path),
            )

    try:
        with s.get(url, stream=True, timeout=TIMEOUT_PDF) as r:
            if r.status_code != 200:
                return DownloadResult(ok=False, reason=f"http_{r.status_code}", url=url)
            ctype = (r.headers.get("Content-Type") or "").lower()
            if "pdf" not in ctype and not url.lower().endswith(".pdf"):
                # Many servers omit correct content-type; allow .pdf URLs
                return DownloadResult(ok=False, reason=f"not_pdf_content_type:{ctype}", url=url)

            tmp_path = out_path.with_suffix(out_path.suffix + ".part")
            total = 0
            with tmp_path.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 64):
                    if not chunk:
                        continue
                    f.write(chunk)
                    total += len(chunk)
                    if total > 200 * 1024 * 1024:
                        # safety
                        tmp_path.unlink(missing_ok=True)
                        return DownloadResult(ok=False, reason="too_large_abort", url=url)

            if total < MIN_SIZE_BYTES:
                tmp_path.unlink(missing_ok=True)
                return DownloadResult(ok=False, reason=f"too_small:{total}", url=url, size_bytes=total)
            if not _is_pdf_header(tmp_path):
                tmp_path.unlink(missing_ok=True)
                return DownloadResult(ok=False, reason="invalid_pdf_header", url=url, size_bytes=total)

            tmp_path.replace(out_path)
            return DownloadResult(
                ok=True,
                reason="downloaded",
                url=url,
                path=str(out_path),
                size_bytes=total,
                sha256=_sha256_file(out_path),
            )
    except requests.RequestException as e:
        return DownloadResult(ok=False, reason=f"request_error:{type(e).__name__}", url=url)
    except Exception as e:
        return DownloadResult(ok=False, reason=f"error:{type(e).__name__}", url=url)


def _fetch_html(s: requests.Session, url: str) -> tuple[Optional[str], Optional[str]]:
    try:
        r = s.get(url, timeout=TIMEOUT_HTML)
        if r.status_code != 200:
            return None, f"http_{r.status_code}"
        return r.text, None
    except requests.RequestException as e:
        return None, f"request_error:{type(e).__name__}"


def _iter_pdf_links(html: str, base_url: str) -> Iterable[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        abs_url = urljoin(base_url, href)
        if ".pdf" not in abs_url.lower():
            continue
        text = " ".join(a.get_text(" ", strip=True).split())
        yield abs_url, text


def _matches_target_period(url: str, text: str) -> bool:
    hay = f"{url} {text}".lower()
    # English
    if "february 2026" in hay or "feb 2026" in hay:
        return True
    if "feb-26" in hay or "feb/26" in hay or "feb-2026" in hay:
        return True
    # Numeric
    if "02/2026" in hay or "2026-02" in hay or "202602" in hay:
        return True
    if "02-2026" in hay or "2/2026" in hay:
        return True
    # Vietnamese-ish common patterns
    if "tháng 2/2026" in hay or "thang 2/2026" in hay or "thang 02/2026" in hay or "tháng 02/2026" in hay:
        return True
    return False


def _prefer_latest_url(urls: list[str]) -> Optional[str]:
    if not urls:
        return None
    # Prefer URLs with explicit day suffix (YYYYMMDD) if present, else longer URL (often includes timestamp folder)
    def key(u: str) -> tuple[int, int]:
        m = re.search(r"(20\d{6})(\d{2})", u)
        dayish = 0
        if m:
            yyyymmdd = m.group(0)
            if len(yyyymmdd) >= 8:
                dayish = int(yyyymmdd[-2:])
        return (dayish, len(u))

    return sorted(urls, key=key, reverse=True)[0]


def _scrape_pdf_links(s: requests.Session, page_url: str) -> tuple[list[tuple[str, str]], list[str]]:
    html, err = _fetch_html(s, page_url)
    if html is None:
        return [], [f"page_fetch_failed:{err}"]
    links: list[tuple[str, str]] = []
    for abs_url, text in _iter_pdf_links(html, page_url):
        links.append((abs_url, text))
    return links, []


def _scrape_pdf_for_period(s: requests.Session, page_url: str) -> tuple[list[str], list[str]]:
    links, errs = _scrape_pdf_links(s, page_url)
    if errs:
        return [], errs
    hits = [u for (u, t) in links if _matches_target_period(u, t)]
    return hits, []


def _pdf_text_contains_period(path: Path) -> bool:
    try:
        reader = PdfReader(str(path))
        pages = reader.pages[:2]
        text = ""
        for p in pages:
            t = p.extract_text() or ""
            text += "\n" + t
        hay = text.lower()
        return (
            "february 2026" in hay
            or "feb 2026" in hay
            or "feb-26" in hay
            or "02/2026" in hay
            or "2026-02" in hay
            or "tháng 2/2026" in hay
            or "tháng 02/2026" in hay
            or "2/2026" in hay
        )
    except Exception:
        return False


def _download_candidates_until_match(
    s: requests.Session,
    candidates: list[str],
    out_path: Path,
    max_try: int = 12,
) -> DownloadResult:
    tmp_dir = OUT_DIR / ".tmp_candidates"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tried = 0
    for url in candidates:
        tried += 1
        if tried > max_try:
            break
        tmp_name = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16] + ".pdf"
        tmp_path = tmp_dir / tmp_name
        r = _download_pdf(s, url, tmp_path)
        if not r.ok:
            continue
        if _pdf_text_contains_period(tmp_path):
            tmp_path.replace(out_path)
            return DownloadResult(
                ok=True,
                reason="downloaded_by_pdf_content_match",
                url=url,
                path=str(out_path),
                size_bytes=out_path.stat().st_size,
                sha256=_sha256_file(out_path),
            )
    return DownloadResult(ok=False, reason="no_candidate_pdf_matched_period")


def _same_origin(a: str, b: str) -> bool:
    try:
        pa = urlparse(a)
        pb = urlparse(b)
        return pa.scheme == pb.scheme and pa.netloc == pb.netloc
    except Exception:
        return False


def _try_direct_urls(s: requests.Session, fund: str, candidates: list[str]) -> tuple[Optional[str], list[str]]:
    errs: list[str] = []
    for url in candidates:
        try:
            r = s.head(url, allow_redirects=True, timeout=TIMEOUT_HTML)
            if r.status_code == 200:
                ctype = (r.headers.get("Content-Type") or "").lower()
                if "pdf" in ctype or url.lower().endswith(".pdf"):
                    return url, errs
                errs.append(f"direct_not_pdf:{url}:{ctype}")
            else:
                errs.append(f"direct_http_{r.status_code}:{url}")
        except requests.RequestException as e:
            errs.append(f"direct_request_error:{type(e).__name__}:{url}")
    return None, errs


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    Path("artifacts").mkdir(parents=True, exist_ok=True)

    s = _session()

    status: dict[str, str] = {}
    debug: dict[str, dict] = {}

    def record(fund_key: str, state: str, **info: object) -> None:
        status[fund_key] = state
        debug[fund_key] = {"state": state, **info}

    try:
        # --- VEIL (factsheet + monthly report) ---
        print("== VEIL ==")
        veil_direct = [
            f"https://wp-veil-dragoncapital-2024.s3.eu-west-2.amazonaws.com/media/{TARGET_YEAR}/02/VEIL_Factsheet_{TARGET_YEAR}02.pdf",
            f"https://wp-veil-dragoncapital-2024.s3.eu-west-2.amazonaws.com/media/{TARGET_YEAR}/02/VEIL_MR_{TARGET_YEAR}02.pdf",
        ]
        veil_downloads: list[DownloadResult] = []
        veil_errs: list[str] = []
        for url, doc_type, out_name in [
            (veil_direct[0], "Factsheet", f"VEIL_Factsheet_{TARGET_PERIOD}.pdf"),
            (veil_direct[1], "MonthlyReport", f"VEIL_MonthlyReport_{TARGET_PERIOD}.pdf"),
        ]:
            r = _download_pdf(s, url, OUT_DIR / out_name)
            veil_downloads.append(r)
            if not r.ok:
                veil_errs.append(f"{doc_type}:{r.reason}")

        if all(r.ok for r in veil_downloads):
            record("VEIL", "downloaded", files=[r.path for r in veil_downloads], urls=[r.url for r in veil_downloads])
        else:
            page_url = "https://www.veil.uk/the-fund/#documents"
            hits, scrape_errs = _scrape_pdf_for_period(s, page_url)
            veil_errs.extend(scrape_errs)
            fallback_downloads: list[DownloadResult] = []
            chosen = hits[:]
            fs = [u for u in chosen if "factsheet" in u.lower() or "fact-sheet" in u.lower() or "fs" in u.lower()]
            mr = [u for u in chosen if "mr" in u.lower() or "monthly" in u.lower() or "report" in u.lower()]
            picked: list[tuple[str, str, str]] = []
            if fs:
                picked.append((_prefer_latest_url(fs) or fs[0], "Factsheet", f"VEIL_Factsheet_{TARGET_PERIOD}.pdf"))
            if mr:
                picked.append((_prefer_latest_url(mr) or mr[0], "MonthlyReport", f"VEIL_MonthlyReport_{TARGET_PERIOD}.pdf"))
            if not picked and hits:
                picked.append((hits[0], "MonthlyReport", f"VEIL_MonthlyReport_{TARGET_PERIOD}.pdf"))
            for url, _, out_name in picked:
                fallback_downloads.append(_download_pdf(s, url, OUT_DIR / out_name))

            if fallback_downloads and all(r.ok for r in fallback_downloads):
                record(
                    "VEIL",
                    "downloaded",
                    files=[r.path for r in fallback_downloads],
                    urls=[r.url for r in fallback_downloads],
                    warnings=veil_errs,
                )
            else:
                record("VEIL", "missing", errors=veil_errs, page_url=page_url, hits=hits)
    except Exception as e:
        record("VEIL", "missing", errors=[f"exception:{type(e).__name__}"])

    try:
        # --- VEF (factsheet + monthly report) ---
        print("== VEF ==")
        vef_page = "https://www.dragoncapital.com/institutional/funds/vef/?fwp_vef_categories=monthly-report"
        vef_hits, vef_scrape_errs = _scrape_pdf_for_period(s, vef_page)
        vef_errs = list(vef_scrape_errs)
        vef_downloads: list[DownloadResult] = []
        if vef_hits:
            fs = [u for u in vef_hits if "factsheet" in u.lower() or "fact-sheet" in u.lower()]
            mr = [u for u in vef_hits if "mr" in u.lower() or "monthly" in u.lower() or "report" in u.lower()]
            picked: list[tuple[str, str]] = []
            if fs:
                picked.append((_prefer_latest_url(fs) or fs[0], f"VEF_Factsheet_{TARGET_PERIOD}.pdf"))
            if mr:
                picked.append((_prefer_latest_url(mr) or mr[0], f"VEF_MonthlyReport_{TARGET_PERIOD}.pdf"))
            if not picked:
                picked.append((vef_hits[0], f"VEF_MonthlyReport_{TARGET_PERIOD}.pdf"))
            for url, out_name in picked:
                vef_downloads.append(_download_pdf(s, url, OUT_DIR / out_name))
        if vef_downloads and all(r.ok for r in vef_downloads):
            record(
                "VEF",
                "downloaded",
                files=[r.path for r in vef_downloads],
                urls=[r.url for r in vef_downloads],
                page_url=vef_page,
            )
        else:
            reasons = [r.reason for r in vef_downloads if not r.ok]
            record("VEF", "missing", page_url=vef_page, hits=vef_hits, errors=vef_errs + reasons)
    except Exception as e:
        record("VEF", "missing", errors=[f"exception:{type(e).__name__}"])

    try:
        # --- VOF (monthly report) ---
        print("== VOF ==")
        vof_direct_candidates = [
            f"https://vof.vinacapital.com/wp-content/uploads/documents/VOF-Monthly_{TARGET_PERIOD}-final.pdf",
            f"https://vof.vinacapital.com/wp-content/uploads/documents/VOF-Monthly_{TARGET_YEAR}-{TARGET_MONTH:02d}-final.pdf",
        ]
        vof_url, vof_direct_errs = _try_direct_urls(s, "VOF", vof_direct_candidates)
        vof_errs = list(vof_direct_errs)
        if vof_url:
            r = _download_pdf(s, vof_url, OUT_DIR / f"VOF_MonthlyReport_{TARGET_PERIOD}.pdf")
            if r.ok:
                record("VOF", "downloaded", files=[r.path], urls=[r.url], method="direct")
            else:
                vof_errs.append(r.reason)
                record("VOF", "missing", errors=vof_errs, tried=vof_direct_candidates)
        else:
            vof_page = "https://vof.vinacapital.com/"
            hits, scrape_errs = _scrape_pdf_for_period(s, vof_page)
            vof_errs.extend(scrape_errs)
            picked = _prefer_latest_url(hits) if hits else None
            if picked:
                r = _download_pdf(s, picked, OUT_DIR / f"VOF_MonthlyReport_{TARGET_PERIOD}.pdf")
                if r.ok:
                    record("VOF", "downloaded", files=[r.path], urls=[r.url], page_url=vof_page, warnings=vof_errs)
                else:
                    record("VOF", "missing", errors=vof_errs + [r.reason], page_url=vof_page, hits=hits)
            else:
                record("VOF", "missing", errors=vof_errs, page_url=vof_page, hits=hits)
    except Exception as e:
        record("VOF", "missing", errors=[f"exception:{type(e).__name__}"])

    try:
        # --- KIM UCITS (factsheet) ---
        print("== KIMUCITS ==")
        kim_ucits_page = "https://koreainvestment.com.vn/en/kim-fund/kim-vietnam-growth-fund-ucits"
        # 1) keyword-filtered hits
        hits, errs = _scrape_pdf_for_period(s, kim_ucits_page)
        picked = _prefer_latest_url(hits) if hits else None
        out_path = OUT_DIR / f"KIMUCITS_Factsheet_{TARGET_PERIOD}.pdf"
        if picked:
            r = _download_pdf(s, picked, out_path)
        else:
            r = DownloadResult(ok=False, reason="no_keyword_hits")
        if not r.ok:
            # 2) fallback: try all PDFs and validate by PDF text
            links, errs2 = _scrape_pdf_links(s, kim_ucits_page)
            all_urls = [u for (u, _) in links]
            r2 = _download_candidates_until_match(s, all_urls, out_path)
            if r2.ok:
                record("KIMUCITS", "downloaded", files=[r2.path], urls=[r2.url], page_url=kim_ucits_page, warnings=errs + errs2 + [r.reason])
            else:
                record("KIMUCITS", "missing", errors=errs + errs2 + [r.reason, r2.reason], page_url=kim_ucits_page, hits=hits, all_pdf_count=len(all_urls))
        else:
            record("KIMUCITS", "downloaded", files=[r.path], urls=[r.url], page_url=kim_ucits_page)
    except Exception as e:
        record("KIMUCITS", "missing", errors=[f"exception:{type(e).__name__}"])

    try:
        # --- KDEF (factsheet) ---
        print("== KDEF ==")
        kdef_page = "https://koreainvestment.com.vn/en/kim-fund/kdef-5778461"
        hits, errs = _scrape_pdf_for_period(s, kdef_page)
        picked = _prefer_latest_url(hits) if hits else None
        out_path = OUT_DIR / f"KDEF_Factsheet_{TARGET_PERIOD}.pdf"
        if picked:
            r = _download_pdf(s, picked, out_path)
        else:
            r = DownloadResult(ok=False, reason="no_keyword_hits")
        if not r.ok:
            links, errs2 = _scrape_pdf_links(s, kdef_page)
            all_urls = [u for (u, _) in links]
            r2 = _download_candidates_until_match(s, all_urls, out_path)
            if r2.ok:
                record("KDEF", "downloaded", files=[r2.path], urls=[r2.url], page_url=kdef_page, warnings=errs + errs2 + [r.reason])
            else:
                record("KDEF", "missing", errors=errs + errs2 + [r.reason, r2.reason], page_url=kdef_page, hits=hits, all_pdf_count=len(all_urls))
        else:
            record("KDEF", "downloaded", files=[r.path], urls=[r.url], page_url=kdef_page)
    except Exception as e:
        record("KDEF", "missing", errors=[f"exception:{type(e).__name__}"])

    # --- VinaCapital onshore funds (monthly report / "Báo cáo tháng") ---
    vinacap_funds = {
        "VMEEF": "https://vinacapital.com/vi/investment-solutions/onshore-funds/vmeef/",
        "VESAF": "https://vinacapital.com/vi/investment-solutions/onshore-funds/vesaf/",
        "VDEF": "https://vinacapital.com/vi/investment-solutions/onshore-funds/vdef/",
        "VEOF": "https://vinacapital.com/vi/investment-solutions/onshore-funds/veof/",
    }
    for fund_key, page_url in vinacap_funds.items():
        try:
            print(f"== {fund_key} ==")
            hits, errs = _scrape_pdf_for_period(s, page_url)
            picked = _prefer_latest_url(hits) if hits else None
            if picked:
                out_name = f"{fund_key}_MonthlyReport_{TARGET_PERIOD}.pdf"
                r = _download_pdf(s, picked, OUT_DIR / out_name)
                if r.ok:
                    record(fund_key, "downloaded", files=[r.path], urls=[r.url], page_url=page_url)
                else:
                    record(fund_key, "missing", errors=errs + [r.reason], page_url=page_url, hits=hits)
            else:
                record(fund_key, "missing", errors=errs, page_url=page_url, hits=hits)
        except Exception as e:
            record(fund_key, "missing", errors=[f"exception:{type(e).__name__}"], page_url=page_url)

    try:
        # --- VNH (monthly report) ---
        print("== VNH ==")
        vnh_page = "https://www.vietnamholding.com/investors/library/"
        hits, errs = _scrape_pdf_for_period(s, vnh_page)
        picked = _prefer_latest_url(hits) if hits else None
        out_path = OUT_DIR / f"VNH_MonthlyReport_{TARGET_PERIOD}.pdf"
        if picked:
            r = _download_pdf(s, picked, out_path)
        else:
            r = DownloadResult(ok=False, reason="no_keyword_hits")
        if not r.ok:
            links, errs2 = _scrape_pdf_links(s, vnh_page)
            all_urls = [u for (u, _) in links]
            r2 = _download_candidates_until_match(s, all_urls, out_path)
            if r2.ok:
                record("VNH", "downloaded", files=[r2.path], urls=[r2.url], page_url=vnh_page, warnings=errs + errs2 + [r.reason])
            else:
                record("VNH", "missing", errors=errs + errs2 + [r.reason, r2.reason], page_url=vnh_page, hits=hits, all_pdf_count=len(all_urls))
        else:
            record("VNH", "downloaded", files=[r.path], urls=[r.url], page_url=vnh_page)
    except Exception as e:
        record("VNH", "missing", errors=[f"exception:{type(e).__name__}"])

    # --- VNH? user list includes VNH yes done. VEF/VEIL etc done.

    # --- PYN (newsletter only) ---
    record(
        "PYN",
        "missing",
        reason="no_public_factsheet_newsletter_only",
        page_url="https://www.pyn.fi/en/pyn-elite-fund/documents/",
    )

    # --- VEF/VOF additional funds requested but not in sources list ---
    # VNH/VEIL/VEF/VOF/KIM/VinaCapital/PYN covered by the registry.

    # Always write outputs even if some funds failed.
    STATUS_JSON_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DEBUG_JSON_PATH.write_text(json.dumps(debug, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ok_count = sum(1 for v in status.values() if v == "downloaded")
    missing = [k for k, v in status.items() if v != "downloaded"]
    print(f"Fund download summary for {TARGET_PERIOD}: {ok_count}/{len(status)} downloaded.")
    if missing:
        print("Missing:", ", ".join(missing))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

