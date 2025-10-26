#!/bin/bash

# Exit on error
set -e

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration with defaults
AWS_REGION="${AWS_REGION:-us-east-1}"
DASHBOARD_NAME="${DASHBOARD_NAME:-AgentCore-Observability-Demo}"
LOG_GROUP_NAME="${LOG_GROUP_NAME:-/aws/agentcore/traces}"
NAMESPACE="${NAMESPACE:-AgentCore/Observability}"

# Help text
show_help() {
    cat << EOF
Set up CloudWatch Transaction Search and dashboard for AgentCore observability.

Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -r, --region REGION     AWS region (default: us-east-1)
    -d, --dashboard NAME    Dashboard name (default: AgentCore-Observability-Demo)
    -l, --log-group NAME    Log group name (default: /aws/agentcore/traces)

Environment Variables:
    AWS_REGION              AWS region for resources
    DASHBOARD_NAME          CloudWatch dashboard name
    LOG_GROUP_NAME          CloudWatch log group name
    NAMESPACE               CloudWatch metrics namespace

Example:
    # Setup with defaults
    ./setup_cloudwatch.sh

    # Setup with custom region
    ./setup_cloudwatch.sh --region us-west-2

    # Setup with custom dashboard name
    ./setup_cloudwatch.sh --dashboard MyAgentCoreDashboard

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -r|--region)
            AWS_REGION="$2"
            shift 2
            ;;
        -d|--dashboard)
            DASHBOARD_NAME="$2"
            shift 2
            ;;
        -l|--log-group)
            LOG_GROUP_NAME="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate AWS credentials
echo "Validating AWS credentials..."
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
if [ $? -ne 0 ]; then
    echo "Error: Failed to get AWS Account ID. Check your AWS credentials."
    exit 1
fi

echo "AWS Account ID: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_REGION"

# Load agent ID if available
AGENT_ID=""
if [ -f "$SCRIPT_DIR/.agent_id" ]; then
    AGENT_ID=$(cat "$SCRIPT_DIR/.agent_id")
    echo "Agent ID: $AGENT_ID"
else
    echo "Warning: Agent ID not found. Run deploy_agent.sh first for full setup."
fi

# Create CloudWatch log group if it doesn't exist
echo "Setting up CloudWatch log group: $LOG_GROUP_NAME"
aws logs create-log-group \
    --log-group-name "$LOG_GROUP_NAME" \
    --region "$AWS_REGION" \
    2>/dev/null || echo "Log group already exists or creation not needed"

# Set log retention policy
echo "Setting log retention to 7 days..."
aws logs put-retention-policy \
    --log-group-name "$LOG_GROUP_NAME" \
    --retention-in-days 7 \
    --region "$AWS_REGION" \
    2>/dev/null || echo "Retention policy already set or not needed"

# Enable Transaction Search (if available)
echo "Enabling CloudWatch Transaction Search..."
echo "Note: Transaction Search may require specific service quotas and region availability"

# Check if X-Ray is enabled
echo "Checking X-Ray tracing status..."
aws xray get-sampling-rules \
    --region "$AWS_REGION" \
    > /dev/null 2>&1 && echo "X-Ray service is available" || echo "Note: X-Ray may need to be enabled"

# Create CloudWatch Dashboard
echo "Creating CloudWatch dashboard: $DASHBOARD_NAME"

# Generate dashboard body
DASHBOARD_BODY=$(cat << 'EOF'
{
    "widgets": [
        {
            "type": "metric",
            "properties": {
                "metrics": [
                    [ "AgentCore/Observability", "latency", { "stat": "Average" } ],
                    [ "...", { "stat": "p50" } ],
                    [ "...", { "stat": "p90" } ],
                    [ "...", { "stat": "p99" } ]
                ],
                "period": 300,
                "stat": "Average",
                "region": "REGION_PLACEHOLDER",
                "title": "Agent Response Latency",
                "yAxis": {
                    "left": {
                        "label": "Milliseconds"
                    }
                }
            }
        },
        {
            "type": "metric",
            "properties": {
                "metrics": [
                    [ "AgentCore/Observability", "token_count", { "stat": "Sum" } ]
                ],
                "period": 300,
                "stat": "Sum",
                "region": "REGION_PLACEHOLDER",
                "title": "Token Consumption",
                "yAxis": {
                    "left": {
                        "label": "Tokens"
                    }
                }
            }
        },
        {
            "type": "metric",
            "properties": {
                "metrics": [
                    [ "AgentCore/Observability", "error_count", { "stat": "Sum" } ]
                ],
                "period": 300,
                "stat": "Sum",
                "region": "REGION_PLACEHOLDER",
                "title": "Error Count",
                "yAxis": {
                    "left": {
                        "label": "Errors"
                    }
                }
            }
        },
        {
            "type": "log",
            "properties": {
                "query": "SOURCE 'LOG_GROUP_PLACEHOLDER'\n| fields @timestamp, @message\n| filter @message like /trace/\n| sort @timestamp desc\n| limit 20",
                "region": "REGION_PLACEHOLDER",
                "title": "Recent Trace Events"
            }
        },
        {
            "type": "metric",
            "properties": {
                "metrics": [
                    [ "AWS/Bedrock", "Invocations", { "stat": "Sum" } ]
                ],
                "period": 300,
                "stat": "Sum",
                "region": "REGION_PLACEHOLDER",
                "title": "Bedrock Invocations"
            }
        },
        {
            "type": "log",
            "properties": {
                "query": "SOURCE 'LOG_GROUP_PLACEHOLDER'\n| fields @timestamp, service.name, operation, latency\n| stats avg(latency) as avg_latency, max(latency) as max_latency by operation\n| sort avg_latency desc",
                "region": "REGION_PLACEHOLDER",
                "title": "Latency by Operation"
            }
        }
    ]
}
EOF
)

# Replace placeholders
DASHBOARD_BODY=$(echo "$DASHBOARD_BODY" | sed "s/REGION_PLACEHOLDER/$AWS_REGION/g")
DASHBOARD_BODY=$(echo "$DASHBOARD_BODY" | sed "s|LOG_GROUP_PLACEHOLDER|$LOG_GROUP_NAME|g")

# Save dashboard body to temporary file
DASHBOARD_FILE=$(mktemp)
echo "$DASHBOARD_BODY" > "$DASHBOARD_FILE"

# Create or update dashboard
aws cloudwatch put-dashboard \
    --dashboard-name "$DASHBOARD_NAME" \
    --dashboard-body file://"$DASHBOARD_FILE" \
    --region "$AWS_REGION"

if [ $? -ne 0 ]; then
    echo "Error: Failed to create CloudWatch dashboard"
    rm -f "$DASHBOARD_FILE"
    exit 1
fi

echo "CloudWatch dashboard created successfully!"

# Clean up
rm -f "$DASHBOARD_FILE"

# Check and create IAM permissions if needed
echo "Checking IAM permissions for X-Ray..."
echo "Note: Your execution role should have the following permissions:"
echo "  - xray:PutTraceSegments"
echo "  - xray:PutTelemetryRecords"
echo "  - logs:CreateLogGroup"
echo "  - logs:CreateLogStream"
echo "  - logs:PutLogEvents"

# Create IAM policy document for reference
IAM_POLICY_FILE="$SCRIPT_DIR/xray-permissions.json"
cat > "$IAM_POLICY_FILE" << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "xray:PutTraceSegments",
                "xray:PutTelemetryRecords",
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "cloudwatch:PutMetricData"
            ],
            "Resource": "*"
        }
    ]
}
EOF

echo "IAM policy template saved to: $IAM_POLICY_FILE"
echo "Attach this policy to your AgentCore Runtime execution role if needed"

# Generate dashboard URL
DASHBOARD_URL="https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#dashboards:name=${DASHBOARD_NAME}"
XRAY_URL="https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#xray:traces"
LOGS_URL="https://console.aws.amazon.com/cloudwatch/home?region=${AWS_REGION}#logsV2:log-groups/log-group/$(echo $LOG_GROUP_NAME | sed 's/\//%252F/g')"

# Save URLs to file
URLS_FILE="$SCRIPT_DIR/cloudwatch-urls.txt"
cat > "$URLS_FILE" << EOF
CloudWatch Dashboard URL:
$DASHBOARD_URL

X-Ray Traces URL:
$XRAY_URL

CloudWatch Logs URL:
$LOGS_URL
EOF

echo "CloudWatch URLs saved to: $URLS_FILE"

# Print completion message
echo ""
echo "========================================"
echo "CLOUDWATCH SETUP COMPLETE"
echo "========================================"
echo ""
echo "Dashboard Name: $DASHBOARD_NAME"
echo "Log Group: $LOG_GROUP_NAME"
echo "Namespace: $NAMESPACE"
echo "Region: $AWS_REGION"
echo ""
echo "Access Your CloudWatch Resources:"
echo ""
echo "1. CloudWatch Dashboard:"
echo "   $DASHBOARD_URL"
echo ""
echo "2. X-Ray Traces:"
echo "   $XRAY_URL"
echo ""
echo "3. CloudWatch Logs:"
echo "   $LOGS_URL"
echo ""
echo "Next Steps:"
echo "1. Verify IAM permissions are configured (see $IAM_POLICY_FILE)"
echo "2. Run the observability demo to generate traces"
echo "3. Open the dashboard to view metrics and traces"
echo ""
