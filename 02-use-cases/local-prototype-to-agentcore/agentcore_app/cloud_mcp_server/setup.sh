#!/bin/bash
set -e

echo "=========================================="
echo "MCP Server Setup"
echo "=========================================="
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found"
    echo "Please create .env file from .env_example:"
    echo "  cp .env_example .env"
    echo "  nano .env  # Edit with your values"
    echo ""
    read -p "Do you want to create .env from .env_example now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cp .env_example .env
        echo "✓ Created .env file"
        echo "Please edit .env with your values and run this script again"
        exit 0
    else
        exit 1
    fi
fi

echo "✓ .env file found"
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt
echo "✓ Requirements installed"
echo ""

# Run gateway setup
echo "=========================================="
echo "Running Gateway Setup"
echo "=========================================="
echo ""
python agentcore_gateway_setup_openapi.py

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "Setup Complete!"
    echo "=========================================="
    echo ""
    echo "Gateway information saved to gateway_info.json"
    echo ""
    echo "Next steps:"
    echo "1. Note your MCP_SERVER_URL and MCP_ACCESS_TOKEN from gateway_info.json"
    echo "2. Add these to your agent's .env file"
    echo "3. Deploy your agent"
    echo ""
    echo "To refresh your token later:"
    echo "  source .venv/bin/activate"
    echo "  python refresh_gateway_token.py"
    echo ""
else
    echo ""
    echo "❌ Setup failed"
    echo "Please check the error messages above"
    exit 1
fi
