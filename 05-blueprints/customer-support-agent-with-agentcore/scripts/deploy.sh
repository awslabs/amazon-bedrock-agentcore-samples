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
check_cmd node     "Install: nvm install 20 && nvm use 20"
check_cmd npm      "Comes with Node.js"
check_cmd docker   "Install: https://docs.docker.com/desktop/setup/install/mac-install/"
check_cmd aws      "Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"

# Verify AWS credentials
if ! aws sts get-caller-identity &>/dev/null; then
    echo "ERROR: AWS credentials are not configured or expired." >&2
    echo "       Run 'aws configure' or refresh your credentials first." >&2
    exit 1
fi

# Verify Docker daemon is running
if ! docker info &>/dev/null 2>&1; then
    echo "ERROR: Docker daemon is not running. Start Docker Desktop or the Docker service." >&2
    exit 1
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
echo "       agentcore status"
echo ""
echo "  2. Create a Cognito user:"
echo "       uv run scripts/cognito-user.py --create"
echo ""
echo "  3. Log in and set your bearer token:"
echo "       eval \$(uv run scripts/cognito-user.py --login --export)"
echo ""
echo "  4. Invoke the agent:"
echo "       agentcore invoke '{\"prompt\": \"Who am I?\"}'"
echo ""
echo "  To tear down all resources later:"
echo "       scripts/teardown.sh"
echo ""
