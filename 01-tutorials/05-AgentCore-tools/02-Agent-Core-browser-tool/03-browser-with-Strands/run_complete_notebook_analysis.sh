#!/bin/bash

# Complete Notebook Analysis Script
# Tests environment setup, imports, and runs all analysis cells

set -e

echo "🚀 Complete Notebook Analysis Test Suite"
echo "========================================"
echo "This script will test:"
echo "1. Environment setup and virtual environment"
echo "2. Package imports and dependencies"
echo "3. System initialization"
echo "4. BBC News analysis"
echo "5. Tesla Stock analysis"
echo "6. GitHub Trending analysis"
echo "7. Results listing and summary"
echo ""

# Check if we're in the right directory
if [ ! -f "02_agentcore-browser-tool-live-view-with-strands.ipynb" ]; then
    echo "❌ Notebook file not found in current directory"
    echo "💡 Please run this script from the notebook directory:"
    echo "   cd 01-tutorials/05-AgentCore-tools/02-Agent-Core-browser-tool/03-browser-with-Strands"
    exit 1
fi

# Test 1: Environment Setup
echo "TEST 1: Environment Setup"
echo "========================="

# Check if virtual environment exists, create if needed
if [ ! -d "venv" ]; then
    echo "🔧 Creating Python 3.12 virtual environment..."
    python3.12 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment"
        echo "💡 Please ensure Python 3.12 is installed"
        exit 1
    fi
fi

echo "🔧 Activating virtual environment..."
source venv/bin/activate

echo "✅ Virtual environment activated"
echo "🐍 Python version: $(python --version)"
echo "📦 Pip version: $(pip --version)"

# Install requirements if they exist
if [ -f "requirements.txt" ]; then
    echo "📦 Installing requirements..."
    pip install -r requirements.txt --quiet
    echo "✅ Requirements installed"
fi
echo ""

# Test 2: Package Dependencies
echo "TEST 2: Package Dependencies"
echo "============================"

echo "🔍 Checking required packages..."
source venv/bin/activate && python -c "
import sys
packages_to_check = [
    'bedrock_agentcore',
    'strands', 
    'playwright',
    'nbformat',
    'boto3',
    'pathlib'
]

missing_packages = []
for package in packages_to_check:
    try:
        __import__(package)
        print(f'✅ {package}')
    except ImportError:
        print(f'❌ {package} - MISSING')
        missing_packages.append(package)

if missing_packages:
    print(f'\\n❌ Missing packages: {missing_packages}')
    sys.exit(1)
else:
    print('\\n✅ All required packages are available')
"

echo ""

# Test 3: System Setup and Initialization
echo "TEST 3: System Setup and Initialization"
echo "======================================="

source venv/bin/activate && ipython -c "
import nbformat

# Load the notebook
with open('02_agentcore-browser-tool-live-view-with-strands.ipynb', 'r') as f:
    nb = nbformat.read(f, as_version=4)

# Get code cells only
code_cells = [cell for cell in nb.cells if cell.cell_type == 'code']

print('=== TESTING IMPORTS ===')
exec(code_cells[2].source)  # imports (cell 5 in notebook)

print('\\n=== TESTING CLASS DEFINITION ===')
exec(code_cells[3].source)  # class definition (cell 7 in notebook)

print('\\n=== TESTING SYSTEM INITIALIZATION ===')
exec(code_cells[4].source)  # system initialization (cell 9 in notebook)

print('\\n✅ System setup and initialization completed successfully!')
"

echo ""

# Test 4: BBC News Analysis
echo "TEST 4: BBC News Analysis"
echo "========================="

source venv/bin/activate && ipython -c "
import nbformat

# Load the notebook
with open('02_agentcore-browser-tool-live-view-with-strands.ipynb', 'r') as f:
    nb = nbformat.read(f, as_version=4)

code_cells = [cell for cell in nb.cells if cell.cell_type == 'code']

# Setup system
exec(code_cells[2].source)  # imports
exec(code_cells[3].source)  # class definition  
exec(code_cells[4].source)  # system initialization

# Execute BBC News analysis (cell 12 in notebook)
print('=== EXECUTING BBC NEWS ANALYSIS ===')
exec(code_cells[5].source)
print('✅ BBC News analysis completed!')
"

echo ""

# Test 5: Tesla Stock Analysis
echo "TEST 5: Tesla Stock Analysis"
echo "============================"

source venv/bin/activate && ipython -c "
import nbformat

# Load the notebook
with open('02_agentcore-browser-tool-live-view-with-strands.ipynb', 'r') as f:
    nb = nbformat.read(f, as_version=4)

code_cells = [cell for cell in nb.cells if cell.cell_type == 'code']

# Setup system
exec(code_cells[2].source)  # imports
exec(code_cells[3].source)  # class definition  
exec(code_cells[4].source)  # system initialization

# Execute Tesla Stock analysis (cell 14 in notebook)
print('=== EXECUTING TESLA STOCK ANALYSIS ===')
exec(code_cells[6].source)
print('✅ Tesla Stock analysis completed!')
"

echo ""

# Test 6: GitHub Trending Analysis
echo "TEST 6: GitHub Trending Analysis"
echo "================================"

source venv/bin/activate && ipython -c "
import nbformat

# Load the notebook
with open('02_agentcore-browser-tool-live-view-with-strands.ipynb', 'r') as f:
    nb = nbformat.read(f, as_version=4)

code_cells = [cell for cell in nb.cells if cell.cell_type == 'code']

# Setup system
exec(code_cells[2].source)  # imports
exec(code_cells[3].source)  # class definition  
exec(code_cells[4].source)  # system initialization

# Execute GitHub Trending analysis (cell 18 in notebook, now cell 7 after removing Amazon)
print('=== EXECUTING GITHUB TRENDING ANALYSIS ===')
exec(code_cells[7].source)
print('✅ GitHub Trending analysis completed!')
"

echo ""

# Test 7: Results and Summary
echo "TEST 7: Results and Summary"
echo "=========================="

source venv/bin/activate && ipython -c "
import nbformat

# Load the notebook
with open('02_agentcore-browser-tool-live-view-with-strands.ipynb', 'r') as f:
    nb = nbformat.read(f, as_version=4)

code_cells = [cell for cell in nb.cells if cell.cell_type == 'code']

# Setup system
exec(code_cells[2].source)  # imports
exec(code_cells[3].source)  # class definition  
exec(code_cells[4].source)  # system initialization

# List analysis results (now cell 8 after removing Amazon)
print('=== LISTING ANALYSIS RESULTS ===')
exec(code_cells[8].source)

# Display recent analysis (now cell 9 after removing Amazon)
print('\\n=== DISPLAYING RECENT ANALYSIS ===')
exec(code_cells[9].source)

# System summary (now cell 10 after removing Amazon)
print('\\n=== SYSTEM SUMMARY ===')
exec(code_cells[10].source)

print('\\n✅ Results and summary completed!')
"

echo ""

# Final Summary
echo "🏁 COMPLETE NOTEBOOK ANALYSIS SUMMARY"
echo "====================================="
echo "✅ Environment Setup: TESTED"
echo "✅ Package Dependencies: TESTED"
echo "✅ System Initialization: TESTED"
echo "✅ BBC News Analysis: COMPLETED"
echo "✅ Tesla Stock Analysis: COMPLETED"
echo "✅ GitHub Trending Analysis: COMPLETED"
echo "✅ Results and Summary: COMPLETED"
echo ""
echo "🎉 All notebook functionality has been tested successfully!"
echo "🌐 Live viewer should be running at: http://localhost:8000"
echo "📁 Check analysis_results/ directory for all outputs"
echo ""
echo "📊 Analysis Results Generated:"
echo "   📰 BBC News analysis with top stories"
echo "   📈 Tesla stock analysis with financial metrics"
echo "   💻 GitHub trending repositories analysis"
echo ""
echo "🎯 The complete Strands + AgentCore system is fully functional!"