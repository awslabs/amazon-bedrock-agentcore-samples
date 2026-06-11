#!/bin/bash

# Slide Deck Agent Demo - Environment Setup Script
# This script creates a Python virtual environment and installs all dependencies

set -e  # Exit on any error

echo "🧠 Slide Deck Agent Demo - Environment Setup"
echo "=============================================="
echo

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "📁 Working directory: $SCRIPT_DIR"
echo

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed or not in PATH"
    echo "Please install Python 3.10+ and try again"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "🐍 Found Python: $PYTHON_VERSION"

# Check if virtual environment already exists
if [ -d "slide_demo_env" ]; then
    echo "⚠️  Virtual environment already exists"
    read -p "Do you want to recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  Removing existing environment..."
        rm -rf slide_demo_env
    else
        echo "👍 Using existing environment"
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "slide_demo_env" ]; then
    echo "🏗️  Creating virtual environment..."
    python3 -m venv slide_demo_env
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment"
        exit 1
    fi
    echo "✅ Virtual environment created: slide_demo_env"
else
    echo "✅ Using existing virtual environment"
fi

echo

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source slide_demo_env/bin/activate

if [ $? -ne 0 ]; then
    echo "❌ Failed to activate virtual environment"
    exit 1
fi

echo "✅ Virtual environment activated"

# Verify we're in the virtual environment
VIRTUAL_ENV_PYTHON=$(which python)
echo "🐍 Using Python: $VIRTUAL_ENV_PYTHON"

echo

# Upgrade pip
echo "⬆️  Upgrading pip..."
python -m pip install --upgrade pip --quiet

if [ $? -ne 0 ]; then
    echo "❌ Failed to upgrade pip"
    exit 1
fi

echo "✅ pip upgraded successfully"

echo

# Install requirements
echo "📦 Installing dependencies from requirements.txt..."
echo "   This may take a few minutes..."

pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies"
    echo "Please check the error messages above and try again"
    exit 1
fi

echo "✅ All dependencies installed successfully"

echo

# Verify key packages
echo "🧪 Verifying key installations..."

# Test python-pptx
python -c "from pptx import Presentation; print('   ✅ python-pptx: OK')" 2>/dev/null || echo "   ❌ python-pptx: Failed"

# Test Flask
python -c "from flask import Flask; print('   ✅ Flask: OK')" 2>/dev/null || echo "   ❌ Flask: Failed"

# Test other key packages
python -c "import boto3; print('   ✅ boto3: OK')" 2>/dev/null || echo "   ❌ boto3: Failed"
python -c "from jinja2 import Template; print('   ✅ Jinja2: OK')" 2>/dev/null || echo "   ❌ Jinja2: Failed"

echo

# Check AWS credentials (optional)
echo "🔐 Checking AWS configuration..."
if command -v aws &> /dev/null; then
    if aws sts get-caller-identity &> /dev/null; then
        echo "   ✅ AWS credentials configured"
    else
        echo "   ⚠️  AWS credentials not configured"
        echo "   💡 Run 'aws configure' to set up AWS access for memory features"
    fi
else
    echo "   ⚠️  AWS CLI not found"
    echo "   💡 Install AWS CLI and run 'aws configure' for full functionality"
fi

echo

# Success message
echo "🎉 Environment setup complete!"
echo
echo "📋 Next steps:"
echo "   1. Activate the environment (if not already active):"
echo "      source slide_demo_env/bin/activate"
echo
echo "   2. Run the demo:"
echo "      python main.py"
echo
echo "   3. Open your browser to:"
echo "      http://localhost:5000"
echo
echo "   4. When done, deactivate with:"
echo "      deactivate"

# Create activation helper script
cat > activate_env.sh << 'EOF'
#!/bin/bash
# Helper script to activate the slide demo environment
source slide_demo_env/bin/activate
echo "🧠 Slide Demo environment activated!"
echo "Run 'python main.py' to start the demo"
EOF

chmod +x activate_env.sh
echo "💡 Created helper script: ./activate_env.sh"

echo
echo "🚀 Ready to demonstrate the importance of Agent Memory!"