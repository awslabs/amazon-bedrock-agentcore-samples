"""
Configuration settings for Slide Deck Agent Demo
"""

import os
from datetime import datetime

# AWS Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID", "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
)

# Memory Configuration
MEMORY_NAME = "SlideDeckAgentMemory"
MEMORY_EXPIRY_DAYS = 30

# Agent Configuration
DEFAULT_USER_ID = "demo_user"
SESSION_PREFIX = "slidedecksession"

# File Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Web UI Configuration
FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5001"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", True)
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")  # Must be set in production

# Default Presentation Settings
DEFAULT_PRESENTATION_SETTINGS = {
    "theme": "professional",
    "color_scheme": "blue",
    "font_family": "Arial, sans-serif",
    "slide_transition": "fade",
    "presentation_type": "tech",
}


def get_session_id():
    """Generate a unique session ID"""
    return f"{SESSION_PREFIX}_{datetime.now().strftime('%Y%m%d%H%M%S')}"


def ensure_directories():
    """Ensure all required directories exist"""
    for directory in [OUTPUT_DIR, TEMPLATES_DIR, STATIC_DIR]:
        os.makedirs(directory, exist_ok=True)
