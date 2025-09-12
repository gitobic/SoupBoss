// SoupBoss Web App JavaScript

class SoupBossApp {
    constructor() {
        this.socket = io();
        this.initializeEventListeners();
        this.initializeSocketEvents();
        this.loadSystemStatus();
    }

    initializeEventListeners() {
        // Resume upload form
        document.getElementById('resumeUploadForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.uploadResume();
        });

        // Company management buttons
        document.getElementById('testCompanyBtn').addEventListener('click', () => this.testCompany());
        document.getElementById('addCompanyBtn').addEventListener('click', () => this.addCompany());

        // Job processing buttons
        document.getElementById('fetchJobsBtn').addEventListener('click', () => this.fetchJobs());
        document.getElementById('generateEmbeddingsBtn').addEventListener('click', () => this.generateEmbeddings());
        document.getElementById('forceEmbeddingsBtn').addEventListener('click', () => this.generateEmbeddings(true));
        document.getElementById('runMatchingBtn').addEventListener('click', () => this.runMatching());

        // Results tab
        document.getElementById('refreshMatchesBtn').addEventListener('click', () => this.loadMatches());
        document.getElementById('sortBy').addEventListener('change', () => this.loadMatches());

        // Tab switching
        document.getElementById('results-tab').addEventListener('shown.bs.tab', () => this.loadMatches());
    }

    initializeSocketEvents() {
        this.socket.on('connect', () => {
            this.logMessage('info', 'Connected to SoupBoss server');
        });

        this.socket.on('disconnect', () => {
            this.logMessage('error', 'Disconnected from server');
        });

        this.socket.on('progress', (data) => {
            this.logMessage(data.type, data.message);
        });

        this.socket.on('job_fetch_complete', (result) => {
            this.handleCommandResult('Job fetch', result);
            this.setButtonLoading('fetchJobsBtn', false);
        });

        this.socket.on('matching_complete', (result) => {
            this.handleCommandResult('Matching', result);
            this.setButtonLoading('runMatchingBtn', false);
            if (result.success) {
                // Switch to results tab and load matches
                const resultsTab = new bootstrap.Tab(document.getElementById('results-tab'));
                resultsTab.show();
                this.loadMatches();
            }
        });
    }

    async loadSystemStatus() {
        try {
            const response = await fetch('/api/status');
            const result = await response.json();
            
            const statusElement = document.getElementById('systemStatus');
            if (result.success) {
                statusElement.innerHTML = `<span class="status-indicator status-online"></span>System Online - ${result.output.replace(/\n/g, ' ')}`;
            } else {
                statusElement.innerHTML = `<span class="status-indicator status-offline"></span>System Issues: ${result.error}`;
            }
        } catch (error) {
            document.getElementById('systemStatus').innerHTML = `<span class="status-indicator status-offline"></span>Connection Error`;
        }
    }

    async uploadResume() {
        const form = document.getElementById('resumeUploadForm');
        const formData = new FormData(form);
        const fileInput = document.getElementById('resumeFile');
        
        if (!fileInput.files.length) {
            this.showAlert('error', 'Please select a resume file');
            return;
        }

        this.logMessage('info', 'Uploading resume...');
        
        try {
            const response = await fetch('/api/upload-resume', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            this.handleCommandResult('Resume upload', result);
            
            if (result.success) {
                form.reset();
            }
        } catch (error) {
            this.logMessage('error', `Upload error: ${error.message}`);
        }
    }

    async testCompany() {
        const company = document.getElementById('companyName').value.trim();
        const source = document.getElementById('jobSource').value;
        
        if (!company) {
            this.showAlert('error', 'Please enter a company name');
            return;
        }

        this.setButtonLoading('testCompanyBtn', true);
        this.logMessage('info', `Testing ${company} on ${source}...`);

        try {
            const response = await fetch('/api/test-company', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ company, source })
            });
            
            const result = await response.json();
            this.handleCommandResult(`Company test (${company})`, result);
            
        } catch (error) {
            this.logMessage('error', `Test error: ${error.message}`);
        } finally {
            this.setButtonLoading('testCompanyBtn', false);
        }
    }

    async addCompany() {
        const company = document.getElementById('companyName').value.trim();
        const source = document.getElementById('jobSource').value;
        
        if (!company) {
            this.showAlert('error', 'Please enter a company name');
            return;
        }

        this.setButtonLoading('addCompanyBtn', true);
        this.logMessage('info', `Adding ${company} to database...`);

        try {
            const response = await fetch('/api/add-company', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ company, source })
            });
            
            const result = await response.json();
            this.handleCommandResult(`Add company (${company})`, result);
            
        } catch (error) {
            this.logMessage('error', `Add company error: ${error.message}`);
        } finally {
            this.setButtonLoading('addCompanyBtn', false);
        }
    }

    fetchJobs() {
        const company = document.getElementById('companyName').value.trim();
        const source = document.getElementById('jobSource').value;
        
        if (!company) {
            this.showAlert('error', 'Please enter a company name');
            return;
        }

        this.setButtonLoading('fetchJobsBtn', true);
        this.logMessage('info', `Starting job fetch for ${company}...`);
        
        // Use WebSocket for real-time updates
        this.socket.emit('start_job_fetch', { company, source });
    }

    async generateEmbeddings(force = false) {
        this.setButtonLoading('generateEmbeddingsBtn', true);
        const action = force ? 'Force regenerating embeddings' : 'Generating embeddings';
        this.logMessage('info', `${action}...`);

        try {
            const response = await fetch('/api/generate-embeddings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ force: force })
            });
            
            const result = await response.json();
            this.handleCommandResult('Generate embeddings', result);
            
        } catch (error) {
            this.logMessage('error', `Embeddings error: ${error.message}`);
        } finally {
            this.setButtonLoading('generateEmbeddingsBtn', false);
        }
    }

    runMatching() {
        this.setButtonLoading('runMatchingBtn', true);
        this.logMessage('info', 'Starting job matching process...');
        
        // Use WebSocket for real-time updates
        this.socket.emit('start_matching', {});
    }

    async loadMatches() {
        const sortBy = document.getElementById('sortBy').value;
        this.logMessage('info', 'Loading job matches...');

        try {
            const response = await fetch(`/api/get-matches?sort_by=${sortBy}&limit=50`);
            const result = await response.json();
            
            if (result.success) {
                this.displayMatches(result);
                this.logMessage('success', `Loaded ${result.count || 0} job matches`);
            } else {
                this.logMessage('error', `Failed to load matches: ${result.error}`);
            }
        } catch (error) {
            this.logMessage('error', `Load matches error: ${error.message}`);
        }
    }

    displayMatches(result) {
        const container = document.getElementById('matchesContainer');
        
        // Check if no matches - handle both string and array formats
        const hasMatches = result.matches && (
            (typeof result.matches === 'string' && result.matches.trim() !== '') ||
            (Array.isArray(result.matches) && result.matches.length > 0)
        );
        
        if (!hasMatches) {
            container.innerHTML = `
                <div class="text-center text-muted">
                    <i class="fas fa-search fa-3x mb-3"></i>
                    <p>No job matches found. Make sure you have uploaded a resume and run the matching process.</p>
                </div>
            `;
            return;
        }

        let matchesHTML = '';

        // Handle JSON data format from match export (already parsed)
        if (result.format === 'json_data') {
            const matchData = result.matches;
            
            if (matchData && Array.isArray(matchData)) {
                matchData.forEach((match, index) => {
                    const score = (match.similarity_score * 100).toFixed(1);
                    const scoreClass = score >= 80 ? 'similarity-high' : score >= 60 ? 'similarity-medium' : 'similarity-low';
                    
                    matchesHTML += `
                        <div class="card job-match-card mb-3">
                            <div class="card-body">
                                <div class="d-flex justify-content-between align-items-start">
                                    <div class="flex-grow-1">
                                        <h6 class="card-title">${this.escapeHtml(match.job_title || 'Job Title')}</h6>
                                        <p class="text-muted mb-1">
                                            <i class="fas fa-building me-1"></i>${this.escapeHtml(match.company_name || match.company || 'Company')}
                                        </p>
                                        <p class="text-muted small mb-1">
                                            <i class="fas fa-map-marker-alt me-1"></i>${this.escapeHtml(match.location || 'Location not specified')}
                                        </p>
                                        <p class="text-muted small mb-1">
                                            <i class="fas fa-sitemap me-1"></i>${this.escapeHtml(match.department || 'Department not specified')}
                                        </p>
                                        <p class="text-muted small mb-1">
                                            <i class="fas fa-user me-1"></i>Resume: ${this.escapeHtml(match.resume_name || 'N/A')}
                                        </p>
                                        ${match.job_description ? `<p class="small text-muted mt-2">${this.escapeHtml(match.job_description.substring(0, 200))}${match.job_description.length > 200 ? '...' : ''}</p>` : ''}
                                    </div>
                                    <div class="text-end">
                                        <span class="similarity-score ${scoreClass}">${score}%</span>
                                        <small class="d-block text-muted">Match Score</small>
                                        ${match.job_url ? `<a href="${match.job_url}" target="_blank" class="btn btn-sm btn-outline-primary mt-2"><i class="fas fa-external-link-alt"></i> View Job</a>` : ''}
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                });
                
                // Add summary info
                if (matchData.length > 0) {
                    const avgScore = (matchData.reduce((sum, match) => sum + match.similarity_score, 0) / matchData.length * 100).toFixed(1);
                    matchesHTML = `
                        <div class="alert alert-info mb-3">
                            <i class="fas fa-info-circle me-2"></i>
                            Showing ${matchData.length} matches • Average similarity: ${avgScore}% • Sorted by: ${result.sort_by || 'similarity'}
                        </div>
                    ` + matchesHTML;
                }
            }
        }
        // Handle legacy JSON string format 
        else if (result.format === 'json') {
            try {
                const matchData = JSON.parse(result.matches);
                if (matchData && Array.isArray(matchData)) {
                    matchData.forEach((match, index) => {
                        const score = (match.similarity_score * 100).toFixed(1);
                        const scoreClass = score >= 80 ? 'similarity-high' : score >= 60 ? 'similarity-medium' : 'similarity-low';
                        
                        matchesHTML += `
                            <div class="card job-match-card mb-3">
                                <div class="card-body">
                                    <div class="d-flex justify-content-between align-items-start">
                                        <div class="flex-grow-1">
                                            <h6 class="card-title">${this.escapeHtml(match.job_title || 'Job Title')}</h6>
                                            <p class="text-muted mb-1">${this.escapeHtml(match.company || 'Company')}</p>
                                            <p class="small text-truncate">${match.description ? this.escapeHtml(match.description.substring(0, 150) + '...') : 'No description'}</p>
                                        </div>
                                        <div class="text-end">
                                            <span class="similarity-score ${scoreClass}">${score}%</span>
                                            <small class="d-block text-muted">Match</small>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                }
            } catch (e) {
                // Fall back to raw display if JSON parsing fails
                matchesHTML = `
                    <div class="card">
                        <div class="card-body">
                            <h6>Match Data (JSON):</h6>
                            <pre style="white-space: pre-wrap; background-color: #f8f9fa; padding: 10px; border-radius: 4px; font-size: 12px;">${this.escapeHtml(result.matches)}</pre>
                        </div>
                    </div>
                `;
            }
        } else {
            // Handle text format from match show
            const matchLines = result.matches.split('\n').filter(line => line.trim());
            let currentMatch = {};
            
            matchLines.forEach((line) => {
                if (line.includes('Job:') || line.includes('Title:')) {
                    if (Object.keys(currentMatch).length > 0) {
                        matchesHTML += this.createMatchCard(currentMatch);
                    }
                    currentMatch = { title: line.replace(/^.*?:/, '').trim() };
                } else if (line.includes('Company:')) {
                    currentMatch.company = line.replace(/^.*?:/, '').trim();
                } else if (line.includes('Score:') || line.includes('Similarity:')) {
                    const scoreMatch = line.match(/(\d+\.?\d*)%?/);
                    currentMatch.score = scoreMatch ? parseFloat(scoreMatch[1]) : 0;
                } else if (line.trim() && !line.includes('---')) {
                    currentMatch.description = (currentMatch.description || '') + ' ' + line.trim();
                }
            });
            
            // Add the last match
            if (Object.keys(currentMatch).length > 0) {
                matchesHTML += this.createMatchCard(currentMatch);
            }
            
            // Fallback to raw output if no structured matches found
            if (!matchesHTML) {
                matchesHTML = `
                    <div class="card">
                        <div class="card-body">
                            <h6>Match Results${result.resume_id ? ` (Resume ${result.resume_id})` : ''}:</h6>
                            <pre style="white-space: pre-wrap; background-color: #f8f9fa; padding: 10px; border-radius: 4px; font-size: 14px;">${result.matches}</pre>
                        </div>
                    </div>
                `;
            }
        }
        
        container.innerHTML = matchesHTML || `
            <div class="text-center text-muted">
                <i class="fas fa-exclamation-triangle fa-2x mb-3"></i>
                <p>Unable to parse match results. Please check the logs.</p>
            </div>
        `;
    }

    createMatchCard(match) {
        const score = match.score || 0;
        const scoreClass = score >= 80 ? 'similarity-high' : score >= 60 ? 'similarity-medium' : 'similarity-low';
        
        return `
            <div class="card job-match-card mb-3">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <h6 class="card-title">${this.escapeHtml(match.title || 'Job Title')}</h6>
                            <p class="text-muted mb-1">${this.escapeHtml(match.company || 'Company')}</p>
                            ${match.description ? `<p class="small text-truncate">${this.escapeHtml(match.description.substring(0, 150))}...</p>` : ''}
                        </div>
                        <div class="text-end">
                            <span class="similarity-score ${scoreClass}">${score.toFixed(1)}%</span>
                            <small class="d-block text-muted">Match</small>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    handleCommandResult(operation, result) {
        if (result.success) {
            this.logMessage('success', `${operation} completed successfully`);
            if (result.output && result.output.trim()) {
                this.logMessage('info', result.output.replace(/\n/g, ' ').substring(0, 100) + '...');
            }
        } else {
            this.logMessage('error', `${operation} failed: ${result.error || 'Unknown error'}`);
            
            // Show suggestion if available
            if (result.suggestion) {
                this.logMessage('warning', `Suggestion: ${result.suggestion}`);
                
                // If it's an embedding mismatch, offer to regenerate
                if (result.error && result.error.includes('dimension mismatch')) {
                    this.showEmbeddingMismatchDialog();
                }
            }
        }
    }
    
    showEmbeddingMismatchDialog() {
        if (confirm('Embedding dimension mismatch detected. This happens when different AI models were used. Would you like to regenerate all embeddings now? (This may take a few minutes)')) {
            this.generateEmbeddings(true); // Force regeneration
        }
    }

    setButtonLoading(buttonId, loading) {
        const button = document.getElementById(buttonId);
        if (loading) {
            button.classList.add('loading');
            button.disabled = true;
        } else {
            button.classList.remove('loading');
            button.disabled = false;
        }
    }

    logMessage(type, message) {
        const log = document.getElementById('progressLog');
        const timestamp = new Date().toLocaleTimeString();
        
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        entry.innerHTML = `<span class="text-muted">[${timestamp}]</span> ${message}`;
        
        log.appendChild(entry);
        log.scrollTop = log.scrollHeight;
        
        // Keep only last 100 entries
        while (log.children.length > 100) {
            log.removeChild(log.firstChild);
        }
    }

    showAlert(type, message) {
        // Create a temporary alert
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type === 'error' ? 'danger' : 'info'} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        const container = document.querySelector('.container');
        container.insertBefore(alertDiv, container.firstChild);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.soupBossApp = new SoupBossApp();
});