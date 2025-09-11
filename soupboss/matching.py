"""
Intelligence Engine for SoupBoss - embedding generation and similarity matching.

Handles embedding generation, caching, and cosine similarity calculations for job-resume matching.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from datetime import datetime
import json

from .db import SoupBossDB
from .embeddings import get_embedding_client
from .config import get_config_manager
from rich.console import Console
from rich.progress import Progress

console = Console()


@dataclass
class MatchResult:
    """Represents a job-resume match result."""
    resume_id: int
    resume_name: str
    job_id: int
    job_title: str
    company_name: str
    similarity_score: float
    adjusted_score: Optional[float] = None
    job_department: Optional[str] = None
    job_location: Optional[str] = None


class EmbeddingPipeline:
    """Manages embedding generation and caching for jobs and resumes."""
    
    def __init__(self, db: SoupBossDB, model_name: Optional[str] = None):
        if model_name is None:
            config = get_config_manager()
            model_name = config.get('ollama', 'model')
        self.db = db
        self.model_name = model_name
        self.embedding_client = get_embedding_client()
        
        # Check if model is ready
        status = self.embedding_client.get_status()
        if not status["model_ready"]:
            console.print(f"[red]Model {model_name} not ready. Please ensure Ollama is running with the model.[/red]")
            raise RuntimeError(f"Embedding model {model_name} not available")
    
    def generate_job_embeddings(self, job_ids: Optional[List[int]] = None, force_regenerate: bool = False) -> int:
        """
        Generate embeddings for jobs.
        
        Args:
            job_ids: Specific job IDs to process (None for all jobs)
            force_regenerate: Force regeneration even if embeddings exist
            
        Returns:
            Number of embeddings generated
        """
        # Get jobs that need embeddings
        if job_ids:
            jobs = []
            for job_id in job_ids:
                job_query = self.db.conn.execute(
                    "SELECT * FROM jobs WHERE id = ?", (job_id,)
                ).fetchone()
                if job_query:
                    jobs.append(dict(job_query))
        else:
            jobs = self.db.get_jobs()
        
        if not jobs:
            console.print("[yellow]No jobs found to process[/yellow]")
            return 0
        
        # Filter jobs that need embedding generation
        jobs_to_process = []
        for job in jobs:
            if force_regenerate or not self._has_job_embedding(job['id']):
                jobs_to_process.append(job)
        
        if not jobs_to_process:
            console.print("[green]All jobs already have embeddings[/green]")
            return 0
        
        console.print(f"[cyan]Generating embeddings for {len(jobs_to_process)} jobs...[/cyan]")
        
        embeddings_generated = 0
        
        with Progress() as progress:
            task = progress.add_task("Processing jobs...", total=len(jobs_to_process))
            
            for job in jobs_to_process:
                progress.update(task, advance=1)
                
                # Create text for embedding (combine title and content)
                job_text = self._prepare_job_text(job)
                
                try:
                    # Generate embedding
                    embeddings = self.embedding_client.generate_embeddings_batch([job_text])
                    if embeddings and len(embeddings) > 0:
                        embedding = embeddings[0]
                    else:
                        raise ValueError("Failed to generate embedding")
                    
                    # Save to database
                    self.db.save_job_embedding(job['id'], self.model_name, embedding)
                    embeddings_generated += 1
                    
                except Exception as e:
                    console.print(f"[red]Error generating embedding for job {job['id']}: {e}[/red]")
                    continue
        
        console.print(f"[green]Generated {embeddings_generated} job embeddings[/green]")
        return embeddings_generated
    
    def generate_resume_embeddings(self, resume_ids: Optional[List[int]] = None, force_regenerate: bool = False) -> int:
        """
        Generate embeddings for resumes.
        
        Args:
            resume_ids: Specific resume IDs to process (None for all resumes)
            force_regenerate: Force regeneration even if embeddings exist
            
        Returns:
            Number of embeddings generated
        """
        # Get resumes that need embeddings
        if resume_ids:
            resumes = []
            for resume_id in resume_ids:
                resume = self.db.get_resume(resume_id)
                if resume:
                    resumes.append(resume)
        else:
            resumes = self.db.get_resumes()
        
        if not resumes:
            console.print("[yellow]No resumes found to process[/yellow]")
            return 0
        
        # Filter resumes that need embedding generation
        resumes_to_process = []
        for resume in resumes:
            if force_regenerate or not self._has_resume_embedding(resume['id']):
                resumes_to_process.append(resume)
        
        if not resumes_to_process:
            console.print("[green]All resumes already have embeddings[/green]")
            return 0
        
        console.print(f"[cyan]Generating embeddings for {len(resumes_to_process)} resumes...[/cyan]")
        
        embeddings_generated = 0
        
        with Progress() as progress:
            task = progress.add_task("Processing resumes...", total=len(resumes_to_process))
            
            for resume in resumes_to_process:
                progress.update(task, advance=1)
                
                # Use resume content text for embedding
                resume_text = resume['content_text']
                
                try:
                    # Generate embedding
                    embeddings = self.embedding_client.generate_embeddings_batch([resume_text])
                    if embeddings and len(embeddings) > 0:
                        embedding = embeddings[0]
                    else:
                        raise ValueError("Failed to generate embedding")
                    
                    # Save to database
                    self.db.save_resume_embedding(resume['id'], self.model_name, embedding)
                    embeddings_generated += 1
                    
                except Exception as e:
                    console.print(f"[red]Error generating embedding for resume {resume['id']}: {e}[/red]")
                    continue
        
        console.print(f"[green]Generated {embeddings_generated} resume embeddings[/green]")
        return embeddings_generated
    
    def _prepare_job_text(self, job: Dict) -> str:
        """Prepare job text for embedding generation."""
        parts = []
        
        # Add job title (weighted more heavily by repeating)
        if job.get('title'):
            parts.append(f"Job Title: {job['title']}")
            parts.append(job['title'])  # Repeat for emphasis
        
        # Add department
        if job.get('department'):
            parts.append(f"Department: {job['department']}")
        
        # Add location
        if job.get('location'):
            parts.append(f"Location: {job['location']}")
        
        # Add job description (main content)
        content = job.get('content_text', '') or job.get('content_html', '')
        if content:
            # Truncate very long content to avoid token limits
            if len(content) > 8000:  # Conservative limit
                content = content[:8000] + "..."
            parts.append(content)
        
        return '\n\n'.join(parts)
    
    def _has_job_embedding(self, job_id: int) -> bool:
        """Check if job has existing embedding."""
        return self.db.get_job_embedding(job_id, self.model_name) is not None
    
    def _has_resume_embedding(self, resume_id: int) -> bool:
        """Check if resume has existing embedding."""
        return self.db.get_resume_embedding(resume_id, self.model_name) is not None
    
    def get_embedding_stats(self) -> Dict:
        """Get statistics about embedding coverage."""
        cursor = self.db.conn.cursor()
        
        # Count jobs with/without embeddings
        cursor.execute("SELECT COUNT(*) as total FROM jobs")
        total_jobs = cursor.fetchone()["total"]
        
        cursor.execute(
            "SELECT COUNT(*) as with_embeddings FROM job_embeddings WHERE embedding_model = ?",
            (self.model_name,)
        )
        jobs_with_embeddings = cursor.fetchone()["with_embeddings"]
        
        # Count resumes with/without embeddings
        cursor.execute("SELECT COUNT(*) as total FROM resumes")
        total_resumes = cursor.fetchone()["total"]
        
        cursor.execute(
            "SELECT COUNT(*) as with_embeddings FROM resume_embeddings WHERE embedding_model = ?",
            (self.model_name,)
        )
        resumes_with_embeddings = cursor.fetchone()["with_embeddings"]
        
        return {
            "model": self.model_name,
            "jobs": {
                "total": total_jobs,
                "with_embeddings": jobs_with_embeddings,
                "coverage_percent": round((jobs_with_embeddings / max(total_jobs, 1)) * 100, 1)
            },
            "resumes": {
                "total": total_resumes,
                "with_embeddings": resumes_with_embeddings,
                "coverage_percent": round((resumes_with_embeddings / max(total_resumes, 1)) * 100, 1)
            }
        }


class SimilarityMatcher:
    """Handles similarity calculations and job-resume matching."""
    
    def __init__(self, db: SoupBossDB, model_name: Optional[str] = None):
        if model_name is None:
            config = get_config_manager()
            model_name = config.get('ollama', 'model')
        self.db = db
        self.model_name = model_name
    
    def calculate_similarity_batch(self, resume_ids: Optional[List[int]] = None, 
                                   job_ids: Optional[List[int]] = None,
                                   save_results: bool = True) -> List[MatchResult]:
        """
        Calculate similarity scores between resumes and jobs in batch.
        
        Args:
            resume_ids: Specific resume IDs to match (None for all)
            job_ids: Specific job IDs to match against (None for all)
            save_results: Whether to save results to database
            
        Returns:
            List of MatchResult objects sorted by similarity score
        """
        # Get resume and job data with embeddings
        resumes_data = self._get_resumes_with_embeddings(resume_ids)
        jobs_data = self._get_jobs_with_embeddings(job_ids)
        
        if not resumes_data:
            console.print("[red]No resumes with embeddings found[/red]")
            return []
        
        if not jobs_data:
            console.print("[red]No jobs with embeddings found[/red]")
            return []
        
        console.print(f"[cyan]Calculating similarities for {len(resumes_data)} resumes against {len(jobs_data)} jobs...[/cyan]")
        
        results = []
        
        with Progress() as progress:
            task = progress.add_task("Computing similarities...", total=len(resumes_data) * len(jobs_data))
            
            for resume in resumes_data:
                for job in jobs_data:
                    progress.update(task, advance=1)
                    
                    # Calculate cosine similarity
                    similarity = self._cosine_similarity(resume['embedding'], job['embedding'])
                    
                    # Create match result
                    match_result = MatchResult(
                        resume_id=resume['id'],
                        resume_name=resume['name'],
                        job_id=job['id'],
                        job_title=job['title'],
                        company_name=job['company_name'],
                        similarity_score=similarity,
                        job_department=job.get('department'),
                        job_location=job.get('location')
                    )
                    
                    results.append(match_result)
                    
                    # Save to database if requested
                    if save_results:
                        self.db.save_match_result(
                            resume['id'], job['id'], similarity, self.model_name
                        )
        
        # Sort by similarity score (highest first)
        results.sort(key=lambda x: x.similarity_score, reverse=True)
        
        console.print(f"[green]Calculated {len(results)} similarity scores[/green]")
        
        return results
    
    def get_top_matches(self, resume_id: int, limit: int = 10) -> List[MatchResult]:
        """Get top job matches for a specific resume."""
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
            WHERE mr.resume_id = ? AND mr.embedding_model = ?
            ORDER BY mr.similarity_score DESC
            LIMIT ?
        """
        
        cursor.execute(query, (resume_id, self.model_name, limit))
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            match_result = MatchResult(
                resume_id=row['resume_id'],
                resume_name=row['resume_name'],
                job_id=row['job_id'],
                job_title=row['job_title'],
                company_name=row['company_name'],
                similarity_score=row['similarity_score'],
                adjusted_score=row['adjusted_score'],
                job_department=row['department'],
                job_location=row['location']
            )
            results.append(match_result)
        
        return results
    
    def get_all_matches(self, limit: int = 100) -> List[MatchResult]:
        """Get all match results across all resumes."""
        return self.db.get_match_results(limit=limit)
    
    def _get_resumes_with_embeddings(self, resume_ids: Optional[List[int]] = None) -> List[Dict]:
        """Get resumes with their embeddings."""
        cursor = self.db.conn.cursor()
        
        if resume_ids:
            placeholders = ','.join('?' * len(resume_ids))
            query = f"""
                SELECT r.*, re.embedding 
                FROM resumes r
                JOIN resume_embeddings re ON r.id = re.resume_id
                WHERE r.id IN ({placeholders}) AND re.embedding_model = ?
            """
            params = resume_ids + [self.model_name]
        else:
            query = """
                SELECT r.*, re.embedding 
                FROM resumes r
                JOIN resume_embeddings re ON r.id = re.resume_id
                WHERE re.embedding_model = ?
            """
            params = [self.model_name]
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            data = dict(row)
            data['embedding'] = np.frombuffer(row['embedding'], dtype=np.float32)
            results.append(data)
        
        return results
    
    def _get_jobs_with_embeddings(self, job_ids: Optional[List[int]] = None) -> List[Dict]:
        """Get jobs with their embeddings."""
        cursor = self.db.conn.cursor()
        
        if job_ids:
            placeholders = ','.join('?' * len(job_ids))
            query = f"""
                SELECT j.*, c.name as company_name, je.embedding 
                FROM jobs j
                JOIN companies c ON j.company_id = c.id
                JOIN job_embeddings je ON j.id = je.job_id
                WHERE j.id IN ({placeholders}) AND je.embedding_model = ?
            """
            params = job_ids + [self.model_name]
        else:
            query = """
                SELECT j.*, c.name as company_name, je.embedding 
                FROM jobs j
                JOIN companies c ON j.company_id = c.id
                JOIN job_embeddings je ON j.id = je.job_id
                WHERE je.embedding_model = ?
            """
            params = [self.model_name]
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            data = dict(row)
            data['embedding'] = np.frombuffer(row['embedding'], dtype=np.float32)
            results.append(data)
        
        return results
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        # Normalize vectors
        a_norm = a / np.linalg.norm(a)
        b_norm = b / np.linalg.norm(b)
        
        # Calculate cosine similarity
        similarity = np.dot(a_norm, b_norm)
        
        return float(similarity)


class IntelligenceEngine:
    """High-level interface for embedding generation and similarity matching."""
    
    def __init__(self, db_path: str = "data/soupboss.db", model_name: Optional[str] = None):
        if model_name is None:
            config = get_config_manager()
            model_name = config.get('ollama', 'model')
        from .db import get_db
        self.db = get_db(db_path)
        self.model_name = model_name
        self.embedding_pipeline = EmbeddingPipeline(self.db, model_name)
        self.similarity_matcher = SimilarityMatcher(self.db, model_name)
    
    def generate_all_embeddings(self, force_regenerate: bool = False) -> Tuple[int, int]:
        """Generate embeddings for all jobs and resumes."""
        job_count = self.embedding_pipeline.generate_job_embeddings(force_regenerate=force_regenerate)
        resume_count = self.embedding_pipeline.generate_resume_embeddings(force_regenerate=force_regenerate)
        return job_count, resume_count
    
    def run_matching(self, resume_ids: Optional[List[int]] = None, 
                     job_ids: Optional[List[int]] = None) -> List[MatchResult]:
        """Run complete matching pipeline."""
        return self.similarity_matcher.calculate_similarity_batch(
            resume_ids=resume_ids, 
            job_ids=job_ids, 
            save_results=True
        )
    
    def get_resume_matches(self, resume_id: int, limit: int = 10) -> List[MatchResult]:
        """Get top matches for a specific resume."""
        return self.similarity_matcher.get_top_matches(resume_id, limit)
    
    def get_embedding_stats(self) -> Dict:
        """Get embedding coverage statistics."""
        return self.embedding_pipeline.get_embedding_stats()


def get_intelligence_engine(db_path: str = "data/soupboss.db", model_name: Optional[str] = None) -> IntelligenceEngine:
    """Get intelligence engine instance."""
    return IntelligenceEngine(db_path, model_name)