#!/usr/bin/env python3
"""
Probe ATS endpoints (Greenhouse, Lever, SmartRecruiters) for a list of company names.

Input file: plain text or CSV with one company name per line.
Output CSV: name_tested,greenhouse,lever,smartrecruiters,active_api

Usage:
  python ats_probe.py --in testlist.csv --out results.csv
"""

import argparse
import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple

import requests
from tqdm import tqdm

GH_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
LEVER_URL = "https://api.lever.co/v0/postings/{token}"
SR_URL = "https://api.smartrecruiters.com/v1/companies/{token}/postings"

HEADERS = {
    "User-Agent": "ATS-Probe/1.0",
    "Accept": "application/json, */*;q=0.8",
    "Connection": "close",
}

def read_companies(path: str) -> List[str]:
    """Read plain text or CSV file with one company name per line."""
    companies: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            name = line.strip()
            if name:
                companies.append(name)
    return companies

def request_with_retries(url: str, timeout: float, delay: float, max_retries: int = 2) -> Tuple[int, dict]:
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            status = resp.status_code
            data = {}
            if status == 200:
                try:
                    data = resp.json()
                except Exception:
                    data = {}
            time.sleep(delay)
            return status, data
        except Exception as e:
            last_exc = e
            time.sleep(min(delay * (attempt + 1), 2.0))
    raise last_exc

def check_greenhouse(token: str, timeout: float, delay: float) -> str:
    url = GH_URL.format(token=token)
    try:
        status, _ = request_with_retries(url, timeout=timeout, delay=delay)
        return "active" if status == 200 else "none"
    except Exception:
        return "none"

def check_lever(token: str, timeout: float, delay: float) -> str:
    url = LEVER_URL.format(token=token)
    try:
        status, _ = request_with_retries(url, timeout=timeout, delay=delay)
        return "active" if status == 200 else "none"
    except Exception:
        return "none"

def check_smartrecruiters(token: str, timeout: float, delay: float) -> str:
    url = SR_URL.format(token=token)
    try:
        status, data = request_with_retries(url, timeout=timeout, delay=delay)
        if status != 200:
            return "none"
        total_found = data.get("totalFound")
        return "active" if isinstance(total_found, int) and total_found > 0 else "none"
    except Exception:
        return "none"

def probe_company(name: str, timeout: float, delay: float) -> Dict[str, str]:
    token = name.strip()
    gh = check_greenhouse(token, timeout, delay)
    lv = check_lever(token, timeout, delay)
    sr = check_smartrecruiters(token, timeout, delay)

    active = "none"
    if gh == "active":
        active = "greenhouse"
    elif lv == "active":
        active = "lever"
    elif sr == "active":
        active = "smartrecruiters"

    return {
        "name_tested": name,
        "greenhouse": gh,
        "lever": lv,
        "smartrecruiters": sr,
        "active_api": active,
    }

def write_results(path: str, rows: List[Dict[str, str]]) -> None:
    fieldnames = ["name_tested", "greenhouse", "lever", "smartrecruiters", "active_api"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

def main():
    ap = argparse.ArgumentParser(description="Probe ATS endpoints for a list of company names.")
    ap.add_argument("--in", dest="input_file", required=True, help="Input file: one company name per line")
    ap.add_argument("--out", dest="output_csv", required=True, help="Output CSV path")
    ap.add_argument("--concurrency", type=int, default=6, help="Concurrent workers (default: 6)")
    ap.add_argument("--delay", type=float, default=0.15, help="Delay (s) between requests (default: 0.15)")
    ap.add_argument("--timeout", type=float, default=6.0, help="Request timeout (s)")
    args = ap.parse_args()

    companies = read_companies(args.input_file)
    if not companies:
        print("No company names found.", file=sys.stderr)
        sys.exit(1)

    results: List[Dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = {ex.submit(probe_company, name, args.timeout, args.delay): name for name in companies}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="Probing", unit="company"):
            try:
                results.append(fut.result())
            except Exception:
                results.append({
                    "name_tested": futures[fut],
                    "greenhouse": "none",
                    "lever": "none",
                    "smartrecruiters": "none",
                    "active_api": "none",
                })

    # Preserve input order
    order = {name: i for i, name in enumerate(companies)}
    results.sort(key=lambda r: order.get(r["name_tested"], 1e9))

    write_results(args.output_csv, results)
    print(f"Wrote {len(results)} results to {args.output_csv}")

if __name__ == "__main__":
    main()