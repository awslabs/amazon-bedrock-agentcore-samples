#!/usr/bin/env bash
# Deploy Lambda function for AgentCore Gateway monitoring tools
# Usage: ./deploy_lambda.sh [function-name] [region]
# Examples:
#   ./deploy_lambda.sh monitoring-agent-lambda us-east-1
#   ./deploy_lambda.sh monitoring-agent-lambda us-west-2

set -Eeuo pipefail

# --- Config / Args ---
FUNCTION_NAME="${1:-monitoring-agent-fn-new}"
REGION="${2:-us-west-2}"            # must match where your function lives
RUNTIME="python3.11"                # your code uses requests; 3.11 is widely available
ROLE_NAME="MonitoringLambdaRole"
MAX_RETRIES=5
RETRY_DELAY=10

# Try to find AWS CLI
AWS_CLI="${AWS_CLI:-aws}"
command -v "$AWS_CLI" >/dev/null 2>&1 || { echo "❌ aws CLI not found"; exit 1; }

# jq is used for robust JSON building; if missing, fail fast
command -v jq >/dev/null 2>&1 || { echo "❌ jq is required (brew install jq / apt-get install jq)"; exit 1; }

echo "🚀 Deploying Lambda function: $FUNCTION_NAME in region: $REGION"

# --- Retry function for AWS commands ---
retry_aws_command() {
    local max_attempts="$1"
    shift
    local delay="$RETRY_DELAY"
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        echo "🔄 Attempt $attempt of $max_attempts..."
        if "$@"; then
            echo "✅ Command succeeded"
            return 0
        fi
        
        if [ $attempt -lt $max_attempts ]; then
            echo "⏳ Command failed. Retrying in ${delay} seconds..."
            sleep "$delay"
            delay=$((delay * 2))  # Exponential backoff
        fi
        attempt=$((attempt + 1))
    done
    
    echo "❌ Command failed after $max_attempts attempts"
    return 1
}

# --- Paths ---
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LAMBDA_SOURCE="${SCRIPT_DIR}/lambda_function.py"
[ -f "$LAMBDA_SOURCE" ] || { echo "❌ Missing $LAMBDA_SOURCE"; exit 1; }

# --- Temp build dir ---
DEPLOY_DIR="$(mktemp -d)"
trap "rm -rf $DEPLOY_DIR" EXIT  # Ensure cleanup on exit
echo "📦 Creating deployment package in: $DEPLOY_DIR"
cp "$LAMBDA_SOURCE" "$DEPLOY_DIR/"

# --- Dependencies (add requests; boto3 is available in Lambda but harmless to include) ---
cat > "$DEPLOY_DIR/requirements.txt" << 'EOF'
requests>=2.31.0
boto3>=1.26.0
EOF

echo "📥 Installing dependencies..."
pushd "$DEPLOY_DIR" >/dev/null
python3 -m pip install --upgrade pip --quiet
python3 -m pip install -r requirements.txt -t . --quiet

# --- Zip package ---
echo "📦 Creating deployment package..."
zip -qr lambda-deployment.zip . -x '*.pyc' '*/__pycache__/*' '*.dist-info/*'

# --- Account id ---
ACCOUNT_ID="$("$AWS_CLI" sts get-caller-identity --query Account --output text 2>/dev/null)" || {
    echo "❌ Failed to get AWS account ID. Check your AWS credentials."
    exit 1
}
echo "🔐 Using AWS Account ID: $ACCOUNT_ID"

# --- IAM Role (IAM is global; do NOT pass --region) ---
echo "🔐 Ensuring IAM role: $ROLE_NAME"
if "$AWS_CLI" iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  echo "✅ IAM role $ROLE_NAME already exists"
else
  echo "🔐 Creating IAM role: $ROLE_NAME"
  cat > trust-policy.json << 'JSON'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "lambda.amazonaws.com" },
    "Action": "sts:AssumeRole"
  }]
}
JSON
  retry_aws_command $MAX_RETRIES "$AWS_CLI" iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document file://trust-policy.json
  # allow role to propagate
  echo "⏳ Waiting for role to propagate..."
  sleep 15
fi

echo "🔐 Attaching AWS managed policies..."
"$AWS_CLI" iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null || true

"$AWS_CLI" iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchReadOnlyAccess 2>/dev/null || true

"$AWS_CLI" iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsReadOnlyAccess 2>/dev/null || true

# Cross-account + CW read policy
echo "🔐 Ensuring custom policy: MonitoringLambdaCrossAccountPolicy"
cat > cross-account-policy.json << 'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": ["sts:AssumeRole"], "Resource": "*" },
    {
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups","logs:DescribeLogStreams","logs:FilterLogEvents","logs:GetLogEvents",
        "cloudwatch:DescribeAlarms","cloudwatch:ListDashboards","cloudwatch:GetDashboard",
        "cloudwatch:DescribeAlarmsForMetric","cloudwatch:GetMetricStatistics"
      ],
      "Resource": "*"
    }
  ]
}
JSON

POLICY_ARN="arn:aws:iam::$ACCOUNT_ID:policy/MonitoringLambdaCrossAccountPolicy"
if "$AWS_CLI" iam get-policy --policy-arn "$POLICY_ARN" >/dev/null 2>&1; then
  echo "🔄 Updating custom policy default version"
  # Delete old non-default versions to avoid limit
  OLD_VERSIONS=$("$AWS_CLI" iam list-policy-versions --policy-arn "$POLICY_ARN" \
    --query "Versions[?IsDefaultVersion==\`false\`].VersionId" --output text 2>/dev/null || true)
  for version in $OLD_VERSIONS; do
    "$AWS_CLI" iam delete-policy-version --policy-arn "$POLICY_ARN" --version-id "$version" 2>/dev/null || true
  done
  
  retry_aws_command $MAX_RETRIES "$AWS_CLI" iam create-policy-version \
    --policy-arn "$POLICY_ARN" \
    --policy-document file://cross-account-policy.json \
    --set-as-default
else
  echo "🆕 Creating custom policy"
  retry_aws_command $MAX_RETRIES "$AWS_CLI" iam create-policy \
    --policy-name MonitoringLambdaCrossAccountPolicy \
    --policy-document file://cross-account-policy.json \
    --description "Policy for monitoring Lambda to access CloudWatch across accounts"
fi

"$AWS_CLI" iam attach-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-arn "$POLICY_ARN" 2>/dev/null || true

ROLE_ARN="arn:aws:iam::$ACCOUNT_ID:role/$ROLE_NAME"

# --- Build environment JSON from .env (if present) ---
ENV_MAP='{}'
if [ -f "$SCRIPT_DIR/.env" ]; then
  echo "📋 Loading environment variables from .env..."
  # helper to read and strip surrounding quotes
  read_env() {
    local key="$1"
    local val
    val="$(grep -E "^${key}=" "$SCRIPT_DIR/.env" | head -n1 | cut -d'=' -f2- || true)"
    # strip leading/trailing quotes if present
    val="${val%\"}"; val="${val#\"}"
    val="${val%\'}"  ; val="${val#\'}"  # Also strip single quotes
    echo -n "$val"
  }
  add_if_present() {
    local key="$1"; local val="$2"
    if [ -n "$val" ]; then
      ENV_MAP="$(jq --arg k "$key" --arg v "$val" '. + {($k):$v}' <<< "$ENV_MAP")"
    fi
  }

  # New Basic Auth configuration
  add_if_present "JIRA_USERNAME"         "$(read_env JIRA_USERNAME)"
  add_if_present "JIRA_API_TOKEN"        "$(read_env JIRA_API_TOKEN)"
  add_if_present "JIRA_INSTANCE_URL"     "$(read_env JIRA_INSTANCE_URL)"
  add_if_present "JIRA_CLOUD"            "$(read_env JIRA_CLOUD)"
  add_if_present "PROJECT_KEY"           "$(read_env PROJECT_KEY)"
  add_if_present "JIRA_ISSUE_TYPE_DEFAULT" "$(read_env JIRA_ISSUE_TYPE_DEFAULT)"
  add_if_present "JIRA_TIMEOUT_SECONDS"  "$(read_env JIRA_TIMEOUT_SECONDS)"
  
  # Legacy OAuth support (if still present)
  add_if_present "JIRA_URL"              "$(read_env JIRA_URL)"
  add_if_present "JIRA_USER"             "$(read_env JIRA_USER)"
  add_if_present "JIRA_TOKEN"            "$(read_env JIRA_TOKEN)"
  add_if_present "JIRA_PROJECT_DEFAULT"  "$(read_env JIRA_PROJECT_DEFAULT)"
  add_if_present "JIRA_PRIORITY_DEFAULT" "$(read_env JIRA_PRIORITY_DEFAULT)"
  add_if_present "JIRA_API_VERSION"      "$(read_env JIRA_API_VERSION)"
  add_if_present "JIRA_MAX_RETRIES"      "$(read_env JIRA_MAX_RETRIES)"
  add_if_present "JIRA_VERIFY_TLS"       "$(read_env JIRA_VERIFY_TLS)"

  echo '{ "Variables": '"$ENV_MAP"' }' > env_vars.json
  echo "✅ Built env_vars.json from .env"
else
  echo "⚠️  No .env file found at $SCRIPT_DIR/.env (continuing without environment variables)"
fi

# --- Wait for role to be assumable ---
echo "⏳ Ensuring role is assumable by Lambda service..."
sleep 5

# --- Create or Update Lambda ---
if "$AWS_CLI" lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" >/dev/null 2>&1; then
  echo "🔄 Updating existing Lambda: $FUNCTION_NAME"
  
  # Update code first
  retry_aws_command $MAX_RETRIES "$AWS_CLI" lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file fileb://lambda-deployment.zip \
    --region "$REGION"
  
  # Wait for function to be updated
  echo "⏳ Waiting for function update to complete..."
  "$AWS_CLI" lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" 2>/dev/null || sleep 10

  # Update configuration
  if [ -f env_vars.json ]; then
    echo "🔧 Updating Lambda environment variables..."
    retry_aws_command $MAX_RETRIES "$AWS_CLI" lambda update-function-configuration \
      --function-name "$FUNCTION_NAME" \
      --timeout 300 \
      --memory-size 512 \
      --environment file://env_vars.json \
      --region "$REGION"
  else
    retry_aws_command $MAX_RETRIES "$AWS_CLI" lambda update-function-configuration \
      --function-name "$FUNCTION_NAME" \
      --timeout 300 \
      --memory-size 512 \
      --region "$REGION"
  fi
else
  echo "🆕 Creating new Lambda: $FUNCTION_NAME"
  
  # Build create command based on whether we have env vars
  CREATE_CMD=("$AWS_CLI" lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime "$RUNTIME" \
    --role "$ROLE_ARN" \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://lambda-deployment.zip \
    --timeout 300 \
    --memory-size 512 \
    --description "Monitoring agent Lambda for AgentCore Gateway" \
    --region "$REGION")
  
  if [ -f env_vars.json ]; then
    CREATE_CMD+=(--environment file://env_vars.json)
  fi
  
  # Try to create with retries
  if ! retry_aws_command $MAX_RETRIES "${CREATE_CMD[@]}"; then
    echo "❌ Failed to create Lambda function after $MAX_RETRIES attempts"
    echo ""
    echo "🔍 Troubleshooting steps:"
    echo "1. Check your network connection"
    echo "2. Verify AWS credentials: aws sts get-caller-identity"
    echo "3. Check AWS service status: https://status.aws.amazon.com/"
    echo "4. Try a different region: ./deploy_lambda.sh $FUNCTION_NAME us-east-1"
    echo "5. Check if you have the necessary IAM permissions"
    echo ""
    echo "📝 You can also try deploying with AWS CLI directly:"
    echo "aws lambda create-function --function-name $FUNCTION_NAME --runtime $RUNTIME --role $ROLE_ARN --handler lambda_function.lambda_handler --zip-file fileb://$DEPLOY_DIR/lambda-deployment.zip --region $REGION"
    exit 1
  fi
fi

# Wait for function to be active
echo "⏳ Waiting for function to become active..."
sleep 10

# --- Permission for AgentCore Gateway to invoke ---
echo "🔐 Adding invoke permissions for AgentCore Gateway (idempotent)..."
SID="agentcore-gateway-invoke-$(date +%s)"
"$AWS_CLI" lambda add-permission \
  --function-name "$FUNCTION_NAME" \
  --statement-id "$SID" \
  --action lambda:InvokeFunction \
  --principal bedrock.amazonaws.com \
  --region "$REGION" 2>/dev/null || \
"$AWS_CLI" lambda add-permission \
  --function-name "$FUNCTION_NAME" \
  --statement-id "$SID" \
  --action lambda:InvokeFunction \
  --principal lambda.amazonaws.com \
  --region "$REGION" 2>/dev/null || true

# --- Output ---
if FUNCTION_ARN="$("$AWS_CLI" lambda get-function \
  --function-name "$FUNCTION_NAME" \
  --region "$REGION" \
  --query 'Configuration.FunctionArn' \
  --output text 2>/dev/null)"; then
  echo ""
  echo "✅ Lambda function deployed successfully!"
  echo "📋 Function ARN: $FUNCTION_ARN"
  echo "🔧 Function Name: $FUNCTION_NAME"
  echo "🌍 Region: $REGION"
  echo ""
  echo "🧪 Test your function with:"
  echo "aws lambda invoke --function-name $FUNCTION_NAME --region $REGION response.json"
else
  echo "⚠️  Function may have been created but unable to retrieve ARN"
  echo "Check manually: aws lambda get-function --function-name $FUNCTION_NAME --region $REGION"
fi

# --- Cleanup ---
popd >/dev/null
rm -f trust-policy.json cross-account-policy.json env_vars.json 2>/dev/null || true
echo "🧹 Cleaned up temporary files"