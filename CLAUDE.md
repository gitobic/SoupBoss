# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🍲 SoupBoss - Intelligent Job Matching System

SoupBoss is a comprehensive AI-powered job matching platform with both CLI and web interfaces. It intelligently matches resumes to job postings using semantic embeddings and provides detailed similarity scoring.

## Package Management - CRITICAL

**ONLY use `uv` for package management, NEVER pip:**
- Install packages: `uv add package`
- Run tools: `uv run tool`
- Run the main application: `uv run python main.py`

**FORBIDDEN commands:**
- `uv pip install` 
- `@latest` syntax
- Any direct pip usage

## 💻 Core Commands & CLI Reference

### 🚀 Quick Start Options

#### **Web Interface (Recommended for Most Users)**
```bash
# Start the web interface - provides full GUI experience
uv run python webapp_manager.py restart
# Or use the legacy script: ./restart_webapp.sh  
# Access at: http://localhost:5000
```

#### **Command Line Interface (Power Users & Automation)**  
```bash
# Run the main CLI application
uv run python main.py
```

### 🔧 Development and Testing Commands
```bash
# Check system status and configuration
uv run python main.py status

# Test embedding functionality
uv run python main.py test-embedding

# Generate comprehensive reports
uv run python main.py report --format html

# Run speed tests and model comparisons
uv run python main.py match speed-test
uv run python main.py match compare-models
```

### 📋 Complete CLI Workflow
```bash
# 1. Add companies and test job board availability
uv run python main.py companies add spacex --source greenhouse
uv run python main.py companies add leverdemo --source lever  
uv run python main.py companies add dynatrace1 --source smartrecruiters

# 2. Fetch jobs from all sources
uv run python main.py jobs fetch --source greenhouse --company spacex
uv run python main.py jobs fetch --source lever --company leverdemo
uv run python main.py jobs fetch --source smartrecruiters --company dynatrace1

# 3. Add and manage resumes
uv run python main.py resumes add /path/to/resume.pdf --name "Senior Developer Resume"
uv run python main.py resumes add /path/to/resume2.docx --name "DevOps Resume"
uv run python main.py resumes list

# 4. Generate embeddings and run matching
uv run python main.py match generate          # Generate embeddings for all content
uv run python main.py match generate --force  # Force regenerate (fixes model compatibility)
uv run python main.py match run               # Run similarity matching

# 5. View and export results
uv run python main.py match show 1            # Show matches for resume ID 1
uv run python main.py match show 1 --limit 10 # Show top 10 matches
uv run python main.py match export --format json --limit 50
uv run python main.py match export --format csv --output results.csv
uv run python main.py match export --format html --output report.html

# 6. System maintenance
uv run python main.py maintenance cleanup     # Clean up old data
uv run python main.py maintenance backup      # Backup database
uv run python main.py maintenance optimize    # Optimize database
```

### 🆚 Web Interface vs CLI Comparison

| Feature | Web Interface | CLI |
|---------|---------------|-----|
| **Ease of Use** | ✅ Point-and-click, visual | ⚡ Command-based, fast |
| **Resume Upload** | ✅ Drag-and-drop, instant | 📁 File paths required |
| **Company Testing** | ✅ One-click testing | 🔧 Manual command execution |
| **Progress Updates** | ✅ Real-time WebSocket updates | 📊 Terminal progress bars |
| **Results Display** | ✅ Beautiful cards, sorting | 📋 Table format |
| **Error Handling** | ✅ Smart suggestions, auto-fix | 🔍 Manual troubleshooting |
| **Remote Access** | ✅ Any device on network | 🖥️ Server access required |
| **Batch Operations** | ⚡ Manual, step-by-step | ✅ Scriptable, automation |
| **Advanced Features** | 🔧 Core features only | ✅ Full feature access |
| **Learning Curve** | 🟢 Beginner-friendly | 🟡 Requires CLI knowledge |

**Recommendation**: Use the web interface for daily operations and the CLI for automation, batch processing, and advanced features.

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

## 🌐 Web Interface

### Quick Start
**Access the web interface at: http://localhost:5000**

```bash
# New consolidated manager (recommended)
uv run python webapp_manager.py restart  # Restart webapp
uv run python webapp_manager.py start    # Start webapp
uv run python webapp_manager.py stop     # Stop webapp
uv run python webapp_manager.py status   # Check status

# Legacy script (still works)
./restart_webapp.sh

# Direct start (minimal output)
uv run python webapp.py
```

### 🎯 Web Interface Overview
The SoupBoss web interface provides a complete graphical workflow for job matching:

#### **Tab 1: Setup & Configuration**
- ✅ **Resume Upload**: Drag-and-drop file upload (PDF, DOCX, TXT, MD)
- ✅ **Company Testing**: Test if companies have job boards before adding
- ✅ **Company Management**: Add companies from all three sources
- ✅ **Job Fetching**: Real-time job retrieval with progress monitoring
- ✅ **AI Processing**: Generate embeddings and run matching algorithms
- ✅ **Force Regeneration**: Fix embedding compatibility issues

#### **Tab 2: Results & Matches**
- ✅ **Professional Job Cards**: Beautiful cards with similarity scores
- ✅ **Smart Sorting**: Sort by similarity, company, title, or date
- ✅ **Detailed Information**: Job title, company, location, department, resume name
- ✅ **Color-coded Scores**: Green (high), orange (medium), red (low) similarity
- ✅ **Summary Statistics**: Total matches, average similarity, current sort method

### 🔧 Web Features in Detail

#### **Resume Processing**
- Upload multiple resumes in various formats (PDF, DOCX, TXT, MD)
- Automatic text extraction and preprocessing
- Resume naming and management
- Compatible with existing CLI resume database

#### **Company & Job Management** 
- **Multi-source Support**: Greenhouse, Lever, SmartRecruiters
- **Company Testing**: Verify job board availability before fetching
- **Real-time Fetching**: Live progress updates via WebSocket
- **Bulk Processing**: Handle thousands of job postings efficiently

#### **AI-Powered Matching**
- **Semantic Embeddings**: Uses Ollama with embeddinggemma:300m model
- **Intelligent Scoring**: Cosine similarity scoring (0.0-1.0 range)
- **Force Regeneration**: Automatically fixes embedding dimension mismatches
- **Smart Error Handling**: Detects and suggests fixes for common issues

#### **Results Display**
- **Professional Cards**: Each job shows:
  - Job title (prominent heading)
  - Company name with building icon
  - Location with map marker
  - Department/team with org chart icon
  - Matching resume with user icon
  - Color-coded similarity percentage
- **Interactive Sorting**: Live reordering by similarity, company, title, or date
- **Summary Information**: Match count, average score, current sort method

### 🚀 Remote Access
**Network Access**: Works from any computer on your network
- Local: `http://localhost:5000`
- Network: `http://[server-ip]:5000` (e.g., `http://192.168.1.115:5000`)

### 🔄 Process Management

#### **Robust Restart System**
The `./restart_webapp.sh` script provides bulletproof process management:
- Kills all existing webapp processes using multiple methods
- Frees port 5000 completely
- Starts webapp cleanly with proper error handling
- Provides clear status feedback throughout

#### **Real-time Communication**
- **WebSocket Integration**: Live progress updates for long operations
- **Progress Monitoring**: Real-time logs in the activity panel  
- **Error Handling**: Smart error detection with suggested solutions
- **Status Updates**: Connection status and system health monitoring

### 🎨 User Experience

#### **Activity Log**
- Real-time operation logs with timestamps
- Color-coded messages (success=green, error=red, info=blue, warning=orange)
- Automatic scrolling and log size management
- Clear operation status and progress tracking

#### **Error Handling & Recovery**
- **Embedding Mismatch Detection**: Automatically detects model compatibility issues
- **Smart Suggestions**: Provides actionable solutions for common problems
- **Graceful Fallbacks**: Falls back to alternative methods when primary approaches fail
- **User-friendly Messages**: Clear error descriptions without technical jargon

### 🛠️ Technical Implementation

#### **Backend (Flask + SocketIO)**
- **Flask 3.1.2+**: Web framework with JSON API endpoints
- **Flask-SocketIO 5.5.1+**: Real-time WebSocket communication
- **Subprocess Integration**: Calls existing SoupBoss CLI commands
- **File Management**: Temporary file handling with automatic cleanup
- **JSON Processing**: Smart parsing of CLI output into structured data

#### **Frontend (Bootstrap + Socket.IO)**
- **Bootstrap 5.1.3**: Professional UI framework (CDN-loaded)
- **Socket.IO 4.0.1**: Client-side real-time communication
- **JavaScript Classes**: Modular, maintainable code organization
- **Responsive Design**: Works on desktop, tablet, and mobile devices

#### **Data Flow**
1. **User Input**: Upload resumes, test companies, configure settings
2. **API Calls**: Frontend makes requests to Flask API endpoints
3. **CLI Integration**: Backend calls SoupBoss CLI commands via subprocess
4. **Real-time Updates**: WebSocket events provide live progress feedback
5. **Data Processing**: JSON export files parsed and formatted for display
6. **Results Presentation**: Professional job cards with interactive sorting

### 📊 Performance & Scalability
- **Efficient Processing**: Handles 1000+ jobs with real-time progress
- **Smart Caching**: Temporary file system with automatic cleanup  
- **Memory Management**: Streaming data processing for large datasets
- **Network Optimized**: Compressed data transfer and efficient APIs

## 🏗️ Development Notes

### **System Architecture**
- **Target**: Single-user local application with network access (not enterprise production)
- **AI Model**: Uses Ollama with embeddinggemma:300m for semantic embeddings (384-dimensional vectors)
- **Database**: SQLite with sqlite-vec extension for vector similarity search
- **Environment**: Runs on headless Ubuntu server with local compute resources
- **Interfaces**: Dual interface - Web GUI and CLI for different use cases

### **File Format Support**
- **Resume Formats**: PDF, DOCX, TXT, MD with automatic text extraction
- **Export Formats**: CSV, JSON, HTML, PDF with customizable templates
- **Data Storage**: SQLite database with efficient vector indexing

### **Network & Access**
- **Web Server**: Flask development server on port 5000
- **Remote Access**: Full network accessibility from any device
- **Real-time Communication**: WebSocket support for live updates
- **Cross-platform**: Works on desktop, tablet, and mobile browsers

### **Performance Characteristics**
- **Scalability**: Handles 1000+ job postings efficiently
- **Processing Speed**: Real-time embedding generation with progress tracking
- **Memory Efficiency**: Streaming processing for large datasets
- **Network Optimized**: Compressed data transfer and smart caching

## 📊 Quick Reference Summary

### **🌐 For New Users (Web Interface)**
1. **Start**: Run `./restart_webapp.sh`
2. **Access**: Open `http://localhost:5000` in any browser
3. **Upload**: Drag-and-drop your resume files
4. **Test**: Enter company name and click "Test Company"
5. **Add**: Click "Add Company" if test succeeds
6. **Fetch**: Click "Fetch Jobs" to retrieve job postings
7. **Process**: Click "Generate Embeddings" then "Run Matching"
8. **View**: Switch to "Results & Matches" tab to see professional job cards
9. **Sort**: Use dropdown to sort by similarity, company, title, or date

### **⚡ For Power Users (CLI)**
```bash
# Complete workflow in 6 commands
uv run python main.py companies add spacex --source greenhouse
uv run python main.py jobs fetch --source greenhouse --company spacex
uv run python main.py resumes add /path/to/resume.pdf --name "My Resume"
uv run python main.py match generate
uv run python main.py match run
uv run python main.py match show 1 --limit 20
```

### **🔧 For Troubleshooting**
- **Embedding Issues**: Use "Force Regenerate" button or `--force` flag
- **Process Conflicts**: Run `./restart_webapp.sh` to clean restart
- **Remote Access**: Use server IP address (e.g., `http://192.168.1.115:5000`)
- **Performance**: Check `uv run python main.py status` for system health

### **🎯 Key Capabilities**
- ✅ **Multi-source Job Fetching**: Greenhouse, Lever, SmartRecruiters
- ✅ **AI-Powered Matching**: Semantic similarity scoring with 74%+ accuracy
- ✅ **Professional Results**: Color-coded match cards with detailed information
- ✅ **Real-time Processing**: Live progress updates and WebSocket communication
- ✅ **Cross-platform Access**: Works from any device on your network
- ✅ **Robust Error Handling**: Smart detection and automatic recovery suggestions

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