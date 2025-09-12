#!/usr/bin/env python3
"""
SoupBoss Web Application
A Flask-based web interface for the SoupBoss job matching system.
"""

import os
import subprocess
import json
import tempfile
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, Response
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'soupboss-web-secret-key'
app.config['UPLOAD_FOLDER'] = 'data/resumes'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize SocketIO for real-time updates
socketio = SocketIO(app, cors_allowed_origins="*")

# Allowed file extensions for resume uploads
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt', 'md'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def run_soupboss_command(command_args, emit_progress=None):
    """Run a SoupBoss CLI command and optionally emit progress updates"""
    try:
        cmd = ['uv', 'run', 'python', 'main.py'] + command_args
        
        if emit_progress:
            emit_progress('info', f"Running command: {' '.join(command_args)}")
        
        # Run command and capture output
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            cwd=os.getcwd()
        )
        
        if result.returncode == 0:
            if emit_progress:
                emit_progress('success', 'Command completed successfully')
            return {'success': True, 'output': result.stdout, 'error': ''}
        else:
            if emit_progress:
                emit_progress('error', f'Command failed: {result.stderr}')
            return {'success': False, 'output': result.stdout, 'error': result.stderr}
            
    except Exception as e:
        error_msg = f"Error running command: {str(e)}"
        if emit_progress:
            emit_progress('error', error_msg)
        return {'success': False, 'output': '', 'error': error_msg}

@app.route('/')
def index():
    """Main page with tabbed interface"""
    return render_template('index.html')

@app.route('/CLI_REFERENCE.md')
def cli_reference():
    """Serve CLI reference documentation"""
    try:
        with open('CLI_REFERENCE.md', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Convert markdown to HTML for better display
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>SoupBoss CLI Reference</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                       max-width: 1200px; margin: 0 auto; padding: 20px; line-height: 1.6; }}
                pre {{ background: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto; }}
                code {{ background: #f8f9fa; padding: 2px 4px; border-radius: 3px; }}
                h1, h2, h3 {{ color: #333; }}
                h1 {{ border-bottom: 2px solid #eee; padding-bottom: 10px; }}
                h2 {{ border-bottom: 1px solid #eee; padding-bottom: 5px; }}
                table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .back-btn {{ display: inline-block; margin-bottom: 20px; padding: 8px 16px; 
                           background: #007bff; color: white; text-decoration: none; 
                           border-radius: 4px; }}
                .back-btn:hover {{ background: #0056b3; color: white; text-decoration: none; }}
            </style>
        </head>
        <body>
            <a href="/" class="back-btn">← Back to SoupBoss Web Interface</a>
            <pre>{content}</pre>
        </body>
        </html>
        """
        return html_content
        
    except FileNotFoundError:
        return "CLI Reference file not found", 404

@app.route('/api/status')
def get_status():
    """Get system status"""
    result = run_soupboss_command(['status'])
    return jsonify(result)

@app.route('/api/upload-resume', methods=['POST'])
def upload_resume():
    """Handle resume file upload"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file selected'})
    
    file = request.files['file']
    resume_name = request.form.get('resume_name', '')
    
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'})
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        # Ensure upload directory exists
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # Save file
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Add resume to SoupBoss
        name_arg = resume_name if resume_name else filename
        result = run_soupboss_command(['resumes', 'add', filepath, '--name', name_arg])
        
        return jsonify(result)
    
    return jsonify({'success': False, 'error': 'Invalid file type'})

@app.route('/api/test-company', methods=['POST'])
def test_company():
    """Test if a company has a job board"""
    data = request.get_json()
    company = data.get('company', '').strip()
    source = data.get('source', 'greenhouse').strip()
    
    if not company:
        return jsonify({'success': False, 'error': 'Company name is required'})
    
    # Map source to the appropriate test script
    script_map = {
        'greenhouse': 'greenhouse_fetch.py',
        'lever': 'lever_fetch.py', 
        'smartrecruiters': 'smartrecruiters_fetch.py'
    }
    
    if source not in script_map:
        return jsonify({'success': False, 'error': 'Invalid source'})
    
    try:
        cmd = ['uv', 'run', 'python', script_map[source], '-test', company]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
        
        success = result.returncode == 0
        return jsonify({
            'success': success,
            'output': result.stdout,
            'error': result.stderr if not success else ''
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/add-company', methods=['POST'])
def add_company():
    """Add a company to SoupBoss"""
    data = request.get_json()
    company = data.get('company', '').strip()
    source = data.get('source', 'greenhouse').strip()
    
    if not company:
        return jsonify({'success': False, 'error': 'Company name is required'})
    
    result = run_soupboss_command(['companies', 'add', company, '--source', source])
    return jsonify(result)

@app.route('/api/fetch-jobs', methods=['POST'])
def fetch_jobs():
    """Fetch jobs for a company"""
    data = request.get_json()
    company = data.get('company', '').strip()
    source = data.get('source', 'greenhouse').strip()
    
    if not company:
        return jsonify({'success': False, 'error': 'Company name is required'})
    
    result = run_soupboss_command(['jobs', 'fetch', '--source', source, '--company', company])
    return jsonify(result)

@app.route('/api/generate-embeddings', methods=['POST'])
def generate_embeddings():
    """Generate embeddings for matching"""
    force = request.get_json().get('force', False) if request.is_json else False
    
    cmd = ['match', 'generate']
    if force:
        cmd.append('--force')
    
    result = run_soupboss_command(cmd)
    return jsonify(result)

@app.route('/api/run-matching', methods=['POST'])
def run_matching():
    """Run job matching algorithm"""
    result = run_soupboss_command(['match', 'run'])
    
    # Check for common embedding dimension mismatch error
    if not result['success'] and 'shapes' in result['error'] and 'not aligned' in result['error']:
        result['error'] = 'Embedding dimension mismatch detected. Different embedding models were used. Please regenerate embeddings first.'
        result['suggestion'] = 'Click "Generate Embeddings" with force option to fix this issue.'
    
    return jsonify(result)

@app.route('/api/get-matches')
def get_matches():
    """Get job matches with sorting options"""
    limit = request.args.get('limit', '50')
    sort_by = request.args.get('sort_by', 'similarity')
    
    # First get list of resumes to know which ones to show matches for
    resumes_result = run_soupboss_command(['resumes', 'list'])
    if not resumes_result['success']:
        return jsonify({'success': False, 'error': 'Failed to get resumes list', 'matches': '', 'count': 0})
    
    # Create a temporary filename for export
    import tempfile
    import os
    import json
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_file = f"webapp_matches_{timestamp}.json"
    
    try:
        # Export matches to a specific file
        export_result = run_soupboss_command([
            'match', 'export', 
            '--format', 'json', 
            '--limit', limit,
            '--output', temp_file
        ])
        
        if export_result['success']:
            # Read the exported JSON file
            if os.path.exists(temp_file):
                try:
                    with open(temp_file, 'r') as f:
                        match_data = json.load(f)
                    
                    # Clean up the temp file
                    os.remove(temp_file)
                    
                    # Extract matches from the nested structure
                    matches_array = match_data.get('matches', []) if isinstance(match_data, dict) else match_data
                    
                    # Sort the matches based on sort_by parameter
                    if isinstance(matches_array, list) and matches_array:
                        if sort_by == 'similarity':
                            matches_array.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
                        elif sort_by == 'company':
                            matches_array.sort(key=lambda x: x.get('company_name', '').lower())
                        elif sort_by == 'title':
                            matches_array.sort(key=lambda x: x.get('job_title', '').lower())
                        elif sort_by == 'date':
                            matches_array.sort(key=lambda x: x.get('posted_date', ''), reverse=True)
                    
                    return jsonify({
                        'success': True,
                        'matches': matches_array,
                        'count': len(matches_array) if isinstance(matches_array, list) else 0,
                        'format': 'json_data',
                        'sort_by': sort_by,
                        'total_matches': match_data.get('total_matches', 0) if isinstance(match_data, dict) else len(matches_array)
                    })
                
                except json.JSONDecodeError as e:
                    # Clean up file and fall back
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    return jsonify({
                        'success': False,
                        'error': f'Failed to parse exported JSON: {str(e)}',
                        'matches': [],
                        'count': 0
                    })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Export file was not created. Export output: {export_result.get("output", "No output")}',
                    'matches': [],
                    'count': 0
                })
        
        # Fallback: try to get matches for first resume using match show
        resume_lines = resumes_result['output'].strip().split('\n')
        resume_id = '1'  # Default to first resume
        
        # Try to extract resume ID from the table
        for line in resume_lines:
            if '│' in line and any(char.isdigit() for char in line):
                parts = [part.strip() for part in line.split('│') if part.strip()]
                if parts and parts[0].isdigit():
                    resume_id = parts[0]
                    break
        
        # Get matches for specific resume
        show_result = run_soupboss_command(['match', 'show', resume_id, '--limit', limit])
        
        if show_result['success']:
            return jsonify({
                'success': True,
                'matches': show_result['output'],
                'count': 0,
                'format': 'text',
                'resume_id': resume_id
            })
        else:
            return jsonify({
                'success': False, 
                'error': f'Failed to get matches. Export error: {export_result.get("error", "Unknown")}, Show error: {show_result.get("error", "Unknown")}',
                'matches': '',
                'count': 0
            })
    
    finally:
        # Cleanup: remove temp file if it still exists
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass

# WebSocket events for real-time updates
@socketio.on('connect')
def handle_connect():
    emit('message', {'type': 'info', 'message': 'Connected to SoupBoss'})

@socketio.on('start_job_fetch')
def handle_job_fetch(data):
    """Handle real-time job fetching"""
    def fetch_with_progress():
        company = data.get('company', '').strip()
        source = data.get('source', 'greenhouse')
        
        def progress_callback(msg_type, message):
            socketio.emit('progress', {'type': msg_type, 'message': message})
        
        result = run_soupboss_command(
            ['jobs', 'fetch', '--source', source, '--company', company],
            emit_progress=progress_callback
        )
        
        socketio.emit('job_fetch_complete', result)
    
    # Run in background thread
    thread = threading.Thread(target=fetch_with_progress)
    thread.start()

@socketio.on('start_matching')
def handle_matching(data):
    """Handle real-time matching process"""
    def match_with_progress():
        def progress_callback(msg_type, message):
            socketio.emit('progress', {'type': msg_type, 'message': message})
        
        # Generate embeddings first
        progress_callback('info', 'Generating embeddings...')
        embed_result = run_soupboss_command(['match', 'generate'], emit_progress=progress_callback)
        
        if embed_result['success']:
            # Run matching
            progress_callback('info', 'Running job matching...')
            match_result = run_soupboss_command(['match', 'run'], emit_progress=progress_callback)
            socketio.emit('matching_complete', match_result)
        else:
            socketio.emit('matching_complete', embed_result)
    
    # Run in background thread
    thread = threading.Thread(target=match_with_progress)
    thread.start()

@app.route('/api/export-matches')
def export_matches():
    """Export job matches in various formats for download"""
    format_type = request.args.get('format', 'csv')
    limit = request.args.get('limit', '50')
    sort_by = request.args.get('sort_by', 'similarity')
    
    # Create temporary file for export
    temp_dir = tempfile.mkdtemp()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if format_type == 'csv':
        filename = f'soupboss_matches_{timestamp}.csv'
        temp_file = os.path.join(temp_dir, filename)
    elif format_type == 'json':
        filename = f'soupboss_matches_{timestamp}.json'
        temp_file = os.path.join(temp_dir, filename)
    elif format_type == 'html':
        filename = f'soupboss_matches_{timestamp}.html'
        temp_file = os.path.join(temp_dir, filename)
    else:
        return jsonify({'success': False, 'error': 'Invalid format type'})
    
    try:
        # Export matches using CLI command
        export_result = run_soupboss_command([
            'match', 'export', '--format', format_type, '--limit', limit, '--output', temp_file
        ])
        
        if export_result['success'] and os.path.exists(temp_file):
            # Read the file content
            with open(temp_file, 'rb') as f:
                file_content = f.read()
            
            # Clean up temp file
            os.remove(temp_file)
            os.rmdir(temp_dir)
            
            # Determine MIME type
            if format_type == 'csv':
                mimetype = 'text/csv'
            elif format_type == 'json':
                mimetype = 'application/json'
            elif format_type == 'html':
                mimetype = 'text/html'
            
            # Return file for download
            return Response(
                file_content,
                mimetype=mimetype,
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'Content-Length': str(len(file_content))
                }
            )
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to export matches: {export_result.get("error", "Unknown error")}'
            })
            
    except Exception as e:
        # Clean up temp files if they exist
        if os.path.exists(temp_file):
            os.remove(temp_file)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
        
        return jsonify({
            'success': False,
            'error': f'Export error: {str(e)}'
        })

@app.route('/api/list-models')
def list_models():
    """Get list of available Ollama models"""
    result = run_soupboss_command(['match', 'list-models'])
    return jsonify(result)

@app.route('/api/get-current-model')
def get_current_model():
    """Get current model from config"""
    try:
        with open('soupboss.config.json', 'r') as f:
            config = json.load(f)
        current_model = config.get('ollama', {}).get('model', 'embeddinggemma:300m')
        return jsonify({'success': True, 'model': current_model})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/set-model', methods=['POST'])
def set_model():
    """Set new embedding model in config"""
    data = request.json
    model_name = data.get('model')
    
    if not model_name:
        return jsonify({'success': False, 'error': 'Model name is required'})
    
    try:
        # Read current config
        with open('soupboss.config.json', 'r') as f:
            config = json.load(f)
        
        # Update model
        config['ollama']['model'] = model_name
        
        # Write back to config
        with open('soupboss.config.json', 'w') as f:
            json.dump(config, f, indent=2)
        
        return jsonify({'success': True, 'message': f'Model updated to {model_name}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/force-regenerate', methods=['POST'])
def force_regenerate():
    """Force regenerate all embeddings"""
    result = run_soupboss_command(['match', 'generate', '--force'])
    return jsonify(result)

@app.route('/api/reset-environment', methods=['POST'])
def reset_environment():
    """Reset entire environment by deleting database and resume files"""
    try:
        import shutil
        
        # Delete database file
        db_path = 'data/soupboss.db'
        if os.path.exists(db_path):
            os.remove(db_path)
        
        # Delete resume files
        resume_dir = 'data/resumes'
        if os.path.exists(resume_dir):
            shutil.rmtree(resume_dir)
            os.makedirs(resume_dir)
        
        return jsonify({
            'success': True, 
            'message': 'Environment reset successfully. Database and resume files deleted.'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/backup-data')
def backup_data():
    """Create and download database backup"""
    result = run_soupboss_command(['maintenance', 'backup'])
    
    if result['success']:
        # The backup command should create a backup file
        # We need to find and return it for download
        backup_files = [f for f in os.listdir('.') if f.startswith('soupboss_backup_') and f.endswith('.db')]
        if backup_files:
            backup_file = sorted(backup_files)[-1]  # Get the most recent
            try:
                with open(backup_file, 'rb') as f:
                    file_content = f.read()
                
                return Response(
                    file_content,
                    mimetype='application/octet-stream',
                    headers={
                        'Content-Disposition': f'attachment; filename="{backup_file}"',
                        'Content-Length': str(len(file_content))
                    }
                )
            except Exception as e:
                return jsonify({'success': False, 'error': f'Failed to read backup file: {str(e)}'})
        else:
            return jsonify({'success': False, 'error': 'Backup file not found'})
    else:
        return jsonify(result)

@app.route('/api/companies-list')
def companies_list():
    """Get list of companies with job counts and embedding status"""
    result = run_soupboss_command(['companies', 'list'])
    
    if result['success']:
        companies_data = []
        lines = result['output'].split('\n')
        
        for line in lines:
            # Parse table rows with company data
            if line.strip() and '│' in line and not line.startswith('┏') and not line.startswith('┗') and not line.startswith('┃'):
                columns = [col.strip() for col in line.split('│') if col.strip()]
                if len(columns) >= 3 and columns[0] != 'ID':  # Skip header
                    # Correct column mapping: ID, Name, Source, Status, Created
                    companies_data.append({
                        'company_id': columns[0] if len(columns) > 0 else 'Unknown',  # Company ID from column 0
                        'name': columns[1] if len(columns) > 1 else 'Unknown',  # Name is column 1
                        'source': columns[2] if len(columns) > 2 else 'Unknown',  # Source is column 2
                        'job_count': '0',  # Will be updated by separate query
                        'embedded_count': '0'  # Will be updated by separate query
                    })
        
        # Get job counts for each company
        for company in companies_data:
            jobs_result = run_soupboss_command(['jobs', 'list', '--company', company['name']])
            if jobs_result['success']:
                # Extract job count from the header line that shows "Job Listings (X of Y)"
                output = jobs_result['output']
                count_match = None
                
                # Look for the count in the header
                for line in output.split('\n'):
                    if 'Job Listings' in line and 'of' in line:
                        # Extract numbers from "Job Listings (33 of 33)"
                        import re
                        match = re.search(r'Job Listings \((\d+) of (\d+)\)', line)
                        if match:
                            company['job_count'] = match.group(1)
                            # For embedded count, assume all jobs in system are embedded
                            company['embedded_count'] = match.group(1)
                            break
                
                # Fallback: count table rows if header parsing failed
                if company['job_count'] == '0':
                    job_lines = [l for l in output.split('\n') if '│' in l and not l.startswith('┏') and not l.startswith('┗') and not l.startswith('┃')]
                    if job_lines:
                        count = max(0, len(job_lines) - 1)  # Subtract header
                        company['job_count'] = str(count)
                        company['embedded_count'] = str(count)  # Assume all embedded
        
        return jsonify({'success': True, 'data': companies_data})
    else:
        return jsonify(result)

@app.route('/api/jobs-list')
def jobs_list():
    """Get list of jobs with details"""
    result = run_soupboss_command(['jobs', 'list', '--limit', '200'])
    
    if result['success']:
        jobs_data = []
        lines = result['output'].split('\n')
        
        for line in lines:
            # Parse table rows with job data  
            if line.strip() and '│' in line and not line.startswith('┏') and not line.startswith('┗') and not line.startswith('┃'):
                columns = [col.strip() for col in line.split('│') if col.strip()]
                if len(columns) >= 4 and columns[0] != 'ID':  # Skip header
                    jobs_data.append({
                        'job_id': columns[0] if len(columns) > 0 else 'Unknown',  # Job ID from column 0
                        'company': columns[1] if len(columns) > 1 else 'Unknown',
                        'title': columns[2] if len(columns) > 2 else 'Unknown',
                        'department': columns[3] if len(columns) > 3 else 'Unknown',
                        'location': columns[4] if len(columns) > 4 else 'Unknown',
                        'source': columns[5] if len(columns) > 5 else 'Unknown',
                        'embedded': 'Yes'  # Assume embedded if in system
                    })
        
        return jsonify({'success': True, 'data': jobs_data})
    else:
        return jsonify(result)

@app.route('/api/resumes-list')
def resumes_list():
    """Get list of resumes with details"""
    result = run_soupboss_command(['resumes', 'list'])
    
    if result['success']:
        resumes_data = []
        lines = result['output'].split('\n')
        
        for line in lines:
            # Parse table rows with resume data
            if line.strip() and '│' in line and not line.startswith('┏') and not line.startswith('┗') and not line.startswith('┃'):
                columns = [col.strip() for col in line.split('│') if col.strip()]
                if len(columns) >= 3 and columns[0] != 'ID':  # Skip header
                    resumes_data.append({
                        'resume_id': columns[0] if len(columns) > 0 else 'Unknown',  # Resume ID from column 0
                        'name': columns[1] if len(columns) > 1 else 'Unknown',
                        'filename': columns[2] if len(columns) > 2 else 'Unknown',
                        'upload_date': columns[4] if len(columns) > 4 else 'Unknown',  # Date is column 4 (Added)
                        'embedded': 'Yes'  # Assume embedded if processed
                    })
        
        return jsonify({'success': True, 'data': resumes_data})
    else:
        return jsonify(result)

@app.route('/api/export-data')
def export_data():
    """Export data listings in various formats"""
    data_type = request.args.get('type', 'companies')
    format_type = request.args.get('format', 'csv')
    
    # Map data types to CLI commands
    if data_type == 'companies':
        export_result = run_soupboss_command(['companies', 'export', '--format', format_type])
    elif data_type == 'jobs':
        export_result = run_soupboss_command(['jobs', 'export', '--format', format_type, '--limit', '500'])
    elif data_type == 'resumes':
        export_result = run_soupboss_command(['resumes', 'export', '--format', format_type])
    else:
        return jsonify({'success': False, 'error': 'Invalid data type'})
    
    if export_result['success']:
        # For now, return the CLI result - in a real implementation you'd generate proper files
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'soupboss_{data_type}_{timestamp}.{format_type}'
        
        # Return the CLI output as file content
        content = export_result.get('output', '')
        
        # Determine MIME type
        if format_type == 'csv':
            mimetype = 'text/csv'
        elif format_type == 'json':
            mimetype = 'application/json'
        else:
            mimetype = 'text/plain'
        
        return Response(
            content,
            mimetype=mimetype,
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Length': str(len(content))
            }
        )
    else:
        return jsonify(export_result)

if __name__ == '__main__':
    # NOTE: For better process management, consider using webapp_manager.py instead
    # which provides start/stop/restart/status functionality
    
    # Ensure data directories exist
    os.makedirs('data/resumes', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    # Run the Flask app with SocketIO
    socketio.run(app, debug=False, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)