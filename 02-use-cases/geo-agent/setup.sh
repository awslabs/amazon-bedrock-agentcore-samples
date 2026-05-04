#!/usr/bin/env bash
# Use return instead of exit when sourced, so we don't kill the user's shell
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    _GEO_SOURCED=1
    _geo_abort() { return 1; }
else
    _GEO_SOURCED=0
    _geo_abort() { exit 1; }
    set -e
fi

# ============================================================
# GEO Agent — One-Step Setup & Deploy
# Usage: source ./setup.sh
# ============================================================

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║       GEO Agent — Setup & Deploy                 ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ----------------------------------------------------------
# Step 0: Prerequisite checks
# ----------------------------------------------------------
echo "--- Checking prerequisites ---"
echo ""

MISSING=""

if ! command -v python3 &>/dev/null; then
    MISSING="${MISSING}  - python3 (>= 3.10)\n"
    MISSING="${MISSING}      macOS:  brew install python@3.10\n"
    MISSING="${MISSING}      Linux:  sudo dnf install python3.11  (AL2023)\n\n"
fi

if ! command -v node &>/dev/null; then
    MISSING="${MISSING}  - node (>= 20) — required by AgentCore toolkit\n"
    MISSING="${MISSING}      macOS:  brew install node@20\n"
    MISSING="${MISSING}      Linux:  sudo dnf install nodejs20  (AL2023)\n"
    MISSING="${MISSING}      Any:    nvm install 20\n\n"
fi

if ! command -v aws &>/dev/null; then
    MISSING="${MISSING}  - aws CLI (v2)\n"
    MISSING="${MISSING}      macOS:  brew install awscli\n"
    MISSING="${MISSING}      Linux:  curl \"https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip\" -o awscliv2.zip && unzip awscliv2.zip && sudo ./aws/install\n\n"
fi

if ! command -v sam &>/dev/null; then
    MISSING="${MISSING}  - sam CLI — required for Lambda/DDB deployment\n"
    MISSING="${MISSING}      macOS:  brew install aws-sam-cli\n"
    MISSING="${MISSING}      Linux:  pipx install aws-sam-cli\n\n"
fi

if [ -n "$MISSING" ]; then
    echo "Missing required tools:"
    echo ""
    printf "$MISSING"
    echo "Install them and re-run: source ./setup.sh"
    _geo_abort
fi

# Prefer a Homebrew Python >= 3.10 over the system python3
PYTHON3="python3"
for candidate in python3.13 python3.12 python3.11 python3.10; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON3="$candidate"
        break
    fi
done

PYTHON_VER=$($PYTHON3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)
NODE_VER=$(node -v 2>/dev/null | sed 's/^v//' | cut -d. -f1)

echo "  $PYTHON3  $PYTHON_VER"
echo "  node     $(node -v 2>/dev/null)"
echo "  aws      $(aws --version 2>/dev/null | awk '{print $1}' | cut -d/ -f2)"
echo "  sam      $(sam --version 2>/dev/null | awk '{print $NF}')"
echo ""

PYTHON_MAJOR=$(echo "$PYTHON_VER" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VER" | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; }; then
    echo "  ✗ Python >= 3.10 required (found $PYTHON_VER)"
    _geo_abort
fi

if [ -n "$NODE_VER" ] && [ "$NODE_VER" -lt 20 ] 2>/dev/null; then
    echo "  ✗ Node >= 20 required (found v$NODE_VER)"
    _geo_abort
fi

echo "  ✓ All prerequisites met"
echo ""

# ----------------------------------------------------------
# Step 1: Collect configuration (one time, used for everything)
# ----------------------------------------------------------
echo "--- Configuration ---"
echo ""

# AWS Region
read -rp "AWS Region [us-east-1]: " AWS_REGION
AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"

# Origin host (required)
while true; do
    read -rp "Target origin domain (e.g. www.setn.com): " ORIGIN_HOST
    if [ -n "$ORIGIN_HOST" ]; then
        ORIGIN_HOST=$(echo "$ORIGIN_HOST" | sed 's|^https\?://||' | sed 's|/.*||')
        break
    fi
    echo "  ⚠ Origin domain is required."
done

# AWS Account ID
DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || true)
if [ -n "$DEFAULT_ACCOUNT" ]; then
    read -rp "AWS Account ID [$DEFAULT_ACCOUNT]: " AWS_ACCOUNT
    AWS_ACCOUNT="${AWS_ACCOUNT:-$DEFAULT_ACCOUNT}"
else
    while true; do
        read -rp "AWS Account ID: " AWS_ACCOUNT
        if [ -n "$AWS_ACCOUNT" ]; then break; fi
        echo "  ⚠ Account ID is required."
    done
fi

# CloudFront Distribution
echo ""
echo "CloudFront distribution setup:"
echo "  - Leave blank to CREATE a new distribution automatically"
echo "  - Enter a distribution domain or ID to use an existing one"
echo ""
read -rp "CloudFront distribution [create new]: " CF_INPUT

CF_DIST_ID=""
CF_DIST_ARN=""
SETUP_CF_ORIGIN="false"
CREATE_DISTRIBUTION="false"
CFF_BEHAVIOR_PATH="*"

if [ -z "$CF_INPUT" ]; then
    CREATE_DISTRIBUTION="true"
    echo "  → Will create a new CloudFront distribution for ${ORIGIN_HOST}"
else
    CF_INPUT=$(echo "$CF_INPUT" | sed 's|^https\?://||' | sed 's|/.*||')
    if echo "$CF_INPUT" | grep -q '\.'; then
        echo "  Looking up distribution for domain: ${CF_INPUT}..."
        CF_DIST_ID=$(aws cloudfront list-distributions \
            --query "DistributionList.Items[?DomainName=='${CF_INPUT}'].Id | [0]" \
            --output text 2>/dev/null || true)
        if [ -z "$CF_DIST_ID" ] || [ "$CF_DIST_ID" = "None" ]; then
            echo "  ✗ Distribution not found for domain: ${CF_INPUT}"
            _geo_abort
        fi
        echo "  ✓ Found distribution: ${CF_DIST_ID}"
    else
        CF_DIST_ID="$CF_INPUT"
        echo "  Verifying distribution ${CF_DIST_ID}..."
        if ! aws cloudfront get-distribution --id "$CF_DIST_ID" --query 'Distribution.Id' --output text &>/dev/null; then
            echo "  ✗ Distribution ${CF_DIST_ID} not found."
            _geo_abort
        fi
        echo "  ✓ Distribution found"
    fi
    CF_DIST_ARN="arn:aws:cloudfront::${AWS_ACCOUNT}:distribution/${CF_DIST_ID}"
    SETUP_CF_ORIGIN="true"

    echo ""
    echo "  Available cache behaviors:"
    echo ""
    DEFAULT_ORIGIN=$(aws cloudfront get-distribution-config --id "$CF_DIST_ID" \
        --query 'DistributionConfig.DefaultCacheBehavior.TargetOriginId' --output text 2>/dev/null)
    echo "    [0] Default (*) → origin: ${DEFAULT_ORIGIN}"
    BEHAVIOR_COUNT=$(aws cloudfront get-distribution-config --id "$CF_DIST_ID" \
        --query 'DistributionConfig.CacheBehaviors.Quantity' --output text 2>/dev/null)
    if [ "$BEHAVIOR_COUNT" != "0" ] && [ -n "$BEHAVIOR_COUNT" ]; then
        BEHAVIOR_PATHS=$(aws cloudfront get-distribution-config --id "$CF_DIST_ID" \
            --query 'DistributionConfig.CacheBehaviors.Items[*].[PathPattern, TargetOriginId]' \
            --output text 2>/dev/null)
        IDX=1
        while IFS=$'\t' read -r bpath borigin; do
            echo "    [${IDX}] ${bpath} → origin: ${borigin}"
            IDX=$((IDX + 1))
        done <<< "$BEHAVIOR_PATHS"
    fi
    echo ""
    read -rp "  Attach CFF to which behavior? [0 = Default(*)]: " BEHAVIOR_CHOICE
    BEHAVIOR_CHOICE="${BEHAVIOR_CHOICE:-0}"
    if [ "$BEHAVIOR_CHOICE" = "0" ]; then
        CFF_BEHAVIOR_PATH="*"
    else
        CFF_BEHAVIOR_PATH=$(aws cloudfront get-distribution-config --id "$CF_DIST_ID" \
            --query "DistributionConfig.CacheBehaviors.Items[$((BEHAVIOR_CHOICE - 1))].PathPattern" \
            --output text 2>/dev/null)
        if [ -z "$CFF_BEHAVIOR_PATH" ] || [ "$CFF_BEHAVIOR_PATH" = "None" ]; then
            echo "  ⚠ Invalid choice, using Default (*)"
            CFF_BEHAVIOR_PATH="*"
        fi
    fi
    echo "  → CFF will be attached to: ${CFF_BEHAVIOR_PATH}"
fi

# Origin verify secret
DEFAULT_SECRET="geo-origin-$(openssl rand -hex 16 2>/dev/null || date +%s%N)"
read -rp "Origin verify secret [$DEFAULT_SECRET]: " ORIGIN_SECRET
ORIGIN_SECRET="${ORIGIN_SECRET:-$DEFAULT_SECRET}"

# DynamoDB table name
read -rp "DynamoDB table name [geo-content]: " TABLE_NAME
TABLE_NAME="${TABLE_NAME:-geo-content}"

# --- Summary & Confirm ---
echo ""
echo "--- Summary ---"
echo "  Region:         $AWS_REGION"
echo "  Origin:         $ORIGIN_HOST"
echo "  Account:        $AWS_ACCOUNT"
if [ "$CREATE_DISTRIBUTION" = "true" ]; then
    echo "  CF Distribution: <will create new>"
else
    echo "  CF Dist ID:     ${CF_DIST_ID}"
    echo "  CFF Behavior:   ${CFF_BEHAVIOR_PATH}"
fi
echo "  Table:          $TABLE_NAME"
echo "  Verify Secret:  $ORIGIN_SECRET"
echo ""
echo "This will:"
echo "  1. Install Python dependencies (venv)"
echo "  2. Deploy GEO Agent to AgentCore"
echo "  3. Deploy Lambda + DynamoDB + CloudFront (SAM)"
echo ""
read -rp "Proceed? [Y/n]: " CONFIRM
CONFIRM="${CONFIRM:-Y}"
if [[ ! "$CONFIRM" =~ ^[Yy] ]]; then
    echo "Aborted."
    _geo_abort
fi

# ==========================================================
# Step 2: Python venv + dependencies
# ==========================================================
echo ""
echo "==> [1/4] Installing Python dependencies..."
$PYTHON3 -m venv .venv
source .venv/bin/activate

# Workaround for SSL certificate issues (common on corporate networks)
export PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org"
export UV_NATIVE_TLS=true

pip install -e . 2>&1 | tail -3

# Fix chardet/charset_normalizer conflict
if pip show chardet > /dev/null 2>&1; then
    pip uninstall chardet -y > /dev/null 2>&1
fi

echo "  ✓ Dependencies installed, venv activated"

# ==========================================================
# Step 3: AgentCore configure + deploy
# ==========================================================
echo ""
echo "==> [2/4] Deploying GEO Agent to AgentCore..."

# Auto-configure agentcore if not already configured
if [ ! -f .bedrock_agentcore.yaml ]; then
    echo "  Running agentcore configure (entrypoint: src/main.py)..."
    echo ""
    echo "  ┌─────────────────────────────────────────────┐"
    echo "  │ When prompted:                              │"
    echo "  │   Entrypoint: src/main.py                   │"
    echo "  │   Region: ${AWS_REGION}                     │"
    echo "  │   Accept defaults for the rest              │"
    echo "  └─────────────────────────────────────────────┘"
    echo ""
    agentcore configure
fi

echo ""
echo "  Deploying agent..."
agentcore deploy

# Extract Agent Runtime ARN from config
AGENT_ARN=$($PYTHON3 -c "
import yaml
with open('.bedrock_agentcore.yaml') as f:
    cfg = yaml.safe_load(f)
agents = cfg.get('agents', {})
for name, agent in agents.items():
    arn = agent.get('bedrock_agentcore', {}).get('agent_arn', '')
    if arn:
        print(arn)
        break
" 2>/dev/null || true)

if [ -z "$AGENT_ARN" ]; then
    echo "  ⚠ Could not extract Agent Runtime ARN from .bedrock_agentcore.yaml"
    echo "    You'll need to set AgentRuntimeArn manually in samconfig.toml"
    read -rp "  Agent Runtime ARN (paste here, or Enter to skip): " AGENT_ARN
fi

if [ -n "$AGENT_ARN" ]; then
    echo "  ✓ Agent ARN: ${AGENT_ARN}"
fi

# ==========================================================
# Step 4: Generate samconfig.toml
# ==========================================================
echo ""
echo "==> [3/4] Building SAM template..."

PARAM_OVERRIDES="TableName=\\\"${TABLE_NAME}\\\" DefaultOriginHost=\\\"${ORIGIN_HOST}\\\" OriginVerifySecret=\\\"${ORIGIN_SECRET}\\\""

if [ -n "$AGENT_ARN" ]; then
    PARAM_OVERRIDES="${PARAM_OVERRIDES} AgentRuntimeArn=\\\"${AGENT_ARN}\\\""
fi

if [ "$CREATE_DISTRIBUTION" = "true" ]; then
    PARAM_OVERRIDES="${PARAM_OVERRIDES} CreateDistribution=\\\"true\\\""
elif [ -n "$CF_DIST_ID" ]; then
    PARAM_OVERRIDES="${PARAM_OVERRIDES} CloudFrontDistributionArn=\\\"${CF_DIST_ARN}\\\" SetupCfOrigin=\\\"${SETUP_CF_ORIGIN}\\\" CffArn=\\\"arn:aws:cloudfront::${AWS_ACCOUNT}:function/geo-bot-router-oac\\\" CffBehaviorPath=\\\"${CFF_BEHAVIOR_PATH}\\\""
fi

cat > samconfig.toml <<EOF
version = 0.1

[default.deploy.parameters]
stack_name = "geo-backend"
resolve_s3 = true
s3_prefix = "geo-backend"
region = "${AWS_REGION}"
confirm_changeset = true
capabilities = "CAPABILITY_IAM"
parameter_overrides = "${PARAM_OVERRIDES}"
image_repositories = []

[default.global.parameters]
region = "${AWS_REGION}"
EOF

echo "  ✓ samconfig.toml generated"

# ==========================================================
# Step 5: SAM build + deploy
# ==========================================================
echo ""
sam build -t infra/template.yaml

echo ""
echo "==> [4/4] Deploying infrastructure (Lambda + DynamoDB + CloudFront)..."
echo ""
sam deploy

# ==========================================================
# Done!
# ==========================================================
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  ✓ All done!                                     ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Show outputs
STACK_STATUS=$(aws cloudformation describe-stacks --stack-name geo-backend \
    --query 'Stacks[0].StackStatus' --output text --region "$AWS_REGION" 2>/dev/null || true)

if [ "$STACK_STATUS" = "CREATE_COMPLETE" ] || [ "$STACK_STATUS" = "UPDATE_COMPLETE" ]; then
    echo "Stack outputs:"
    aws cloudformation describe-stacks --stack-name geo-backend \
        --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
        --output table --region "$AWS_REGION" 2>/dev/null || true
    echo ""

    if [ "$CREATE_DISTRIBUTION" = "true" ]; then
        CF_DOMAIN=$(aws cloudformation describe-stacks --stack-name geo-backend \
            --query "Stacks[0].Outputs[?OutputKey=='DistributionDomain'].OutputValue" \
            --output text --region "$AWS_REGION" 2>/dev/null || true)
        if [ -n "$CF_DOMAIN" ] && [ "$CF_DOMAIN" != "None" ]; then
            echo "Test with:"
            echo "  curl -H 'User-Agent: GPTBot' \"https://${CF_DOMAIN}/\""
            echo ""
        fi
    fi
fi

echo "venv is active. Run 'deactivate' to exit."
echo ""
