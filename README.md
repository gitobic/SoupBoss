<div align="center">
  <img src="img/logo_v3-soupboss-trsp.png" alt="SoupBoss Logo" width="200">
  
  # SoupBoss
  
  **Intelligent Job Matching System with Semantic Similarity Scoring**
  
  [![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
  [![Package Manager](https://img.shields.io/badge/package%20manager-uv-green.svg)](https://github.com/astral-sh/uv)
  
</div>

## Overview

SoupBoss is an intelligent job matching system that uses semantic similarity to connect resumes with job opportunities. It ingests job postings from multiple sources, processes resumes in various formats, and provides AI-powered matching with detailed scoring.

**Key Features:**
- 🔍 **Multi-source job ingestion** from Greenhouse, Lever, SmartRecruiters APIs
- 📄 **Multi-format resume processing** (PDF, DOCX, TXT, Markdown)
- 🤖 **AI-powered semantic matching** using Ollama embeddings
- 📊 **Professional reporting** in CSV, JSON, and HTML formats
- 🛠️ **Complete CLI interface** with 40+ commands across 7 groups
- 🗄️ **Vector database** with SQLite and similarity search

## Quick Start

### Prerequisites
- Python 3.13+
- [uv package manager](https://github.com/astral-sh/uv) (required)

### Installation

**⚠️ CRITICAL: Only use `uv` for package management**

```bash
# Clone the repository
git clone <repository-url>
cd soupboss

# Install dependencies
uv sync

# Check system status
uv run python main.py status
```

### Basic Workflow

```bash
# 1. Add a company to track
uv run python main.py companies add spacex --source greenhouse

# 2. Fetch jobs from the company
uv run python main.py jobs fetch --source greenhouse --company spacex

# 3. Add a resume
uv run python main.py resumes add /path/to/resume.pdf --name "My Resume"

# 4. Generate embeddings
uv run python main.py match generate

# 5. Run matching
uv run python main.py match run

# 6. View results
uv run python main.py match show 1

# 7. Generate comprehensive report
uv run python main.py report --format html
```

## Architecture

### Core Modules
- **`cli.py`** - Complete Click-based CLI interface
- **`db.py`** - SQLite database with vector support
- **`embeddings.py`** - Ollama client integration with nomic-embed-text
- **`ingestion.py`** - Unified job fetching from multiple APIs
- **`matching.py`** - AI matching engine with cosine similarity
- **`export.py`** - Professional export and reporting system
- **`maintenance.py`** - Data cleanup and system maintenance
- **`config.py`** - Configuration management (.env and JSON)

### Data Flow
1. **Ingestion** → Job data from APIs and data files
2. **Processing** → Resume parsing and content extraction
3. **Embedding** → Semantic vector generation via Ollama
4. **Matching** → Cosine similarity scoring
5. **Export** → Professional reports and analysis

## Command Groups

| Group | Description | Key Commands |
|-------|-------------|--------------|
| `jobs` | Job management and ingestion | `fetch`, `list`, `import`, `export` |
| `companies` | Company source management | `add`, `list`, `test` |
| `resumes` | Resume file management | `add`, `list`, `show`, `remove` |
| `match` | AI matching operations | `generate`, `run`, `show`, `export` |
| `maintenance` | System maintenance | `stats`, `clear-*`, `reset-system` |
| `config` | Configuration management | `show`, `set`, `env`, `validate` |

## Supported Integrations

### Job Board APIs
- **Greenhouse** - `https://boards-api.greenhouse.io/v1/boards/{company}/jobs`
- **Lever** - `https://api.lever.co/v0/postings/{company}`
- **SmartRecruiters** - `https://api.smartrecruiters.com/v1/companies/{company}/postings`
- **Disney Data Files** - JSON files from Workday scraper

### Resume Formats
- PDF (.pdf)
- Word Documents (.docx)
- Plain Text (.txt)
- Markdown (.md)

### Export Formats
- CSV (.csv)
- JSON (.json)
- HTML (.html)
- PDF reports

## Configuration

The system uses multiple configuration approaches:

- **`.env`** - Environment variables for runtime configuration
- **`soupboss.config.json`** - Persistent JSON configuration settings
- **`data/soupboss.db`** - SQLite database with vector extensions

```bash
# View current configuration
uv run python main.py config show

# Set configuration values
uv run python main.py config set database max_connections 10

# Manage environment variables
uv run python main.py config env OLLAMA_HOST localhost
```

## API Data Fetchers

Standalone CLI utilities for direct API access:

```bash
# Test company job boards
uv run python greenhouse_fetch.py -test spacex
uv run python lever_fetch.py -test leverdemo
uv run python smartrecruiters_fetch.py -test dynatrace1

# Fetch job data
uv run python greenhouse_fetch.py -fetch spacex
uv run python lever_fetch.py -fetch leverdemo

# Bulk processing
uv run python greenhouse_fetch.py -in companies.txt -split -out ./data/
```

## Documentation

- **[CLI_REFERENCE.md](CLI_REFERENCE.md)** - Complete command reference
- **[CLAUDE.md](CLAUDE.md)** - Claude Code integration guide

## Package Management

**⚠️ CRITICAL REQUIREMENTS:**

✅ **ALLOWED:**
- `uv add package`
- `uv run tool`
- `uv sync`

❌ **FORBIDDEN:**
- `uv pip install`
- `@latest` syntax
- Direct pip usage

## System Requirements

- **Target Environment**: Single-user local application
- **Python Version**: 3.13+
- **Database**: SQLite with vector extensions
- **AI Model**: Ollama with nomic-embed-text
- **Platform**: Tested on Ubuntu (headless server)

## Development Status

✅ **Complete Systems:**
- Dependencies & CLI interface
- Database with vector support
- AI integration (Ollama)
- Job ingestion from APIs
- Resume management
- Intelligence engine
- Export & reporting
- Maintenance & configuration

🚧 **Remaining:**
- End-to-end workflow testing

---

<div align="center">
  <em>Built for intelligent job matching and semantic similarity analysis</em>
</div>