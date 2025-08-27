"""
Configuration and constants for LocalMCP MCP Server
"""

from pathlib import Path

# Server configuration
SERVER_NAME = "LocalMCP"
SERVER_VERSION = "1.0.0"
PROJECTS_DIR = Path.home() / "local_mcp_projects"

# Auto Insurance API configuration
AUTO_INSURANCE_API_URL = "http://localhost:8001"

# Web scraping configuration
WEB_REQUEST_TIMEOUT = 15
WEB_SEARCH_MAX_RESULTS = 20
WEB_SCRAPE_MAX_TEXT_LENGTH = 5000
WEB_SCRAPE_MAX_LINKS = 20
WEB_SCRAPE_MAX_IMAGES = 10
WEB_SCRAPE_MAX_TABLES = 3

# Command execution configuration
COMMAND_TIMEOUT = 30.0

# Request headers for web operations
DEFAULT_WEB_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

SCRAPING_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
}
