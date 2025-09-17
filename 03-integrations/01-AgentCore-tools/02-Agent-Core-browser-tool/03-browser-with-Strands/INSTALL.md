# Installation Guide

## Quick Setup (Recommended)

```bash
chmod +x setup.sh
./setup.sh
```

## Manual Installation

### 1. Python Environment

```bash
# Ensure Python 3.10+ is available
python3.10 --version  # Should show 3.10.x

# Create virtual environment
python3.10 -m venv venv_310

# Activate virtual environment
source venv_310/bin/activate  # On Windows: venv_310\Scripts\activate
```

### 2. Install Python Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install all Python packages
pip install -r requirements.txt
```

### 3. Install Browser Binaries

```bash
# IMPORTANT: Install Playwright browser binaries
playwright install
```

This step downloads the actual browser binaries (Chromium, Firefox, WebKit) that Playwright needs for browser automation. This is separate from the Python package installation.

### 4. Verify Installation

```bash
# Test basic functionality
python bedrock_strands_browser_tool.py

# Run comprehensive tests
python test_integration.py
```

## Dependencies Breakdown

### Core Framework Dependencies
- `strands-agents` - Strands agentic framework
- `strands-agents-tools` - Strands tool integrations
- `bedrock-agentcore` - AWS Bedrock AgentCore SDK

### AWS Dependencies  
- `boto3` - AWS SDK for Python
- `python-dotenv` - Environment variable management

### Browser Automation Dependencies
- `playwright>=1.55.0` - Browser automation framework
- `nest-asyncio>=1.6.0` - Async event loop handling

### Utility Dependencies
- `beautifulsoup4` - HTML parsing
- `requests` - HTTP client
- `rich` - Terminal formatting

## Troubleshooting

### Playwright Installation Issues

If `playwright install` fails:

```bash
# Try installing specific browsers
playwright install chromium

# Or install with dependencies
playwright install --with-deps
```

### Python Version Issues

If Python 3.10 is not available:

```bash
# On macOS with Homebrew
brew install python@3.10

# On Ubuntu/Debian
sudo apt update
sudo apt install python3.10 python3.10-venv

# On Windows
# Download from python.org
```

### AWS Credentials

Ensure AWS credentials are configured:

```bash
# Check current configuration
aws sts get-caller-identity

# Configure if needed
aws configure
```

## Environment Variables

Copy and edit the environment template:

```bash
cp .env.template .env
# Edit .env with your specific values
```

Required variables:
- `AWS_REGION` - Your preferred AWS region
- `AWS_ACCESS_KEY_ID` - Your AWS access key (optional if using IAM roles)
- `AWS_SECRET_ACCESS_KEY` - Your AWS secret key (optional if using IAM roles)