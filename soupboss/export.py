"""
Export functionality for SoupBoss - generate reports in CSV, JSON, and HTML formats.

Handles exporting match results, job listings, resume data, and summary reports.
"""

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
from dataclasses import asdict

from .db import SoupBossDB
from .matching import MatchResult, get_intelligence_engine
from rich.console import Console

console = Console()


class ExportManager:
    """Handles data export in multiple formats."""
    
    def __init__(self, db: SoupBossDB):
        self.db = db
    
    def export_match_results(self, 
                           format: str, 
                           output_path: Optional[str] = None,
                           resume_id: Optional[int] = None,
                           limit: Optional[int] = None) -> str:
        """
        Export match results in specified format.
        
        Args:
            format: Export format ('csv', 'json', 'html')
            output_path: Custom output file path
            resume_id: Filter by specific resume ID
            limit: Limit number of results
            
        Returns:
            Path to generated file
        """
        # Get match results
        if resume_id:
            results = self._get_resume_matches(resume_id, limit or 50)
        else:
            results = self._get_all_match_results(limit or 100)
        
        if not results:
            console.print("[yellow]No match results found to export[/yellow]")
            return ""
        
        # Generate filename if not provided
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            resume_suffix = f"_resume_{resume_id}" if resume_id else ""
            output_path = f"soupboss_matches{resume_suffix}_{timestamp}.{format}"
        
        # Ensure output directory exists
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Export based on format
        if format == 'csv':
            return self._export_matches_csv(results, str(output_file))
        elif format == 'json':
            return self._export_matches_json(results, str(output_file))
        elif format == 'html':
            return self._export_matches_html(results, str(output_file))
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def export_jobs(self, 
                    format: str,
                    output_path: Optional[str] = None,
                    company_id: Optional[int] = None,
                    source: Optional[str] = None) -> str:
        """Export job listings in specified format."""
        jobs = self.db.get_jobs(company_id=company_id, source=source)
        
        if not jobs:
            console.print("[yellow]No jobs found to export[/yellow]")
            return ""
        
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"soupboss_jobs_{timestamp}.{format}"
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        if format == 'csv':
            return self._export_jobs_csv(jobs, str(output_file))
        elif format == 'json':
            return self._export_jobs_json(jobs, str(output_file))
        elif format == 'html':
            return self._export_jobs_html(jobs, str(output_file))
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def export_resumes(self, 
                      format: str,
                      output_path: Optional[str] = None) -> str:
        """Export resume listings in specified format."""
        resumes = self.db.get_resumes()
        
        if not resumes:
            console.print("[yellow]No resumes found to export[/yellow]")
            return ""
        
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"soupboss_resumes_{timestamp}.{format}"
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        if format == 'csv':
            return self._export_resumes_csv(resumes, str(output_file))
        elif format == 'json':
            return self._export_resumes_json(resumes, str(output_file))
        elif format == 'html':
            return self._export_resumes_html(resumes, str(output_file))
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def generate_summary_report(self, 
                               format: str = 'html',
                               output_path: Optional[str] = None) -> str:
        """Generate comprehensive summary report."""
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"soupboss_summary_report_{timestamp}.{format}"
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Gather summary data
        summary_data = self._get_summary_data()
        
        if format == 'html':
            return self._generate_summary_html(summary_data, str(output_file))
        elif format == 'json':
            return self._generate_summary_json(summary_data, str(output_file))
        else:
            raise ValueError("Summary reports only support HTML and JSON formats")
    
    def _get_resume_matches(self, resume_id: int, limit: int) -> List[Dict]:
        """Get match results for specific resume."""
        engine = get_intelligence_engine()
        match_results = engine.get_resume_matches(resume_id, limit)
        
        # Convert to dict format
        results = []
        for match in match_results:
            results.append({
                'resume_id': match.resume_id,
                'resume_name': match.resume_name,
                'job_id': match.job_id,
                'job_title': match.job_title,
                'company_name': match.company_name,
                'department': match.job_department,
                'location': match.job_location,
                'similarity_score': round(match.similarity_score, 4),
                'adjusted_score': round(match.adjusted_score, 4) if match.adjusted_score else None
            })
        
        return results
    
    def _get_all_match_results(self, limit: int) -> List[Dict]:
        """Get all match results."""
        cursor = self.db.conn.cursor()
        
        query = """
            SELECT 
                mr.resume_id, r.name as resume_name,
                mr.job_id, j.title as job_title, j.department, j.location,
                c.name as company_name,
                mr.similarity_score, mr.adjusted_score
            FROM match_results mr
            JOIN resumes r ON mr.resume_id = r.id
            JOIN jobs j ON mr.job_id = j.id
            JOIN companies c ON j.company_id = c.id
            ORDER BY mr.similarity_score DESC
            LIMIT ?
        """
        
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            results.append({
                'resume_id': row['resume_id'],
                'resume_name': row['resume_name'],
                'job_id': row['job_id'],
                'job_title': row['job_title'],
                'company_name': row['company_name'],
                'department': row['department'],
                'location': row['location'],
                'similarity_score': round(row['similarity_score'], 4),
                'adjusted_score': round(row['adjusted_score'], 4) if row['adjusted_score'] else None
            })
        
        return results
    
    def _export_matches_csv(self, results: List[Dict], output_path: str) -> str:
        """Export match results to CSV."""
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            if not results:
                return output_path
            
            fieldnames = [
                'resume_id', 'resume_name', 'job_id', 'job_title', 
                'company_name', 'department', 'location', 
                'similarity_score', 'adjusted_score'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                writer.writerow(result)
        
        console.print(f"[green]Exported {len(results)} match results to {output_path}[/green]")
        return output_path
    
    def _export_matches_json(self, results: List[Dict], output_path: str) -> str:
        """Export match results to JSON."""
        export_data = {
            'generated_at': datetime.now().isoformat(),
            'total_matches': len(results),
            'matches': results
        }
        
        with open(output_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(export_data, jsonfile, indent=2, ensure_ascii=False)
        
        console.print(f"[green]Exported {len(results)} match results to {output_path}[/green]")
        return output_path
    
    def _export_matches_html(self, results: List[Dict], output_path: str) -> str:
        """Export match results to HTML."""
        html_content = self._generate_matches_html_content(results)
        
        with open(output_path, 'w', encoding='utf-8') as htmlfile:
            htmlfile.write(html_content)
        
        console.print(f"[green]Exported {len(results)} match results to {output_path}[/green]")
        return output_path
    
    def _generate_matches_html_content(self, results: List[Dict]) -> str:
        """Generate HTML content for match results."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>SoupBoss Match Results</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .stats {{ background: #f5f5f5; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .score {{ font-weight: bold; }}
        .high-score {{ color: #2e7d32; }}
        .medium-score {{ color: #f57c00; }}
        .low-score {{ color: #d32f2f; }}
        .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>SoupBoss Match Results</h1>
        <p>Generated on {timestamp}</p>
    </div>
    
    <div class="stats">
        <strong>Total Matches:</strong> {len(results)}
    </div>
    
    <table>
        <thead>
            <tr>
                <th>Rank</th>
                <th>Score</th>
                <th>Resume</th>
                <th>Job Title</th>
                <th>Company</th>
                <th>Department</th>
                <th>Location</th>
            </tr>
        </thead>
        <tbody>
"""
        
        for i, result in enumerate(results, 1):
            score = result['similarity_score']
            score_class = ('high-score' if score >= 0.6 else 
                          'medium-score' if score >= 0.4 else 'low-score')
            
            html += f"""
            <tr>
                <td>{i}</td>
                <td class="score {score_class}">{score:.3f}</td>
                <td>{self._html_escape(result['resume_name'])}</td>
                <td>{self._html_escape(result['job_title'])}</td>
                <td>{self._html_escape(result['company_name'])}</td>
                <td>{self._html_escape(result['department'] or 'N/A')}</td>
                <td>{self._html_escape(result['location'] or 'N/A')}</td>
            </tr>
"""
        
        html += """
        </tbody>
    </table>
    
    <div class="footer">
        <p>🤖 Generated with <a href="https://claude.ai/code">Claude Code</a> | SoupBoss Intelligence Engine</p>
    </div>
</body>
</html>
"""
        return html
    
    def _export_jobs_csv(self, jobs: List[Dict], output_path: str) -> str:
        """Export jobs to CSV."""
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            if not jobs:
                return output_path
            
            fieldnames = [
                'id', 'external_id', 'company_name', 'source', 'title', 
                'department', 'location', 'created_at'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for job in jobs:
                row = {
                    'id': job['id'],
                    'external_id': job['external_id'],
                    'company_name': job['company_name'],
                    'source': job['source'],
                    'title': job['title'],
                    'department': job.get('department', ''),
                    'location': job.get('location', ''),
                    'created_at': job['created_at']
                }
                writer.writerow(row)
        
        console.print(f"[green]Exported {len(jobs)} jobs to {output_path}[/green]")
        return output_path
    
    def _export_jobs_json(self, jobs: List[Dict], output_path: str) -> str:
        """Export jobs to JSON."""
        export_data = {
            'generated_at': datetime.now().isoformat(),
            'total_jobs': len(jobs),
            'jobs': jobs
        }
        
        with open(output_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(export_data, jsonfile, indent=2, ensure_ascii=False)
        
        console.print(f"[green]Exported {len(jobs)} jobs to {output_path}[/green]")
        return output_path
    
    def _export_jobs_html(self, jobs: List[Dict], output_path: str) -> str:
        """Export jobs to HTML."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>SoupBoss Job Listings</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #2196F3; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .source {{ font-weight: bold; text-transform: capitalize; }}
        .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>SoupBoss Job Listings</h1>
        <p>Generated on {timestamp}</p>
        <p><strong>Total Jobs:</strong> {len(jobs)}</p>
    </div>
    
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Title</th>
                <th>Company</th>
                <th>Department</th>
                <th>Location</th>
                <th>Source</th>
                <th>Added</th>
            </tr>
        </thead>
        <tbody>
"""
        
        for job in jobs:
            html += f"""
            <tr>
                <td>{job['id']}</td>
                <td>{self._html_escape(job['title'])}</td>
                <td>{self._html_escape(job['company_name'])}</td>
                <td>{self._html_escape(job.get('department', 'N/A'))}</td>
                <td>{self._html_escape(job.get('location', 'N/A'))}</td>
                <td class="source">{job['source']}</td>
                <td>{job['created_at'][:10]}</td>
            </tr>
"""
        
        html += """
        </tbody>
    </table>
    
    <div class="footer">
        <p>🤖 Generated with <a href="https://claude.ai/code">Claude Code</a> | SoupBoss</p>
    </div>
</body>
</html>
"""
        
        with open(output_path, 'w', encoding='utf-8') as htmlfile:
            htmlfile.write(html)
        
        console.print(f"[green]Exported {len(jobs)} jobs to {output_path}[/green]")
        return output_path
    
    def _export_resumes_csv(self, resumes: List[Dict], output_path: str) -> str:
        """Export resumes to CSV."""
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            if not resumes:
                return output_path
            
            fieldnames = [
                'id', 'name', 'file_type', 'file_size', 'created_at'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for resume in resumes:
                row = {
                    'id': resume['id'],
                    'name': resume['name'],
                    'file_type': resume['file_type'],
                    'file_size': resume['file_size'],
                    'created_at': resume['created_at']
                }
                writer.writerow(row)
        
        console.print(f"[green]Exported {len(resumes)} resumes to {output_path}[/green]")
        return output_path
    
    def _export_resumes_json(self, resumes: List[Dict], output_path: str) -> str:
        """Export resumes to JSON."""
        # Remove content_text for JSON export to keep file size manageable
        export_resumes = []
        for resume in resumes:
            resume_copy = resume.copy()
            resume_copy.pop('content_text', None)
            export_resumes.append(resume_copy)
        
        export_data = {
            'generated_at': datetime.now().isoformat(),
            'total_resumes': len(resumes),
            'resumes': export_resumes
        }
        
        with open(output_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(export_data, jsonfile, indent=2, ensure_ascii=False)
        
        console.print(f"[green]Exported {len(resumes)} resumes to {output_path}[/green]")
        return output_path
    
    def _export_resumes_html(self, resumes: List[Dict], output_path: str) -> str:
        """Export resumes to HTML."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>SoupBoss Resume Collection</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #FF9800; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .file-type {{ font-weight: bold; text-transform: uppercase; }}
        .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>SoupBoss Resume Collection</h1>
        <p>Generated on {timestamp}</p>
        <p><strong>Total Resumes:</strong> {len(resumes)}</p>
    </div>
    
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Type</th>
                <th>Size (KB)</th>
                <th>Added</th>
            </tr>
        </thead>
        <tbody>
"""
        
        for resume in resumes:
            size_kb = round(resume['file_size'] / 1024, 1)
            html += f"""
            <tr>
                <td>{resume['id']}</td>
                <td>{self._html_escape(resume['name'])}</td>
                <td class="file-type">{resume['file_type']}</td>
                <td>{size_kb}</td>
                <td>{resume['created_at'][:10]}</td>
            </tr>
"""
        
        html += """
        </tbody>
    </table>
    
    <div class="footer">
        <p>🤖 Generated with <a href="https://claude.ai/code">Claude Code</a> | SoupBoss</p>
    </div>
</body>
</html>
"""
        
        with open(output_path, 'w', encoding='utf-8') as htmlfile:
            htmlfile.write(html)
        
        console.print(f"[green]Exported {len(resumes)} resumes to {output_path}[/green]")
        return output_path
    
    def _get_summary_data(self) -> Dict:
        """Get comprehensive summary data."""
        # Get basic counts
        job_count = self.db.get_job_count()
        resume_count = self.db.get_resume_count()
        companies = self.db.get_companies()
        
        # Get embedding stats
        engine = get_intelligence_engine()
        embedding_stats = engine.get_embedding_stats()
        
        # Get match results count
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM match_results")
        match_count = cursor.fetchone()["total"]
        
        # Get top matches
        top_matches = self._get_all_match_results(10)
        
        return {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'companies': len(companies),
                'jobs': job_count,
                'resumes': resume_count,
                'match_results': match_count
            },
            'companies_list': companies,
            'embedding_stats': embedding_stats,
            'top_matches': top_matches
        }
    
    def _generate_summary_html(self, data: Dict, output_path: str) -> str:
        """Generate HTML summary report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>SoupBoss Summary Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; line-height: 1.6; }}
        .header {{ text-align: center; margin-bottom: 40px; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 40px; }}
        .summary-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }}
        .summary-card h3 {{ margin: 0 0 10px 0; color: #333; }}
        .summary-card .number {{ font-size: 2em; font-weight: bold; color: #4CAF50; }}
        .section {{ margin-bottom: 40px; }}
        .section h2 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .score {{ font-weight: bold; }}
        .high-score {{ color: #2e7d32; }}
        .medium-score {{ color: #f57c00; }}
        .low-score {{ color: #d32f2f; }}
        .footer {{ text-align: center; margin-top: 50px; color: #666; font-size: 0.9em; }}
        .company-badge {{ display: inline-block; background: #e3f2fd; padding: 4px 8px; border-radius: 4px; margin: 2px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>SoupBoss Summary Report</h1>
        <p>Generated on {timestamp}</p>
    </div>
    
    <div class="summary-grid">
        <div class="summary-card">
            <h3>Companies</h3>
            <div class="number">{data['summary']['companies']}</div>
        </div>
        <div class="summary-card">
            <h3>Jobs</h3>
            <div class="number">{data['summary']['jobs']}</div>
        </div>
        <div class="summary-card">
            <h3>Resumes</h3>
            <div class="number">{data['summary']['resumes']}</div>
        </div>
        <div class="summary-card">
            <h3>Matches</h3>
            <div class="number">{data['summary']['match_results']}</div>
        </div>
    </div>
    
    <div class="section">
        <h2>Companies</h2>
        <div>
"""
        
        # Add company list
        for company in data['companies_list']:
            html += f'<span class="company-badge">{self._html_escape(company["name"])} ({company["source"]})</span>'
        
        html += """
        </div>
    </div>
    
    <div class="section">
        <h2>Embedding Coverage</h2>
        <table>
            <thead>
                <tr><th>Type</th><th>Total</th><th>With Embeddings</th><th>Coverage</th></tr>
            </thead>
            <tbody>
"""
        
        # Add embedding stats
        stats = data['embedding_stats']
        html += f"""
                <tr>
                    <td>Jobs</td>
                    <td>{stats['jobs']['total']}</td>
                    <td>{stats['jobs']['with_embeddings']}</td>
                    <td>{stats['jobs']['coverage_percent']}%</td>
                </tr>
                <tr>
                    <td>Resumes</td>
                    <td>{stats['resumes']['total']}</td>
                    <td>{stats['resumes']['with_embeddings']}</td>
                    <td>{stats['resumes']['coverage_percent']}%</td>
                </tr>
"""
        
        html += """
            </tbody>
        </table>
    </div>
    
    <div class="section">
        <h2>Top 10 Matches</h2>
        <table>
            <thead>
                <tr><th>Rank</th><th>Score</th><th>Resume</th><th>Job</th><th>Company</th></tr>
            </thead>
            <tbody>
"""
        
        # Add top matches
        for i, match in enumerate(data['top_matches'][:10], 1):
            score = match['similarity_score']
            score_class = ('high-score' if score >= 0.6 else 
                          'medium-score' if score >= 0.4 else 'low-score')
            html += f"""
                <tr>
                    <td>{i}</td>
                    <td class="score {score_class}">{score:.3f}</td>
                    <td>{self._html_escape(match['resume_name'])}</td>
                    <td>{self._html_escape(match['job_title'])}</td>
                    <td>{self._html_escape(match['company_name'])}</td>
                </tr>
"""
        
        html += """
            </tbody>
        </table>
    </div>
    
    <div class="footer">
        <p>🤖 Generated with <a href="https://claude.ai/code">Claude Code</a> | SoupBoss Intelligence Engine</p>
    </div>
</body>
</html>
"""
        
        with open(output_path, 'w', encoding='utf-8') as htmlfile:
            htmlfile.write(html)
        
        console.print(f"[green]Generated summary report: {output_path}[/green]")
        return output_path
    
    def _generate_summary_json(self, data: Dict, output_path: str) -> str:
        """Generate JSON summary report."""
        with open(output_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(data, jsonfile, indent=2, ensure_ascii=False)
        
        console.print(f"[green]Generated summary report: {output_path}[/green]")
        return output_path
    
    def _html_escape(self, text: str) -> str:
        """Basic HTML escaping."""
        if not text:
            return ""
        return (str(text)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#x27;"))


def get_export_manager(db_path: str = "data/soupboss.db") -> ExportManager:
    """Get export manager instance."""
    from .db import get_db
    db = get_db(db_path)
    return ExportManager(db)