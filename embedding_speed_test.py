#!/usr/bin/env python3
"""
Embedding Speed Test for SoupBoss - Focus on embedding generation performance.

This script provides focused speed testing for embedding generation across different models.
"""

import time
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# Import SoupBoss modules
from soupboss.embeddings import OllamaEmbeddingClient
from soupboss.db import get_db
from soupboss.matching import IntelligenceEngine

console = Console()


@dataclass
class SpeedTestResult:
    """Results from speed testing a single model."""
    model_name: str
    total_jobs: int
    total_resumes: int
    job_embedding_time: float
    resume_embedding_time: float
    total_time: float
    avg_time_per_item: float
    items_per_second: float
    embedding_dimension: int
    success_rate: float


class EmbeddingSpeedTester:
    """Focused speed testing for embedding generation."""
    
    def __init__(self):
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
            # Fallback models
            return ['nomic-embed-text']
    
    def list_available_models(self):
        """Display available models for speed testing."""
        console.print("[bold cyan]Available Embedding Models for Speed Testing:[/bold cyan]")
        
        if not self.available_models:
            console.print("[yellow]No embedding models found. Make sure Ollama is running with embedding models.[/yellow]")
            return
        
        for i, model in enumerate(self.available_models, 1):
            console.print(f"  {i}. {model}")
        
        console.print(f"\n[green]Total: {len(self.available_models)} models available[/green]")
    
    def run_speed_test(self, model_name: str, force_regenerate: bool = False) -> SpeedTestResult:
        """Run speed test for a single model."""
        console.print(f"[cyan]Running speed test for: {model_name}[/cyan]")
        
        client = OllamaEmbeddingClient(model=model_name)
        
        # Check if model is available
        if not client.ensure_model_ready():
            raise RuntimeError(f"Model {model_name} is not available")
        
        with get_db() as db:
            # Get jobs and resumes to process
            if force_regenerate:
                jobs_cursor = db.conn.execute("SELECT id, content_text, title FROM jobs WHERE content_text IS NOT NULL")
                resumes_cursor = db.conn.execute("SELECT id, content_text, name FROM resumes WHERE content_text IS NOT NULL")
            else:
                # Only process items without existing embeddings for this model
                jobs_cursor = db.conn.execute("""
                    SELECT j.id, j.content_text, j.title 
                    FROM jobs j
                    LEFT JOIN job_embeddings je ON j.id = je.job_id AND je.embedding_model = ?
                    WHERE j.content_text IS NOT NULL AND je.id IS NULL
                """, (model_name,))
                
                resumes_cursor = db.conn.execute("""
                    SELECT r.id, r.content_text, r.name 
                    FROM resumes r
                    LEFT JOIN resume_embeddings re ON r.id = re.resume_id AND re.embedding_model = ?
                    WHERE r.content_text IS NOT NULL AND re.id IS NULL
                """, (model_name,))
            
            jobs_to_process = jobs_cursor.fetchall()
            resumes_to_process = resumes_cursor.fetchall()
            
            total_items = len(jobs_to_process) + len(resumes_to_process)
            
            if total_items == 0:
                console.print(f"[yellow]No items to process for {model_name} (all embeddings exist)[/yellow]")
                # Get existing stats for already processed items
                return self._get_existing_stats(db, model_name)
            
            console.print(f"[cyan]Processing {len(jobs_to_process)} jobs and {len(resumes_to_process)} resumes[/cyan]")
            
            # Track timing and success metrics
            job_times = []
            resume_times = []
            failures = 0
            embedding_dim = 0
            
            overall_start = time.time()
            
            with Progress(
                SpinnerColumn(),
                *Progress.get_default_columns(),
                console=console
            ) as progress:
                
                # Process jobs
                if jobs_to_process:
                    job_task = progress.add_task(f"Processing {len(jobs_to_process)} jobs...", total=len(jobs_to_process))
                    
                    for job in jobs_to_process:
                        job_id, content, title = job
                        
                        start_time = time.time()
                        try:
                            embedding = client.generate_embedding(content)
                            end_time = time.time()
                            
                            if embedding is not None:
                                if embedding_dim == 0:
                                    embedding_dim = len(embedding)
                                
                                # Save to database
                                db.save_job_embedding(job_id, model_name, embedding)
                                job_times.append(end_time - start_time)
                            else:
                                failures += 1
                        except Exception as e:
                            failures += 1
                            console.print(f"[red]Error processing job {job_id}: {e}[/red]")
                        
                        progress.update(job_task, advance=1)
                
                # Process resumes
                if resumes_to_process:
                    resume_task = progress.add_task(f"Processing {len(resumes_to_process)} resumes...", total=len(resumes_to_process))
                    
                    for resume in resumes_to_process:
                        resume_id, content, name = resume
                        
                        start_time = time.time()
                        try:
                            embedding = client.generate_embedding(content)
                            end_time = time.time()
                            
                            if embedding is not None:
                                if embedding_dim == 0:
                                    embedding_dim = len(embedding)
                                
                                # Save to database
                                db.save_resume_embedding(resume_id, model_name, embedding)
                                resume_times.append(end_time - start_time)
                            else:
                                failures += 1
                        except Exception as e:
                            failures += 1
                            console.print(f"[red]Error processing resume {resume_id}: {e}[/red]")
                        
                        progress.update(resume_task, advance=1)
            
            overall_time = time.time() - overall_start
            
            # Calculate metrics
            total_job_time = sum(job_times)
            total_resume_time = sum(resume_times)
            total_embedding_time = total_job_time + total_resume_time
            successful_items = len(job_times) + len(resume_times)
            
            avg_time_per_item = total_embedding_time / successful_items if successful_items > 0 else 0
            items_per_second = successful_items / total_embedding_time if total_embedding_time > 0 else 0
            success_rate = (successful_items / total_items * 100) if total_items > 0 else 100
            
            return SpeedTestResult(
                model_name=model_name,
                total_jobs=len(jobs_to_process),
                total_resumes=len(resumes_to_process),
                job_embedding_time=total_job_time,
                resume_embedding_time=total_resume_time,
                total_time=overall_time,
                avg_time_per_item=avg_time_per_item,
                items_per_second=items_per_second,
                embedding_dimension=embedding_dim,
                success_rate=success_rate
            )
    
    def _get_existing_stats(self, db, model_name: str) -> SpeedTestResult:
        """Get stats for models that already have embeddings."""
        job_count = db.conn.execute(
            "SELECT COUNT(*) FROM job_embeddings WHERE embedding_model = ?", (model_name,)
        ).fetchone()[0]
        
        resume_count = db.conn.execute(
            "SELECT COUNT(*) FROM resume_embeddings WHERE embedding_model = ?", (model_name,)
        ).fetchone()[0]
        
        # Get embedding dimension
        result = db.conn.execute(
            "SELECT embedding FROM job_embeddings WHERE embedding_model = ? LIMIT 1", (model_name,)
        ).fetchone()
        
        embedding_dim = 0
        if result:
            import numpy as np
            embedding = np.frombuffer(result[0], dtype=np.float32)
            embedding_dim = len(embedding)
        
        return SpeedTestResult(
            model_name=model_name,
            total_jobs=job_count,
            total_resumes=resume_count,
            job_embedding_time=0.0,
            resume_embedding_time=0.0,
            total_time=0.0,
            avg_time_per_item=0.0,
            items_per_second=0.0,
            embedding_dimension=embedding_dim,
            success_rate=100.0
        )
    
    def run_comparison_test(self, models: List[str], force_regenerate: bool = False) -> List[SpeedTestResult]:
        """Run speed test comparison across multiple models."""
        results = []
        
        console.print(f"[bold cyan]Running speed test comparison for {len(models)} models[/bold cyan]")
        console.print(f"Models: {', '.join(models)}")
        console.print()
        
        for model in models:
            try:
                result = self.run_speed_test(model, force_regenerate)
                results.append(result)
                console.print(f"[green]✓ Completed speed test for {model}[/green]")
            except Exception as e:
                console.print(f"[red]✗ Failed speed test for {model}: {e}[/red]")
                continue
        
        return results
    
    def display_results(self, results: List[SpeedTestResult]):
        """Display speed test results in a formatted table."""
        if not results:
            console.print("[red]No results to display[/red]")
            return
        
        console.print("\n[bold cyan]Embedding Speed Test Results[/bold cyan]")
        
        table = Table(title="Speed Test Comparison")
        table.add_column("Model", style="bold")
        table.add_column("Items", style="cyan")
        table.add_column("Total Time (s)", style="green")
        table.add_column("Avg Time/Item (s)", style="yellow")
        table.add_column("Items/Second", style="magenta")
        table.add_column("Dimension", style="blue")
        table.add_column("Success %", style="green")
        
        for result in results:
            total_items = result.total_jobs + result.total_resumes
            table.add_row(
                result.model_name,
                f"{total_items} ({result.total_jobs}J, {result.total_resumes}R)",
                f"{result.total_time:.2f}",
                f"{result.avg_time_per_item:.3f}",
                f"{result.items_per_second:.2f}",
                str(result.embedding_dimension),
                f"{result.success_rate:.1f}%"
            )
        
        console.print(table)
        
        # Find fastest model
        if len(results) > 1:
            fastest = min(results, key=lambda x: x.avg_time_per_item if x.avg_time_per_item > 0 else float('inf'))
            console.print(f"\n[bold green]🏆 Fastest model: {fastest.model_name} ({fastest.avg_time_per_item:.3f}s per item)[/bold green]")
    
    def save_results(self, results: List[SpeedTestResult], output_file: str):
        """Save speed test results to JSON file."""
        results_data = {
            'test_date': datetime.now().isoformat(),
            'total_models_tested': len(results),
            'results': []
        }
        
        for result in results:
            results_data['results'].append({
                'model_name': result.model_name,
                'total_jobs': result.total_jobs,
                'total_resumes': result.total_resumes,
                'job_embedding_time': result.job_embedding_time,
                'resume_embedding_time': result.resume_embedding_time,
                'total_time': result.total_time,
                'avg_time_per_item': result.avg_time_per_item,
                'items_per_second': result.items_per_second,
                'embedding_dimension': result.embedding_dimension,
                'success_rate': result.success_rate
            })
        
        with open(output_file, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        console.print(f"[green]✓ Saved speed test results to {output_file}[/green]")


@click.group()
def cli():
    """SoupBoss Embedding Speed Test - Focused performance testing for embedding generation."""
    pass


@cli.command("list")
def list_models():
    """List available embedding models."""
    tester = EmbeddingSpeedTester()
    tester.list_available_models()


@cli.command("test")
@click.option("--models", "-m", help="Comma-separated list of models to test (default: all available)")
@click.option("--force", is_flag=True, help="Force regeneration of existing embeddings")
@click.option("--save", help="Save results to JSON file")
def run_speed_test(models, force, save):
    """Run embedding speed test for specified models."""
    tester = EmbeddingSpeedTester()
    
    if models:
        models_to_test = [m.strip() for m in models.split(',')]
    else:
        models_to_test = tester.available_models
        if not models_to_test:
            console.print("[red]No embedding models available. Make sure Ollama is running with embedding models.[/red]")
            return
    
    # Validate models
    invalid_models = [m for m in models_to_test if m not in tester.available_models]
    if invalid_models:
        console.print(f"[red]Invalid models: {', '.join(invalid_models)}[/red]")
        console.print("Use 'embedding_speed_test.py list' to see available models")
        return
    
    results = tester.run_comparison_test(models_to_test, force)
    tester.display_results(results)
    
    if save and results:
        tester.save_results(results, save)


@cli.command("single")
@click.argument("model_name")
@click.option("--force", is_flag=True, help="Force regeneration of existing embeddings")
def test_single_model(model_name, force):
    """Test a single model for embedding speed."""
    tester = EmbeddingSpeedTester()
    
    if model_name not in tester.available_models:
        console.print(f"[red]Model '{model_name}' not available[/red]")
        console.print("Use 'embedding_speed_test.py list' to see available models")
        return
    
    try:
        result = tester.run_speed_test(model_name, force)
        tester.display_results([result])
    except Exception as e:
        console.print(f"[red]Speed test failed: {e}[/red]")


if __name__ == "__main__":
    cli()