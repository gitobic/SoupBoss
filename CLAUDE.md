# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Package Management - CRITICAL

**ONLY use `uv` for package management, NEVER pip:**
- Install packages: `uv add package`
- Run tools: `uv run tool`
- Run the main application: `uv run python main.py`

**FORBIDDEN commands:**
- `uv pip install` 
- `@latest` syntax
- Any direct pip usage

## Core Commands

### Development and Testing
```bash
# Run the main application
uv run python main.py

# Check system status
uv run python main.py status

# Test embedding functionality
uv run python main.py test-embedding

# Generate comprehensive reports
uv run python main.py report --format html
```

### Common Workflow Commands
```bash
# Add company and fetch jobs
uv run python main.py companies add spacex --source greenhouse
uv run python main.py jobs fetch --source greenhouse --company spacex

# Add resume and run matching
uv run python main.py resumes add /path/to/resume.pdf --name "My Resume"
uv run python main.py match generate
uv run python main.py match run

# View results
uv run python main.py match show 1
```

### API Data Fetchers (Standalone Scripts)
```bash
# Test if company has job board
uv run python greenhouse_fetch.py -test spacex
uv run python lever_fetch.py -test leverdemo
uv run python smartrecruiters_fetch.py -test dynatrace1

# Fetch jobs from APIs
uv run python greenhouse_fetch.py -fetch spacex
uv run python lever_fetch.py -fetch leverdemo
uv run python smartrecruiters_fetch.py -fetch dynatrace1

# Import Disney data files
uv run python disney_data_importer.py -file disney_workday_html_100.json

# Bulk process from file
uv run python greenhouse_fetch.py -in companies.txt -split -out ./data/
```

## System Architecture

SoupBoss is an intelligent job matching system with a complete CLI interface organized into 7 command groups:

### Core Modules (soupboss/ package)
1. **cli.py** - Complete Click-based CLI with 40+ commands across 7 groups
2. **db.py** - SQLite database with vector support using SoupBossDB class  
3. **embeddings.py** - Ollama client integration with nomic-embed-text model
4. **ingestion.py** - Unified job fetching from Greenhouse and Lever APIs
5. **matching.py** - Intelligence engine with embedding generation and cosine similarity
6. **export.py** - Professional export system (CSV/JSON/HTML)
7. **maintenance.py** - Data cleanup, backup, optimization, and system reset
8. **config.py** - Configuration management with .env and JSON persistence

### Data Flow
1. **Ingestion**: Jobs fetched from APIs (Greenhouse, Lever, SmartRecruiters) and Disney data files
2. **Storage**: SQLite database with vector extensions for embeddings
3. **Processing**: Multi-format resume processing (PDF/DOCX/TXT/MD)
4. **AI Matching**: Semantic embeddings via Ollama + cosine similarity scoring
5. **Export**: Professional reporting in CSV/JSON/HTML formats

### Key Command Groups
- `jobs` - Job management and ingestion from APIs
- `companies` - Company source management  
- `resumes` - Resume file management and processing
- `match` - AI matching operations and similarity scoring
- `maintenance` - System maintenance and data cleanup
- `config` - Configuration management (.env and JSON)

## Configuration Files

### Critical Configuration
- `.env` - Environment variables for runtime configuration
- `soupboss.config.json` - Persistent JSON configuration settings
- `data/soupboss.db` - SQLite database with vector extensions

### Dependencies (pyproject.toml)
- Python 3.13+ required
- Key dependencies: click, rich, ollama, sqlite-vec, pandas, PyPDF2, python-docx
- Entry point: `soupboss = "soupboss.cli:main"`

## Development Notes

- **Target**: Single-user local application (not enterprise production)
- **AI Model**: Uses Ollama with nomic-embed-text for semantic embeddings
- **Database**: SQLite with sqlite-vec extension for vector similarity search
- **Environment**: Runs on headless Ubuntu server with local compute resources
- **File Support**: PDF, DOCX, TXT, MD resume formats
- **Export Formats**: CSV, JSON, HTML, PDF

## API Integrations

### Supported Job Boards
- **Greenhouse**: `https://boards-api.greenhouse.io/v1/boards/{company}/jobs`
- **Lever**: `https://api.lever.co/v0/postings/{company}`  
- **SmartRecruiters**: `https://api.smartrecruiters.com/v1/companies/{company}/postings`
- **Disney**: JSON data files from Workday scraper

### Data Processing
- Converts HTML job descriptions to both text and preserves HTML
- Semantic embedding generation for all content
- Cosine similarity scoring for job-resume matching
- Complete audit trail and data integrity validation