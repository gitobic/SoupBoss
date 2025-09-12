<div align="center">
  <img src="img/logo_v3-soupboss-trsp.png" alt="SoupBoss Logo" width="200">
  
  # SoupBoss
  
  **Intelligent Job Matching System with Semantic Similarity Scoring**
  
  [![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
  [![Package Manager](https://img.shields.io/badge/package%20manager-uv-green.svg)](https://github.com/astral-sh/uv)
  [![Ollama](https://img.shields.io/badge/AI-Ollama-orange.svg)](https://ollama.com)
  
</div>

## Overview

SoupBoss is an intelligent(?) job matching system that leverages AI-powered semantic similarity to connect resumes with job opportunities. It processes job postings from multiple sources, analyzes resumes in various formats, and provides sophisticated matching with detailed scoring and comprehensive reporting.

**Key Features:**
- 🔍 **Multi-source job ingestion** from Greenhouse, Lever, SmartRecruiters APIs
- 📄 **Multi-format resume processing** (PDF, DOCX, TXT, Markdown)
- 🤖 **AI-powered semantic matching** using local Ollama embeddings
- 📊 **Professional reporting** in CSV, JSON, and HTML formats
- 🛠️ **Complete CLI interface** with 40+ commands across 7 groups
- 🗄️ **Vector database** with SQLite and similarity search
- ⚡ **Performance benchmarking** for embedding model comparison
- 🔧 **Standalone operation** - no external APIs required

## Prerequisites

### Required Software
- **Python 3.13+** (required for modern language features)
- **[uv package manager](https://github.com/astral-sh/uv)** (critical - do not use pip)
- **[Ollama](https://ollama.com)** installed and running locally

### Ollama Setup

**⚠️ CRITICAL: SoupBoss requires Ollama running locally on your machine.**

SoupBoss connects directly to Ollama (default: `localhost:11434`) for all AI operations. This provides:
- **Privacy**: All processing happens locally
- **Control**: Choose your preferred embedding model
- **Performance**: Direct access without API limitations

```bash
# Install Ollama from https://ollama.com
# Then pull an embedding model:
ollama pull nomic-embed-text
# or
ollama pull bge-large
```

## Quick Start

### Installation

**⚠️ CRITICAL: Only use `uv` for package management - never use pip**

```bash
# Clone the repository
git clone <repository-url>
cd soupboss

# Install dependencies (uv handles everything automatically)
uv sync

# Verify installation and check Ollama connection
uv run python main.py status

# Test embedding functionality
uv run python main.py test-embedding
```

### Complete Workflow

Follow this step-by-step guide to get from zero to job matches:

```bash
# 1. Add a company to track
uv run python main.py companies add spacex --source greenhouse

# 2. Test if the company has an active job board
uv run python main.py companies test spacex --source greenhouse

# 3. Fetch jobs from the company
uv run python main.py jobs fetch --source greenhouse --company spacex

# 4. Verify jobs were imported
uv run python main.py jobs list --company spacex

# 5. Add your resume(s)
uv run python main.py resumes add /path/to/resume.pdf --name "My Resume"
uv run python main.py resumes add /path/to/resume.docx --name "Alternative Resume"

# 6. Check resume was processed
uv run python main.py resumes list

# 7. Generate AI embeddings (this takes time but runs once)
uv run python main.py match generate --time

# 8. Run similarity matching
uv run python main.py match run

# 9. View your top 20 matches
uv run python main.py match show --limit 20

# 10. Generate a comprehensive HTML report
uv run python main.py report --format html --output my_matches.html

# 11. View detailed system statistics
uv run python main.py maintenance stats
```

### Bulk Operations

For processing multiple companies or large datasets:

```bash
# Create a companies.txt file with one company per line
echo -e "spacex\ntesla\nopenai" > companies.txt

# Bulk fetch jobs
uv run python main.py jobs fetch --source greenhouse --companies-file companies.txt

# Add multiple resumes at once
uv run python main.py resumes add /resumes/*.pdf

# Export all matches to CSV
uv run python main.py match export --format csv --output all_matches.csv
```

## Embedding Model Performance

SoupBoss supports multiple embedding models through Ollama. Based on comprehensive benchmarking with 1,083 items (1,082 jobs + 1 resume):

| Model | Speed (items/sec) | Time per Item (s) | Total Time (63s) | Embedding Dimensions |
|-------|------------------|-------------------|------------------|-------------------|
| **mstute/snowflake-arctic-embed-m** | **17.13** | **0.058** | 63.23s | 768 |
| **bge-large** | 17.11 | 0.058 | 63.29s | 1024 |
| **bge-m3** | 17.12 | 0.058 | 63.26s | 1024 |
| **granite-embedding:278m** | 17.11 | 0.058 | 63.31s | 768 |
| **granite-embedding** | 17.09 | 0.059 | 63.37s | 768 |
| **nomic-embed-text** | 17.10 | 0.058 | 63.34s | 768 |
| **sellerscrisp/jina-embeddings-v4** | 17.13 | 0.058 | 63.23s | 512 |
| **dengcao/EmbeddingGemma** | 17.08 | 0.059 | 63.39s | 3584 |
| **mxbai-embed-large** | 17.03 | 0.059 | 63.58s | 1024 |

**Recommendations:**
- **Best Overall**: `snowflake-arctic-embed-m` - fastest with good quality
- **Most Popular**: `nomic-embed-text` - reliable and widely used
- **High Dimension**: `dengcao/EmbeddingGemma` - 3584 dimensions for detailed analysis
- **Balanced**: `bge-large` - good speed with 1024 dimensions

### Run Your Own Benchmarks

```bash
# Test all available models
uv run python main.py match speed-test --save my_results.json

# Compare specific models
uv run python main.py match speed-test --models "nomic-embed-text,bge-large" --force

# Test with timing details
uv run python main.py match generate --time --model bge-large --force
```

## Architecture

### Core Components

```
soupboss/
├── cli.py                 # Complete CLI interface (40+ commands)
├── db.py                  # SQLite with vector search
├── embeddings.py          # Ollama client integration
├── ingestion.py           # Multi-API job fetching
├── matching.py            # AI similarity engine
├── export.py              # Professional reporting
├── maintenance.py         # System utilities
└── config.py              # Configuration management
```

### Data Flow

```
Job APIs → Ingestion → SQLite Database ← Resume Files
    ↓                      ↓                ↑
Ollama Embeddings ←→ Vector Storage ←→ Similarity Matching
    ↓                                       ↓
Reports & Analysis ←← Match Results ←←←←←←←←←┘
```

## Command Groups

| Group | Purpose | Key Commands | Examples |
|-------|---------|--------------|----------|
| **jobs** | Job data management | `fetch`, `list`, `import` | Ingest from APIs, bulk import |
| **companies** | Company tracking | `add`, `list`, `test` | Manage job sources |
| **resumes** | Resume management | `add`, `show`, `remove` | Process candidate files |
| **match** | AI matching | `generate`, `run`, `show` | Create embeddings, find matches |
| **maintenance** | System upkeep | `stats`, `clear-*`, `backup` | Database maintenance |
| **config** | Configuration | `show`, `set`, `validate` | System settings |

## Supported Integrations

### Job Board APIs
- **Greenhouse**: `https://boards-api.greenhouse.io/v1/boards/{company}/jobs`
- **Lever**: `https://api.lever.co/v0/postings/{company}`
- **SmartRecruiters**: `https://api.smartrecruiters.com/v1/companies/{company}/postings`
- **Disney Data**: Custom JSON import from Workday scraper

### Resume Formats
- **PDF** (.pdf) - Full text extraction
- **Word Documents** (.docx) - Microsoft Word format
- **Plain Text** (.txt) - Direct text processing
- **Markdown** (.md) - Formatted text with structure

### Export & Reporting
- **CSV** (.csv) - Structured data for Excel/analysis
- **JSON** (.json) - Machine-readable data format
- **HTML** (.html) - Rich formatted reports with styling
- **PDF** (.pdf) - Professional printable reports

## Configuration

SoupBoss uses a flexible configuration system:

```bash
# Environment variables (.env file)
OLLAMA_HOST=localhost
OLLAMA_PORT=11434
OLLAMA_MODEL=nomic-embed-text

# View current settings
uv run python main.py config show

# Update Ollama connection
uv run python main.py config env OLLAMA_HOST localhost
uv run python main.py config env OLLAMA_MODEL bge-large

# Database and system settings
uv run python main.py config set database timeout 30
uv run python main.py config set embedding batch_size 100

# Export configuration template
uv run python main.py config template --output .env.example
```

## Standalone Utilities

Direct API access without the main system:

```bash
# Test company job boards
uv run python greenhouse_fetch.py -test spacex
uv run python lever_fetch.py -test leverdemo

# Direct job fetching
uv run python greenhouse_fetch.py -fetch spacex
uv run python smartrecruiters_fetch.py -fetch dynatrace1

# Bulk operations
uv run python greenhouse_fetch.py -in companies.txt -out ./data/

# Import Disney Workday data
uv run python disney_data_importer.py -file disney_jobs.json
```

## Advanced Usage

### Model Comparison & Analysis
```bash
# Compare embedding models for quality and speed
uv run python main.py match compare-models --save comparison.json

# Switch between models
uv run python main.py match switch-model bge-large --generate

# View model statistics
uv run python main.py match list-models
```

### System Maintenance
```bash
# Database optimization
uv run python main.py maintenance optimize

# Data validation
uv run python main.py maintenance validate

# Backup before major operations
uv run python main.py maintenance backup --output backup.db

# Clean start (removes everything)
uv run python main.py maintenance reset-system --force
```

## Documentation

- **[CLI_REFERENCE.md](CLI_REFERENCE.md)** - Complete command reference with examples
- **[CLAUDE.md](CLAUDE.md)** - Claude Code integration and development guide

## Troubleshooting

### Common Issues

**Ollama Connection Failed:**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if not running
ollama serve

# Test connection through SoupBoss
uv run python main.py test-embedding
```

**Package Installation Issues:**
```bash
# Ensure you're using uv (not pip)
which uv

# Clean reinstall
rm -rf .venv
uv sync
```

**Embedding Generation Slow:**
```bash
# Test different models for speed
uv run python main.py match speed-test --models "nomic-embed-text,bge-large"

# Monitor system resources during generation
uv run python main.py match generate --time --force
```

## Development Status

**✅ Complete:**
- Multi-source job ingestion
- Resume processing (all formats)
- AI-powered semantic matching
- Complete CLI interface
- Professional reporting
- Model benchmarking

**🚧 In Progress:**
- Web interface development
- Enhanced model comparison
- Automated job scraping
- Performance optimization

---

<div align="center">
  <em>Built for intelligent job matching with local AI and complete data control</em>
  <br><br>
  <strong>No external AI APIs • Complete privacy • Local processing</strong>
</div>