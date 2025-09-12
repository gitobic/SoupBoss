#!/usr/bin/env python3
"""
SoupBoss Web Application Manager
Consolidated script for managing the SoupBoss web interface with start/stop/restart functionality.
"""

import argparse
import os
import signal
import subprocess
import sys
import time
import threading
from typing import List, Optional

def kill_webapp_processes(verbose: bool = True) -> bool:
    """Kill all webapp processes using multiple methods"""
    if verbose:
        print("🔄 Stopping SoupBoss web processes...")
    
    killed_pids = []
    
    # Method 1: pkill by name patterns
    try:
        patterns = ['webapp.py', 'start_webapp.py', 'webapp_manager.py.*start']
        for pattern in patterns:
            result = subprocess.run(['pkill', '-f', pattern], capture_output=True)
            if result.returncode == 0 and verbose:
                print(f"   • Killed processes matching: {pattern}")
    except FileNotFoundError:
        pass
    
    # Method 2: Kill by port usage
    try:
        result = subprocess.run(['lsof', '-ti:5000'], capture_output=True, text=True)
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGKILL)
                    killed_pids.append(pid)
                    if verbose:
                        print(f"   • Killed PID {pid} using port 5000")
                except (ValueError, OSError):
                    pass
    except FileNotFoundError:
        pass
    
    # Method 3: Python processes containing webapp
    try:
        result = subprocess.run(['pgrep', '-f', 'python.*webapp'], capture_output=True, text=True)
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid not in killed_pids:
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                        if verbose:
                            print(f"   • Killed Python webapp PID {pid}")
                    except (ValueError, OSError):
                        pass
    except FileNotFoundError:
        pass
    
    # Wait for cleanup
    time.sleep(2)
    
    # Verify port is free
    port_free = True
    try:
        result = subprocess.run(['lsof', '-i:5000'], capture_output=True, text=True)
        if result.stdout.strip():
            if verbose:
                print("⚠️  Port 5000 may still be in use:")
                print(result.stdout)
            port_free = False
        else:
            if verbose:
                print("✅ Port 5000 is free")
    except FileNotFoundError:
        if verbose:
            print("✅ Port 5000 should be free")
    
    return port_free

def check_dependencies() -> bool:
    """Check if required packages are installed"""
    try:
        import flask
        import flask_socketio
        return True
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("Run: uv add flask flask-socketio")
        return False

def start_webapp(quiet: bool = False) -> None:
    """Start the webapp with proper setup and error handling"""
    if not quiet:
        print("🚀 Starting SoupBoss Web Application...")
        print("📊 Interface will be available at:")
        print("   • http://localhost:5000")  
        print("   • http://127.0.0.1:5000")
        print("\n✨ Features: Resume upload, Company testing, Job fetching, AI matching")
        print("💡 Press Ctrl+C to stop the server")
        print("=" * 60)
    
    try:
        # Ensure required directories exist
        for directory in ['data/resumes', 'templates', 'static']:
            os.makedirs(directory, exist_ok=True)
        
        # Import and run the webapp
        from webapp import app, socketio
        socketio.run(
            app, 
            debug=False, 
            host='0.0.0.0', 
            port=5000, 
            allow_unsafe_werkzeug=True
        )
        
    except OSError as e:
        if "Address already in use" in str(e):
            print("\n❌ Error: Port 5000 is still in use!")
            print("🔧 Try running: python webapp_manager.py restart")
            sys.exit(1)
        else:
            raise
    except KeyboardInterrupt:
        if not quiet:
            print("\n👋 SoupBoss Web App stopped. Goodbye!")
        sys.exit(0)
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure webapp.py exists in the current directory")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting web app: {e}")
        sys.exit(1)

def restart_webapp() -> None:
    """Restart the webapp by killing existing processes and starting fresh"""
    print("🍲 SoupBoss Web App Restart")
    print("=" * 30)
    
    # Check dependencies first
    if not check_dependencies():
        sys.exit(1)
    
    # Kill existing processes
    port_free = kill_webapp_processes()
    
    # Start the webapp
    start_webapp()

def status_webapp() -> None:
    """Show webapp status"""
    print("📊 SoupBoss Web App Status")
    print("=" * 25)
    
    # Check if port is in use
    try:
        result = subprocess.run(['lsof', '-i:5000'], capture_output=True, text=True)
        if result.stdout.strip():
            print("✅ Web app appears to be running on port 5000")
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    print(f"   • PID {parts[1]} ({parts[0]})")
        else:
            print("⚪ Web app is not running")
    except FileNotFoundError:
        print("❓ Cannot check status (lsof not available)")
    
    # Check if webapp.py exists
    if os.path.exists('webapp.py'):
        print("✅ webapp.py found")
    else:
        print("❌ webapp.py not found")
    
    # Check dependencies
    if check_dependencies():
        print("✅ Dependencies available")
    else:
        print("❌ Missing dependencies")

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description='SoupBoss Web Application Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python webapp_manager.py start          # Start the web app
  python webapp_manager.py stop           # Stop the web app  
  python webapp_manager.py restart        # Restart the web app
  python webapp_manager.py status         # Show status
  python webapp_manager.py start --quiet  # Start without verbose output
        """
    )
    
    parser.add_argument(
        'action', 
        choices=['start', 'stop', 'restart', 'status'],
        help='Action to perform'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress verbose output'
    )
    
    args = parser.parse_args()
    
    if args.action == 'start':
        start_webapp(quiet=args.quiet)
    elif args.action == 'stop':
        kill_webapp_processes(verbose=not args.quiet)
    elif args.action == 'restart':
        restart_webapp()
    elif args.action == 'status':
        status_webapp()

if __name__ == '__main__':
    main()