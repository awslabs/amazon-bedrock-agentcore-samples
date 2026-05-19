"""
Launch the Market Trends Agent demo UI.
Starts the FastAPI backend and React frontend together.

Usage:
    uv run python run_demo_ui.py
"""

import subprocess
import sys
import os
import time
import signal
from pathlib import Path

FRONTEND_DIR = Path(__file__).parent / "frontend"
BACKEND_MODULE = "api_server:app"


def check_frontend_deps():
    """Install frontend dependencies if node_modules is missing"""
    if not (FRONTEND_DIR / "node_modules").exists():
        print("📦 Installing frontend dependencies...")
        # shell=True required: npm is a .cmd on Windows and needs shell to resolve
        subprocess.run(["npm", "install"], cwd=FRONTEND_DIR, check=True, shell=True)


def main():
    # Verify agent is deployed
    arn_file = Path(__file__).parent / ".agent_arn"
    if not arn_file.exists():
        print("⚠️  No .agent_arn file found. Deploy the agent first: uv run python deploy.py")
        print("   Starting UI anyway — it will show 'Agent Not Deployed' status.\n")

    check_frontend_deps()

    print("🚀 Starting Market Trends Agent Demo UI")
    print("   Backend:  http://localhost:8001")
    print("   Frontend: http://localhost:3000")
    print("   Press Ctrl+C to stop\n")

    # Start backend (FastAPI + uvicorn)
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", BACKEND_MODULE, "--host", "0.0.0.0", "--port", "8001", "--reload"],
        cwd=Path(__file__).parent,
    )

    # Give backend a moment to start
    time.sleep(2)

    # Start frontend (Vite dev server)
    # shell=True required: npm is a .cmd on Windows and needs shell to resolve
    frontend = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=FRONTEND_DIR,
        shell=True,
    )

    # Wait for Ctrl+C and clean up both processes
    def shutdown(sig, frame):
        print("\n🛑 Shutting down...")
        frontend.terminate()
        backend.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Keep alive
    try:
        backend.wait()
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
