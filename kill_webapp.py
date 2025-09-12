#!/usr/bin/env python3
"""
SoupBoss Web App Kill Script
Forcefully stops all webapp processes
"""

import subprocess
import signal
import os
import time

def kill_webapp():
    """Kill webapp processes using multiple methods"""
    print("🔄 Stopping SoupBoss web processes...")
    
    methods_tried = []
    
    # Method 1: pkill by name
    try:
        result1 = subprocess.run(['pkill', '-f', 'webapp.py'], capture_output=True)
        result2 = subprocess.run(['pkill', '-f', 'start_webapp.py'], capture_output=True)
        methods_tried.append("pkill by name")
    except:
        pass
    
    # Method 2: Kill by port
    try:
        result = subprocess.run(['lsof', '-ti:5000'], capture_output=True, text=True)
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                try:
                    subprocess.run(['kill', '-9', pid])
                    print(f"   • Killed PID {pid} using port 5000")
                except:
                    pass
            methods_tried.append("kill by port")
    except:
        pass
    
    # Method 3: Python processes containing webapp
    try:
        result = subprocess.run(['pgrep', '-f', 'python.*webapp'], capture_output=True, text=True)
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                try:
                    subprocess.run(['kill', '-9', pid])
                    print(f"   • Killed Python webapp PID {pid}")
                except:
                    pass
            methods_tried.append("pgrep python webapp")
    except:
        pass
    
    # Wait and check
    time.sleep(2)
    
    try:
        result = subprocess.run(['lsof', '-i:5000'], capture_output=True, text=True)
        if result.stdout.strip():
            print("⚠️  Port 5000 may still be in use:")
            print(result.stdout)
        else:
            print("✅ Port 5000 is free")
    except:
        print("✅ Port 5000 should be free")
    
    print(f"🔧 Methods used: {', '.join(methods_tried) if methods_tried else 'none needed'}")

if __name__ == '__main__':
    kill_webapp()