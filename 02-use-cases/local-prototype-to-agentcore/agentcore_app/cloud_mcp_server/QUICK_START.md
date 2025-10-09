# MCP Server - Quick Start Guide

## 🚀 Quick Setup (5 minutes)

### Step 1: Configure Environment

```bash
cd cloud_mcp_server

# Copy example and edit
cp .env_example .env
nano .env
```

Required values:
- `AWS_REGION` - Your AWS region
- `API_GATEWAY_URL` - Your deployed Insurance API URL
- `API_KEY` - Your API key
- `OPENAPI_FILE_PATH` - Path to openapi.json

### Step 2: Run Automated Setup

```bash
./setup.sh
```

That's it! The script will:
- ✅ Create virtual environment
- ✅ Install all packages
- ✅ Set up the gateway
- ✅ Save configuration to `gateway_info.json`

### Step 3: Get Your Credentials

```bash
# View your MCP URL and token
cat gateway_info.json
```

Copy these values:
- `gateway.mcp_url` → Use as `MCP_SERVER_URL`
- `auth.access_token` → Use as `MCP_ACCESS_TOKEN`

## 🔄 Token Refresh

When your token expires:

```bash
source .venv/bin/activate
python refresh_gateway_token.py
```

## 🐛 Troubleshooting

### "No module named 'bedrock_agentcore_starter_toolkit'"

**Solution**: Use virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### "externally-managed-environment" error

**Solution**: This is macOS protecting system Python. Use the virtual environment (already handled by `./setup.sh`)

### ".env file not found"

**Solution**: 
```bash
cp .env_example .env
nano .env  # Add your values
```

## 📝 Manual Commands

If you prefer manual control:

```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Install packages
pip install -r requirements.txt

# Run setup
python agentcore_gateway_setup_openapi.py

# Refresh token (when needed)
python refresh_gateway_token.py
```

## 🎯 Next Steps

After setup:
1. Copy `MCP_SERVER_URL` and `MCP_ACCESS_TOKEN` from `gateway_info.json`
2. Add them to your agent's `.env` file
3. Deploy your agent

See [README.md](README.md) for full documentation.
