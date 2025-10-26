# Setup Scripts Summary

## Overview

Complete set of deployment and setup scripts for the Simple Dual Observability Tutorial, enabling Amazon Bedrock AgentCore observability with dual platform support (AWS CloudWatch and Braintrust).

## Created Scripts

### 1. check_prerequisites.sh (6.5 KB)
**Purpose:** Validate environment and prerequisites before deployment

**Features:**
- AWS CLI installation and version check
- AWS credentials validation
- Python 3.11+ verification
- boto3 package check
- AWS service availability (AgentCore, CloudWatch, X-Ray)
- Permission validation
- Colored output with PASS/WARN/FAIL indicators
- Verbose mode for detailed diagnostics

**Usage:**
```bash
./check_prerequisites.sh
./check_prerequisites.sh --verbose
```

### 2. deploy_agent.sh (7.9 KB)
**Purpose:** Deploy Strands agent to AgentCore Runtime with OTEL instrumentation

**Features:**
- Creates agent configuration with three tools:
  - get_weather: Weather information
  - get_time: Time zone information
  - calculate: Mathematical calculations
- Configures OTEL automatic instrumentation
- Supports custom model selection
- Dual export setup (CloudWatch + optional Braintrust)
- Saves agent ID and environment configuration
- Comprehensive error handling

**Usage:**
```bash
./deploy_agent.sh
./deploy_agent.sh --region us-west-2
./deploy_agent.sh --model anthropic.claude-3-haiku-20240307-v1:0
export BRAINTRUST_API_KEY=bt-xxxxx && ./deploy_agent.sh
```

**Outputs:**
- `.agent_id` - Deployed agent identifier
- `.env` - Environment configuration file

### 3. setup_cloudwatch.sh (9.3 KB)
**Purpose:** Configure CloudWatch Transaction Search and dashboard

**Features:**
- Creates CloudWatch log groups with retention policies
- Enables X-Ray tracing
- Generates comprehensive dashboard with 6 widgets:
  1. Agent Response Latency (P50, P90, P99)
  2. Token Consumption over time
  3. Error Count tracking
  4. Recent Trace Events log viewer
  5. Bedrock Invocations count
  6. Latency by Operation analysis
- Creates IAM policy template for X-Ray permissions
- Generates direct URLs to all CloudWatch resources

**Usage:**
```bash
./setup_cloudwatch.sh
./setup_cloudwatch.sh --region us-west-2
./setup_cloudwatch.sh --dashboard MyCustomDashboard
```

**Outputs:**
- `cloudwatch-urls.txt` - Direct links to resources
- `xray-permissions.json` - IAM policy template

### 4. setup_braintrust.sh (12 KB)
**Purpose:** Configure Braintrust integration for AI-focused observability

**Features:**
- Interactive guided setup for Braintrust account creation
- API key generation assistance
- Connection testing and validation
- OTEL configuration for dual export
- Creates comprehensive usage documentation
- Supports both interactive and automated modes

**Usage:**
```bash
./setup_braintrust.sh                        # Interactive
./setup_braintrust.sh --api-key bt-xxxxx    # Automated
./setup_braintrust.sh --test                 # Test existing config
```

**Outputs:**
- `.env` - Updated with Braintrust API key
- `config/otel_config_braintrust.yaml` - OTEL config with dual export
- `braintrust-usage.md` - Comprehensive usage guide

### 5. setup_all.sh (5.2 KB)
**Purpose:** Orchestrate complete end-to-end deployment

**Features:**
- Sequential execution of all setup steps
- Progress confirmation between steps
- Supports CloudWatch-only or dual-platform setup
- Comprehensive summary with all access links
- Error handling with graceful degradation

**Usage:**
```bash
./setup_all.sh                           # CloudWatch only
./setup_all.sh --braintrust              # Interactive dual setup
./setup_all.sh --api-key bt-xxxxx        # Automated dual setup
./setup_all.sh --region us-west-2        # Custom region
```

### 6. cleanup.sh (4.8 KB)
**Purpose:** Remove all deployed resources and cleanup

**Features:**
- Deletes AgentCore Runtime agent
- Removes CloudWatch dashboard
- Optionally deletes log groups
- Backs up configuration files
- Interactive confirmation (can be forced)
- Comprehensive cleanup report

**Usage:**
```bash
./cleanup.sh                    # Interactive cleanup
./cleanup.sh --force            # No confirmations
./cleanup.sh --keep-logs        # Preserve log groups
```

**Outputs:**
- `.env.backup` - Backup of environment configuration

## Additional Files

### README.md (7.4 KB)
Comprehensive documentation covering:
- Script descriptions and usage
- Quick start guides
- Prerequisites
- Common operations
- Troubleshooting
- Support resources

### .gitignore
Excludes generated files:
- `.agent_id`
- `.env` and `.env.backup`
- `cloudwatch-urls.txt`
- `xray-permissions.json`
- `braintrust-usage.md`

## Workflow

### Recommended Flow

```bash
# 1. Check prerequisites
./check_prerequisites.sh

# 2. Run complete setup
./setup_all.sh --braintrust

# 3. Load environment
source .env

# 4. Run demo
cd ..
python simple_observability.py --scenario all

# 5. View results
# - CloudWatch: URLs in cloudwatch-urls.txt
# - Braintrust: https://www.braintrust.dev/app

# 6. Cleanup when done
./cleanup.sh
```

### Manual Step-by-Step Flow

```bash
# 1. Validate environment
./check_prerequisites.sh

# 2. Deploy agent
./deploy_agent.sh
source .env

# 3. Setup CloudWatch
./setup_cloudwatch.sh

# 4. (Optional) Setup Braintrust
./setup_braintrust.sh

# 5. Run demo
cd ..
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID

# 6. Cleanup
./cleanup.sh
```

## Key Features

### Error Handling
- All scripts use `set -e` for immediate error exit
- Comprehensive error messages with actionable fixes
- Validation of AWS credentials before operations
- Service availability checks

### User Experience
- Clear progress indicators
- Contextual help with `-h` or `--help`
- Environment variable support for automation
- Interactive confirmations for destructive operations
- Comprehensive output with next steps

### Security
- No hardcoded credentials
- API keys stored in `.env` (git-ignored)
- Secure AWS credential handling via AWS CLI
- TLS for all external connections
- IAM policy templates provided (not auto-applied)

### Flexibility
- Support for custom regions
- Model selection for agent deployment
- Optional Braintrust integration
- Configurable dashboard and log group names
- Both interactive and automated modes

## Generated Files Location

All generated files are created in the `/scripts` directory:

```
scripts/
├── .agent_id                    # Agent identifier
├── .env                         # Environment configuration
├── .env.backup                  # Backup created during cleanup
├── cloudwatch-urls.txt          # CloudWatch resource URLs
├── xray-permissions.json        # IAM policy template
└── braintrust-usage.md          # Braintrust usage guide
```

## Prerequisites Verified

The scripts check and require:
- AWS CLI (latest version recommended)
- AWS credentials configured
- Python 3.11+
- boto3 package
- jq (recommended)
- curl (required for Braintrust)
- AgentCore Runtime service availability
- CloudWatch, X-Ray, and Logs permissions

## Best Practices Implemented

### Bash Scripting
- Use of `set -e` for error handling
- Clear echo statements (no emojis for compatibility)
- Environment variables with sensible defaults
- Help text with `-h` flag
- Validation before destructive operations

### AWS Operations
- Service availability checks before operations
- Graceful handling of existing resources
- Proper error messages from AWS API calls
- IAM policy templates (not auto-created)

### Documentation
- Inline comments for complex operations
- Comprehensive README
- Generated usage guides
- Example commands in help text

## Testing

All scripts have been validated with:
- Bash syntax checking: `bash -n script.sh`
- Executable permissions set
- Help text accessibility
- Error handling paths

## Support

For issues:
- Check `README.md` for troubleshooting
- Run `check_prerequisites.sh` for diagnostics
- Review generated `braintrust-usage.md` for Braintrust issues
- Check AWS CloudFormation events for deployment issues

## Version Information

- Created: 2025-10-25
- Tutorial: Simple Dual Observability
- Platform: Amazon Bedrock AgentCore
- Observability: CloudWatch X-Ray + Braintrust
- Architecture: AgentCore Runtime (serverless)
