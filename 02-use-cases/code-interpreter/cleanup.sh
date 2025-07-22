#!/bin/bash

# Cleanup script for AgentCore Code Interpreter

echo "🧹 Cleaning up AgentCore Code Interpreter..."

# Stop running processes
echo "⏹ Stopping running processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

# Clean up log files
echo "📄 Cleaning up log files..."
rm -f backend.log frontend.log *.pid

# Clean up temporary files
echo "🗑 Cleaning up temporary files..."
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true

# Clean up frontend build files
echo "🌐 Cleaning up frontend build files..."
rm -rf frontend/build
rm -rf frontend/.eslintcache

# Clean up node_modules (optional - uncomment if needed)
echo "📦 Cleaning up node_modules..."
rm -rf frontend/node_modules

# Clean up Python virtual environment (optional - uncomment if needed)
echo "🐍 Cleaning up virtual environment..."
rm -rf venv

echo "✅ Cleanup completed!"
echo ""
echo "To restart the application:"
echo "  1. Run: ./setup.sh (if you removed venv or node_modules)"
echo "  2. Run: ./start.sh"
