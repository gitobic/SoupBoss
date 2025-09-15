#!/usr/bin/env python3
"""
SmartRecruiters API CLI Utility

A command-line tool to query SmartRecruiters job boards for job listings.

Usage Examples:
  # Test if a company has a SmartRecruiters job board
  python smartrecruiters_fetch.py -test dynatrace1

  # Fetch all jobs for a company (single combined JSON file)
  python smartrecruiters_fetch.py -fetch dynatrace1

  # Fetch jobs with a limit
  python smartrecruiters_fetch.py -fetch dynatrace1 -limit 10

  # Fetch jobs and split into separate files (one per job)
  python smartrecruiters_fetch.py -fetch dynatrace1 -split

  # Fetch jobs with custom output directory
  python smartrecruiters_fetch.py -fetch dynatrace1 -out ./output/

  # Combine split mode with output directory and limit
  python smartrecruiters_fetch.py -fetch dynatrace1 -limit 5 -split -out ./jobs/

  # Bulk process companies from a file
  python smartrecruiters_fetch.py -in companies.txt

  # Bulk process with split mode and custom output
  python smartrecruiters_fetch.py -in companies.txt -split -out ./bulk_output/

Output Formats:
  - Default: YYYY-MM-DD-HHMM-company.json (all jobs in one file)
  - Split mode: YYYY-MM-DD-HHMM-company-JobID.json (one file per job)
"""

import argparse
import html
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import html2text
import requests


class SmartRecruitersAPI:
    """Client for interacting with SmartRecruiters job board API."""
    
    BASE_URL = "https://api.smartrecruiters.com/v1/companies"
    
    def __init__(self, company: str):
        self.company = company.lower()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'smartrecruiters-api-cli/1.0',
            'Accept': 'application/json'
        })
    
    def test_company(self) -> bool:
        """Test if company identifier can be queried via SmartRecruiters API.
        Note: SmartRecruiters API returns the same response for non-existent companies
        and companies with no current jobs, so this tests API accessibility rather 
        than company existence."""
        try:
            response = self.session.get(f"{self.BASE_URL}/{self.company}/postings", params={'limit': 1, 'offset': 0})
            if response.status_code == 200:
                data = response.json()
                # Valid API response should have the expected JSON structure
                return isinstance(data, dict) and 'totalFound' in data and 'content' in data
            return False
        except (requests.RequestException, ValueError):
            return False
    
    def get_jobs(self, limit: Optional[int] = None) -> List[Dict]:
        """Fetch all job listings with pagination support."""
        jobs = []
        offset = 0
        per_page = 100
        
        while True:
            try:
                params = {'offset': offset, 'limit': per_page}
                response = self.session.get(f"{self.BASE_URL}/{self.company}/postings", params=params)
                response.raise_for_status()
                
                data = response.json()
                page_jobs = data.get('content', [])
                
                if not page_jobs:
                    break
                
                jobs.extend(page_jobs)
                
                if limit and len(jobs) >= limit:
                    jobs = jobs[:limit]
                    break
                
                # Check if we've reached the end based on pagination info
                total_found = data.get('totalFound', 0)
                if offset + per_page >= total_found:
                    break
                
                offset += per_page
                
            except requests.RequestException as e:
                print(f"Error fetching jobs (offset={offset}): {e}", file=sys.stderr)
                break
        
        return jobs
    
    def get_job_details(self, job_id: str) -> Optional[Dict]:
        """Fetch detailed information for a specific job."""
        try:
            response = self.session.get(f"{self.BASE_URL}/{self.company}/postings/{job_id}")
            response.raise_for_status()
            job_data = response.json()
            
            # Clean up job description fields if they exist
            if 'jobAd' in job_data and 'sections' in job_data['jobAd']:
                sections = job_data['jobAd']['sections']
                
                # Process each section that contains HTML text
                for section_key, section_data in sections.items():
                    if isinstance(section_data, dict) and 'text' in section_data:
                        html_content = section_data['text']
                        if html_content:
                            # Decode HTML entities
                            decoded_content = html.unescape(html_content)
                            
                            # Convert HTML to readable text
                            h = html2text.HTML2Text()
                            h.ignore_links = False
                            h.body_width = 0  # Don't wrap lines
                            section_data['text_plain'] = h.handle(decoded_content).strip()
                            
                            # Keep the original HTML content as well
                            section_data['text_html'] = decoded_content
            
            return job_data
        except requests.RequestException as e:
            print(f"Error fetching job details for {job_id}: {e}", file=sys.stderr)
            return None


def generate_filename(company: str, output_dir: Optional[str] = None) -> str:
    """Generate timestamped filename for job data."""
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    filename = f"{timestamp}-{company}.json"
    
    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return os.path.join(output_dir, filename)
    
    return filename


def generate_split_filename(company: str, job_id: str, output_dir: Optional[str] = None) -> str:
    """Generate timestamped filename for individual job data."""
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    filename = f"{timestamp}-{company}-{job_id}.json"
    
    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return os.path.join(output_dir, filename)
    
    return filename


def save_jobs_data(jobs: List[Dict], filename: str) -> None:
    """Save job data to JSON file."""
    data = {
        'timestamp': datetime.now().isoformat(),
        'total_jobs': len(jobs),
        'jobs': jobs
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Saved {len(jobs)} jobs to {filename}")


def save_job_data(job: Dict, filename: str) -> None:
    """Save individual job data to JSON file."""
    data = {
        'timestamp': datetime.now().isoformat(),
        'job': job
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def read_companies_file(filepath: str) -> List[str]:
    """Read company names from input file."""
    companies = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                company = line.strip()
                if company and not company.startswith('#'):
                    companies.append(company)
    except FileNotFoundError:
        print(f"Error: Input file '{filepath}' not found.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        sys.exit(1)
    
    return companies


def main():
    parser = argparse.ArgumentParser(
        description="Query SmartRecruiters job boards for job listings",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('-test', dest='test_company', metavar='COMPANY',
                       help='Test if company has an active SmartRecruiters job board')
    parser.add_argument('-fetch', dest='fetch_company', metavar='COMPANY',
                       help='Fetch all job listings for a company')
    parser.add_argument('-limit', type=int, metavar='NUMBER',
                       help='Limit the number of jobs fetched')
    parser.add_argument('-in', dest='input_file', metavar='FILEPATH',
                       help='File containing list of companies to process in bulk')
    parser.add_argument('-out', dest='output_dir', metavar='DIRECTORY',
                       help='Output directory for JSON files')
    parser.add_argument('-split', action='store_true',
                       help='Split jobs into separate JSON files (one per job)')
    
    args = parser.parse_args()
    
    if not any([args.test_company, args.fetch_company, args.input_file]):
        parser.print_help()
        sys.exit(1)
    
    if args.test_company:
        api = SmartRecruitersAPI(args.test_company)
        if api.test_company():
            print(f"✓ {args.test_company} has an active SmartRecruiters job board")
        else:
            print(f"✗ {args.test_company} does not have an active SmartRecruiters job board or is unreachable")
            sys.exit(1)
    
    elif args.fetch_company:
        api = SmartRecruitersAPI(args.fetch_company)
        
        if not api.test_company():
            print(f"Error: {args.fetch_company} does not have an active SmartRecruiters job board", file=sys.stderr)
            sys.exit(1)
        
        print(f"Fetching jobs for {args.fetch_company}...")
        jobs = api.get_jobs(limit=args.limit)
        
        if not jobs:
            print(f"No jobs found for {args.fetch_company}")
            return
        
        print(f"Found {len(jobs)} jobs, fetching detailed descriptions...")
        
        detailed_jobs = []
        for i, job in enumerate(jobs, 1):
            print(f"Processing job {i}/{len(jobs)}: {job.get('name', 'Unknown')}", end='\r')
            
            job_details = api.get_job_details(job['id'])
            if job_details:
                detailed_jobs.append(job_details)
                
                # If split mode, save each job individually
                if args.split:
                    split_filename = generate_split_filename(args.fetch_company, job_details['id'], args.output_dir)
                    save_job_data(job_details, split_filename)
        
        print(f"\nCompleted processing {len(detailed_jobs)} jobs")
        
        if args.split:
            print(f"Saved {len(detailed_jobs)} individual job files")
        else:
            filename = generate_filename(args.fetch_company, args.output_dir)
            save_jobs_data(detailed_jobs, filename)
    
    elif args.input_file:
        companies = read_companies_file(args.input_file)
        print(f"Processing {len(companies)} companies from {args.input_file}")
        
        for i, company in enumerate(companies, 1):
            print(f"\n[{i}/{len(companies)}] Processing {company}...")
            
            api = SmartRecruitersAPI(company)
            if not api.test_company():
                print(f"  ✗ {company} - No active job board or unreachable")
                continue
            
            print(f"  ✓ {company} - Fetching jobs...")
            jobs = api.get_jobs(limit=args.limit)
            
            if not jobs:
                print(f"  - No jobs found for {company}")
                continue
            
            print(f"  - Found {len(jobs)} jobs, fetching details...")
            
            detailed_jobs = []
            for job in jobs:
                job_details = api.get_job_details(job['id'])
                if job_details:
                    detailed_jobs.append(job_details)
                    
                    # If split mode, save each job individually
                    if args.split:
                        split_filename = generate_split_filename(company, job_details['id'], args.output_dir)
                        save_job_data(job_details, split_filename)
            
            if args.split:
                print(f"  - Saved {len(detailed_jobs)} individual job files")
            else:
                filename = generate_filename(company, args.output_dir)
                save_jobs_data(detailed_jobs, filename)
                print(f"  - Saved {len(detailed_jobs)} jobs")


if __name__ == "__main__":
    main()