# Scripts Directory

This directory contains utility scripts for setting up and managing the insurance agent.

## Scripts

### Identity Setup

#### `setup_identity.sh`
Automated bash script for setting up AgentCore Identity infrastructure.

**Usage:**
```bash
./scripts/setup_identity.sh
```

**What it does:**
- Validates environment variables
- Runs `identity_setup.py` to create identity resources
- Updates `.env` file with generated values
- Creates `identity_config.json` with configuration

**Prerequisites:**
- `.env` file with required variables (AWS_REGION, GATEWAY_INFO_FILE)
- MCP Gateway already deployed
- AWS credentials configured

#### `identity_setup.py`
Python script that creates AgentCore Identity resources.

**Usage:**
```bash
python scripts/identity_setup.py
```

**What it creates:**
- Workload Identity for the agent (Phase 2: Inbound)
- API Key Credential Provider (Phase 1: Outbound)
- Stores API key securely in Identity service

**Output:**
- `identity_config.json` - Configuration file with created resources
- Updates `.env` with WORKLOAD_IDENTITY_ARN and other values

### Utility Scripts

#### `cleanup_duplicate_memories.py`
Cleans up duplicate memory resources in AgentCore Memory service.

**Usage:**
```bash
python scripts/cleanup_duplicate_memories.py
```

**What it does:**
- Lists all memory resources
- Identifies duplicates by name
- Optionally deletes duplicate memories
- Keeps the most recent version

**When to use:**
- After multiple deployments that created duplicate memories
- To clean up test memory resources
- Before production deployment

#### `fix_env_path.sh`
Fixes path issues in `.env` file.

**Usage:**
```bash
./scripts/fix_env_path.sh
```

**What it does:**
- Corrects relative paths in `.env` file
- Updates GATEWAY_INFO_FILE path
- Ensures paths are relative to the agent directory

## Running Scripts

All scripts should be run from the `cloud_strands_insurance_agent` directory:

```bash
# From the agent directory
cd cloud_strands_insurance_agent

# Run identity setup
./scripts/setup_identity.sh

# Or run Python scripts directly
python scripts/identity_setup.py
python scripts/cleanup_duplicate_memories.py
```

## Script Dependencies

### Identity Setup Scripts
- Requires: `bedrock-agentcore` package
- Requires: `.env` file with AWS_REGION
- Requires: `gateway_info.json` from MCP server setup

### Cleanup Scripts
- Requires: `bedrock-agentcore` package
- Requires: AWS credentials with appropriate permissions

## Troubleshooting

### "Permission denied" errors
Make scripts executable:
```bash
chmod +x scripts/*.sh
```

### "Module not found" errors
Ensure you're in a virtual environment with dependencies installed:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### "Gateway info file not found"
Deploy the MCP gateway first:
```bash
cd ../cloud_mcp_server
./setup.sh
```

## Integration with deploy_all.sh

The main deployment script (`deploy_all.sh`) calls these scripts in order:
1. Insurance API deployment
2. MCP Gateway setup
3. **Identity setup** (`scripts/setup_identity.sh`)
4. Agent deployment

## See Also

- [IDENTITY_README.md](../md_files/IDENTITY_README.md) - Complete identity documentation
- [IDENTITY_QUICK_START.md](../md_files/IDENTITY_QUICK_START.md) - Quick start guide
- [README.md](../README.md) - Main project README
