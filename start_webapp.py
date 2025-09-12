#!/usr/bin/env python3
"""
SoupBoss Web App Startup Script
Run this to start the web interface for SoupBoss
"""

import os
import sys
from webapp import app, socketio

def main():
    print("🍲 Starting SoupBoss Web Application...")
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
        
    except KeyboardInterrupt:
        print("\n👋 SoupBoss Web App stopped. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error starting web app: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()