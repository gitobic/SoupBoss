"""
Data maintenance and cleanup functionality for SoupBoss.

This module provides comprehensive data management tools including:
- Selective data clearing (jobs, resumes, embeddings)
- Full system reset functionality
- Data cleanup utilities
- Statistics and validation
"""

import sqlite3
import shutil
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm

from .db import SoupBossDB


class DataManager:
    """Manages data cleanup, reset, and maintenance operations."""
    
    def __init__(self, db_path: str = "data/soupboss.db"):
        self.db_path = db_path
        self.db_manager = SoupBossDB(db_path)
        self.console = Console()
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Count all data
                stats = {}
                
                # Companies
                cursor.execute("SELECT COUNT(*) FROM companies")
                stats['companies'] = cursor.fetchone()[0]
                
                # Jobs
                cursor.execute("SELECT COUNT(*) FROM jobs")
                stats['jobs'] = cursor.fetchone()[0]
                
                # Resumes
                cursor.execute("SELECT COUNT(*) FROM resumes")
                stats['resumes'] = cursor.fetchone()[0]
                
                # Job embeddings
                cursor.execute("SELECT COUNT(*) FROM job_embeddings")
                stats['job_embeddings'] = cursor.fetchone()[0]
                
                # Resume embeddings
                cursor.execute("SELECT COUNT(*) FROM resume_embeddings")
                stats['resume_embeddings'] = cursor.fetchone()[0]
                
                # Total embeddings
                stats['embeddings'] = stats['job_embeddings'] + stats['resume_embeddings']
                
                # Match results
                cursor.execute("SELECT COUNT(*) FROM match_results")
                stats['match_results'] = cursor.fetchone()[0]
                
                # Database file size
                if os.path.exists(self.db_path):
                    stats['db_size_mb'] = round(os.path.getsize(self.db_path) / (1024 * 1024), 2)
                else:
                    stats['db_size_mb'] = 0
                
                return stats
                
        except sqlite3.Error as e:
            self.console.print(f"[red]Database error getting stats: {e}[/red]")
            return {}
    
    def display_system_stats(self):
        """Display current system statistics in a formatted table."""
        stats = self.get_system_stats()
        
        if not stats:
            self.console.print("[red]Unable to retrieve system statistics[/red]")
            return
        
        table = Table(title="SoupBoss System Statistics")
        table.add_column("Category", style="cyan")
        table.add_column("Count", style="green")
        
        table.add_row("Companies", str(stats['companies']))
        table.add_row("Jobs", str(stats['jobs']))
        table.add_row("Resumes", str(stats['resumes']))
        table.add_row("Total Embeddings", str(stats['embeddings']))
        table.add_row("  ├─ Job Embeddings", str(stats['job_embeddings']))
        table.add_row("  └─ Resume Embeddings", str(stats['resume_embeddings']))
        table.add_row("Match Results", str(stats['match_results']))
        table.add_row("Database Size", f"{stats['db_size_mb']} MB")
        
        self.console.print(table)
    
    def clear_jobs_data(self, confirm: bool = True) -> bool:
        """Clear all job-related data including embeddings and matches."""
        if confirm:
            if not Confirm.ask(
                "This will delete ALL jobs, job embeddings, and match results. Continue?",
                default=False
            ):
                self.console.print("[yellow]Operation cancelled[/yellow]")
                return False
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete in proper order to respect foreign key constraints
                cursor.execute("DELETE FROM match_results")
                cursor.execute("DELETE FROM job_embeddings")
                cursor.execute("DELETE FROM jobs")
                
                conn.commit()
                
                self.console.print("[green]✓ All job data cleared successfully[/green]")
                return True
                
        except sqlite3.Error as e:
            self.console.print(f"[red]Error clearing job data: {e}[/red]")
            return False
    
    def clear_resumes_data(self, confirm: bool = True) -> bool:
        """Clear all resume-related data including embeddings and matches."""
        if confirm:
            if not Confirm.ask(
                "This will delete ALL resumes, resume embeddings, and match results. Continue?",
                default=False
            ):
                self.console.print("[yellow]Operation cancelled[/yellow]")
                return False
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete in proper order to respect foreign key constraints
                cursor.execute("DELETE FROM match_results")
                cursor.execute("DELETE FROM resume_embeddings")
                cursor.execute("DELETE FROM resumes")
                
                conn.commit()
                
                self.console.print("[green]✓ All resume data cleared successfully[/green]")
                return True
                
        except sqlite3.Error as e:
            self.console.print(f"[red]Error clearing resume data: {e}[/red]")
            return False
    
    def clear_embeddings_cache(self, confirm: bool = True) -> bool:
        """Clear all embedding data, forcing regeneration on next use."""
        if confirm:
            if not Confirm.ask(
                "This will delete ALL embeddings and match results (jobs/resumes remain). Continue?",
                default=False
            ):
                self.console.print("[yellow]Operation cancelled[/yellow]")
                return False
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete match results first (depends on embeddings)
                cursor.execute("DELETE FROM match_results")
                cursor.execute("DELETE FROM job_embeddings")
                cursor.execute("DELETE FROM resume_embeddings")
                
                conn.commit()
                
                self.console.print("[green]✓ All embeddings cache cleared successfully[/green]")
                self.console.print("[yellow]Note: Embeddings will be regenerated on next matching operation[/yellow]")
                return True
                
        except sqlite3.Error as e:
            self.console.print(f"[red]Error clearing embeddings cache: {e}[/red]")
            return False
    
    def clear_match_results(self, confirm: bool = True) -> bool:
        """Clear only match results, keeping jobs, resumes, and embeddings."""
        if confirm:
            if not Confirm.ask(
                "This will delete ALL match results (jobs/resumes/embeddings remain). Continue?",
                default=False
            ):
                self.console.print("[yellow]Operation cancelled[/yellow]")
                return False
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM match_results")
                conn.commit()
                
                self.console.print("[green]✓ All match results cleared successfully[/green]")
                return True
                
        except sqlite3.Error as e:
            self.console.print(f"[red]Error clearing match results: {e}[/red]")
            return False
    
    def reset_system(self, confirm: bool = True) -> bool:
        """Complete system reset - clears ALL data including companies."""
        if confirm:
            self.console.print("[bold red]⚠️  FULL SYSTEM RESET ⚠️[/bold red]")
            self.console.print("This will delete:")
            self.console.print("• All companies and job sources")
            self.console.print("• All jobs and job data")  
            self.console.print("• All resumes and resume data")
            self.console.print("• All embeddings and AI data")
            self.console.print("• All match results and analyses")
            
            if not Confirm.ask(
                "[bold red]Are you ABSOLUTELY sure you want to reset everything?[/bold red]",
                default=False
            ):
                self.console.print("[yellow]System reset cancelled[/yellow]")
                return False
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete all data in reverse dependency order
                cursor.execute("DELETE FROM match_results")
                cursor.execute("DELETE FROM resume_embeddings")
                cursor.execute("DELETE FROM job_embeddings")
                cursor.execute("DELETE FROM resumes")
                cursor.execute("DELETE FROM jobs")
                cursor.execute("DELETE FROM companies")
                
                # Reset any auto-increment counters
                cursor.execute("DELETE FROM sqlite_sequence")
                
                conn.commit()
                
                self.console.print("[green]✓ Complete system reset successful[/green]")
                self.console.print("[yellow]System is now empty and ready for fresh data[/yellow]")
                return True
                
        except sqlite3.Error as e:
            self.console.print(f"[red]Error during system reset: {e}[/red]")
            return False
    
    def backup_database(self, backup_path: Optional[str] = None) -> bool:
        """Create a backup of the current database."""
        if not os.path.exists(self.db_path):
            self.console.print("[red]Database file not found[/red]")
            return False
        
        if backup_path is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"data/soupboss_backup_{timestamp}.db"
        
        try:
            # Ensure backup directory exists
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            
            # Copy database file
            shutil.copy2(self.db_path, backup_path)
            
            self.console.print(f"[green]✓ Database backed up to: {backup_path}[/green]")
            return True
            
        except Exception as e:
            self.console.print(f"[red]Error creating backup: {e}[/red]")
            return False
    
    def optimize_database(self) -> bool:
        """Optimize database performance by running VACUUM and ANALYZE."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                self.console.print("[yellow]Optimizing database...[/yellow]")
                
                # Get size before optimization
                size_before = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
                
                # Vacuum to reclaim space and defragment
                conn.execute("VACUUM")
                
                # Update statistics for query optimization
                conn.execute("ANALYZE")
                
                conn.commit()
                
                # Get size after optimization
                size_after = os.path.getsize(self.db_path)
                size_saved = size_before - size_after
                
                self.console.print("[green]✓ Database optimization complete[/green]")
                if size_saved > 0:
                    self.console.print(f"[green]Space reclaimed: {size_saved / 1024:.1f} KB[/green]")
                
                return True
                
        except sqlite3.Error as e:
            self.console.print(f"[red]Error optimizing database: {e}[/red]")
            return False
    
    def validate_data_integrity(self) -> bool:
        """Validate database integrity and relationships."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                issues = []
                
                # Check database integrity
                cursor.execute("PRAGMA integrity_check")
                integrity_result = cursor.fetchone()[0]
                if integrity_result != "ok":
                    issues.append(f"Database integrity check failed: {integrity_result}")
                
                # Check for orphaned job embeddings
                cursor.execute("""
                    SELECT COUNT(*) FROM job_embeddings e
                    WHERE job_id NOT IN (SELECT id FROM jobs)
                """)
                orphaned_job_embeddings = cursor.fetchone()[0]
                if orphaned_job_embeddings > 0:
                    issues.append(f"Found {orphaned_job_embeddings} orphaned job embeddings")
                
                # Check for orphaned resume embeddings
                cursor.execute("""
                    SELECT COUNT(*) FROM resume_embeddings e
                    WHERE resume_id NOT IN (SELECT id FROM resumes)
                """)
                orphaned_resume_embeddings = cursor.fetchone()[0]
                if orphaned_resume_embeddings > 0:
                    issues.append(f"Found {orphaned_resume_embeddings} orphaned resume embeddings")
                
                # Check for orphaned match results
                cursor.execute("""
                    SELECT COUNT(*) FROM match_results m
                    WHERE job_id NOT IN (SELECT id FROM jobs)
                       OR resume_id NOT IN (SELECT id FROM resumes)
                """)
                orphaned_matches = cursor.fetchone()[0]
                if orphaned_matches > 0:
                    issues.append(f"Found {orphaned_matches} orphaned match results")
                
                if issues:
                    self.console.print("[red]Data integrity issues found:[/red]")
                    for issue in issues:
                        self.console.print(f"[red]• {issue}[/red]")
                    return False
                else:
                    self.console.print("[green]✓ Data integrity validation passed[/green]")
                    return True
                
        except sqlite3.Error as e:
            self.console.print(f"[red]Error validating data integrity: {e}[/red]")
            return False
    
    def cleanup_orphaned_data(self) -> bool:
        """Clean up orphaned records that reference deleted data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Clean up orphaned job embeddings
                cursor.execute("""
                    DELETE FROM job_embeddings 
                    WHERE job_id NOT IN (SELECT id FROM jobs)
                """)
                orphaned_job_embeddings = cursor.rowcount
                
                # Clean up orphaned resume embeddings
                cursor.execute("""
                    DELETE FROM resume_embeddings 
                    WHERE resume_id NOT IN (SELECT id FROM resumes)
                """)
                orphaned_resume_embeddings = cursor.rowcount
                
                # Clean up orphaned match results
                cursor.execute("""
                    DELETE FROM match_results 
                    WHERE job_id NOT IN (SELECT id FROM jobs)
                       OR resume_id NOT IN (SELECT id FROM resumes)
                """)
                orphaned_matches = cursor.rowcount
                
                conn.commit()
                
                total_cleaned = orphaned_job_embeddings + orphaned_resume_embeddings + orphaned_matches
                if total_cleaned > 0:
                    self.console.print(f"[green]✓ Cleaned up {total_cleaned} orphaned records[/green]")
                    if orphaned_job_embeddings > 0:
                        self.console.print(f"  • Job embeddings: {orphaned_job_embeddings}")
                    if orphaned_resume_embeddings > 0:
                        self.console.print(f"  • Resume embeddings: {orphaned_resume_embeddings}")
                    if orphaned_matches > 0:
                        self.console.print(f"  • Match results: {orphaned_matches}")
                else:
                    self.console.print("[green]✓ No orphaned data found[/green]")
                
                return True
                
        except sqlite3.Error as e:
            self.console.print(f"[red]Error cleaning orphaned data: {e}[/red]")
            return False