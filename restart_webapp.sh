#!/bin/bash

echo "🍲 SoupBoss Web App Restart Script"
echo "=================================="

echo "🔄 Stopping existing processes..."

# Kill webapp processes
pkill -f "webapp.py" 2>/dev/null
pkill -f "start_webapp.py" 2>/dev/null

# Kill processes using port 5000
if command -v lsof >/dev/null 2>&1; then
    PIDS=$(lsof -ti:5000 2>/dev/null)
    if [ ! -z "$PIDS" ]; then
        echo "   • Killing processes using port 5000: $PIDS"
        echo $PIDS | xargs kill -9 2>/dev/null
    fi
fi

# Kill any python processes with webapp in command line
WEBAPP_PIDS=$(pgrep -f "python.*webapp" 2>/dev/null)
if [ ! -z "$WEBAPP_PIDS" ]; then
    echo "   • Killing webapp Python processes: $WEBAPP_PIDS"
    echo $WEBAPP_PIDS | xargs kill -9 2>/dev/null
fi

echo "⏳ Waiting 2 seconds for cleanup..."
sleep 2

# Check if port is free
if command -v lsof >/dev/null 2>&1; then
    PORT_CHECK=$(lsof -i:5000 2>/dev/null)
    if [ ! -z "$PORT_CHECK" ]; then
        echo "⚠️  Warning: Port 5000 still in use"
        echo "$PORT_CHECK"
    else
        echo "✅ Port 5000 is free"
    fi
fi

echo ""
echo "🚀 Starting SoupBoss Web Application..."
echo "📊 Interface will be available at:"
echo "   • http://localhost:5000"
echo "   • http://127.0.0.1:5000"
echo ""
echo "💡 Press Ctrl+C to stop the server"
echo "=================================="

# Start the webapp
uv run python webapp.py