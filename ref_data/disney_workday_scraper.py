#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Disney Careers Unified Scraper (HTML / Workday / Hybrid)
+ Unicode Sanitization
+ CSV Export
+ Concurrency with global rate limiting and retries

Modes
-----
- html: crawl disneycareers.com pages and parse fields from HTML job pages
- workday: (may be gated on Disney) try Workday CXS list + detail
- hybrid: use HTML to enumerate jobs, then enrich each via Workday detail /jobs/{id}

Safety
------
- --concurrency: number of parallel workers for detail fetches
- --rate: global requests/second (shared across workers)
- Retries with exponential backoff on 429/5xx

Sanitization
------------
--sanitize will:
    * Normalize text to NFC
    * Replace NBSP (\u00A0) with normal spaces
    * Remove zero-width spaces / joiners / BOM

Hybrid, sanitized, CSV, cautious speed
python unified_scraper.py --mode hybrid --pages 5 --max-items 50 \
  --concurrency 4 --rate 2 --retries 2 \
  --sanitize \
  --out hybrid_50.json --csv hybrid_50.csv

HTML only, faster but still polite
python unified_scraper.py --mode html --pages 6 \
  --concurrency 6 --rate 3 \
  --sanitize \
  --out html_60.json --csv html_60.csv

Get it all
python unified_scraper.py --mode hybrid --pages 101 --concurrency 6 --rate 6 --retries 2 --sanitize --out hybrid_101.json 

Get it all v2
python unified_scraper.py --mode html --pages 101 \               
  --concurrency 6 --rate 6 \
  --sanitize \
  --out html_100.json --csv html_100.csv


Notes on throttling
	•	--rate is global across all threads, so --concurrency 8 --rate 2 still averages ~2 req/s.
	•	On 429/5xx, requests retry with exponential backoff (0.75s, 1.5s, 3.0s …).
	•	Pager/listing requests are kept sequential to avoid weird page duplication logic; only detail fetches run in parallel.

"""

import re
import os
import sys
import csv
import json
import time
import uuid
import math
import argparse
import unicodedata
import threading
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import (
    urljoin, urlparse, urlsplit, urlunsplit, urlencode, parse_qsl
)
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

# ---------- Constants ----------
HTML_BASE = "https://www.disneycareers.com"
HTML_START_URL = "https://www.disneycareers.com/en/search-jobs"

WD_DEFAULT_BASE = "https://disney.wd5.myworkdayjobs.com/wday/cxs/disney/disneycareer"
WD_LIST_ENDPOINT = "/jobs"
WD_DETAIL_ENDPOINT = "/jobs/{job_id}"

DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

DETAIL_PATH_RE = re.compile(r"^/en/job/[^/]+/[^/]+/\d+/\d+/?$")  # disney HTML job URLs
JOB_ID_FROM_URL_RE = re.compile(r"/(\d+)(?:/?)$")                # last numeric path segment (job id)

DEFAULT_CSV_FIELDS = [
    "id",
    "displayRequisitionId",
    "title",
    "postedOn",
    "locationsText",
    "jobUrl",
    "detail.brand",
    "detail.businessUnit",
    "detail.jobFamily",
]

# ---------- Unicode sanitizer ----------
ZERO_WIDTHS = {"\u200b", "\u200c", "\u200d", "\ufeff"}
NBSP = "\u00a0"

def _clean_string(s: str, debug: bool = False) -> str:
    if s is None:
        return s
    original = s
    s = unicodedata.normalize("NFC", s)
    if NBSP in s:
        s = s.replace(NBSP, " ")
    if any(ch in s for ch in ZERO_WIDTHS):
        for ch in ZERO_WIDTHS:
            s = s.replace(ch, "")
    if debug and s != original:
        removed = sum(original.count(ch) for ch in ZERO_WIDTHS) + original.count(NBSP)
        if removed:
            print(f"[SANITIZE] removed ~{removed} invisible/nbsp chars", file=sys.stderr)
    return s

def _clean_obj(obj, debug: bool = False):
    if isinstance(obj, dict):
        return {k: _clean_obj(v, debug) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_obj(v, debug) for v in obj]
    if isinstance(obj, str):
        return _clean_string(obj, debug)
    return obj

# ---------- Rate Limiter & Retry ----------
class RateLimiter:
    """Simple global token bucket: up to `rate` tokens per second."""
    def __init__(self, rate: float):
        self.rate = max(0.1, rate)  # floor
        self.capacity = max(1.0, rate * 2.0)
        self.tokens = self.capacity
        self.last = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self):
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last
            self.last = now
            # Refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            if self.tokens < 1.0:
                # need to wait for 1 token
                need = 1.0 - self.tokens
                sleep_for = need / self.rate
                time.sleep(sleep_for)
                self.tokens = 0.0
                self.last = time.monotonic()
            else:
                self.tokens -= 1.0

RETRY_STATUS = {429, 500, 502, 503, 504}

def do_request(session: requests.Session, method: str, url: str, *,
               headers: Dict[str, str] = None,
               params: Dict[str, Any] = None,
               json_body: Any = None,
               timeout: float = 30.0,
               retries: int = 2,
               backoff_base: float = 0.75,
               rate_limiter: Optional[RateLimiter] = None,
               debug: bool = False) -> requests.Response:
    """Make a request with global rate-limiting + retry/backoff on 429/5xx."""
    attempt = 0
    while True:
        attempt += 1
        if rate_limiter:
            rate_limiter.acquire()
        try:
            r = session.request(
                method=method.upper(),
                url=url,
                headers=headers,
                params=params,
                json=json_body,
                timeout=timeout,
            )
        except Exception as e:
            if attempt > retries + 1:
                raise
            sleep_time = backoff_base * (2 ** (attempt - 1))
            if debug:
                print(f"[REQ] network error {e}; retry {attempt-1}/{retries} in {sleep_time:.2f}s", file=sys.stderr)
            time.sleep(sleep_time)
            continue

        if (r.status_code in RETRY_STATUS) and (attempt <= retries + 1):
            sleep_time = backoff_base * (2 ** (attempt - 1))
            if debug:
                print(f"[REQ] {r.status_code} retry {attempt-1}/{retries} in {sleep_time:.2f}s ({url})", file=sys.stderr)
            time.sleep(sleep_time)
            continue

        return r

# ---------- Common helpers ----------
def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": DEFAULT_UA})
    return s

def debug_print(enabled: bool, *args):
    if enabled:
        print(*args, file=sys.stderr, flush=True)

def write_outputs(all_jobs: List[Dict[str, Any]], combined_path: str, ndjson: bool, per_dir: Optional[str]):
    if per_dir:
        os.makedirs(per_dir, exist_ok=True)
        for j in all_jobs:
            jid = (
                j.get("jobId")
                or j.get("displayRequisitionId")
                or j.get("id")
                or re.sub(r"[^A-Za-z0-9]+", "_", j.get("jobName") or j.get("title") or "unknown")
            )
            with open(os.path.join(per_dir, f"{jid}.json"), "w", encoding="utf-8") as f:
                json.dump(j, f, ensure_ascii=False, indent=2)

    if ndjson:
        for rec in all_jobs:
            print(json.dumps(rec, ensure_ascii=False))
        return

    outdoc = {"metadata": {"count": len(all_jobs)}, "jobs": all_jobs}
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(outdoc, f, ensure_ascii=False, indent=2)

def _get_path(d: Dict[str, Any], dotted: str):
    cur = d
    for part in dotted.split("."):
        if isinstance(cur, dict) and (part in cur):
            cur = cur[part]
        else:
            return None
    return cur

def write_csv(all_jobs: List[Dict[str, Any]], csv_path: str, fields: List[str]):
    os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        for j in all_jobs:
            row = []
            for col in fields:
                val = _get_path(j, col)
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                row.append("" if val is None else str(val))
            writer.writerow(row)

# =========================
# HTML MODE
# =========================
def http_get(url: str, session: requests.Session, headers: Dict[str, str], debug: bool,
             rate_limiter: Optional[RateLimiter], timeout: float, retries: int) -> str:
    if headers is None:
        headers = {}
    r = do_request(session, "GET", url, headers=headers, timeout=timeout,
                   retries=retries, rate_limiter=rate_limiter)
    r.raise_for_status()
    return r.text

def html_headers() -> Dict[str, str]:
    return {
        "User-Agent": DEFAULT_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": HTML_BASE,
    }

def html_parse_detail_links(soup: BeautifulSoup) -> List[str]:
    links = []
    for a in soup.select('#search-results a[href]'):
        href = a.get("href", "").strip()
        if DETAIL_PATH_RE.match(href):
            links.append(href)
    seen, out = set(), []
    for h in links:
        if h not in seen:
            seen.add(h); out.append(h)
    return out

def with_query_param(url: str, key: str, value: str) -> str:
    parts = urlsplit(url)
    qs = dict(parse_qsl(parts.query))
    qs[key] = value
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(qs), parts.fragment))

def ensure_en_path(u: str) -> str:
    parts = urlsplit(u)
    path = parts.path
    if "/en/search-jobs" in path:
        return u
    if "/search-jobs" in path:
        path = path.replace("/search-jobs", "/en/search-jobs")
    elif path == "" or path == "/":
        path = "/en/search-jobs"
    return urlunsplit((parts.scheme or "https", parts.netloc or "www.disneycareers.com", path, parts.query, parts.fragment))

def normalize_pager_href(start_url: str, href: str) -> Optional[str]:
    if not href:
        return None
    if href.startswith("http"):
        return ensure_en_path(href)
    if href.startswith("?") or href.startswith("&"):
        return with_query_param(start_url, "p", href.split("=")[-1])
    if "/search-jobs&p=" in href:
        page = href.split("&p=")[-1]
        base = ensure_en_path(start_url)
        return with_query_param(base, "p", page)
    if href.startswith("/search-jobs"):
        absu = urljoin(HTML_BASE, href)
        return ensure_en_path(absu)
    absu = urljoin(start_url, href)
    return ensure_en_path(absu)

def html_collect_pager_urls(soup: BeautifulSoup, start_url: str, debug: bool) -> List[str]:
    urls = []
    pager = soup.select_one("div.pagination-paging")
    if pager:
        for a in pager.select("a[href]"):
            fixed = normalize_pager_href(start_url, a.get("href", "").strip())
            if fixed:
                urls.append(fixed)
    for a in soup.select('a[rel="next"][href]'):
        fixed = normalize_pager_href(start_url, a["href"])
        if fixed:
            urls.append(fixed)
    seen, uniq = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u); uniq.append(u)
    if "p=" not in urlsplit(start_url).query:
        filtered = []
        for u in uniq:
            q = dict(parse_qsl(urlsplit(u).query))
            if q.get("p") == "1":
                continue
            filtered.append(u)
        uniq = filtered
    debug_print(debug, f"[HTML] pager URLs discovered (deduped): {len(uniq)}")
    for u in uniq:
        debug_print(debug, f"        pager -> {u}")
    return uniq

def text_or_none(el):
    return el.get_text(" ", strip=True) if el else None

def extract_labeled_value(soup: BeautifulSoup, label_regex, container_selector=None) -> Optional[str]:
    scopes = soup.select(container_selector) if container_selector else [soup]
    for scope in scopes:
        for lbl in scope.find_all(string=label_regex):
            parent = getattr(lbl, "parent", None)
            if not parent:
                continue
            sib = parent.find_next_sibling()
            if sib:
                val = text_or_none(sib)
                if val:
                    return val
            maybe_inline = parent.find_all(string=True)
            if len(maybe_inline) >= 2:
                candidate = (maybe_inline[-1] or "").strip()
                if candidate and not re.search(label_regex, candidate, flags=re.I):
                    return candidate
    return None

def html_parse_detail_page(html: str, url: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    title = text_or_none(soup.select_one("h1")) or (soup.select_one('meta[property="og:title"]') or {}).get("content")
    desc_div = soup.select_one("div.ats-description")
    description_html = str(desc_div) if desc_div else None
    job_id = extract_labeled_value(soup, re.compile(r"^\s*Job\s*ID\s*$", re.I))
    if not job_id:
        tail = urlparse(url).path.rstrip("/").split("/")[-1]
        if tail.isdigit():
            job_id = tail
    business = extract_labeled_value(soup, re.compile(r"^\s*Business\s*$", re.I))
    locations_raw = extract_labeled_value(soup, re.compile(r"^\s*Location\s*$", re.I))
    locations = [s.strip() for s in (locations_raw or "").split("/") if s.strip()] or None
    date_posted = extract_labeled_value(soup, re.compile(r"^\s*Date\s*$", re.I)) \
                  or extract_labeled_value(soup, re.compile(r"posted", re.I))
    return {
        "jobUrl": url,
        "jobName": title,
        "jobId": job_id,
        "business": business,
        "locations": locations,
        "datePosted": date_posted,
        "summaryHtml": description_html,
    }

def html_collect_urls(args, session, rate_limiter, timeout, retries) -> List[str]:
    seen_urls = set()
    # first page
    first_html = http_get(args.start_url, session, html_headers(), args.debug, rate_limiter, timeout, retries)
    soup = BeautifulSoup(first_html, "html.parser")
    page1_links = html_parse_detail_links(soup)
    debug_print(args.debug, f"[HTML] page1 detail links: {len(page1_links)}")
    for h in page1_links:
        seen_urls.add(urljoin(HTML_BASE, h))
        if args.max_items and len(seen_urls) >= args.max_items:
            break

    pager_urls = html_collect_pager_urls(soup, args.start_url, args.debug)
    if args.pages:
        pager_urls = pager_urls[: max(0, args.pages - 1)]

    for purl in pager_urls:
        if args.max_items and len(seen_urls) >= args.max_items:
            break
        try:
            html = http_get(purl, session, html_headers(), args.debug, rate_limiter, timeout, retries)
            psoup = BeautifulSoup(html, "html.parser")
            hrefs = html_parse_detail_links(psoup)
            debug_print(args.debug, f"[HTML] pager page detail links: {len(hrefs)}  ({purl})")
            for h in hrefs:
                seen_urls.add(urljoin(HTML_BASE, h))
                if args.max_items and len(seen_urls) >= args.max_items:
                    break
        except Exception as e:
            debug_print(args.debug, f"[HTML] pager fetch failed: {purl} ({e})")

    # Synthesize additional pages
    if args.pages and (not args.max_items or len(seen_urls) < args.max_items):
        approx_per_page = 10
        target_items = args.pages * approx_per_page
        hard_cap = args.max_items or float("inf")
        if len(seen_urls) < min(target_items, hard_cap):
            debug_print(args.debug, "[HTML] Synthesizing extra pages via ?p=2..N")
            crawled_pages = set(["1"])
            for u in pager_urls:
                q = dict(parse_qsl(urlsplit(u).query))
                pval = q.get("p")
                if pval:
                    crawled_pages.add(pval)
            for n in range(2, args.pages + 1):
                if str(n) in crawled_pages or len(seen_urls) >= hard_cap:
                    continue
                probe = ensure_en_path(with_query_param(args.start_url, "p", str(n)))
                try:
                    html = http_get(probe, session, html_headers(), args.debug, rate_limiter, timeout, retries)
                    psoup = BeautifulSoup(html, "html.parser")
                    hrefs = html_parse_detail_links(psoup)
                    before = len(seen_urls)
                    for h in hrefs:
                        seen_urls.add(urljoin(HTML_BASE, h))
                        if len(seen_urls) >= hard_cap:
                            break
                    after = len(seen_urls)
                    debug_print(args.debug, f"[HTML] synth {probe}: +{after-before} (now {after})")
                    if after == before:
                        break
                except Exception as e:
                    debug_print(args.debug, f"[HTML] synth failed: {probe} ({e})")
                    break

    urls = sorted(seen_urls)
    if args.max_items:
        urls = urls[: args.max_items]
    debug_print(args.debug, f"[HTML] collected {len(urls)} detail URLs")
    return urls

# =========================
# WORKDAY MODE (list + detail)
# =========================
def _wd_host_from_base(base: str) -> str:
    parts = urlsplit(base)
    scheme = parts.scheme or "https"
    return f"{scheme}://{parts.netloc}"

def _wd_referer_from_base(base: str) -> str:
    return f"{_wd_host_from_base(base)}/en-US/disneycareer"

def _xhrish_headers(base: str, browser_id: str) -> Dict[str, str]:
    origin = _wd_host_from_base(base)
    referer = _wd_referer_from_base(base)
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": origin,
        "Referer": referer,
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": DEFAULT_UA,
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "wd-browser-id": browser_id,
    }

def wd_warmup(session: requests.Session, base: str, debug: bool, rate_limiter: Optional[RateLimiter], timeout: float, retries: int, browser_id: str):
    # seed cookie
    host = urlsplit(base).netloc
    session.cookies.set("wd-browser-id", browser_id, domain=host, path="/")
    # referer page
    ref = _wd_referer_from_base(base)
    try:
        do_request(session, "GET", ref, headers={
            "User-Agent": DEFAULT_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }, timeout=timeout, retries=retries, rate_limiter=rate_limiter, debug=debug)
    except Exception as e:
        debug_print(debug, f"[WD] warm-up error (ignored): {e}")
    # prime list endpoint
    list_url = f"{base}{WD_LIST_ENDPOINT}"
    try:
        do_request(session, "GET", list_url, headers=_xhrish_headers(base, browser_id),
                   timeout=timeout, retries=retries, rate_limiter=rate_limiter, debug=debug)
    except Exception as e:
        debug_print(debug, f"[WD] prime error (ignored): {e}")

def wd_list_jobs(session: requests.Session,
                 base: str,
                 search_text: str,
                 applied_facets: Dict[str, Any],
                 limit: int,
                 max_pages: Optional[int],
                 rate_limiter: Optional[RateLimiter],
                 timeout: float,
                 retries: int,
                 debug: bool) -> List[Dict[str, Any]]:
    postings: List[Dict[str, Any]] = []
    offset = 0
    pages = 0
    browser_id = str(uuid.uuid4())
    wd_warmup(session, base, debug, rate_limiter, timeout, retries, browser_id)
    url = f"{base}{WD_LIST_ENDPOINT}"
    while True:
        payload = {"limit": limit, "offset": offset, "searchText": search_text, "appliedFacets": applied_facets or {}}
        r = do_request(session, "POST", url, headers=_xhrish_headers(base, browser_id),
                       json_body=payload, timeout=timeout, retries=retries, rate_limiter=rate_limiter, debug=debug)

        if r.status_code != 200:
            snippet = r.text[:300] if r.text else ""
            debug_print(debug, f"[WD] list non-200: {r.status_code}; body[:300]={snippet!r}")
            return postings

        data = r.json()
        page = data.get("jobPostings", []) or []
        postings.extend(page)

        offset += limit
        pages += 1
        total = data.get("total", None)

        if max_pages and pages >= max_pages:
            return postings
        if not page:
            return postings
        if total is not None and offset >= total:
            return postings

def wd_fetch_detail(session: requests.Session, base: str, job_id: str,
                    rate_limiter: Optional[RateLimiter], timeout: float, retries: int,
                    debug: bool, browser_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not job_id:
        return None
    if not browser_id:
        browser_id = str(uuid.uuid4())
        session.cookies.set("wd-browser-id", browser_id, domain=urlsplit(base).netloc, path="/")
    url = f"{base}{WD_DETAIL_ENDPOINT.format(job_id=job_id)}"
    r = do_request(session, "GET", url, headers=_xhrish_headers(base, browser_id),
                   timeout=timeout, retries=retries, rate_limiter=rate_limiter, debug=debug)
    if not r.ok:
        r = do_request(session, "POST", url, headers=_xhrish_headers(base, browser_id), json_body={},
                       timeout=timeout, retries=retries, rate_limiter=rate_limiter, debug=debug)
    if not r.ok:
        return None
    try:
        return r.json()
    except Exception:
        return None

def wd_get_nested(d: Dict[str, Any], path: List[str], default=None):
    cur = d
    for p in path:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return default
    return cur

def wd_normalize(list_item: Dict[str, Any], detail: Optional[Dict[str, Any]], base: str) -> Dict[str, Any]:
    internal_id = list_item.get("id")
    title = list_item.get("title") or list_item.get("jobName")
    bullet_fields = list_item.get("bulletFields") or []
    display_req_id = bullet_fields[0] if isinstance(bullet_fields, list) and bullet_fields else list_item.get("jobId")
    time_type = list_item.get("timeType")
    posted_on = list_item.get("postedOn") or list_item.get("datePosted")
    locations_text = list_item.get("locationsText") or ("/".join(list_item.get("locations") or []) if list_item.get("locations") else None)
    external_path = list_item.get("externalPath")
    # Build jobUrl for both cases
    if external_path:
        job_url = f"{_wd_host_from_base(base)}{external_path}"
    else:
        job_url = list_item.get("jobUrl")

    description_html = qualifications_html = job_family = brand = business_unit = locations_detail = None
    if detail:
        description_html = wd_get_nested(detail, ["jobPostingInfo", "jobDescription"])
        qualifications_html = wd_get_nested(detail, ["jobPostingInfo", "qualifications"])
        job_family = wd_get_nested(detail, ["jobPostingInfo", "jobFamily"])
        brand = wd_get_nested(detail, ["jobPostingInfo", "brand"])
        business_unit = wd_get_nested(detail, ["jobPostingInfo", "businessUnit"])
        locations_detail = wd_get_nested(detail, ["jobPostingInfo", "location"])

    return {
        "id": internal_id,
        "displayRequisitionId": display_req_id,
        "title": title,
        "timeType": time_type,
        "postedOn": posted_on,
        "locationsText": locations_text,
        "jobUrl": job_url,
        "externalPath": external_path,
        "detail": {
            "brand": brand,
            "businessUnit": business_unit,
            "jobFamily": job_family,
            "descriptionHtml": description_html,
            "qualificationsHtml": qualifications_html,
            "locations": locations_detail,
        }
    }

# =========================
# HYBRID MODE (HTML enumerate → Workday detail)
# =========================
def run_hybrid_mode(args) -> List[Dict[str, Any]]:
    base_session = build_session()
    rate_limiter = RateLimiter(args.rate)

    # 1) get detail URLs from HTML listing (sequential for pager safety)
    detail_urls = html_collect_urls(args, base_session, rate_limiter, args.timeout, args.retries)

    # 2) fetch HTML pages for visible fields + job IDs (concurrent)
    def fetch_html_job(url: str) -> Tuple[str, Dict[str, Any]]:
        try:
            html = http_get(url, base_session, html_headers(), args.debug, rate_limiter, args.timeout, args.retries)
            parsed = html_parse_detail_page(html, url)
            # fallback id from URL path if missing
            if not parsed.get("jobId"):
                m = JOB_ID_FROM_URL_RE.search(urlparse(url).path.rstrip("/"))
                if m:
                    parsed["jobId"] = m.group(1)
            return (url, parsed)
        except Exception as e:
            return (url, {"jobUrl": url, "error": str(e)})

    html_items: List[Dict[str, Any]] = []
    ids: List[Optional[str]] = []

    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = [ex.submit(fetch_html_job, u) for u in detail_urls]
        for fut in as_completed(futures):
            url, parsed = fut.result()
            html_items.append(parsed)
            jid = parsed.get("jobId")
            ids.append(str(jid) if jid and str(jid).isdigit() else None)

    # 3) Workday detail per id (concurrent)
    browser_id = str(uuid.uuid4())
    wd_warmup(base_session, args.base, args.debug, rate_limiter, args.timeout, args.retries, browser_id)

    def fetch_wd(jid: Optional[str]) -> Optional[Dict[str, Any]]:
        if not jid:
            return None
        return wd_fetch_detail(base_session, args.base, jid, rate_limiter, args.timeout, args.retries, args.debug, browser_id)

    details: List[Optional[Dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = [ex.submit(fetch_wd, jid) for jid in ids]
        for fut in as_completed(futures):
            details.append(fut.result())

    # Details order may differ; align by index using a dict
    # Since as_completed scrambles order, rebuild in original order with a simple map:
    # We'll re-run in-order fetch with limited concurrency to preserve order:
    details_in_order: List[Optional[Dict[str, Any]]] = []
    for jid in ids:
        details_in_order.append(fetch_wd(jid))

    # 4) Stitch/normalize
    enriched: List[Dict[str, Any]] = []
    for item, jid, det in zip(html_items, ids, details_in_order):
        stitched = {
            "id": jid,
            "jobName": item.get("jobName"),
            "title": item.get("jobName"),
            "jobId": item.get("jobId"),
            "displayRequisitionId": item.get("jobId"),
            "jobUrl": item.get("jobUrl"),
            "locations": item.get("locations"),
            "locationsText": "/".join(item.get("locations") or []) if item.get("locations") else None,
            "business": item.get("business"),
            "datePosted": item.get("datePosted"),
            "postedOn": item.get("datePosted"),
            "externalPath": None,
        }
        normalized = wd_normalize(stitched, det, args.base)
        if not normalized["detail"]["descriptionHtml"] and item.get("summaryHtml"):
            normalized["detail"]["descriptionHtml"] = item.get("summaryHtml")
        enriched.append(normalized)

    return enriched

# =========================
# Mode runners
# =========================
def run_html_mode(args) -> List[Dict[str, Any]]:
    session = build_session()
    rate_limiter = RateLimiter(args.rate)

    urls = html_collect_urls(args, session, rate_limiter, args.timeout, args.retries)

    # Concurrency for detail pages
    def fetch_one(u: str) -> Dict[str, Any]:
        try:
            html = http_get(u, session, html_headers(), args.debug, rate_limiter, args.timeout, args.retries)
            return html_parse_detail_page(html, u)
        except Exception as e:
            return {"jobUrl": u, "error": str(e)}

    jobs: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = [ex.submit(fetch_one, u) for u in urls]
        for fut in as_completed(futures):
            jobs.append(fut.result())

    return jobs

def run_workday_mode(args) -> List[Dict[str, Any]]:
    session = build_session()
    rate_limiter = RateLimiter(args.rate)

    applied_facets: Dict[str, Any] = {}
    for kv in (args.facet or []):
        if "=" in kv:
            k, v = kv.split("=", 1)
            applied_facets.setdefault(k, [])
            applied_facets[k].append(v)

    listings = wd_list_jobs(
        session=session,
        base=args.base,
        search_text=args.search or "",
        applied_facets=applied_facets,
        limit=args.limit,
        max_pages=args.max_pages,
        rate_limiter=rate_limiter,
        timeout=args.timeout,
        retries=args.retries,
        debug=args.debug,
    )

    if not listings:
        debug_print(args.debug, "[WD] listing returned 0; tenant likely gated. Use --mode hybrid.")
        return []

    # Fetch details concurrently if requested
    if args.details:
        browser_id = str(uuid.uuid4())
        wd_warmup(session, args.base, args.debug, rate_limiter, args.timeout, args.retries, browser_id)

        def fetch_one(item: Dict[str, Any]) -> Dict[str, Any]:
            jid = item.get("id")
            det = wd_fetch_detail(session, args.base, jid, rate_limiter, args.timeout, args.retries, args.debug, browser_id) if jid else None
            return wd_normalize(item, det, args.base)

        results: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futures = [ex.submit(fetch_one, it) for it in listings]
            for fut in as_completed(futures):
                results.append(fut.result())
        return results

    # No details: just normalize
    return [wd_normalize(it, None, args.base) for it in listings]

# =========================
# CLI
# =========================
def build_arg_parser():
    ap = argparse.ArgumentParser(description="Disney Careers scraper: --mode html | workday | hybrid")
    ap.add_argument("--mode", choices=["html", "workday", "hybrid"], required=True, help="Scrape via HTML, Workday API, or Hybrid")

    # Safety / networking
    ap.add_argument("--concurrency", type=int, default=4, help="Parallel workers for detail fetches (HTML & WD)")
    ap.add_argument("--rate", type=float, default=2.0, help="Global requests per second across all workers")
    ap.add_argument("--timeout", type=float, default=30.0, help="Per-request timeout (seconds)")
    ap.add_argument("--retries", type=int, default=2, help="Retries on 429/5xx (exponential backoff)")

    # Common outputs
    ap.add_argument("--out", default="disney_careers.json", help="Combined JSON output path")
    ap.add_argument("--per-job-dir", default=None, help="Also write one JSON per job into this directory")
    ap.add_argument("--ndjson", action="store_true", help="Output one job per line to stdout (NDJSON)")
    ap.add_argument("--debug", action="store_true", help="Verbose debug logs")
    ap.add_argument("--max-items", type=int, default=None, help="Safety cap: stop after about N jobs")
    ap.add_argument("--sanitize", action="store_true",
                    help="Normalize text & strip zero-widths/NBSP before writing output")

    # CSV
    ap.add_argument("--csv", dest="csv_path", default=None, help="Optional CSV output path")
    ap.add_argument("--csv-fields", default=",".join(DEFAULT_CSV_FIELDS),
                    help="Comma-separated field list for CSV; supports dotted paths (e.g., detail.brand)")

    # HTML / Hybrid
    ap.add_argument("--start-url", default=HTML_START_URL, help="[html/hybrid] Listing start URL")
    ap.add_argument("--pages", type=int, default=None, help="[html/hybrid] Max listing pages to fetch")

    # Workday
    ap.add_argument("--base", default=WD_DEFAULT_BASE, help="[workday/hybrid] Workday CXS base URL (no trailing slash)")
    ap.add_argument("--search", default="", help="[workday] Search text")
    ap.add_argument("--facet", action="append", default=None, help='[workday] Facet key=value (repeatable). Ex: --facet locations=country:us')
    ap.add_argument("--limit", type=int, default=50, help="[workday] List page size")
    ap.add_argument("--max-pages", type=int, default=None, help="[workday] Max list pages")
    ap.add_argument("--details", action="store_true", help="[workday] Fetch per-job detail/description")
    return ap

def main():
    ap = build_arg_parser()
    args = ap.parse_args()

    if args.mode == "html":
        jobs = run_html_mode(args)
    elif args.mode == "workday":
        jobs = run_workday_mode(args)
    else:
        jobs = run_hybrid_mode(args)

    if args.max_items:
        jobs = jobs[: args.max_items]

    if args.sanitize:
        jobs = _clean_obj(jobs, args.debug)

    write_outputs(jobs, combined_path=args.out, ndjson=args.ndjson, per_dir=args.per_job_dir)

    if args.csv_path:
        fields = [c.strip() for c in (args.csv_fields or "").split(",") if c.strip()]
        write_csv(jobs, args.csv_path, fields)

if __name__ == "__main__":
    main()