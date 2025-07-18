#!/bin/bash

# Bedrock AgentCore Gateway AWS Operations Agent Client Runner
# Runs the modular AWS Operations Agent client (main.py)

set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SRC_DIR="$SCRIPT_DIR/src"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🤖 Bedrock AgentCore Gateway AWS Operations Agent Client"
echo "====================================="

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/venv"
fi

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Install requirements
echo "📦 Installing requirements..."
pip install -q -r "$SCRIPT_DIR/requirements.txt"

# Set Python path
export PYTHONPATH="$SRC_DIR:$PYTHONPATH"

echo "🚀 Starting AWS Operations Agent Client..."
echo ""

# Run the client
python3 "$SRC_DIR/main.py" "$@"
