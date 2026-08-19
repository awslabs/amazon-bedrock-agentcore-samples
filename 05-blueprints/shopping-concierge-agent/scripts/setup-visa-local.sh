#!/bin/bash
# Setup script for Visa local development
set -e

HOSTS_ENTRY="127.0.0.1 vcas.local.com"

echo "🔧 Visa Local Development Setup"
echo ""

# Stop server on port 5001
lsof -ti:5001 2>/dev/null | xargs kill -9 2>/dev/null || true

# Add hosts entry if missing
if ! grep -q "vcas.local.com" /etc/hosts; then
    echo "Adding vcas.local.com to /etc/hosts (requires sudo)..."
    echo "$HOSTS_ENTRY" | sudo tee -a /etc/hosts > /dev/null
fi

# Check uv
if ! command -v uv &> /dev/null; then
    echo "❌ uv not installed. See: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

# Setup venv and install deps
cd concierge_agent/local-visa-server
[ ! -d ".venv" ] && uv venv
uv pip install -r requirements.txt -q
cd ../..

echo ""
echo "✅ Setup complete!"
echo ""
echo "Start server:  cd concierge_agent/local-visa-server && uv run python server.py"
echo "Access:        https://vcas.local.com:5001/"
