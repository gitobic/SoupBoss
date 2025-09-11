"""
Embedding Model Evaluation and Comparison Framework for SoupBoss

This module provides tools to compare different embedding models for job matching accuracy.
It generates embeddings with multiple models and compares their matching performance.
"""

import json
import os
import time
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from statistics import mean, stdev

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .embeddings import OllamaEmbeddingClient
from .db import get_db, SoupBossDB
from .matching import IntelligenceEngine

console = Console()


@dataclass
class ModelEvaluation:
    """Results from evaluating a single embedding model."""
    model_name: str
    total_jobs: int
    total_resumes: int
    avg_embedding_time: float
    embedding_dimension: int
    top_10_avg_score: float
    score_variance: float
    coverage_percentage: float
    unique_matches_top_10: int
    diversity_score: float
    processing_time: float


@dataclass
class ComparisonResult:
    """Comparison results between multiple models."""
    models: List[ModelEvaluation]
    best_by_score: str
    best_by_diversity: str
    best_by_speed: str
    comparison_summary: Dict[str, any]


class EmbeddingModelEvaluator:
    """Evaluate and compare embedding models for job matching."""
    
    def __init__(self, db: Optional[SoupBossDB] = None):
        self.db = db
        self.available_models = self._get_available_models()
        
    def _get_available_models(self) -> List[str]:
        """Get list of available embedding models from Ollama."""
        try:
            import ollama
            client = ollama.Client()
            models_response = client.list()
            
            embedding_models = []
            for model in models_response.models:
                model_name = model.model
                # Common embedding models - expanded detection
                if any(keyword in model_name.lower() for keyword in [
                    'embed', 'bge', 'mxbai', 'nomic', 'sentence', 'all-minilm'
                ]):
                    # Remove :latest suffix for consistency
                    clean_name = model_name.replace(':latest', '')
                    embedding_models.append(clean_name)
            
            return embedding_models
            
        except Exception as e:
            console.print(f"[red]Error getting available models: {e}[/red]")
            # Get fallback from config
            from .config import get_config_manager
            config = get_config_manager()
            return [config.get('ollama', 'model')]  # Fallback to configured model
    
    def generate_embeddings_for_model(self, model_name: str, 
                                    force_regenerate: bool = False) -> ModelEvaluation:
        """Generate embeddings for all jobs and resumes using specified model."""
        console.print(f"[cyan]Evaluating model: {model_name}[/cyan]")
        
        client = OllamaEmbeddingClient(model=model_name)
        start_time = time.time()
        
        # Check if model is available
        if not client.ensure_model_ready():
            raise RuntimeError(f"Model {model_name} is not available")
        
        with get_db() as db:
            # Get jobs that need embeddings
            if force_regenerate:
                cursor = db.conn.execute("SELECT id, content_text, title FROM jobs WHERE content_text IS NOT NULL")
            else:
                cursor = db.conn.execute("""
                    SELECT j.id, j.content_text, j.title 
                    FROM jobs j
                    LEFT JOIN job_embeddings je ON j.id = je.job_id AND je.embedding_model = ?
                    WHERE j.content_text IS NOT NULL AND je.id IS NULL
                """, (model_name,))
            
            jobs_to_process = cursor.fetchall()
            
            # Get resumes that need embeddings
            if force_regenerate:
                cursor = db.conn.execute("SELECT id, content_text, name FROM resumes WHERE content_text IS NOT NULL")
            else:
                cursor = db.conn.execute("""
                    SELECT r.id, r.content_text, r.name 
                    FROM resumes r
                    LEFT JOIN resume_embeddings re ON r.id = re.resume_id AND re.embedding_model = ?
                    WHERE r.content_text IS NOT NULL AND re.id IS NULL
                """, (model_name,))
            
            resumes_to_process = cursor.fetchall()
            
            total_items = len(jobs_to_process) + len(resumes_to_process)
            
            if total_items == 0:
                console.print(f"[yellow]All embeddings already exist for {model_name}[/yellow]")
            else:
                console.print(f"[cyan]Generating {len(jobs_to_process)} job and {len(resumes_to_process)} resume embeddings[/cyan]")
                
                embedding_times = []
                
                with Progress() as progress:
                    task = progress.add_task(f"Processing with {model_name}...", total=total_items)
                    
                    # Process jobs
                    for job in jobs_to_process:
                        job_id, content, title = job
                        
                        embed_start = time.time()
                        embedding = client.generate_embedding(content)
                        embed_time = time.time() - embed_start
                        embedding_times.append(embed_time)
                        
                        if embedding is not None:
                            # Store embedding
                            db.save_job_embedding(job_id, model_name, embedding)
                        
                        progress.update(task, advance=1)
                    
                    # Process resumes
                    for resume in resumes_to_process:
                        resume_id, content, name = resume
                        
                        embed_start = time.time()
                        embedding = client.generate_embedding(content)
                        embed_time = time.time() - embed_start
                        embedding_times.append(embed_time)
                        
                        if embedding is not None:
                            # Store embedding
                            db.save_resume_embedding(resume_id, model_name, embedding)
                        
                        progress.update(task, advance=1)
            
            # Calculate evaluation metrics
            metrics = self._calculate_model_metrics(db, model_name)
            
            processing_time = time.time() - start_time
            metrics.processing_time = processing_time
            
            if jobs_to_process or resumes_to_process:
                metrics.avg_embedding_time = mean(embedding_times) if embedding_times else 0.0
            
            return metrics
    
    def _calculate_model_metrics(self, db: SoupBossDB, model_name: str) -> ModelEvaluation:
        """Calculate evaluation metrics for a model."""
        # Get counts
        cursor = db.conn.execute("""
            SELECT COUNT(*) FROM job_embeddings WHERE embedding_model = ?
        """, (model_name,))
        total_jobs = cursor.fetchone()[0]
        
        cursor = db.conn.execute("""
            SELECT COUNT(*) FROM resume_embeddings WHERE embedding_model = ?
        """, (model_name,))
        total_resumes = cursor.fetchone()[0]
        
        # Get embedding dimension (from first job embedding)
        cursor = db.conn.execute("""
            SELECT embedding FROM job_embeddings WHERE embedding_model = ? LIMIT 1
        """, (model_name,))
        result = cursor.fetchone()
        embedding_dim = 0
        if result:
            embedding = np.frombuffer(result[0], dtype=np.float32)
            embedding_dim = len(embedding)
        
        # Calculate similarity scores for evaluation
        scores = self._calculate_sample_similarities(db, model_name)
        
        top_10_avg = mean(scores[:10]) if len(scores) >= 10 else (mean(scores) if scores else 0.0)
        score_variance = stdev(scores) if len(scores) > 1 else 0.0
        
        # Calculate diversity (percentage of job space covered in top matches)
        diversity_percentage = self._calculate_diversity(db, model_name)
        
        # Coverage percentage (what % of jobs/resumes have embeddings)
        cursor = db.conn.execute("SELECT COUNT(*) FROM jobs WHERE content_text IS NOT NULL")
        total_possible_jobs = cursor.fetchone()[0]
        
        cursor = db.conn.execute("SELECT COUNT(*) FROM resumes WHERE content_text IS NOT NULL")
        total_possible_resumes = cursor.fetchone()[0]
        
        coverage_jobs = (total_jobs / total_possible_jobs * 100) if total_possible_jobs > 0 else 0
        coverage_resumes = (total_resumes / total_possible_resumes * 100) if total_possible_resumes > 0 else 0
        coverage_percentage = (coverage_jobs + coverage_resumes) / 2
        
        return ModelEvaluation(
            model_name=model_name,
            total_jobs=total_jobs,
            total_resumes=total_resumes,
            avg_embedding_time=0.0,  # Will be set by caller
            embedding_dimension=embedding_dim,
            top_10_avg_score=top_10_avg,
            score_variance=score_variance,
            coverage_percentage=coverage_percentage,
            unique_matches_top_10=int(diversity_percentage * total_jobs / 100),  # For backwards compatibility
            diversity_score=diversity_percentage,
            processing_time=0.0  # Will be set by caller
        )
    
    def _calculate_sample_similarities(self, db: SoupBossDB, model_name: str, 
                                     sample_size: int = 100) -> List[float]:
        """Calculate similarity scores for a sample of resume-job pairs."""
        # Get sample of resumes with embeddings
        cursor = db.conn.execute("""
            SELECT r.id, re.embedding
            FROM resumes r
            JOIN resume_embeddings re ON r.id = re.resume_id
            WHERE re.embedding_model = ?
            ORDER BY RANDOM()
            LIMIT ?
        """, (model_name, min(sample_size, 10)))  # Limit resumes to avoid too much computation
        
        resume_data = cursor.fetchall()
        if not resume_data:
            return []
        
        # Get sample of jobs with embeddings
        cursor = db.conn.execute("""
            SELECT j.id, je.embedding
            FROM jobs j
            JOIN job_embeddings je ON j.id = je.job_id
            WHERE je.embedding_model = ?
            ORDER BY RANDOM()
            LIMIT ?
        """, (model_name, sample_size))
        
        job_data = cursor.fetchall()
        if not job_data:
            return []
        
        # Calculate similarities
        scores = []
        for resume_id, resume_embedding_blob in resume_data[:5]:  # Limit to 5 resumes
            resume_embedding = np.frombuffer(resume_embedding_blob, dtype=np.float32)
            
            resume_scores = []
            for job_id, job_embedding_blob in job_data:
                job_embedding = np.frombuffer(job_embedding_blob, dtype=np.float32)
                # Use cosine similarity calculation
                dot_product = np.dot(resume_embedding, job_embedding)
                norm_a = np.linalg.norm(resume_embedding)
                norm_b = np.linalg.norm(job_embedding)
                similarity = dot_product / (norm_a * norm_b) if (norm_a * norm_b) != 0 else 0.0
                resume_scores.append(similarity)
            
            # Add top scores for this resume
            resume_scores.sort(reverse=True)
            scores.extend(resume_scores[:20])  # Top 20 per resume
        
        scores.sort(reverse=True)
        return scores
    
    def _calculate_diversity(self, db: SoupBossDB, model_name: str) -> float:
        """Calculate diversity metric - percentage of unique jobs appearing in top matches."""
        # Get top 10 matches for each resume (more meaningful diversity metric)
        cursor = db.conn.execute("""
            SELECT DISTINCT mr.job_id
            FROM (
                SELECT mr.job_id, mr.resume_id,
                       ROW_NUMBER() OVER (PARTITION BY mr.resume_id ORDER BY mr.similarity_score DESC) as rn
                FROM match_results mr
                JOIN job_embeddings je ON mr.job_id = je.job_id
                JOIN resume_embeddings re ON mr.resume_id = re.resume_id
                WHERE je.embedding_model = ? AND re.embedding_model = ?
            ) mr
            WHERE mr.rn <= 10
        """, (model_name, model_name))
        
        unique_jobs_in_top_matches = len(cursor.fetchall())
        
        # Get total number of jobs available for this model
        cursor = db.conn.execute("""
            SELECT COUNT(*) FROM job_embeddings WHERE embedding_model = ?
        """, (model_name,))
        total_jobs = cursor.fetchone()[0]
        
        # Return percentage of job space covered in top matches
        diversity_percentage = (unique_jobs_in_top_matches / max(1, total_jobs)) * 100
        return diversity_percentage
    
    def compare_models(self, models_to_compare: List[str], 
                      force_regenerate: bool = False) -> ComparisonResult:
        """Compare multiple embedding models."""
        if not models_to_compare:
            models_to_compare = self.available_models
        
        console.print(f"[bold cyan]Comparing {len(models_to_compare)} embedding models[/bold cyan]")
        console.print(f"Models: {', '.join(models_to_compare)}")
        
        evaluations = []
        
        for model_name in models_to_compare:
            try:
                evaluation = self.generate_embeddings_for_model(model_name, force_regenerate)
                evaluations.append(evaluation)
                console.print(f"[green]✓ Completed evaluation for {model_name}[/green]")
            except Exception as e:
                console.print(f"[red]✗ Failed to evaluate {model_name}: {e}[/red]")
                continue
        
        if not evaluations:
            raise RuntimeError("No models could be evaluated")
        
        # Determine best models
        best_by_score = max(evaluations, key=lambda x: x.top_10_avg_score).model_name
        best_by_diversity = max(evaluations, key=lambda x: x.diversity_score).model_name
        best_by_speed = min(evaluations, key=lambda x: x.avg_embedding_time).model_name
        
        # Create comparison summary
        comparison_summary = {
            'evaluation_date': datetime.now().isoformat(),
            'models_compared': len(evaluations),
            'best_overall_score': max(e.top_10_avg_score for e in evaluations),
            'score_range': {
                'min': min(e.top_10_avg_score for e in evaluations),
                'max': max(e.top_10_avg_score for e in evaluations),
                'avg': mean(e.top_10_avg_score for e in evaluations)
            },
            'speed_range': {
                'fastest': min(e.avg_embedding_time for e in evaluations if e.avg_embedding_time > 0),
                'slowest': max(e.avg_embedding_time for e in evaluations if e.avg_embedding_time > 0),
                'avg': mean(e.avg_embedding_time for e in evaluations if e.avg_embedding_time > 0)
            } if any(e.avg_embedding_time > 0 for e in evaluations) else None
        }
        
        return ComparisonResult(
            models=evaluations,
            best_by_score=best_by_score,
            best_by_diversity=best_by_diversity,
            best_by_speed=best_by_speed,
            comparison_summary=comparison_summary
        )
    
    def print_comparison_results(self, comparison: ComparisonResult):
        """Print a formatted comparison table."""
        console.print("\n[bold cyan]Embedding Model Comparison Results[/bold cyan]")
        
        table = Table(title="Model Performance Comparison")
        table.add_column("Model", style="bold")
        table.add_column("Avg Score", style="green")
        table.add_column("Diversity", style="yellow")
        table.add_column("Dimension", style="cyan")
        table.add_column("Avg Time (s)", style="magenta")
        table.add_column("Coverage %", style="blue")
        table.add_column("Jobs", style="dim")
        table.add_column("Resumes", style="dim")
        
        for model in comparison.models:
            table.add_row(
                model.model_name,
                f"{model.top_10_avg_score:.3f}",
                f"{model.diversity_score:.2f}",
                str(model.embedding_dimension),
                f"{model.avg_embedding_time:.2f}" if model.avg_embedding_time > 0 else "N/A",
                f"{model.coverage_percentage:.1f}%",
                str(model.total_jobs),
                str(model.total_resumes)
            )
        
        console.print(table)
        
        # Print recommendations
        console.print("\n[bold yellow]Recommendations:[/bold yellow]")
        console.print(f"🏆 [bold green]Best for accuracy:[/bold green] {comparison.best_by_score}")
        console.print(f"🎯 [bold yellow]Best for diversity:[/bold yellow] {comparison.best_by_diversity}")
        console.print(f"⚡ [bold cyan]Fastest processing:[/bold cyan] {comparison.best_by_speed}")
        
        if comparison.comparison_summary.get('score_range'):
            score_range = comparison.comparison_summary['score_range']
            score_improvement = ((score_range['max'] - score_range['min']) / score_range['min'] * 100)
            if score_improvement > 5:
                console.print(f"📈 [bold]Potential improvement:[/bold] Up to {score_improvement:.1f}% better matching scores")
    
    def save_comparison_results(self, comparison: ComparisonResult, output_file: str):
        """Save comparison results to JSON file."""
        results_data = {
            'comparison_summary': comparison.comparison_summary,
            'best_models': {
                'by_score': comparison.best_by_score,
                'by_diversity': comparison.best_by_diversity,
                'by_speed': comparison.best_by_speed
            },
            'model_evaluations': []
        }
        
        for model in comparison.models:
            results_data['model_evaluations'].append({
                'model_name': model.model_name,
                'total_jobs': model.total_jobs,
                'total_resumes': model.total_resumes,
                'avg_embedding_time': model.avg_embedding_time,
                'embedding_dimension': model.embedding_dimension,
                'top_10_avg_score': model.top_10_avg_score,
                'score_variance': model.score_variance,
                'coverage_percentage': model.coverage_percentage,
                'unique_matches_top_10': model.unique_matches_top_10,
                'diversity_score': model.diversity_score,
                'processing_time': model.processing_time
            })
        
        with open(output_file, 'w') as f:
            json.dump(results_data, f, indent=2, default=str)
        
        console.print(f"[green]✓ Saved results to {output_file}[/green]")


def get_model_evaluator() -> EmbeddingModelEvaluator:
    """Get a model evaluator instance."""
    return EmbeddingModelEvaluator()