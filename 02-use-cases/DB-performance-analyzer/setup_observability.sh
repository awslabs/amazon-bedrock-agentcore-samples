#!/bin/bash
set -e

echo "=== Setting up AgentCore Gateway Observability ==="

# Make script executable
chmod +x scripts/enable_observability.sh

# Enable CloudWatch Transaction Search and configure log groups
echo "Enabling CloudWatch Transaction Search and configuring log groups..."
./scripts/enable_observability.sh

echo "=== AgentCore Gateway Observability Setup Complete ==="
echo "To view observability data, open the CloudWatch console and navigate to:"
echo "  - Application Signals > Transaction search"
echo "  - Log groups > /aws/vendedlogs/bedrock-agentcore/<resource-id>"
echo "  - X-Ray > Traces"