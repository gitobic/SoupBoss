#!/usr/bin/env python3
"""
SoupBoss Web App Restart Script
Forcefully kills any existing webapp processes and restarts cleanly
"""

import os
import subprocess
import signal
import time
import psutil
import sys
from webapp import app, socketio

def kill_webapp_processes():
    """Kill all webapp processes using multiple methods"""
    print("🔄 Stopping existing SoupBoss web processes...")
    
    # Method 1: Kill by process name
    killed_by_name = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['cmdline']:
                cmdline = ' '.join(proc.info['cmdline'])
                if 'webapp.py' in cmdline or 'start_webapp.py' in cmdline:
                    print(f"   • Killing process {proc.info['pid']}: {cmdline}")
                    proc.kill()
                    killed_by_name.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    # Method 2: Kill by port usage
    killed_by_port = []
    for proc in psutil.process_iter(['pid', 'name', 'connections']):
        try:
            for conn in proc.info['connections']:
                if conn.laddr.port == 5000:
                    if proc.info['pid'] not in killed_by_name:
                        print(f"   • Killing process {proc.info['pid']} using port 5000")
                        proc.kill()
                        killed_by_port.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, AttributeError):
            pass
    
    # Method 3: Use system commands as backup
    try:
        subprocess.run(['pkill', '-f', 'webapp.py'], capture_output=True)
        subprocess.run(['pkill', '-f', 'start_webapp.py'], capture_output=True)
    except:
        pass
    
    # Method 4: Force kill port 5000 users
    try:
        result = subprocess.run(['lsof', '-ti:5000'], capture_output=True, text=True)
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGKILL)
                    print(f"   • Force killed PID {pid} using port 5000")
                except:
                    pass
    except:
        pass
    
    # Wait for processes to die
    time.sleep(2)
    
    # Verify port is free
    try:
        result = subprocess.run(['lsof', '-i:5000'], capture_output=True, text=True)
        if result.stdout.strip():
            print("⚠️  Warning: Port 5000 may still be in use")
            print(result.stdout)
        else:
            print("✅ Port 5000 is now free")
    except:
        print("✅ Port 5000 should be free")

def check_dependencies():
    """Check if required packages are installed"""
    print("🔍 Checking dependencies...")
    
    try:
        import flask
        import flask_socketio
        print("✅ Flask and Flask-SocketIO are available")
        return True
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("Run: uv add flask flask-socketio")
        return False

def start_webapp():
    """Start the webapp with proper error handling"""
    print("🚀 Starting SoupBoss Web Application...")
    print("📊 Interface will be available at:")
    print("   • http://localhost:5000")
    print("   • http://127.0.0.1:5000")
    print("   • http://0.0.0.0:5000")
    print("\n✨ Features available:")
    print("   • Resume upload and processing")
    print("   • Company job board testing")
    print("   • Job fetching from Greenhouse, Lever, SmartRecruiters") 
    print("   • AI-powered job matching with real-time progress")
    print("   • Results viewing and sorting")
    print("\n🛠️  Make sure SoupBoss CLI is properly configured first!")
    print("💡 Press Ctrl+C to stop the server")
    print("=" * 60)
    
    try:
        # Ensure required directories exist
        os.makedirs('data/resumes', exist_ok=True)
        os.makedirs('templates', exist_ok=True)
        os.makedirs('static', exist_ok=True)
        
        # Run the app
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
            print("🔧 Try running this script again, or manually kill processes using port 5000:")
            print("   sudo lsof -ti:5000 | xargs kill -9")
            sys.exit(1)
        else:
            raise
    except KeyboardInterrupt:
        print("\n👋 SoupBoss Web App stopped. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error starting web app: {e}")
        sys.exit(1)

def main():
    """Main restart function"""
    print("🍲 SoupBoss Web App Restart Script")
    print("=" * 40)
    
    # Check dependencies first
    if not check_dependencies():
        sys.exit(1)
    
    # Kill existing processes
    kill_webapp_processes()
    
    # Start the webapp
    start_webapp()

if __name__ == '__main__':
    main()