#!/bin/bash

# Setup script for Bedrock AgentCore Browser Tool with Strands Integration
# This script sets up the environment and installs all required dependencies

echo "🚀 Setting up Bedrock AgentCore Browser Tool with Strands Integration"
echo "=================================================================="

# Check Python version
if command -v python3.10 &> /dev/null; then
    python_version=$(python3.10 --version 2>&1 | grep -o '[0-9]\+\.[0-9]\+')
    echo "✅ Python $python_version detected (using python3.10)"
else
    python_version=$(python3 --version 2>&1 | grep -o '[0-9]\+\.[0-9]\+')
    required_version="3.10"
    
    if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" = "$required_version" ]; then
        echo "✅ Python $python_version detected (>= 3.10 required)"
    else
        echo "❌ Python 3.10+ required. Current version: $python_version"
        echo "Please install Python 3.10+ or ensure python3.10 is available"
        exit 1
    fi
fi

# Create virtual environment
echo "📦 Creating virtual environment..."
python3.10 -m venv venv_310

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv_310/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📚 Installing Python dependencies..."
pip install -r requirements.txt

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
playwright install

echo ""
echo "🎉 Setup completed successfully!"
echo ""
echo "To use the integration:"
echo "1. Activate the virtual environment: source venv_310/bin/activate"
echo "2. Configure AWS credentials (if not already done)"
echo "3. Run the test: python test_integration.py"
echo "4. Use in your code: from bedrock_strands_browser_tool import browse_web"
echo ""
echo "✅ Ready to use Bedrock AgentCore browser automation with Strands!"