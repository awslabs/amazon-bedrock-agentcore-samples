# Installation Guide for NovaAct Browser Tutorial

## Quick Start

**⚠️ IMPORTANT: Python 3.10+ Required**

This tutorial requires Python 3.10 or higher. It has been tested with Python 3.12.

### 1. Check Python Version

```bash
python3 --version
# Should show 3.10.x or higher

# Or specifically check for Python 3.12
python3.12 --version
```

### 2. Install Python 3.12 (if needed)

**macOS:**
```bash
brew install python@3.12
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-pip
```

**Windows:**
Download from [python.org](https://www.python.org/downloads/)

### 3. Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python3.12 -m venv nova_act_env

# Activate virtual environment
source nova_act_env/bin/activate  # macOS/Linux
# or
nova_act_env\Scripts\activate     # Windows

# Upgrade pip
pip install --upgrade pip
```

### 4. Install Dependencies

```bash
# Install all requirements
pip install -r requirements.txt

# Install Playwright browsers (required for browser automation)
playwright install
```

### 5. Verify Installation

```bash
# Test imports
python3.12 -c "
import nova_act
import bedrock_agentcore
import playwright
import fastapi
import uvicorn
import websockets
print('✅ All dependencies installed successfully')
"
```

## Alternative Installation Methods

### Option 1: System-wide Installation (macOS with Homebrew)

If you encounter "externally-managed-environment" errors:

```bash
# Install some packages via brew
brew install fastapi uvicorn

# Install Python packages with user flag
python3.12 -m pip install nova-act bedrock-agentcore boto3 rich playwright websockets --user --break-system-packages

# Install Playwright browsers
python3.12 -m playwright install
```

### Option 2: Using pipx

```bash
# Install pipx
brew install pipx  # macOS
# or
python3 -m pip install --user pipx  # Other systems

# Install packages (note: this installs them as separate applications)
pipx install nova-act
pipx install bedrock-agentcore
# Continue for other packages...
```

## Troubleshooting

### Common Issues and Solutions

#### 1. "externally-managed-environment" Error

**Problem:** Modern Python installations prevent system-wide package installation.

**Solutions:**
- **Recommended:** Use virtual environment (see step 3 above)
- **Alternative:** Add `--user --break-system-packages` flags
- **Alternative:** Use `pipx` for application installs

#### 2. "No matching distribution found for nova-act"

**Problem:** nova-act requires Python 3.10+

**Solution:**
```bash
# Check Python version
python3 --version

# If < 3.10, install newer Python
brew install python@3.12  # macOS
# or follow OS-specific instructions above
```

#### 3. Playwright Installation Issues

**Problem:** Missing system dependencies or browser binaries

**Solutions:**
```bash
# Linux: Install system dependencies
sudo apt-get install libnss3 libatk-bridge2.0-0 libdrm2 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libxss1 libasound2

# Reinstall Playwright
pip uninstall playwright
pip install playwright
playwright install

# Verify Playwright installation
python3 -c "from playwright.sync_api import sync_playwright; print('Playwright OK')"
```

#### 4. Import Errors in Jupyter Notebooks

**Problem:** Jupyter using wrong Python environment

**Solutions:**
```bash
# Install Jupyter in your virtual environment
pip install jupyter

# Or install kernel for your environment
pip install ipykernel
python -m ipykernel install --user --name=nova_act_env

# Start Jupyter and select the correct kernel
jupyter notebook
```

#### 5. "interactive_tools" Import Errors

**Problem:** Incorrect import path in notebooks

**Solution:**
- Ensure the path `sys.path.append("../../interactive_tools")` is correct
- Verify `interactive_tools` directory exists at the expected location
- Restart Jupyter kernel after making changes

## Environment Setup

After successful installation, configure your environment:

### 1. AWS Credentials

```bash
# Option 1: AWS CLI
aws configure

# Option 2: Environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

### 2. NovaAct API Key

```bash
export NOVAACT_API_KEY=your_novaact_api_key
```

### 3. Verify Complete Setup

```bash
# Test all components
python3.12 -c "
import os
import nova_act
import bedrock_agentcore
import boto3

print('✅ Python packages: OK')
print('✅ AWS SDK: OK')
print('✅ NovaAct: OK')

# Check environment variables
if os.getenv('NOVAACT_API_KEY'):
    print('✅ NovaAct API Key: Set')
else:
    print('⚠️  NovaAct API Key: Not set')

if os.getenv('AWS_ACCESS_KEY_ID'):
    print('✅ AWS Credentials: Set')
else:
    print('⚠️  AWS Credentials: Not set (may use default profile)')
"
```

## Next Steps

Once installation is complete:

1. Open the tutorial notebooks in Jupyter
2. Ensure the correct Python kernel is selected
3. Run the first cell to verify all imports work
4. Follow the tutorial step by step

## Getting Help

If you encounter issues not covered here:

1. Check the main [README.md](README.md) for detailed troubleshooting
2. Verify your Python version meets requirements (3.10+)
3. Ensure you're using a virtual environment
4. Check that all environment variables are set correctly

---

**Note:** This installation guide is specifically for the NovaAct browser tutorial. For other tutorials in this repository, check their individual requirements.