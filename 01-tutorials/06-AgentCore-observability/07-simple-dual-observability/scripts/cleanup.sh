#!/bin/bash

# Exit on error
set -e

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
DASHBOARD_NAME="${DASHBOARD_NAME:-AgentCore-Observability-Demo}"
LOG_GROUP_NAME="${LOG_GROUP_NAME:-/aws/agentcore/traces}"
FORCE=false

# Help text
show_help() {
    cat << EOF
Clean up resources created by the AgentCore observability demo.

This script removes:
1. Deployed agent from AgentCore Runtime
2. CloudWatch dashboard
3. CloudWatch log groups (optional)
4. Local configuration files

Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -r, --region REGION     AWS region (default: us-east-1)
    -f, --force             Skip confirmation prompts
    -k, --keep-logs         Keep CloudWatch log groups

Environment Variables:
    AWS_REGION              AWS region for resources
    DASHBOARD_NAME          CloudWatch dashboard name
    LOG_GROUP_NAME          CloudWatch log group name

Example:
    # Interactive cleanup
    ./cleanup.sh

    # Force cleanup without prompts
    ./cleanup.sh --force

    # Cleanup but keep logs
    ./cleanup.sh --keep-logs

EOF
}

KEEP_LOGS=false

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
        -f|--force)
            FORCE=true
            shift
            ;;
        -k|--keep-logs)
            KEEP_LOGS=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

echo "========================================"
echo "AGENTCORE OBSERVABILITY CLEANUP"
echo "========================================"
echo ""
echo "This will remove the following resources:"
echo ""

# Check what exists
AGENT_ID=""
if [ -f "$SCRIPT_DIR/.deployment_metadata.json" ]; then
    AGENT_ID=$(jq -r '.agent_id' "$SCRIPT_DIR/.deployment_metadata.json")
    echo "- AgentCore Runtime Agent: $AGENT_ID"
fi

echo "- CloudWatch Dashboard: $DASHBOARD_NAME"

if [ "$KEEP_LOGS" = false ]; then
    echo "- CloudWatch Log Group: $LOG_GROUP_NAME"
else
    echo "- CloudWatch Log Group: (KEEPING)"
fi

echo "- Local configuration files"
echo ""
echo "Region: $AWS_REGION"
echo ""

if [ "$FORCE" = false ]; then
    read -p "Continue with cleanup? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cleanup cancelled"
        exit 0
    fi
    echo ""
fi

# Delete agent
if [ -n "$AGENT_ID" ]; then
    echo "Deleting agent: $AGENT_ID"
    uv run python "$SCRIPT_DIR/delete_agent.py" \
        --region "$AWS_REGION" \
        --agent-id "$AGENT_ID" \
        2>/dev/null || echo "Note: Agent may already be deleted or not found"
    echo "Agent deletion complete"
fi

# Delete CloudWatch dashboard
echo "Deleting CloudWatch dashboard: $DASHBOARD_NAME"
aws cloudwatch delete-dashboards \
    --dashboard-names "$DASHBOARD_NAME" \
    --region "$AWS_REGION" \
    2>/dev/null || echo "Note: Dashboard may not exist"

# Delete log group (if not keeping)
if [ "$KEEP_LOGS" = false ]; then
    echo "Deleting CloudWatch log group: $LOG_GROUP_NAME"
    aws logs delete-log-group \
        --log-group-name "$LOG_GROUP_NAME" \
        --region "$AWS_REGION" \
        2>/dev/null || echo "Note: Log group may not exist"
fi

# Delete local files
echo "Cleaning up local configuration files..."

if [ -f "$SCRIPT_DIR/.deployment_metadata.json" ]; then
    rm "$SCRIPT_DIR/.deployment_metadata.json"
    echo "Removed: .deployment_metadata.json"
fi

if [ -f "$SCRIPT_DIR/cloudwatch-urls.txt" ]; then
    rm "$SCRIPT_DIR/cloudwatch-urls.txt"
    echo "Removed: cloudwatch-urls.txt"
fi

if [ -f "$SCRIPT_DIR/xray-permissions.json" ]; then
    rm "$SCRIPT_DIR/xray-permissions.json"
    echo "Removed: xray-permissions.json"
fi

if [ -f "$SCRIPT_DIR/braintrust-usage.md" ]; then
    rm "$SCRIPT_DIR/braintrust-usage.md"
    echo "Removed: braintrust-usage.md"
fi

echo ""
echo "========================================"
echo "CLEANUP COMPLETE"
echo "========================================"
echo ""
echo "Resources removed:"
if [ -n "$AGENT_ID" ]; then
    echo "- Agent: $AGENT_ID"
fi
echo "- Dashboard: $DASHBOARD_NAME"
if [ "$KEEP_LOGS" = false ]; then
    echo "- Log Group: $LOG_GROUP_NAME"
fi
echo "- Local configuration files"
echo ""
echo "To redeploy, run:"
echo "  ./setup_all.sh"
echo ""
