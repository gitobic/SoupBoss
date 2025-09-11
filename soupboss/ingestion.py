"""
Job ingestion module for SoupBoss.

Integrates existing Greenhouse and Lever API fetchers into the unified system.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .db import SoupBossDB
from rich.console import Console
from rich.progress import Progress, TaskID

console = Console()


class GreenhouseAPI:
    """Client for interacting with Greenhouse.io job board API."""
    
    BASE_URL = "https://boards-api.greenhouse.io/v1/boards"
    
    def __init__(self, company: str):
        import requests
        self.company = company.lower()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'soupboss-greenhouse/1.0',
            'Accept': 'application/json'
        })
    
    def test_company(self) -> bool:
        """Test if company has an active Greenhouse job board."""
        try:
            import requests
            response = self.session.get(f"{self.BASE_URL}/{self.company}/jobs", params={'per_page': 1})
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def get_jobs(self, limit: Optional[int] = None) -> List[Dict]:
        """Fetch all job listings with pagination support."""
        import requests
        jobs = []
        page = 1
        per_page = 100
        
        while True:
            try:
                params = {'page': page, 'per_page': per_page}
                response = self.session.get(f"{self.BASE_URL}/{self.company}/jobs", params=params)
                response.raise_for_status()
                
                page_jobs = response.json().get('jobs', [])
                if not page_jobs:
                    break
                
                jobs.extend(page_jobs)
                
                if limit and len(jobs) >= limit:
                    jobs = jobs[:limit]
                    break
                
                page += 1
                
            except requests.RequestException as e:
                console.print(f"[red]Error fetching jobs page {page}: {e}[/red]")
                break
        
        return jobs
    
    def get_job_details(self, job_id: int) -> Optional[Dict]:
        """Fetch detailed information for a specific job."""
        try:
            import requests
            import html
            import html2text
            
            response = self.session.get(f"{self.BASE_URL}/{self.company}/jobs/{job_id}")
            response.raise_for_status()
            job_data = response.json()
            
            # Clean up the content field if it exists
            if 'content' in job_data and job_data['content']:
                # Decode HTML entities
                decoded_content = html.unescape(job_data['content'])
                
                # Convert HTML to readable text
                h = html2text.HTML2Text()
                h.ignore_links = False
                h.body_width = 0  # Don't wrap lines
                job_data['content_text'] = h.handle(decoded_content).strip()
                
                # Keep the original HTML content as well
                job_data['content_html'] = decoded_content
            
            return job_data
        except Exception as e:
            console.print(f"[red]Error fetching job details for {job_id}: {e}[/red]")
            return None


class LeverAPI:
    """Client for interacting with Lever.co job board API."""
    
    BASE_URL = "https://api.lever.co/v0/postings"
    
    def __init__(self, company: str):
        import requests
        self.company = company.lower()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'soupboss-lever/1.0',
            'Accept': 'application/json'
        })
    
    def test_company(self) -> bool:
        """Test if company has an active Lever job board."""
        try:
            import requests
            response = self.session.get(f"{self.BASE_URL}/{self.company}", params={'limit': 1, 'mode': 'json'})
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def get_jobs(self, limit: Optional[int] = None) -> List[Dict]:
        """Fetch all job listings with pagination support."""
        import requests
        jobs = []
        skip = 0
        per_page = 100
        
        while True:
            try:
                params = {'skip': skip, 'limit': per_page, 'mode': 'json'}
                response = self.session.get(f"{self.BASE_URL}/{self.company}", params=params)
                response.raise_for_status()
                
                page_jobs = response.json()
                if not page_jobs:
                    break
                
                jobs.extend(page_jobs)
                
                if limit and len(jobs) >= limit:
                    jobs = jobs[:limit]
                    break
                
                # If we got less than per_page, we've reached the end
                if len(page_jobs) < per_page:
                    break
                
                skip += per_page
                
            except requests.RequestException as e:
                console.print(f"[red]Error fetching jobs (skip={skip}): {e}[/red]")
                break
        
        return jobs
    
    def get_job_details(self, job_id: str) -> Optional[Dict]:
        """Fetch detailed information for a specific job."""
        try:
            import requests
            import html
            import html2text
            
            response = self.session.get(f"{self.BASE_URL}/{self.company}/{job_id}", params={'mode': 'json'})
            response.raise_for_status()
            job_data = response.json()
            
            # Clean up the description field if it exists
            if 'description' in job_data and job_data['description']:
                # Decode HTML entities
                decoded_content = html.unescape(job_data['description'])
                
                # Convert HTML to readable text
                h = html2text.HTML2Text()
                h.ignore_links = False
                h.body_width = 0  # Don't wrap lines
                job_data['description_text'] = h.handle(decoded_content).strip()
                
                # Keep the original HTML content as well
                job_data['description_html'] = decoded_content
            
            return job_data
        except Exception as e:
            console.print(f"[red]Error fetching job details for {job_id}: {e}[/red]")
            return None


class SmartRecruitersAPI:
    """Client for interacting with SmartRecruiters job board API."""
    
    BASE_URL = "https://api.smartrecruiters.com/v1/companies"
    
    def __init__(self, company: str):
        import requests
        self.company = company.lower()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'soupboss-smartrecruiters/1.0',
            'Accept': 'application/json'
        })
    
    def test_company(self) -> bool:
        """Test if company identifier can be queried via SmartRecruiters API."""
        try:
            import requests
            response = self.session.get(f"{self.BASE_URL}/{self.company}/postings", params={'limit': 1, 'offset': 0})
            if response.status_code == 200:
                data = response.json()
                return isinstance(data, dict) and 'totalFound' in data and 'content' in data
            return False
        except (requests.RequestException, ValueError):
            return False
    
    def get_jobs(self, limit: Optional[int] = None) -> List[Dict]:
        """Fetch all job listings with pagination support."""
        import requests
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
                console.print(f"[red]Error fetching jobs (offset={offset}): {e}[/red]")
                break
        
        return jobs
    
    def get_job_details(self, job_id: str) -> Optional[Dict]:
        """Fetch detailed information for a specific job."""
        try:
            import requests
            import html
            import html2text
            
            response = self.session.get(f"{self.BASE_URL}/{self.company}/postings/{job_id}")
            response.raise_for_status()
            job_data = response.json()
            
            # Clean up job description fields if they exist
            if 'jobAd' in job_data and 'sections' in job_data['jobAd']:
                sections = job_data['jobAd']['sections']
                
                # Collect all section text into consolidated fields
                all_html_parts = []
                all_text_parts = []
                
                # Process each section that contains HTML text
                for section_key, section_data in sections.items():
                    if isinstance(section_data, dict) and 'text' in section_data:
                        html_content = section_data['text']
                        if html_content:
                            # Decode HTML entities
                            decoded_content = html.unescape(html_content)
                            all_html_parts.append(decoded_content)
                            
                            # Convert HTML to readable text
                            h = html2text.HTML2Text()
                            h.ignore_links = False
                            h.body_width = 0  # Don't wrap lines
                            plain_text = h.handle(decoded_content).strip()
                            all_text_parts.append(plain_text)
                            
                            # Store individual section conversion
                            section_data['text_plain'] = plain_text
                            section_data['text_html'] = decoded_content
                
                # Add consolidated content fields for consistency with other APIs
                job_data['content_html'] = '\n\n'.join(all_html_parts)
                job_data['content_text'] = '\n\n'.join(all_text_parts)
            
            return job_data
        except Exception as e:
            console.print(f"[red]Error fetching job details for {job_id}: {e}[/red]")
            return None


class DisneyDataImporter:
    """Client for importing Disney job data from JSON files."""
    
    def __init__(self):
        import html2text
        self.h = html2text.HTML2Text()
        self.h.ignore_links = False
        self.h.body_width = 0  # Don't wrap lines
    
    def load_jobs_from_file(self, file_path: str) -> List[Dict]:
        """Load Disney job data from JSON file."""
        import json
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both direct job arrays and wrapped format
            if isinstance(data, dict) and 'jobs' in data:
                jobs = data['jobs']
            elif isinstance(data, list):
                jobs = data
            else:
                raise ValueError("Invalid JSON format: expected array of jobs or object with 'jobs' field")
            
            return jobs
            
        except Exception as e:
            console.print(f"[red]Error loading Disney data from {file_path}: {e}[/red]")
            return []
    
    def process_disney_job(self, job_data: Dict) -> Dict:
        """Process a Disney job record to standardized format."""
        # Extract basic fields
        job_id = str(job_data.get('jobId', ''))
        job_name = job_data.get('jobName', 'Unknown Job')
        job_url = job_data.get('jobUrl', '')
        business = job_data.get('business')
        locations = job_data.get('locations', [])
        summary_html = job_data.get('summaryHtml', '')
        
        # Process locations - extract meaningful location from complex data
        location_text = None
        if locations:
            if isinstance(locations, list) and locations:
                # Take the first location that's not the massive select string
                for loc in locations:
                    if isinstance(loc, str) and not loc.startswith("Select Location"):
                        parts = loc.split(',')
                        if parts and len(parts[0].strip()) < 50:
                            location_text = parts[0].strip()
                            break
            elif isinstance(locations, str) and not locations.startswith("Select Location"):
                parts = locations.split(',')
                if parts:
                    location_text = parts[0].strip()
        
        # Convert HTML description to plain text
        content_text = None
        if summary_html:
            try:
                content_text = self.h.handle(summary_html).strip()
            except Exception:
                content_text = summary_html  # Fallback to raw HTML
        
        # Extract department from HTML patterns if not in business field
        department = business
        if not department and summary_html:
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
            'raw_data': job_data
        }


class JobIngester:
    """Unified job ingestion interface for multiple sources."""
    
    def __init__(self, db: SoupBossDB):
        self.db = db
    
    def ingest_company_jobs(self, source: str, company: str, limit: Optional[int] = None) -> Tuple[int, int]:
        """
        Ingest jobs for a company from specified source.
        
        Returns:
            Tuple of (jobs_processed, jobs_saved)
        """
        # Add or get company in database
        company_id = self.db.add_company(company, source)
        
        # Initialize appropriate API client
        if source == "greenhouse":
            api = GreenhouseAPI(company)
        elif source == "lever":
            api = LeverAPI(company)
        elif source == "smartrecruiters":
            api = SmartRecruitersAPI(company)
        elif source == "disney":
            # Disney doesn't use traditional API, handle in import_from_file method
            console.print(f"[yellow]Disney source requires file import. Use import_from_file method instead.[/yellow]")
            return 0, 0
        else:
            raise ValueError(f"Unsupported source: {source}")
        
        # Test if company is reachable
        if not api.test_company():
            console.print(f"[red]Company '{company}' not found on {source} or unreachable[/red]")
            return 0, 0
        
        console.print(f"[green]Fetching jobs from {source} for {company}...[/green]")
        
        # Get job list
        jobs = api.get_jobs(limit=limit)
        if not jobs:
            console.print(f"[yellow]No jobs found for {company} on {source}[/yellow]")
            return 0, 0
        
        console.print(f"Found {len(jobs)} jobs, processing details...")
        
        jobs_processed = 0
        jobs_saved = 0
        
        with Progress() as progress:
            task = progress.add_task(f"Processing {company} jobs...", total=len(jobs))
            
            for job in jobs:
                progress.update(task, advance=1)
                jobs_processed += 1
                
                # Get detailed job information
                job_details = api.get_job_details(job['id'])
                if not job_details:
                    continue
                
                # Extract standardized fields based on source
                if source == "greenhouse":
                    job_data = self._extract_greenhouse_data(job_details)
                elif source == "lever":
                    job_data = self._extract_lever_data(job_details)
                else:  # smartrecruiters
                    job_data = self._extract_smartrecruiters_data(job_details)
                
                # Save to database
                try:
                    job_id = self.db.add_job(
                        external_id=str(job_data['external_id']),
                        company_id=company_id,
                        source=source,
                        title=job_data['title'],
                        department=job_data['department'],
                        location=job_data['location'],
                        content_html=job_data['content_html'],
                        content_text=job_data['content_text'],
                        raw_data=job_details
                    )
                    jobs_saved += 1
                except Exception as e:
                    console.print(f"[red]Error saving job {job_data['title']}: {e}[/red]")
        
        console.print(f"[green]Processed {jobs_processed} jobs, saved {jobs_saved} to database[/green]")
        return jobs_processed, jobs_saved
    
    def _extract_greenhouse_data(self, job_details: Dict) -> Dict:
        """Extract standardized data from Greenhouse job details."""
        return {
            'external_id': job_details['id'],
            'title': job_details.get('title', 'Unknown Title'),
            'department': job_details.get('departments', [{}])[0].get('name') if job_details.get('departments') else None,
            'location': job_details.get('location', {}).get('name') if job_details.get('location') else None,
            'content_html': job_details.get('content_html', job_details.get('content')),
            'content_text': job_details.get('content_text', job_details.get('content'))
        }
    
    def _extract_lever_data(self, job_details: Dict) -> Dict:
        """Extract standardized data from Lever job details."""
        categories = job_details.get('categories', {})
        location_data = job_details.get('location')
        location_str = None
        if location_data:
            location_str = location_data if isinstance(location_data, str) else location_data
        
        return {
            'external_id': job_details['id'],
            'title': job_details.get('text', 'Unknown Title'),
            'department': categories.get('team') if categories else None,
            'location': location_str,
            'content_html': job_details.get('description_html', job_details.get('description')),
            'content_text': job_details.get('description_text', job_details.get('description'))
        }
    
    def _extract_smartrecruiters_data(self, job_details: Dict) -> Dict:
        """Extract standardized data from SmartRecruiters job details."""
        # Extract department from function classification
        department = None
        if 'function' in job_details and job_details['function']:
            function_data = job_details['function']
            if isinstance(function_data, dict):
                department = function_data.get('label')
            elif isinstance(function_data, str):
                department = function_data
        
        # Extract location
        location = None
        if 'location' in job_details and job_details['location']:
            location_data = job_details['location']
            if isinstance(location_data, dict):
                # Try different location fields
                location = (location_data.get('city') or 
                           location_data.get('region') or 
                           location_data.get('country', {}).get('label'))
            elif isinstance(location_data, str):
                location = location_data
        
        return {
            'external_id': job_details['id'],
            'title': job_details.get('name', 'Unknown Title'),
            'department': department,
            'location': location,
            'content_html': job_details.get('content_html'),
            'content_text': job_details.get('content_text')
        }
    
    def ingest_from_file_list(self, source: str, filepath: str, limit: Optional[int] = None) -> Dict[str, Tuple[int, int]]:
        """
        Ingest jobs from a list of companies in a file.
        
        Returns:
            Dictionary mapping company names to (processed, saved) counts
        """
        companies = self._read_companies_file(filepath)
        results = {}
        
        console.print(f"[cyan]Processing {len(companies)} companies from {filepath}[/cyan]")
        
        for i, company in enumerate(companies, 1):
            console.print(f"\n[bold cyan][{i}/{len(companies)}] Processing {company}...[/bold cyan]")
            
            try:
                processed, saved = self.ingest_company_jobs(source, company, limit)
                results[company] = (processed, saved)
            except Exception as e:
                console.print(f"[red]Error processing {company}: {e}[/red]")
                results[company] = (0, 0)
        
        return results
    
    def import_from_file(self, source: str, company: str, file_path: str, limit: Optional[int] = None) -> Tuple[int, int]:
        """
        Import jobs from a data file for specific sources like Disney.
        
        Args:
            source: Data source type ("disney")
            company: Company identifier
            file_path: Path to data file
            limit: Optional limit on number of jobs to import
        
        Returns:
            Tuple of (jobs_processed, jobs_saved)
        """
        if source != "disney":
            raise ValueError(f"File import not supported for source: {source}")
        
        # Add or get company in database
        company_id = self.db.add_company(company, source)
        
        console.print(f"[green]Importing {source} jobs from {file_path}...[/green]")
        
        # Load and process Disney data
        disney_importer = DisneyDataImporter()
        jobs = disney_importer.load_jobs_from_file(file_path)
        
        if not jobs:
            console.print(f"[yellow]No jobs found in {file_path}[/yellow]")
            return 0, 0
        
        if limit:
            jobs = jobs[:limit]
        
        console.print(f"Processing {len(jobs)} Disney jobs...")
        
        jobs_processed = 0
        jobs_saved = 0
        
        with Progress() as progress:
            task = progress.add_task(f"Importing {company} jobs...", total=len(jobs))
            
            for job_data in jobs:
                progress.update(task, advance=1)
                jobs_processed += 1
                
                # Process Disney job data to standardized format
                job_info = disney_importer.process_disney_job(job_data)
                
                # Save to database
                try:
                    job_id = self.db.add_job(
                        external_id=job_info['external_id'],
                        company_id=company_id,
                        source=source,
                        title=job_info['title'],
                        department=job_info['department'],
                        location=job_info['location'],
                        content_html=job_info['content_html'],
                        content_text=job_info['content_text'],
                        raw_data=job_info['raw_data']
                    )
                    jobs_saved += 1
                except Exception as e:
                    console.print(f"[red]Error saving job {job_info['title']}: {e}[/red]")
        
        console.print(f"[green]Imported {jobs_processed} jobs, saved {jobs_saved} to database[/green]")
        return jobs_processed, jobs_saved
    
    def _read_companies_file(self, filepath: str) -> List[str]:
        """Read company names from input file."""
        companies = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    company = line.strip()
                    if company and not company.startswith('#'):
                        companies.append(company)
        except FileNotFoundError:
            console.print(f"[red]Error: Input file '{filepath}' not found.[/red]")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]Error reading input file: {e}[/red]")
            sys.exit(1)
        
        return companies


def get_ingester(db_path: str = "data/soupboss.db") -> JobIngester:
    """Get job ingester instance with database connection."""
    from .db import get_db
    db = get_db(db_path)
    return JobIngester(db)