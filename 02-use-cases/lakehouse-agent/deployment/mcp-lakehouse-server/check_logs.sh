#!/bin/bash
# Check CloudWatch Logs for MCP Runtime
#
# Usage: ./check_logs.sh [--follow]

set -e

# Get runtime ARN from SSM
echo "📋 Getting runtime ARN from SSM..."
RUNTIME_ARN=$(aws ssm get-parameter --name /app/lakehouse-agent/mcp-server-runtime-arn --query 'Parameter.Value' --output text)

if [ -z "$RUNTIME_ARN" ]; then
    echo "❌ Error: Could not get runtime ARN from SSM"
    echo "   Parameter: /app/lakehouse-agent/mcp-server-runtime-arn"
    exit 1
fi

# Extract runtime ID from ARN
RUNTIME_ID=$(echo "$RUNTIME_ARN" | cut -d'/' -f2)
LOG_GROUP="/aws/bedrock-agentcore/runtime/$RUNTIME_ID"

echo "✅ Runtime ARN: $RUNTIME_ARN"
echo "✅ Runtime ID: $RUNTIME_ID"
echo "✅ Log Group: $LOG_GROUP"
echo ""

# Check if log group exists
if ! aws logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" --query 'logGroups[0].logGroupName' --output text 2>/dev/null | grep -q "$LOG_GROUP"; then
    echo "⚠️  Warning: Log group does not exist yet"
    echo "   This is normal if the runtime hasn't been invoked yet"
    echo "   Try invoking the runtime first, then check logs again"
    exit 0
fi

echo "📊 Log group exists!"
echo ""

# Check for --follow flag
if [ "$1" = "--follow" ]; then
    echo "🔄 Following logs (press Ctrl+C to stop)..."
    echo ""
    aws logs tail "$LOG_GROUP" --follow
else
    echo "📜 Recent logs (last 50 lines):"
    echo "   Use './check_logs.sh --follow' to follow logs in real-time"
    echo ""
    aws logs tail "$LOG_GROUP" --since 1h | tail -50
fi
