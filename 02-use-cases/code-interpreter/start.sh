#!/bin/bash

# Integrated Start Script for AgentCore Code Interpreter
# Includes automatic setup if dependencies are missing

echo "🚀 AgentCore Code Interpreter - Starting Application"
echo "============================================================"

# Function to check if setup is needed
check_setup_needed() {
    local setup_needed=false
    
    # Check virtual environment
    if [ ! -d "venv" ]; then
        echo "📦 Virtual environment not found"
        setup_needed=true
    fi
    
    # Check Python dependencies
    if [ -d "venv" ]; then
        source venv/bin/activate
        if ! python -c "import strands, bedrock_agentcore, fastapi" 2>/dev/null; then
            echo "📦 Python dependencies missing"
            setup_needed=true
        fi
        deactivate 2>/dev/null || true
    fi
    
    # Check frontend dependencies
    if [ ! -d "frontend/node_modules" ]; then
        echo "📦 Frontend dependencies not found"
        setup_needed=true
    fi
    
    # Check .env file
    if [ ! -f ".env" ]; then
        echo "⚙️  Configuration file (.env) not found"
        setup_needed=true
    fi
    
    if [ "$setup_needed" = true ]; then
        return 0  # Setup needed
    else
        return 1  # Setup not needed
    fi
}

# Function to run setup
run_setup() {
    echo "🔧 Running automatic setup..."
    
    # Check if Python is installed
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python 3 is required but not installed. Please install Python 3.8 or higher."
        exit 1
    fi
    
    # Check if Node.js is installed
    if ! command -v node &> /dev/null; then
        echo "❌ Node.js is required but not installed. Please install Node.js 16 or higher."
        exit 1
    fi
    
    # Create virtual environment for Python backend
    if [ ! -d "venv" ]; then
        echo "📦 Creating Python virtual environment..."
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    
    # Install Python dependencies
    echo "📦 Installing Python dependencies..."
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
    
    # Install Node.js dependencies for frontend
    if [ ! -d "frontend/node_modules" ]; then
        echo "📦 Installing Node.js dependencies..."
        cd frontend
        npm install --silent
        cd ..
    fi
    
    # Create .env file if it doesn't exist
    if [ ! -f .env ]; then
        echo "⚙️  Creating .env file..."
        if [ -f .env.example ]; then
            cp .env.example .env
        else
            cat > .env << EOF
# AWS Configuration (choose one method)
AWS_PROFILE=default
AWS_REGION=us-east-1

# Application Configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
REACT_APP_API_URL=http://localhost:8000
EOF
        fi
        echo "📝 Please configure your AWS credentials in .env file"
    fi
    
    # Run setup verification
    echo "✅ Verifying setup..."
    if python tests/verify_setup.py > /dev/null 2>&1; then
        echo "✅ Setup verification successful"
    else
        echo "⚠️  Setup verification had warnings (continuing anyway)"
    fi
    
    deactivate
    echo "✅ Setup completed successfully"
}

# Function to check if backend is ready
check_backend() {
    local max_attempts=30
    local attempt=1
    
    echo "🔍 Waiting for backend to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo "✅ Backend is ready!"
            return 0
        fi
        
        if [ $attempt -eq 1 ]; then
            echo "⏳ Backend starting up..."
        elif [ $((attempt % 5)) -eq 0 ]; then
            echo "⏳ Still waiting... (${attempt}s)"
        fi
        
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo "❌ Backend failed to start after 60 seconds"
    echo "🔧 Check logs: tail -f backend.log"
    echo "🔧 Run diagnostics: python tests/verify_setup.py"
    return 1
}

# Function to start backend
start_backend() {
    echo "🚀 Starting backend server..."
    
    # Kill any existing backend processes
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    sleep 2
    
    # Start backend
    (
        source venv/bin/activate
        cd backend
        
        # Check if main.py exists
        if [ ! -f "main.py" ]; then
            echo "❌ backend/main.py not found"
            exit 1
        fi
        
        # Start the backend with error logging
        python main.py 2>&1 | tee ../backend.log &
        BACKEND_PID=$!
        echo $BACKEND_PID > ../backend.pid
        echo "📝 Backend started with PID: $BACKEND_PID"
    )
}

# Function to start frontend
start_frontend() {
    echo "🚀 Starting frontend server..."
    
    # Kill any existing frontend processes
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
    sleep 2
    
    cd frontend
    
    # Check if package.json exists
    if [ ! -f "package.json" ]; then
        echo "❌ frontend/package.json not found"
        exit 1
    fi
    
    # Start the frontend
    npm start 2>&1 | tee ../frontend.log &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > ../frontend.pid
    echo "📝 Frontend started with PID: $FRONTEND_PID"
    cd ..
}

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    
    # Kill backend
    if [ -f backend.pid ]; then
        BACKEND_PID=$(cat backend.pid)
        kill $BACKEND_PID 2>/dev/null || true
        rm -f backend.pid
    fi
    
    # Kill frontend
    if [ -f frontend.pid ]; then
        FRONTEND_PID=$(cat frontend.pid)
        kill $FRONTEND_PID 2>/dev/null || true
        rm -f frontend.pid
    fi
    
    # Kill any remaining processes on ports
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
    
    echo "✅ Cleanup completed"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Main execution
main() {
    # Check if setup is needed and run it
    if check_setup_needed; then
        echo "🔧 Setup required. Running automatic setup..."
        run_setup
        echo ""
    else
        echo "✅ Setup verified. Starting application..."
    fi
    
    # Start backend
    start_backend
    
    # Wait for backend to be ready
    if ! check_backend; then
        echo "❌ Cannot start frontend without backend"
        cleanup
        exit 1
    fi
    
    # Start frontend
    start_frontend
    
    echo ""
    echo "🎉 Application started successfully!"
    echo "📊 Backend:  http://localhost:8000"
    echo "🌐 Frontend: http://localhost:3000"
    echo ""
    echo "📋 Logs:"
    echo "   Backend:  tail -f backend.log"
    echo "   Frontend: tail -f frontend.log"
    echo ""
    echo "Press Ctrl+C to stop the application"
    echo ""
    
    # Wait for user interrupt
    while true; do
        sleep 1
    done
}

# Run main function
main
