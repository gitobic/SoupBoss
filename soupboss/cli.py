#!/usr/bin/env python3
"""
SoupBoss CLI - Main command-line interface for job matching system.
"""

import click
import os
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def main():
    """SoupBoss - Intelligent job matching system with semantic similarity scoring."""
    pass


@main.group()
def jobs():
    """Manage job listings from Greenhouse, Lever, SmartRecruiters APIs and Disney data files."""
    pass


@jobs.command("fetch")
@click.option("--source", type=click.Choice(["greenhouse", "lever", "smartrecruiters"]), required=True,
              help="API source to fetch from")
@click.option("--company", required=True, help="Company identifier")
@click.option("--limit", type=int, help="Maximum number of jobs to fetch")
@click.option("--companies-file", "-f", type=click.Path(exists=True), 
              help="File containing list of companies to process")
def fetch_jobs(source, company, limit, companies_file):
    """Fetch job listings from API sources."""
    from .ingestion import get_ingester
    
    try:
        ingester = get_ingester()
        
        if companies_file:
            console.print(f"[cyan]Bulk processing companies from {companies_file}...[/cyan]")
            results = ingester.ingest_from_file_list(source, companies_file, limit)
            
            # Show summary
            total_processed = sum(r[0] for r in results.values())
            total_saved = sum(r[1] for r in results.values())
            
            table = Table(title=f"Bulk Ingestion Results - {source.title()}")
            table.add_column("Company", style="cyan")
            table.add_column("Processed", style="yellow")
            table.add_column("Saved", style="green")
            
            for company_name, (processed, saved) in results.items():
                table.add_row(company_name, str(processed), str(saved))
            
            table.add_row("TOTAL", str(total_processed), str(total_saved), style="bold")
            console.print(table)
            
        else:
            processed, saved = ingester.ingest_company_jobs(source, company, limit)
            console.print(f"[green]Successfully processed {processed} jobs, saved {saved} to database[/green]")
            
    except Exception as e:
        console.print(f"[red]Error during job ingestion: {e}[/red]")
        raise click.Abort()


@jobs.command("list")
@click.option("--company", help="Filter by company name")
@click.option("--source", type=click.Choice(["greenhouse", "lever", "smartrecruiters", "disney"]), help="Filter by source")
@click.option("--limit", type=int, default=50, help="Maximum jobs to display")
@click.option("--pdf", type=click.Path(), help="Export results to PDF file")
def list_jobs(company, source, limit, pdf):
    """List all stored job postings."""
    from .db import get_db
    
    try:
        with get_db() as db:
            # Get company ID if filtering by company
            company_id = None
            if company:
                companies = db.get_companies()
                for c in companies:
                    if c['name'].lower() == company.lower():
                        company_id = c['id']
                        break
                if company_id is None:
                    console.print(f"[red]Company '{company}' not found[/red]")
                    return
            
            jobs = db.get_jobs(company_id=company_id, source=source)
            
            if not jobs:
                console.print("[yellow]No jobs found matching criteria[/yellow]")
                return
            
            # Show up to limit
            display_jobs = jobs[:limit]
            
            table = Table(title=f"Job Listings ({len(display_jobs)} of {len(jobs)})")
            table.add_column("ID", style="cyan", width=6)
            table.add_column("Company", style="green")
            table.add_column("Title", style="bold")
            table.add_column("Department", style="yellow")
            table.add_column("Location", style="magenta")
            table.add_column("Source", style="blue")
            
            for job in display_jobs:
                table.add_row(
                    str(job['id']),
                    job['company_name'],
                    job['title'][:40] + "..." if len(job['title']) > 40 else job['title'],
                    job['department'] or "N/A",
                    job['location'] or "N/A",
                    job['source']
                )
            
            # Export to PDF if requested
            if pdf:
                from .pdf_export import get_pdf_exporter, generate_pdf_filename
                
                pdf_path = pdf if pdf.endswith('.pdf') else f"{pdf}.pdf"
                exporter = get_pdf_exporter()
                
                # Prepare filter info for PDF
                filters = {}
                if company:
                    filters['company'] = company
                if source:
                    filters['source'] = source
                if limit < len(jobs):
                    filters['limit'] = limit
                
                exporter.export_jobs_list(display_jobs, pdf_path, filters=filters)
                console.print(f"[green]✓ Exported {len(display_jobs)} jobs to {pdf_path}[/green]")
            else:
                console.print(table)
                
                if len(jobs) > limit:
                    console.print(f"[dim]Showing {limit} of {len(jobs)} total jobs. Use --limit to see more.[/dim]")
                
    except Exception as e:
        console.print(f"[red]Error listing jobs: {e}[/red]")
        raise click.Abort()


@jobs.command("clean")
def clean_jobs():
    """Remove all job data from storage."""
    if click.confirm("Are you sure you want to delete all job data?"):
        from .db import get_db
        
        try:
            with get_db() as db:
                job_count = db.get_job_count()
                console.print(f"[red]Removing {job_count} jobs from database...[/red]")
                db.clear_jobs()
                console.print("[green]Job data cleared successfully[/green]")
        except Exception as e:
            console.print(f"[red]Error cleaning job data: {e}[/red]")
            raise click.Abort()


@main.group()
def companies():
    """Manage company sources for job fetching."""
    pass


@companies.command("add")
@click.argument("name")
@click.option("--source", type=click.Choice(["greenhouse", "lever", "smartrecruiters"]), required=True,
              help="API source")
def add_company(name, source):
    """Add a company to track."""
    from .db import get_db
    
    try:
        with get_db() as db:
            company_id = db.add_company(name, source)
            console.print(f"[green]Added company '{name}' (ID: {company_id}) for {source}[/green]")
    except Exception as e:
        console.print(f"[red]Error adding company: {e}[/red]")
        raise click.Abort()


@companies.command("list")
@click.option("--pdf", type=click.Path(), help="Export results to PDF file")
def list_companies(pdf):
    """List all tracked companies."""
    from .db import get_db
    
    try:
        with get_db() as db:
            companies = db.get_companies()
            
            if not companies:
                console.print("[yellow]No companies configured[/yellow]")
                return
            
            table = Table(title="Tracked Companies")
            table.add_column("ID", style="cyan", width=6)
            table.add_column("Name", style="bold")
            table.add_column("Source", style="green")
            table.add_column("Status", style="yellow")
            table.add_column("Created", style="dim")
            
            for company in companies:
                table.add_row(
                    str(company['id']),
                    company['name'],
                    company['source'],
                    "Active" if company['active'] else "Inactive",
                    company['created_at'][:10]  # Show just date
                )
            
            # Export to PDF if requested
            if pdf:
                from .pdf_export import get_pdf_exporter
                
                pdf_path = pdf if pdf.endswith('.pdf') else f"{pdf}.pdf"
                exporter = get_pdf_exporter()
                
                # Prepare companies data for PDF export
                companies_data = []
                for company in companies:
                    companies_data.append({
                        'id': company['id'],
                        'name': company['name'],
                        'source': company['source'],
                        'status': "Active" if company['active'] else "Inactive",
                        'created_at': company['created_at']
                    })
                
                exporter.export_companies_list(companies_data, pdf_path)
                console.print(f"[green]✓ Exported {len(companies)} companies to {pdf_path}[/green]")
            else:
                console.print(table)
                
    except Exception as e:
        console.print(f"[red]Error listing companies: {e}[/red]")
        raise click.Abort()


@companies.command("test")
@click.argument("name")
@click.option("--source", type=click.Choice(["greenhouse", "lever", "smartrecruiters", "disney"]), required=True,
              help="API source")
def test_company(name, source):
    """Test if company has active job board."""
    from .ingestion import GreenhouseAPI, LeverAPI, SmartRecruitersAPI
    
    try:
        if source == "greenhouse":
            api = GreenhouseAPI(name)
        elif source == "lever":
            api = LeverAPI(name)
        elif source == "smartrecruiters":
            api = SmartRecruitersAPI(name)
        else:  # disney
            console.print(f"[yellow]Disney source requires file import. Use 'jobs import' command instead.[/yellow]")
            return
        
        console.print(f"[cyan]Testing {name} on {source}...[/cyan]")
        
        if api.test_company():
            console.print(f"[green]✓ {name} has active {source} job board[/green]")
        else:
            console.print(f"[red]✗ {name} not found on {source} or unreachable[/red]")
    except Exception as e:
        console.print(f"[red]Error testing company: {e}[/red]")
        raise click.Abort()


@main.group()
def resumes():
    """Manage resume files and profiles."""
    pass


@resumes.command("add")
@click.argument("resume_path", type=click.Path(exists=True))
@click.option("--name", help="Name for this resume profile")
def add_resume(resume_path, name):
    """Add a resume file to the system."""
    from .resumes import get_resume_manager
    
    try:
        manager = get_resume_manager()
        
        # Show file info first
        file_info = manager.get_file_info(resume_path)
        if "error" in file_info:
            console.print(f"[red]{file_info['error']}[/red]")
            return
        
        console.print(f"[cyan]Processing file: {file_info['name']} ({file_info['size_mb']} MB)[/cyan]")
        
        if not file_info['supported']:
            console.print(f"[red]Unsupported file type: {file_info['extension']}[/red]")
            console.print("[dim]Supported types: .pdf, .txt, .md[/dim]")
            return
        
        if file_info['too_large']:
            console.print("[red]File too large (max 10MB)[/red]")
            return
        
        # Process the resume
        resume_id = manager.add_resume(resume_path, name)
        
        if resume_id:
            console.print(f"[green]✓ Resume added successfully (ID: {resume_id})[/green]")
        else:
            console.print("[red]✗ Failed to add resume[/red]")
            
    except Exception as e:
        console.print(f"[red]Error adding resume: {e}[/red]")
        raise click.Abort()


@resumes.command("list")
@click.option("--preview", is_flag=True, help="Show content preview")
def list_resumes(preview):
    """List all stored resumes."""
    from .resumes import get_resume_manager
    
    try:
        manager = get_resume_manager()
        resumes = manager.list_resumes()
        
        if not resumes:
            console.print("[yellow]No resumes found[/yellow]")
            return
        
        # Show statistics
        stats = manager.get_stats()
        console.print(f"[dim]{stats['total']} resumes • {stats['total_size_mb']} MB total[/dim]")
        
        table = Table(title="Stored Resumes")
        table.add_column("ID", style="cyan", width=6)
        table.add_column("Name", style="bold")
        table.add_column("Type", style="green", width=8)
        table.add_column("Size", style="yellow", width=8)
        table.add_column("Added", style="dim")
        if preview:
            table.add_column("Preview", style="white", max_width=50)
        
        for resume in resumes:
            size_mb = round(resume['file_size'] / (1024 * 1024), 2)
            
            row_data = [
                str(resume['id']),
                resume['name'],
                resume['file_type'].upper(),
                f"{size_mb}MB",
                resume['created_at'][:10]  # Show just date
            ]
            
            if preview:
                preview_text = manager.get_resume_preview(resume['id'], 100)
                if preview_text:
                    # Clean preview for table display
                    preview_clean = preview_text.replace('\n', ' ').strip()
                    if len(preview_clean) > 50:
                        preview_clean = preview_clean[:47] + "..."
                    row_data.append(preview_clean)
                else:
                    row_data.append("[dim]No preview[/dim]")
            
            table.add_row(*row_data)
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing resumes: {e}[/red]")
        raise click.Abort()


@resumes.command("remove")
@click.argument("resume_id", type=int)
def remove_resume(resume_id):
    """Remove a resume from the system."""
    from .resumes import get_resume_manager
    
    try:
        manager = get_resume_manager()
        
        # Get resume info first
        resume = manager.get_resume(resume_id)
        if not resume:
            console.print(f"[red]Resume {resume_id} not found[/red]")
            return
        
        console.print(f"[yellow]Resume: {resume['name']} ({resume['file_type'].upper()})[/yellow]")
        
        if click.confirm(f"Remove resume {resume_id}?"):
            success = manager.remove_resume(resume_id)
            if success:
                console.print(f"[green]✓ Resume {resume_id} removed successfully[/green]")
            else:
                console.print(f"[red]✗ Failed to remove resume {resume_id}[/red]")
        
    except Exception as e:
        console.print(f"[red]Error removing resume: {e}[/red]")
        raise click.Abort()


@resumes.command("show")
@click.argument("resume_id", type=int)
@click.option("--full", is_flag=True, help="Show full content instead of preview")
def show_resume(resume_id, full):
    """Show resume details and content."""
    from .resumes import get_resume_manager
    
    try:
        manager = get_resume_manager()
        resume = manager.get_resume(resume_id)
        
        if not resume:
            console.print(f"[red]Resume {resume_id} not found[/red]")
            return
        
        # Show metadata
        console.print(f"[bold cyan]Resume: {resume['name']}[/bold cyan]")
        console.print(f"ID: {resume['id']}")
        console.print(f"Type: {resume['file_type'].upper()}")
        console.print(f"Size: {round(resume['file_size'] / 1024, 1)} KB")
        console.print(f"File: {resume['file_path']}")
        console.print(f"Added: {resume['created_at']}")
        console.print()
        
        # Show content
        if full:
            console.print("[bold]Full Content:[/bold]")
            console.print(resume['content_text'])
        else:
            preview = manager.get_resume_preview(resume_id, 1000)
            console.print("[bold]Content Preview:[/bold]")
            console.print(preview)
            
            if len(resume['content_text']) > 1000:
                console.print(f"\n[dim]... ({len(resume['content_text']) - 1000} more characters)[/dim]")
                console.print("[dim]Use --full to see complete content[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error showing resume: {e}[/red]")
        raise click.Abort()


@resumes.command("rename")
@click.argument("resume_id", type=int)
@click.argument("new_name")
def rename_resume(resume_id, new_name):
    """Rename a resume."""
    from .resumes import get_resume_manager
    
    try:
        manager = get_resume_manager()
        
        # Check if resume exists
        resume = manager.get_resume(resume_id)
        if not resume:
            console.print(f"[red]Resume {resume_id} not found[/red]")
            return
        
        success = manager.update_resume_name(resume_id, new_name)
        if success:
            console.print(f"[green]✓ Renamed resume {resume_id}: '{resume['name']}' → '{new_name}'[/green]")
        else:
            console.print(f"[red]✗ Failed to rename resume {resume_id}[/red]")
        
    except Exception as e:
        console.print(f"[red]Error renaming resume: {e}[/red]")
        raise click.Abort()


@main.group()
def match():
    """Run job matching and generate reports."""
    pass


@match.command("generate")
@click.option("--jobs-only", is_flag=True, help="Generate embeddings for jobs only")
@click.option("--resumes-only", is_flag=True, help="Generate embeddings for resumes only")
@click.option("--force", is_flag=True, help="Force regeneration of existing embeddings")
def generate_embeddings(jobs_only, resumes_only, force):
    """Generate embeddings for jobs and resumes."""
    from .matching import get_intelligence_engine
    
    try:
        engine = get_intelligence_engine()
        
        if jobs_only:
            job_count = engine.embedding_pipeline.generate_job_embeddings(force_regenerate=force)
            console.print(f"[green]Generated {job_count} job embeddings[/green]")
        elif resumes_only:
            resume_count = engine.embedding_pipeline.generate_resume_embeddings(force_regenerate=force)
            console.print(f"[green]Generated {resume_count} resume embeddings[/green]")
        else:
            job_count, resume_count = engine.generate_all_embeddings(force_regenerate=force)
            console.print(f"[green]Generated {job_count} job embeddings and {resume_count} resume embeddings[/green]")
        
        # Show updated stats
        stats = engine.get_embedding_stats()
        console.print(f"\n[cyan]Embedding Coverage:[/cyan]")
        console.print(f"Jobs: {stats['jobs']['with_embeddings']}/{stats['jobs']['total']} ({stats['jobs']['coverage_percent']}%)")
        console.print(f"Resumes: {stats['resumes']['with_embeddings']}/{stats['resumes']['total']} ({stats['resumes']['coverage_percent']}%)")
        
    except Exception as e:
        console.print(f"[red]Error generating embeddings: {e}[/red]")
        raise click.Abort()


@match.command("run")
@click.option("--resume-id", type=int, help="Specific resume to match against")
@click.option("--job-ids", help="Comma-separated list of job IDs to match against")
@click.option("--limit", type=int, default=50, help="Maximum matches to return")
def run_matching(resume_id, job_ids, limit):
    """Run similarity matching between resumes and jobs."""
    from .matching import get_intelligence_engine
    
    try:
        engine = get_intelligence_engine()
        
        # Parse job IDs if provided
        job_id_list = None
        if job_ids:
            try:
                job_id_list = [int(x.strip()) for x in job_ids.split(',')]
            except ValueError:
                console.print("[red]Invalid job IDs format. Use comma-separated integers.[/red]")
                return
        
        # Parse resume IDs if provided
        resume_id_list = [resume_id] if resume_id else None
        
        console.print("[cyan]Running similarity matching...[/cyan]")
        results = engine.run_matching(resume_ids=resume_id_list, job_ids=job_id_list)
        
        if not results:
            console.print("[yellow]No matches found. Make sure embeddings are generated.[/yellow]")
            return
        
        # Show top results
        display_results = results[:limit]
        
        table = Table(title=f"Top Matches ({len(display_results)} of {len(results)})")
        table.add_column("Score", style="bold green", width=8)
        table.add_column("Resume", style="cyan")
        table.add_column("Job Title", style="bold")
        table.add_column("Company", style="yellow")
        table.add_column("Department", style="dim")
        table.add_column("Location", style="magenta")
        
        for result in display_results:
            table.add_row(
                f"{result.similarity_score:.3f}",
                result.resume_name,
                result.job_title[:30] + "..." if len(result.job_title) > 30 else result.job_title,
                result.company_name,
                result.job_department or "N/A",
                result.job_location or "N/A"
            )
        
        console.print(table)
        
        if len(results) > limit:
            console.print(f"[dim]Showing top {limit} matches. Use --limit to see more.[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error during matching: {e}[/red]")
        raise click.Abort()


@match.command("show")
@click.argument("resume_id", type=int)
@click.option("--limit", type=int, default=10, help="Number of top matches to show")
@click.option("--pdf", type=click.Path(), help="Export results to PDF file")
def show_matches(resume_id, limit, pdf):
    """Show top matches for a specific resume."""
    from .matching import get_intelligence_engine
    
    try:
        engine = get_intelligence_engine()
        
        # Check if resume exists
        resume = engine.db.get_resume(resume_id)
        if not resume:
            console.print(f"[red]Resume {resume_id} not found[/red]")
            return
        
        console.print(f"[bold cyan]Top matches for: {resume['name']}[/bold cyan]")
        
        results = engine.get_resume_matches(resume_id, limit)
        
        if not results:
            console.print("[yellow]No matches found. Run matching first with 'match run'.[/yellow]")
            return
        
        table = Table(title=f"Top {len(results)} Matches")
        table.add_column("Rank", style="dim", width=6)
        table.add_column("Score", style="bold green", width=8)
        table.add_column("Job Title", style="bold")
        table.add_column("Company", style="yellow")
        table.add_column("Department", style="dim")
        table.add_column("Location", style="magenta")
        
        for i, result in enumerate(results, 1):
            table.add_row(
                str(i),
                f"{result.similarity_score:.3f}",
                result.job_title,
                result.company_name,
                result.job_department or "N/A",
                result.job_location or "N/A"
            )
        
        # Export to PDF if requested
        if pdf:
            from .pdf_export import get_pdf_exporter
            
            pdf_path = pdf if pdf.endswith('.pdf') else f"{pdf}.pdf"
            exporter = get_pdf_exporter()
            
            # Prepare match results data for PDF export
            matches_data = []
            for result in results:
                matches_data.append({
                    'similarity_score': result.similarity_score,
                    'resume_name': result.resume_name,
                    'job_title': result.job_title,
                    'company_name': result.company_name,
                    'job_department': result.job_department
                })
            
            # Prepare filter info for PDF
            filters = {'resume_name': resume['name']}
            
            exporter.export_match_results(matches_data, pdf_path, 
                                        title=f"Match Results for {resume['name']}", filters=filters)
            console.print(f"[green]✓ Exported {len(results)} matches to {pdf_path}[/green]")
        else:
            console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error showing matches: {e}[/red]")
        raise click.Abort()


@match.command("compare-models")
@click.option("--models", help="Comma-separated list of models to compare (default: all available)")
@click.option("--force", is_flag=True, help="Force regeneration of embeddings")
@click.option("--save", help="Save results to JSON file")
def compare_models(models, force, save):
    """Compare different embedding models for matching accuracy.
    
    METRICS EXPLAINED:
    
    • Avg Score: Mean cosine similarity of top 10 matches from a random sample of 
      resume-job pairs. Uses random sampling (ORDER BY RANDOM()) so results vary 
      between runs. Higher scores indicate better semantic matching quality.
      
    • Diversity: Percentage of unique jobs appearing in top 10 matches across all 
      resumes. Formula: (unique_jobs_in_top10_matches / total_jobs_available) × 100.
      Higher diversity means the model finds varied job matches rather than always 
      recommending the same jobs.
      
    • Coverage: Percentage of jobs/resumes that have embeddings generated for this model.
    
    • Dimension: Vector size of the embeddings (e.g., 768 dimensions).
    
    Note: Avg Score results differ between runs due to random sampling. For consistent 
    comparisons, save results with --save and compare multiple runs.
    """
    from .embedding_evaluation import get_model_evaluator
    
    try:
        evaluator = get_model_evaluator()
        
        # Parse models list
        models_to_compare = None
        if models:
            models_to_compare = [m.strip() for m in models.split(',')]
        
        console.print(f"[cyan]Starting embedding model comparison...[/cyan]")
        
        # Run comparison
        comparison = evaluator.compare_models(models_to_compare or [], force_regenerate=force)
        
        # Print results
        evaluator.print_comparison_results(comparison)
        
        # Save results if requested
        if save:
            evaluator.save_comparison_results(comparison, save)
        
    except Exception as e:
        console.print(f"[red]Error comparing models: {e}[/red]")
        raise click.Abort()


@match.command("switch-model")
@click.argument("model_name")
@click.option("--generate", is_flag=True, help="Generate embeddings for new model immediately")
def switch_model(model_name, generate):
    """Switch to a different embedding model."""
    import os
    
    try:
        # Check if model is available
        from .embeddings import OllamaEmbeddingClient
        client = OllamaEmbeddingClient(model=model_name)
        
        if not client.ensure_model_ready():
            console.print(f"[red]Model {model_name} is not available[/red]")
            return
        
        # Update environment variable or config
        console.print(f"[cyan]Switching to embedding model: {model_name}[/cyan]")
        
        # TODO: Add persistent config setting
        console.print(f"[yellow]Note: To make this permanent, update your configuration[/yellow]")
        console.print(f"[yellow]Current session will use {model_name}[/yellow]")
        
        if generate:
            console.print(f"[cyan]Generating embeddings with {model_name}...[/cyan]")
            from .embedding_evaluation import get_model_evaluator
            evaluator = get_model_evaluator()
            evaluation = evaluator.generate_embeddings_for_model(model_name)
            console.print(f"[green]✓ Generated {evaluation.total_jobs} job and {evaluation.total_resumes} resume embeddings[/green]")
        
    except Exception as e:
        console.print(f"[red]Error switching model: {e}[/red]")
        raise click.Abort()


@match.command("list-models")
def list_models():
    """List available embedding models."""
    from .embedding_evaluation import get_model_evaluator
    
    try:
        evaluator = get_model_evaluator()
        available = evaluator.available_models
        
        console.print(f"[cyan]Available embedding models ({len(available)}):[/cyan]")
        
        # Get current models in database
        from .db import get_db
        with get_db() as db:
            cursor = db.conn.execute("""
                SELECT embedding_model, COUNT(*) as job_count
                FROM job_embeddings 
                GROUP BY embedding_model
            """)
            current_models = {row[0]: row[1] for row in cursor.fetchall()}
            
            cursor = db.conn.execute("""
                SELECT embedding_model, COUNT(*) as resume_count
                FROM resume_embeddings 
                GROUP BY embedding_model
            """)
            resume_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        table = Table(title="Embedding Models")
        table.add_column("Model", style="bold")
        table.add_column("Status", style="green")
        table.add_column("Job Embeddings", style="cyan")
        table.add_column("Resume Embeddings", style="yellow")
        
        for model in available:
            status = "Available"
            job_count = current_models.get(model, 0)
            resume_count = resume_counts.get(model, 0)
            
            if job_count > 0 or resume_count > 0:
                status = "In Use"
            
            table.add_row(model, status, str(job_count), str(resume_count))
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing models: {e}[/red]")
        raise click.Abort()


@match.command("stats")
def show_stats():
    """Show embedding and matching statistics."""
    from .matching import get_intelligence_engine
    
    try:
        engine = get_intelligence_engine()
        stats = engine.get_embedding_stats()
        
        console.print("[bold cyan]Intelligence Engine Statistics[/bold cyan]")
        console.print(f"Model: {stats['model']}")
        console.print()
        
        # Embedding coverage
        table = Table(title="Embedding Coverage")
        table.add_column("Type", style="cyan")
        table.add_column("Total", style="yellow")
        table.add_column("With Embeddings", style="green")
        table.add_column("Coverage", style="bold")
        
        table.add_row(
            "Jobs", 
            str(stats['jobs']['total']),
            str(stats['jobs']['with_embeddings']),
            f"{stats['jobs']['coverage_percent']}%"
        )
        
        table.add_row(
            "Resumes", 
            str(stats['resumes']['total']),
            str(stats['resumes']['with_embeddings']),
            f"{stats['resumes']['coverage_percent']}%"
        )
        
        console.print(table)
        
        # Match results count
        cursor = engine.db.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as total FROM match_results WHERE embedding_model = ?",
            (engine.model_name,)
        )
        total_matches = cursor.fetchone()["total"]
        
        console.print(f"\nTotal match results: {total_matches}")
        
        if stats['jobs']['coverage_percent'] < 100 or stats['resumes']['coverage_percent'] < 100:
            console.print("\n[yellow]💡 Run 'match generate' to create missing embeddings[/yellow]")
        
    except Exception as e:
        console.print(f"[red]Error showing statistics: {e}[/red]")
        raise click.Abort()


@match.command("export")
@click.option("--format", type=click.Choice(["csv", "json", "html"]), default="csv", help="Export format")
@click.option("--output", "-o", help="Output file path")
@click.option("--resume-id", type=int, help="Export matches for specific resume only")
@click.option("--limit", type=int, help="Limit number of results to export")
def export_results(format, output, resume_id, limit):
    """Export matching results to various formats."""
    from .export import get_export_manager
    
    try:
        export_manager = get_export_manager()
        
        console.print(f"[cyan]Exporting match results as {format.upper()}...[/cyan]")
        
        output_path = export_manager.export_match_results(
            format=format,
            output_path=output,
            resume_id=resume_id,
            limit=limit
        )
        
        if output_path:
            console.print(f"[green]✓ Export completed: {output_path}[/green]")
        
    except Exception as e:
        console.print(f"[red]Error exporting results: {e}[/red]")
        raise click.Abort()


@jobs.command("import")
@click.option("--source", type=click.Choice(["disney"]), required=True,
              help="Data source type for import")
@click.option("--company", default="disney", help="Company identifier (default: disney)")
@click.option("--file", "data_file", type=click.Path(exists=True), required=True,
              help="Data file to import from")
@click.option("--limit", type=int, help="Maximum number of jobs to import")
def import_jobs(source, company, data_file, limit):
    """Import job listings from data files."""
    from .ingestion import get_ingester
    
    try:
        ingester = get_ingester()
        processed, saved = ingester.import_from_file(source, company, data_file, limit)
        console.print(f"[green]Successfully imported {processed} jobs, saved {saved} to database[/green]")
        
    except Exception as e:
        console.print(f"[red]Error importing jobs: {e}[/red]")
        sys.exit(1)


@jobs.command("export")
@click.option("--format", type=click.Choice(["csv", "json", "html"]), default="csv", help="Export format")
@click.option("--output", "-o", help="Output file path")
@click.option("--company", help="Filter by company name")
@click.option("--source", type=click.Choice(["greenhouse", "lever", "smartrecruiters", "disney"]), help="Filter by source")
def export_jobs(format, output, company, source):
    """Export job listings to various formats."""
    from .export import get_export_manager
    
    try:
        export_manager = get_export_manager()
        
        # Get company ID if filtering by company
        company_id = None
        if company:
            with export_manager.db as db:
                companies = db.get_companies()
                for c in companies:
                    if c['name'].lower() == company.lower():
                        company_id = c['id']
                        break
                if company_id is None:
                    console.print(f"[red]Company '{company}' not found[/red]")
                    return
        
        console.print(f"[cyan]Exporting jobs as {format.upper()}...[/cyan]")
        
        output_path = export_manager.export_jobs(
            format=format,
            output_path=output,
            company_id=company_id,
            source=source
        )
        
        if output_path:
            console.print(f"[green]✓ Export completed: {output_path}[/green]")
        
    except Exception as e:
        console.print(f"[red]Error exporting jobs: {e}[/red]")
        raise click.Abort()


@resumes.command("export")
@click.option("--format", type=click.Choice(["csv", "json", "html"]), default="csv", help="Export format")
@click.option("--output", "-o", help="Output file path")
def export_resumes(format, output):
    """Export resume listings to various formats."""
    from .export import get_export_manager
    
    try:
        export_manager = get_export_manager()
        
        console.print(f"[cyan]Exporting resumes as {format.upper()}...[/cyan]")
        
        output_path = export_manager.export_resumes(
            format=format,
            output_path=output
        )
        
        if output_path:
            console.print(f"[green]✓ Export completed: {output_path}[/green]")
        
    except Exception as e:
        console.print(f"[red]Error exporting resumes: {e}[/red]")
        raise click.Abort()


@main.command("report")
@click.option("--format", type=click.Choice(["html", "json"]), default="html", help="Report format")
@click.option("--output", "-o", help="Output file path")
def generate_report(format, output):
    """Generate comprehensive summary report."""
    from .export import get_export_manager
    
    try:
        export_manager = get_export_manager()
        
        console.print(f"[cyan]Generating summary report as {format.upper()}...[/cyan]")
        
        output_path = export_manager.generate_summary_report(
            format=format,
            output_path=output
        )
        
        if output_path:
            console.print(f"[green]✓ Report generated: {output_path}[/green]")
            if format == "html":
                console.print(f"[dim]Open in browser: file://{os.path.abspath(output_path)}[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error generating report: {e}[/red]")
        raise click.Abort()


@main.group()
def maintenance():
    """Data cleanup and maintenance operations."""
    pass


@maintenance.command("stats")
def show_maintenance_stats():
    """Show detailed system statistics."""
    from .maintenance import DataManager
    
    try:
        manager = DataManager()
        manager.display_system_stats()
        
    except Exception as e:
        console.print(f"[red]Error showing maintenance stats: {e}[/red]")
        raise click.Abort()


@maintenance.command("clear-jobs")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def clear_jobs_data(force):
    """Clear all job data including embeddings and matches."""
    from .maintenance import DataManager
    
    try:
        manager = DataManager()
        success = manager.clear_jobs_data(confirm=not force)
        
        if success:
            console.print("[cyan]💡 Tip: Run 'companies list' to see remaining companies[/cyan]")
        
    except Exception as e:
        console.print(f"[red]Error clearing job data: {e}[/red]")
        raise click.Abort()


@maintenance.command("clear-resumes")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def clear_resumes_data(force):
    """Clear all resume data including embeddings and matches."""
    from .maintenance import DataManager
    
    try:
        manager = DataManager()
        success = manager.clear_resumes_data(confirm=not force)
        
        if success:
            console.print("[cyan]💡 Tip: Upload new resumes with 'resumes add'[/cyan]")
        
    except Exception as e:
        console.print(f"[red]Error clearing resume data: {e}[/red]")
        raise click.Abort()


@maintenance.command("clear-embeddings")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def clear_embeddings_cache(force):
    """Clear all embeddings cache forcing regeneration."""
    from .maintenance import DataManager
    
    try:
        manager = DataManager()
        success = manager.clear_embeddings_cache(confirm=not force)
        
        if success:
            console.print("[cyan]💡 Tip: Run 'match generate' to recreate embeddings[/cyan]")
        
    except Exception as e:
        console.print(f"[red]Error clearing embeddings cache: {e}[/red]")
        raise click.Abort()


@maintenance.command("clear-matches")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def clear_match_results(force):
    """Clear only match results, keeping jobs/resumes/embeddings."""
    from .maintenance import DataManager
    
    try:
        manager = DataManager()
        success = manager.clear_match_results(confirm=not force)
        
        if success:
            console.print("[cyan]💡 Tip: Run 'match run' to regenerate matches[/cyan]")
        
    except Exception as e:
        console.print(f"[red]Error clearing match results: {e}[/red]")
        raise click.Abort()


@maintenance.command("reset-system")
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def reset_system(force):
    """Complete system reset - clears ALL data including companies."""
    from .maintenance import DataManager
    
    try:
        manager = DataManager()
        success = manager.reset_system(confirm=not force)
        
        if success:
            console.print("[cyan]💡 System is now empty. Start fresh with 'companies add'[/cyan]")
        
    except Exception as e:
        console.print(f"[red]Error during system reset: {e}[/red]")
        raise click.Abort()


@maintenance.command("backup")
@click.option("--output", "-o", help="Backup file path")
def backup_database(output):
    """Create a backup of the current database."""
    from .maintenance import DataManager
    
    try:
        manager = DataManager()
        success = manager.backup_database(output)
        
    except Exception as e:
        console.print(f"[red]Error creating backup: {e}[/red]")
        raise click.Abort()


@maintenance.command("optimize")
def optimize_database():
    """Optimize database performance."""
    from .maintenance import DataManager
    
    try:
        manager = DataManager()
        success = manager.optimize_database()
        
    except Exception as e:
        console.print(f"[red]Error optimizing database: {e}[/red]")
        raise click.Abort()


@maintenance.command("validate")
def validate_data():
    """Validate data integrity and check for issues."""
    from .maintenance import DataManager
    
    try:
        manager = DataManager()
        is_valid = manager.validate_data_integrity()
        
        if not is_valid:
            console.print("[yellow]💡 Run 'maintenance cleanup' to fix issues automatically[/yellow]")
        
    except Exception as e:
        console.print(f"[red]Error validating data: {e}[/red]")
        raise click.Abort()


@maintenance.command("cleanup")
def cleanup_orphaned():
    """Clean up orphaned records and data inconsistencies."""
    from .maintenance import DataManager
    
    try:
        manager = DataManager()
        success = manager.cleanup_orphaned_data()
        
    except Exception as e:
        console.print(f"[red]Error cleaning up data: {e}[/red]")
        raise click.Abort()


@main.group()
def config():
    """Configure system settings."""
    pass


@config.command("show")
@click.option("--section", help="Show specific configuration section only")
def show_config(section):
    """Display current configuration."""
    from .config import get_config_manager
    
    try:
        config_manager = get_config_manager()
        
        if section:
            section_data = config_manager.get(section)
            if section_data:
                console.print(f"[bold cyan]{section.title()} Configuration:[/bold cyan]")
                for key, value in section_data.items():
                    console.print(f"  {key}: {value}")
            else:
                console.print(f"[red]Configuration section '{section}' not found[/red]")
        else:
            config_manager.display_config()
        
    except Exception as e:
        console.print(f"[red]Error showing configuration: {e}[/red]")
        raise click.Abort()


@config.command("set")
@click.argument("section")
@click.argument("key")
@click.argument("value")
def set_config(section, key, value):
    """Set configuration value (format: section key value)."""
    from .config import get_config_manager
    
    try:
        config_manager = get_config_manager()
        
        # Convert value to appropriate type based on existing config
        existing_value = config_manager.get(section, key)
        if existing_value is not None:
            if isinstance(existing_value, bool):
                value = value.lower() in ('true', '1', 'yes', 'on')
            elif isinstance(existing_value, int):
                try:
                    value = int(value)
                except ValueError:
                    console.print(f"[red]Invalid integer value: {value}[/red]")
                    return
            elif isinstance(existing_value, float):
                try:
                    value = float(value)
                except ValueError:
                    console.print(f"[red]Invalid float value: {value}[/red]")
                    return
        
        success = config_manager.set(section, key, value)
        if success:
            console.print(f"[green]✓ Set {section}.{key} = {value}[/green]")
        else:
            console.print(f"[red]✗ Failed to set configuration[/red]")
        
    except Exception as e:
        console.print(f"[red]Error setting configuration: {e}[/red]")
        raise click.Abort()


@config.command("env")
@click.argument("key")
@click.argument("value")
def set_env_var(key, value):
    """Set environment variable in .env file."""
    from .config import get_config_manager
    
    try:
        config_manager = get_config_manager()
        success = config_manager.set_env_var(key, value)
        if success:
            console.print(f"[green]✓ Set environment variable {key} = {value}[/green]")
            console.print("[dim]Configuration reloaded with new environment variable[/dim]")
        else:
            console.print(f"[red]✗ Failed to set environment variable[/red]")
        
    except Exception as e:
        console.print(f"[red]Error setting environment variable: {e}[/red]")
        raise click.Abort()


@config.command("unset")
@click.argument("key")
def unset_env_var(key):
    """Remove environment variable from .env file."""
    from .config import get_config_manager
    
    try:
        config_manager = get_config_manager()
        success = config_manager.unset_env_var(key)
        if success:
            console.print(f"[green]✓ Removed environment variable {key}[/green]")
        else:
            console.print(f"[red]✗ Failed to remove environment variable[/red]")
        
    except Exception as e:
        console.print(f"[red]Error removing environment variable: {e}[/red]")
        raise click.Abort()


@config.command("validate")
def validate_config():
    """Validate current configuration."""
    from .config import get_config_manager
    
    try:
        config_manager = get_config_manager()
        issues = config_manager.validate_config()
        
        if not issues:
            console.print("[green]✓ Configuration validation passed[/green]")
        else:
            console.print("[red]Configuration validation failed:[/red]")
            for issue in issues:
                console.print(f"[red]• {issue}[/red]")
        
    except Exception as e:
        console.print(f"[red]Error validating configuration: {e}[/red]")
        raise click.Abort()


@config.command("reset")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def reset_config(confirm):
    """Reset configuration to default values."""
    from .config import get_config_manager
    
    try:
        if not confirm:
            if not click.confirm("Reset all configuration to defaults?"):
                console.print("[yellow]Reset cancelled[/yellow]")
                return
        
        config_manager = get_config_manager()
        success = config_manager.reset_to_defaults()
        if success:
            console.print("[green]✓ Configuration reset to defaults[/green]")
        else:
            console.print("[red]✗ Failed to reset configuration[/red]")
        
    except Exception as e:
        console.print(f"[red]Error resetting configuration: {e}[/red]")
        raise click.Abort()


@config.command("template")
@click.option("--output", "-o", help="Output file path")
def export_template(output):
    """Export .env template file."""
    from .config import get_config_manager
    
    try:
        config_manager = get_config_manager()
        success = config_manager.export_env_template(output)
        if success:
            console.print("[cyan]💡 Edit the template file and rename to .env to use[/cyan]")
        
    except Exception as e:
        console.print(f"[red]Error exporting template: {e}[/red]")
        raise click.Abort()


@config.command("info")
def connection_info():
    """Show connection information for configured services."""
    from .config import get_config_manager
    
    try:
        config_manager = get_config_manager()
        info = config_manager.get_connection_info()
        
        console.print("[bold cyan]Service Connection Information[/bold cyan]")
        
        # Database info
        console.print(f"\n[bold]Database:[/bold]")
        console.print(f"  Path: {info['database']['path']}")
        console.print(f"  Exists: {'✓' if info['database']['exists'] else '✗'}")
        
        # Ollama info
        console.print(f"\n[bold]Ollama:[/bold]")
        console.print(f"  Host: {info['ollama']['host']}")
        console.print(f"  Port: {info['ollama']['port']}")
        console.print(f"  URL: {info['ollama']['url']}")
        console.print(f"  Model: {info['ollama']['model']}")
        
    except Exception as e:
        console.print(f"[red]Error getting connection info: {e}[/red]")
        raise click.Abort()


@main.command("status")
def status():
    """Show system status and statistics."""
    from .db import get_db
    
    console.print("[bold green]SoupBoss System Status[/bold green]")
    
    table = Table(title="System Overview")
    table.add_column("Component", style="cyan", no_wrap=True)
    table.add_column("Status", style="magenta")
    table.add_column("Details", style="green")
    
    # Database status
    try:
        with get_db() as db:
            job_count = db.get_job_count()
            resume_count = db.get_resume_count()
            companies = db.get_companies()
            
            table.add_row("Database", "Connected", f"SQLite with {len(companies)} companies")
            table.add_row("Jobs", str(job_count), f"Stored job postings")
            table.add_row("Resumes", str(resume_count), f"Uploaded resume files")
    except Exception as e:
        table.add_row("Database", "Error", f"Connection failed: {str(e)[:50]}")
        table.add_row("Jobs", "Unknown", "Database error")
        table.add_row("Resumes", "Unknown", "Database error")
    
    # Ollama status
    try:
        from .embeddings import get_embedding_client
        client = get_embedding_client()
        status_info = client.get_status()
        
        if status_info["connection"] and status_info["model_ready"]:
            table.add_row("Ollama", "Ready", f"Model: {status_info['model']}")
        elif status_info["connection"]:
            table.add_row("Ollama", "Connected", f"Model not ready: {status_info['model']}")
        else:
            table.add_row("Ollama", "Offline", status_info.get("error", "Connection failed"))
    except Exception as e:
        table.add_row("Ollama", "Error", f"Status check failed: {str(e)[:50]}")
    
    console.print(table)


@main.command("reset")
def reset():
    """Reset entire system (remove all data).""" 
    console.print("[yellow]⚠️  The 'reset' command has been moved to 'maintenance reset-system'[/yellow]")
    console.print("[cyan]💡 Use: soupboss maintenance reset-system[/cyan]")


@main.command("test-embedding")
@click.option("--text", default="This is a test sentence for embedding generation.",
              help="Text to use for testing embeddings")
def test_embedding(text):
    """Test the ollama embedding functionality."""
    from .embeddings import test_embedding_client
    
    success = test_embedding_client(text)
    if success:
        console.print("[bold green]Embedding test completed successfully![/bold green]")
    else:
        console.print("[bold red]Embedding test failed![/bold red]")


if __name__ == "__main__":
    main()