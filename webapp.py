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
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
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

if __name__ == '__main__':
    # Ensure data directories exist
    os.makedirs('data/resumes', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    # Run the Flask app with SocketIO
    socketio.run(app, debug=False, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)