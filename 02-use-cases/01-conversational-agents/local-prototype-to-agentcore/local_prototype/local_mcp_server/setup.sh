#!/bin/bash

# LocalMCP MCP Server Setup Script

echo "🚀 Setting up LocalMCP MCP Server..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

echo "✅ Setup complete!"
echo ""
echo "To run the server:"
echo "  source venv/bin/activate"
echo "  python server.py"
echo ""
echo "To run the demo client:"
echo "  python client.py"
echo ""
echo "To run interactive mode:"
echo "  python client.py -i"
