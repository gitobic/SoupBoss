# SoupBoss CLI Reference

This document provides a complete reference of all available CLI commands organized by their nested structure.

## Main Commands

```
main.py
├── status                      Show system status and statistics
├── report                      Generate comprehensive summary report
│   ├── --format                Report format (html, json) [default: html]
│   └── --output, -o           Output file path
├── test-embedding             Test the ollama embedding functionality
│   └── --text                 Text to use for testing embeddings
└── reset                      Reset entire system (redirects to maintenance reset-system)
```

## Command Groups

### jobs - Manage job listings from Greenhouse, Lever, SmartRecruiters APIs and Disney data files

```
main.py jobs
├── fetch                      Fetch job listings from API sources
│   ├── --source               API source (greenhouse, lever, smartrecruiters) [required]
│   ├── --company              Company identifier [required]
│   ├── --limit                Maximum number of jobs to fetch
│   └── --companies-file, -f   File containing list of companies to process
├── list                       List all stored job postings
│   ├── --company              Filter by company name
│   ├── --source               Filter by source (greenhouse, lever, smartrecruiters, disney)
│   ├── --limit                Maximum jobs to display [default: 50]
│   └── --pdf                  Export results to PDF file
├── clean                      Remove all job data from storage
├── import                     Import job listings from data files
│   ├── --source               Data source type (disney) [required]
│   ├── --company              Company identifier [default: disney]
│   ├── --file                 Data file to import from [required]
│   └── --limit                Maximum number of jobs to import
└── export                     Export job listings to various formats
    ├── --format               Export format (csv, json, html) [default: csv]
    ├── --output, -o           Output file path
    ├── --company              Filter by company name
    └── --source               Filter by source (greenhouse, lever, smartrecruiters, disney)
```

### companies - Manage company sources for job fetching

```
main.py companies
├── add                        Add a company to track
│   ├── name                   Company name [argument]
│   └── --source               API source (greenhouse, lever, smartrecruiters) [required]
├── list                       List all tracked companies
│   └── --pdf                  Export results to PDF file
└── test                       Test if company has active job board
    ├── name                   Company name [argument]
    └── --source               API source (greenhouse, lever, smartrecruiters, disney) [required]
```

### resumes - Manage resume files and profiles

```
main.py resumes
├── add                        Add a resume file to the system
│   ├── resume_path            Path to resume file [argument]
│   └── --name                 Name for this resume profile
├── list                       List all stored resumes
│   └── --preview              Show content preview
├── show                       Show resume details and content
│   ├── resume_id              Resume ID [argument]
│   └── --full                 Show full content instead of preview
├── remove                     Remove a resume from the system
│   └── resume_id              Resume ID [argument]
├── rename                     Rename a resume
│   ├── resume_id              Resume ID [argument]
│   └── new_name               New resume name [argument]
└── export                     Export resume listings to various formats
    ├── --format               Export format (csv, json, html) [default: csv]
    └── --output, -o           Output file path
```

### match - Run job matching and generate reports

```
main.py match
├── generate                   Generate embeddings for jobs and resumes
│   ├── --jobs-only            Generate embeddings for jobs only
│   ├── --resumes-only         Generate embeddings for resumes only
│   └── --force                Force regeneration of existing embeddings
├── run                        Run similarity matching between resumes and jobs
│   ├── --resume-id            Specific resume to match against
│   ├── --job-ids              Comma-separated list of job IDs to match against
│   └── --limit                Maximum matches to return [default: 50]
├── show                       Show top matches for a specific resume
│   ├── resume_id              Resume ID [argument]
│   ├── --limit                Number of top matches to show [default: 10]
│   └── --pdf                  Export results to PDF file
├── stats                      Show embedding and matching statistics
├── export                     Export matching results to various formats
│   ├── --format               Export format (csv, json, html) [default: csv]
│   ├── --output, -o           Output file path
│   ├── --resume-id            Export matches for specific resume only
│   └── --limit                Limit number of results to export
├── compare-models             Compare different embedding models for matching accuracy
│   ├── --models               Comma-separated list of models to compare
│   ├── --force                Force regeneration of embeddings
│   └── --save                 Save results to JSON file
├── switch-model               Switch to a different embedding model
│   ├── model_name             Model name [argument]
│   └── --generate             Generate embeddings for new model immediately
└── list-models                List available embedding models
```

### maintenance - Data cleanup and maintenance operations

```
main.py maintenance
├── stats                      Show detailed system statistics
├── clear-jobs                 Clear all job data including embeddings and matches
│   └── --force                Skip confirmation prompt
├── clear-resumes              Clear all resume data including embeddings and matches
│   └── --force                Skip confirmation prompt
├── clear-embeddings           Clear all embeddings cache forcing regeneration
│   └── --force                Skip confirmation prompt
├── clear-matches              Clear only match results, keeping jobs/resumes/embeddings
│   └── --force                Skip confirmation prompt
├── reset-system               Complete system reset - clears ALL data including companies
│   └── --force                Skip confirmation prompt
├── backup                     Create a backup of the current database
│   └── --output, -o           Backup file path
├── optimize                   Optimize database performance
├── validate                   Validate data integrity and check for issues
└── cleanup                    Clean up orphaned records and data inconsistencies
```

### config - Configure system settings

```
main.py config
├── show                       Display current configuration
│   └── --section              Show specific configuration section only
├── set                        Set configuration value
│   ├── section                Configuration section [argument]
│   ├── key                    Configuration key [argument]
│   └── value                  Configuration value [argument]
├── env                        Set environment variable in .env file
│   ├── key                    Environment variable key [argument]
│   └── value                  Environment variable value [argument]
├── unset                      Remove environment variable from .env file
│   └── key                    Environment variable key [argument]
├── validate                   Validate current configuration
├── reset                      Reset configuration to default values
│   └── --confirm              Skip confirmation prompt
├── template                   Export .env template file
│   └── --output, -o           Output file path
└── info                       Show connection information for configured services
```

## Usage Examples

### Basic Workflow
```bash
# Check system status
uv run python main.py status

# Add a company to track
uv run python main.py companies add spacex --source greenhouse

# Fetch jobs from the company
uv run python main.py jobs fetch --source greenhouse --company spacex

# Add a resume
uv run python main.py resumes add /path/to/resume.pdf --name "My Resume"

# Generate embeddings
uv run python main.py match generate

# Run matching
uv run python main.py match run

# Show matches for a specific resume
uv run python main.py match show 1

# Generate a comprehensive report
uv run python main.py report --format html
```

### Bulk Operations
```bash
# Bulk fetch jobs from multiple companies
uv run python main.py jobs fetch --source greenhouse --companies-file companies.txt

# Clear all job data
uv run python main.py maintenance clear-jobs --force

# Reset entire system
uv run python main.py maintenance reset-system
```

### Configuration Management
```bash
# Show current configuration
uv run python main.py config show

# Set a configuration value
uv run python main.py config set database max_connections 10

# Set an environment variable
uv run python main.py config env OLLAMA_HOST localhost

# Export configuration template
uv run python main.py config template --output .env.example
```

### Export and Reporting
```bash
# Export jobs to CSV
uv run python main.py jobs export --format csv --output jobs.csv

# Export matches to HTML
uv run python main.py match export --format html --output matches.html

# Generate comprehensive HTML report
uv run python main.py report --format html --output report.html
```

## Command Line Flags

- `--force` - Skip confirmation prompts in destructive operations
- `--pdf` - Export results to PDF file format
- `--full` - Show complete content instead of previews
- `--preview` - Show content previews in list commands
- `-o, --output` - Specify output file path
- `-f, --companies-file` - Specify file containing list of companies

## File Formats Supported

### Resume Files
- PDF (.pdf)
- Text (.txt)
- Markdown (.md)
- Word Documents (.docx) - limited support

### Data Sources
- **Greenhouse API** - `https://boards-api.greenhouse.io/v1/boards/{company}/jobs`
- **Lever API** - `https://api.lever.co/v0/postings/{company}`
- **SmartRecruiters API** - `https://api.smartrecruiters.com/v1/companies/{company}/postings`
- **Disney Data Files** - JSON files from Disney Workday scraper

### Export Formats
- CSV (.csv)
- JSON (.json)
- HTML (.html)
- PDF (.pdf) - for specific list and match commands