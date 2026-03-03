#!/usr/bin/env bash
# scripts/deploy.sh — one-command deployment for the AgentCore Support Demo
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CDK_DIR="$REPO_ROOT/cdk"
OUTPUTS_FILE="$REPO_ROOT/cdk-outputs.json"
YAML_FILE="$REPO_ROOT/.bedrock_agentcore.yaml"
STACK_KEY="supportAgentDemo-AgentCoreStack"

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
check_cmd() {
    if ! command -v "$1" &>/dev/null; then
        echo "ERROR: $1 is not installed. $2" >&2
        exit 1
    fi
}

echo "==> Pre-flight checks"
check_cmd uv       "Install: https://docs.astral.sh/uv/getting-started/installation/"
check_cmd node     "Install nvm (https://github.com/nvm-sh/nvm#installing-and-updating), then run: nvm install 20 && nvm use 20"
check_cmd npm      "Comes with Node.js"
check_cmd docker   "Install: https://docs.docker.com/desktop/setup/install/mac-install/"
check_cmd aws      "Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"

# Verify AWS CLI version >= 2.32.0 (required for `aws login`)
REQUIRED_CLI_VERSION="2.32.0"
AWS_CLI_VERSION=$(aws --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
if [ -n "$AWS_CLI_VERSION" ]; then
    if [ "$(printf '%s\n' "$REQUIRED_CLI_VERSION" "$AWS_CLI_VERSION" | sort -V | head -n1)" != "$REQUIRED_CLI_VERSION" ]; then
        echo "WARNING: AWS CLI version $AWS_CLI_VERSION detected. 'aws login' requires v$REQUIRED_CLI_VERSION+." >&2
        echo "         Update: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html" >&2
    fi
fi

# Verify AWS credentials
if ! aws sts get-caller-identity &>/dev/null; then
    echo "ERROR: AWS credentials are not configured or expired." >&2
    echo "       Run 'aws login' to authenticate, or 'aws configure' to set up credentials." >&2
    echo "       Details: https://docs.aws.amazon.com/signin/latest/userguide/command-line-sign-in.html" >&2
    exit 1
fi

# Verify Docker daemon is running
if ! docker info &>/dev/null 2>&1; then
    echo "ERROR: Docker daemon is not running. Start Docker Desktop or the Docker service." >&2
    exit 1
fi

# Check npm cache ownership (root-owned files from a previous sudo npm install will cause EACCES)
NPM_CACHE_DIR="${HOME}/.npm"
if [ -d "$NPM_CACHE_DIR" ]; then
    NPM_CACHE_OWNER=$(ls -ld "$NPM_CACHE_DIR" | awk '{print $3}')
    if [ "$NPM_CACHE_OWNER" != "$(whoami)" ]; then
        echo "ERROR: npm cache directory ($NPM_CACHE_DIR) is owned by '$NPM_CACHE_OWNER' instead of '$(whoami)'." >&2
        echo "       This was likely caused by a previous 'sudo npm install'." >&2
        echo "       Fix: sudo chown -R \$(whoami) $NPM_CACHE_DIR" >&2
        exit 1
    fi
fi

# Check Bedrock model access for required model (Claude Sonnet 4.5)
# Bedrock auto-enables all serverless models, but Anthropic requires a one-time usage form.
# Note: This tests the *deployer's* credentials. The agent runtime uses its own execution role,
# so a failure here does not necessarily mean the deployed agent will fail.
REQUIRED_MODEL="global.anthropic.claude-sonnet-4-5-20250929-v1:0"
echo "    Verifying Bedrock model access ($REQUIRED_MODEL)..."
if BODY_FILE=$(mktemp 2>/dev/null) && \
   echo -n '{"anthropic_version":"bedrock-2023-05-31","max_tokens":32,"messages":[{"role":"user","content":"hi"}]}' > "$BODY_FILE" && \
   aws bedrock-runtime invoke-model --model-id "$REQUIRED_MODEL" \
       --content-type "application/json" --accept "application/json" \
       --cli-connect-timeout 5 --cli-read-timeout 10 \
       --body "fileb://$BODY_FILE" /dev/null > /dev/null 2>&1; then
    rm -f "$BODY_FILE"
    echo "    Model access verified."
else
    rm -f "${BODY_FILE:-}"
    echo "WARNING: Could not invoke Bedrock model ($REQUIRED_MODEL)." >&2
    echo "         Possible reasons:" >&2
    echo "" >&2
    echo "         1. Anthropic first-time usage form not completed." >&2
    echo "            Complete it in the Bedrock console Playground by selecting any Anthropic Claude model." >&2
    echo "            Details: https://aws.amazon.com/blogs/security/simplified-amazon-bedrock-model-access/" >&2
    echo "" >&2
    echo "         2. Your current IAM identity lacks bedrock:InvokeModel permission." >&2
    echo "            Note: the deployed agent uses its own execution role, so this may not" >&2
    echo "            be a problem. Verify after deployment with: uv run agentcore invoke" >&2
    echo "" >&2
    echo "         The deploy will continue." >&2
fi

echo "    All checks passed."

# ---------------------------------------------------------------------------
# Install dependencies
# ---------------------------------------------------------------------------
echo ""
echo "==> Installing Python dependencies (uv sync)"
(cd "$REPO_ROOT" && uv sync)

echo ""
echo "==> Installing CDK dependencies (npm install)"
(cd "$CDK_DIR" && npm install)

# ---------------------------------------------------------------------------
# Bootstrap & Deploy
# ---------------------------------------------------------------------------
echo ""
echo "==> Bootstrapping CDK (if needed)"
(cd "$CDK_DIR" && npm run cdk -- bootstrap)

echo ""
echo "==> Deploying all stacks"
(cd "$CDK_DIR" && npm run cdk:deploy:ci -- --outputs-file "$OUTPUTS_FILE")

if [ ! -f "$OUTPUTS_FILE" ]; then
    echo "ERROR: CDK deploy succeeded but $OUTPUTS_FILE was not created." >&2
    exit 1
fi
echo "    CDK outputs written to $OUTPUTS_FILE"

# ---------------------------------------------------------------------------
# Generate .bedrock_agentcore.yaml from CDK outputs
# ---------------------------------------------------------------------------
echo ""
echo "==> Generating .bedrock_agentcore.yaml"

python3 - "$OUTPUTS_FILE" "$YAML_FILE" "$STACK_KEY" <<'PYEOF'
import json, sys, pathlib

outputs_path, yaml_path, stack_key = sys.argv[1], sys.argv[2], sys.argv[3]
with open(outputs_path) as f:
    stack = json.load(f)[stack_key]

agent_id = stack["RuntimeId"]
agent_arn = stack["RuntimeArn"]
account = stack["AccountId"]
region = stack["Region"]
discovery_url = stack["AuthorizerDiscoveryUrl"]

yaml_content = f"""\
default_agent: supportAgentDemo_Agent
agents:
  supportAgentDemo_Agent:
    name: supportAgentDemo_Agent
    language: python
    node_version: null
    entrypoint: ./src/main.py
    deployment_type: container
    runtime_type: null
    platform: linux/amd64
    container_runtime: null
    source_path: ./src
    aws:
      execution_role: null
      execution_role_auto_create: false
      account: '{account}'
      region: {region}
      ecr_repository: null
      ecr_auto_create: false
      s3_path: null
      s3_auto_create: false
      network_configuration:
        network_mode: PUBLIC
        network_mode_config: null
      protocol_configuration:
        server_protocol: HTTP
      observability:
        enabled: true
      lifecycle_configuration:
        idle_runtime_session_timeout: null
        max_lifetime: null
    bedrock_agentcore:
      agent_id: {agent_id}
      agent_arn: {agent_arn}
      agent_session_id: null
    codebuild:
      project_name: null
      execution_role: null
      source_bucket: null
    memory:
      mode: NO_MEMORY
      memory_id: null
      memory_arn: null
      memory_name: null
      event_expiry_days: 30
      first_invoke_memory_check_done: false
      was_created_by_toolkit: false
    identity:
      credential_providers: []
      workload: null
    aws_jwt:
      enabled: false
      audiences: []
      signing_algorithm: ES384
      issuer_url: null
      duration_seconds: 300
    authorizer_configuration:
      customJWTAuthorizer:
        discoveryUrl: {discovery_url}
    request_header_configuration:
      requestHeaderAllowlist:
      - Authorization
    oauth_configuration: null
    api_key_env_var_name: null
    api_key_credential_provider_name: null
    is_generated_by_agentcore_create: true
"""

pathlib.Path(yaml_path).write_text(yaml_content)
PYEOF

echo "    Generated $YAML_FILE"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  Deployment complete!"
echo "============================================================"
echo ""
echo "Next steps:"
echo ""
echo "  1. Check agent status:"
echo "       uv run agentcore status"
echo ""
echo "  2. Create a Cognito user:"
echo "       uv run scripts/cognito-user.py --create"
echo ""
echo "  3. Log in and set your bearer token:"
echo "       eval \$(uv run scripts/cognito-user.py --login --export)"
echo ""
echo "  4. Invoke the agent:"
echo "       uv run agentcore invoke '{\"prompt\": \"Who am I?\"}'"
echo ""
echo "  To tear down all resources later:"
echo "       scripts/teardown.sh"
echo ""
