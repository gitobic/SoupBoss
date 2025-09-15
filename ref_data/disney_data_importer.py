#!/usr/bin/env python3
"""
Disney Data Importer - Load Disney job data from JSON files

A utility to import Disney job data from scraped JSON files into JobGoblin.
This module provides a simple way to load pre-scraped Disney job data without
the complexity and maintenance overhead of a web scraper.

Usage Examples:
  # Import Disney jobs from JSON file
  python disney_data_importer.py -file disney_workday_html_100.json

  # Test file format without importing
  python disney_data_importer.py -test disney_workday_html_100.json

  # Show statistics about the data file
  python disney_data_importer.py -stats disney_workday_html_100.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import html2text


class DisneyDataImporter:
    """Importer for Disney job data from JSON files."""
    
    def __init__(self):
        self.h = html2text.HTML2Text()
        self.h.ignore_links = False
        self.h.body_width = 0  # Don't wrap lines
    
    def load_jobs_from_file(self, file_path: str) -> List[Dict]:
        """Load and parse Disney job data from JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both direct job arrays and wrapped format
            if isinstance(data, dict) and 'jobs' in data:
                jobs = data['jobs']
                metadata = data.get('metadata', {})
                print(f"Loaded {len(jobs)} jobs from file (metadata: {metadata.get('count', 'unknown')} total)")
            elif isinstance(data, list):
                jobs = data
                print(f"Loaded {len(jobs)} jobs from file")
            else:
                raise ValueError("Invalid JSON format: expected array of jobs or object with 'jobs' field")
            
            # Process each job to standardize format
            processed_jobs = []
            for job in jobs:
                processed_job = self._process_disney_job(job)
                processed_jobs.append(processed_job)
            
            return processed_jobs
            
        except FileNotFoundError:
            print(f"Error: File '{file_path}' not found.", file=sys.stderr)
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in '{file_path}': {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error loading Disney data: {e}", file=sys.stderr)
            sys.exit(1)
    
    def _process_disney_job(self, job_data: Dict) -> Dict:
        """Process a Disney job record to standardize format."""
        # Extract basic fields
        job_id = str(job_data.get('jobId', ''))
        job_name = job_data.get('jobName', 'Unknown Job')
        job_url = job_data.get('jobUrl', '')
        business = job_data.get('business')
        locations = job_data.get('locations', [])
        date_posted = job_data.get('datePosted')
        summary_html = job_data.get('summaryHtml', '')
        
        # Process locations - can be a list or a single long string
        location_text = None
        if locations:
            if isinstance(locations, list):
                # Filter out the massive "Select Location..." string and extract actual locations
                filtered_locations = []
                for loc in locations:
                    if isinstance(loc, str) and not loc.startswith("Select Location"):
                        # Split on common separators and take first meaningful location
                        parts = loc.split(',')
                        if parts:
                            clean_loc = parts[0].strip()
                            if clean_loc and len(clean_loc) < 50:  # Reasonable location name
                                filtered_locations.append(clean_loc)
                                break
                if filtered_locations:
                    location_text = filtered_locations[0]
            elif isinstance(locations, str) and not locations.startswith("Select Location"):
                parts = locations.split(',')
                if parts:
                    location_text = parts[0].strip()
        
        # Convert HTML description to plain text
        content_text = None
        if summary_html:
            try:
                content_text = self.h.handle(summary_html).strip()
            except Exception as e:
                print(f"Warning: Could not convert HTML to text for job {job_id}: {e}", file=sys.stderr)
                content_text = summary_html  # Fallback to raw HTML
        
        # Extract department/business unit from HTML if not in business field
        department = business
        if not department and summary_html:
            # Try to extract department from common HTML patterns
            if "Entertainment" in summary_html:
                department = "Entertainment"
            elif "Technology" in summary_html or "Engineering" in summary_html:
                department = "Technology"
            elif "Operations" in summary_html:
                department = "Operations"
            elif "Marketing" in summary_html:
                department = "Marketing"
        
        return {
            'external_id': job_id,
            'title': job_name,
            'department': department,
            'location': location_text,
            'content_html': summary_html,
            'content_text': content_text,
            'job_url': job_url,
            'date_posted': date_posted,
            'raw_data': job_data
        }
    
    def test_file_format(self, file_path: str) -> bool:
        """Test if file format is valid Disney JSON without processing."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict) and 'jobs' in data:
                jobs = data['jobs']
                metadata = data.get('metadata', {})
                print(f"✓ Valid Disney JSON format with {len(jobs)} jobs (metadata: {metadata})")
            elif isinstance(data, list):
                print(f"✓ Valid Disney JSON format with {len(data)} jobs")
            else:
                print("✗ Invalid format: expected array of jobs or object with 'jobs' field")
                return False
            
            # Test first job structure
            test_jobs = jobs if isinstance(data, dict) else data
            if test_jobs:
                first_job = test_jobs[0]
                required_fields = ['jobId', 'jobName', 'jobUrl']
                missing_fields = [field for field in required_fields if field not in first_job]
                if missing_fields:
                    print(f"✗ Missing required fields in first job: {missing_fields}")
                    return False
                print(f"✓ First job has required fields: {', '.join(required_fields)}")
            
            return True
            
        except Exception as e:
            print(f"✗ Error testing file: {e}")
            return False
    
    def show_file_stats(self, file_path: str):
        """Show statistics about the Disney data file."""
        try:
            jobs = self.load_jobs_from_file(file_path)
            
            print(f"\n=== Disney Data File Statistics ===")
            print(f"Total jobs: {len(jobs)}")
            
            # Count jobs by department
            departments = {}
            locations = {}
            for job in jobs:
                dept = job.get('department') or 'Unknown'
                departments[dept] = departments.get(dept, 0) + 1
                
                loc = job.get('location') or 'Unknown'
                locations[loc] = locations.get(loc, 0) + 1
            
            print(f"\nTop departments:")
            sorted_depts = sorted(departments.items(), key=lambda x: x[1], reverse=True)[:10]
            for dept, count in sorted_depts:
                print(f"  {dept}: {count}")
            
            print(f"\nTop locations:")
            sorted_locs = sorted(locations.items(), key=lambda x: x[1], reverse=True)[:10]
            for loc, count in sorted_locs:
                print(f"  {loc}: {count}")
            
            # Sample job titles
            print(f"\nSample job titles:")
            for i, job in enumerate(jobs[:5]):
                print(f"  {i+1}. {job.get('title', 'Unknown')}")
            
        except Exception as e:
            print(f"Error generating stats: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Import Disney job data from JSON files",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('-file', dest='import_file', metavar='FILEPATH',
                       help='Disney JSON file to import')
    parser.add_argument('-test', dest='test_file', metavar='FILEPATH',
                       help='Test if file format is valid Disney JSON')
    parser.add_argument('-stats', dest='stats_file', metavar='FILEPATH',
                       help='Show statistics about Disney data file')
    
    args = parser.parse_args()
    
    if not any([args.import_file, args.test_file, args.stats_file]):
        parser.print_help()
        sys.exit(1)
    
    importer = DisneyDataImporter()
    
    if args.test_file:
        if importer.test_file_format(args.test_file):
            print("File format test passed!")
            sys.exit(0)
        else:
            print("File format test failed!")
            sys.exit(1)
    
    elif args.stats_file:
        importer.show_file_stats(args.stats_file)
    
    elif args.import_file:
        print(f"Loading Disney jobs from {args.import_file}...")
        jobs = importer.load_jobs_from_file(args.import_file)
        
        print(f"\nProcessed {len(jobs)} Disney jobs")
        print("To import into JobGoblin, use:")
        print(f"  uv run python main.py jobs import --source disney --file {args.import_file}")


if __name__ == "__main__":
    main()