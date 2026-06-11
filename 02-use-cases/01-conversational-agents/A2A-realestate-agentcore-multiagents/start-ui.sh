#!/bin/bash

echo "======================================================================"
echo "Real Estate UI - Starting Application"
echo "======================================================================"

# Generate UI configuration with fresh token
echo "📝 Generating UI configuration..."
python generate_ui_config.py

if [ $? -ne 0 ]; then
    echo "❌ Failed to generate configuration"
    exit 1
fi

# Navigate to UI directory
cd ui

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo ""
    echo "📦 Installing dependencies..."
    npm install
fi

echo ""
echo "🚀 Starting React development server..."
echo "The UI will open at: http://localhost:3000"
echo ""
echo "Mode: Direct connection to AWS AgentCore"
echo "No backend server needed!"
echo ""
echo "Press Ctrl+C to stop the server"
echo "======================================================================"

npm start
