#!/bin/bash

# Setup and run script for Device Management Chat Application

echo "🚀 Setting up Device Management Chat Application..."

# Function to check if Docker is available
check_docker() {
    if command -v docker &>/dev/null && command -v docker-compose &>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to setup and run with Docker
run_with_docker() {
    echo "🐳 Using Docker deployment..."
    
    # Check if .env file exists
    if [ ! -f ".env" ]; then
        echo "📄 Creating .env file from template..."
        cp .env.example .env
        echo "⚠️  Please update the .env file with your configuration:"
        echo "   - AWS_REGION"
        echo "   - AGENT_ARN"
        echo "   - Cognito settings (optional)"
        echo ""
        echo "Then run this script again."
        exit 1
    fi
    
    # Build and run with Docker Compose
    echo "🔨 Building and starting containers..."
    docker-compose up -d
    
    echo "✅ Application started successfully!"
    echo "📱 Access the application at http://localhost:5001"
    echo "📋 View logs with: docker-compose logs -f"
    echo "🛑 Stop with: docker-compose down"
}

# Function to setup and run locally
run_locally() {
    echo "🐍 Using local Python deployment..."
    
    # Check if Python 3.12 is installed
    if command -v python3.12 &>/dev/null; then
        echo "✅ Python 3.12 found"
        PYTHON_CMD=python3.12
    elif command -v python3 &>/dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        echo "🔍 Found Python $PYTHON_VERSION"
        if [[ "$PYTHON_VERSION" == 3.12* ]]; then
            echo "✅ Python 3.12 found"
            PYTHON_CMD=python3
        else
            echo "⚠️  Warning: Python 3.12 is recommended, but using $PYTHON_VERSION"
            PYTHON_CMD=python3
        fi
    else
        echo "❌ Python 3.12 not found. Please install Python 3.12"
        exit 1
    fi

    # Check if virtual environment exists
    if [ ! -d "venv" ]; then
        echo "🔧 Creating virtual environment..."
        $PYTHON_CMD -m venv venv
        echo "✅ Virtual environment created"
    fi

    # Activate virtual environment
    echo "🔌 Activating virtual environment..."
    source venv/bin/activate

    # Install dependencies
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt

    # Check if .env file exists
    if [ ! -f ".env" ]; then
        echo "📄 Creating .env file from template..."
        cp .env.example .env
        echo "⚠️  Please update the .env file with your configuration:"
        echo "   - AWS_REGION"
        echo "   - AGENT_ARN"
        echo "   - Cognito settings (optional)"
        echo ""
        echo "Then run this script again."
        exit 1
    fi

    # Run the application
    echo "🚀 Starting the application..."
    echo "📱 Access the application at http://localhost:5001"
    uvicorn main:app --host 0.0.0.0 --port 5001 --reload
}

# Main execution
echo "Choose deployment method:"
echo "1. Docker (recommended)"
echo "2. Local Python"
echo ""

# Check if Docker is available and prefer it
if check_docker; then
    echo "🐳 Docker detected - using Docker deployment"
    run_with_docker
else
    echo "🐍 Docker not available - using local Python deployment"
    run_locally
fi
