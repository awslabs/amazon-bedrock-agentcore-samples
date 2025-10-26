#!/bin/bash

# Exit on error
set -e

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration with defaults
AWS_REGION="${AWS_REGION:-us-east-1}"
SERVICE_NAME="${SERVICE_NAME:-agentcore-observability-demo}"

# Help text
show_help() {
    cat << EOF
Set up Braintrust integration for AgentCore observability.

This script guides you through:
1. Creating a Braintrust account
2. Generating an API key
3. Configuring OTEL integration
4. Testing the connection

Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -k, --api-key KEY       Braintrust API key (if already generated)
    -s, --service NAME      Service name (default: agentcore-observability-demo)
    -t, --test              Test existing Braintrust configuration

Environment Variables:
    BRAINTRUST_API_KEY      Braintrust API key
    SERVICE_NAME            Service name for OTEL traces

Example:
    # Interactive setup
    ./setup_braintrust.sh

    # Setup with existing API key
    ./setup_braintrust.sh --api-key bt-xxxxx

    # Test existing configuration
    ./setup_braintrust.sh --test

EOF
}

# Test mode flag
TEST_MODE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -k|--api-key)
            BRAINTRUST_API_KEY="$2"
            shift 2
            ;;
        -s|--service)
            SERVICE_NAME="$2"
            shift 2
            ;;
        -t|--test)
            TEST_MODE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Test configuration function
test_braintrust_config() {
    echo "Testing Braintrust configuration..."

    if [ -z "$BRAINTRUST_API_KEY" ]; then
        echo "Error: BRAINTRUST_API_KEY not set"
        echo "Set it with: export BRAINTRUST_API_KEY=your_api_key"
        exit 1
    fi

    echo "API Key found (first 10 chars): ${BRAINTRUST_API_KEY:0:10}..."

    # Test connection using curl
    echo "Testing connection to Braintrust API..."
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $BRAINTRUST_API_KEY" \
        https://api.braintrust.dev/v1/projects)

    if [ "$RESPONSE" = "200" ]; then
        echo "Success! Connection to Braintrust API verified"
        echo "Your Braintrust integration is configured correctly"
        return 0
    else
        echo "Error: Failed to connect to Braintrust API (HTTP $RESPONSE)"
        echo "Please check your API key and network connectivity"
        return 1
    fi
}

# If test mode, run test and exit
if [ "$TEST_MODE" = true ]; then
    test_braintrust_config
    exit 0
fi

# Main setup flow
echo "========================================"
echo "BRAINTRUST SETUP GUIDE"
echo "========================================"
echo ""

# Check if API key already provided
if [ -n "$BRAINTRUST_API_KEY" ]; then
    echo "API key detected, testing configuration..."
    if test_braintrust_config; then
        echo "Configuration verified!"
    else
        echo "Configuration test failed. Please check your API key."
        exit 1
    fi
else
    # Interactive setup
    echo "Step 1: Create a Braintrust Account"
    echo "-----------------------------------"
    echo ""
    echo "1. Visit: https://www.braintrust.dev"
    echo "2. Click 'Sign Up' or 'Get Started'"
    echo "3. Create an account using:"
    echo "   - GitHub (recommended)"
    echo "   - Google"
    echo "   - Email"
    echo ""
    read -p "Press ENTER when you have created your account..."
    echo ""

    echo "Step 2: Generate API Key"
    echo "------------------------"
    echo ""
    echo "1. Log in to Braintrust: https://www.braintrust.dev/app"
    echo "2. Navigate to Settings (click your profile icon)"
    echo "3. Select 'API Keys' from the menu"
    echo "4. Click 'Create API Key'"
    echo "5. Give it a name: 'AgentCore Observability Demo'"
    echo "6. Copy the generated API key"
    echo ""
    echo "IMPORTANT: Save this key securely - it will only be shown once!"
    echo ""
    read -p "Press ENTER when you have your API key ready..."
    echo ""

    # Prompt for API key
    echo "Step 3: Enter API Key"
    echo "---------------------"
    echo ""
    read -p "Paste your Braintrust API key: " BRAINTRUST_API_KEY
    echo ""

    if [ -z "$BRAINTRUST_API_KEY" ]; then
        echo "Error: No API key provided"
        exit 1
    fi

    # Test the API key
    echo "Testing API key..."
    if ! test_braintrust_config; then
        echo "Error: API key validation failed"
        exit 1
    fi
fi

# Save configuration
echo ""
echo "Step 4: Configuration Summary"
echo "--------------------------"
echo ""
echo "Braintrust API Key configured successfully."
echo ""
echo "To use the observability demo with Braintrust, set these environment variables:"
echo ""
echo "  export BRAINTRUST_API_KEY=$BRAINTRUST_API_KEY"
echo "  export AWS_REGION=$AWS_REGION"
echo "  export SERVICE_NAME=$SERVICE_NAME"
echo ""

# Create OTEL config with Braintrust
echo "Creating OpenTelemetry configuration..."

OTEL_CONFIG_FILE="$PARENT_DIR/config/otel_config_braintrust.yaml"
cat > "$OTEL_CONFIG_FILE" << EOF
# OpenTelemetry Collector Configuration
# Dual export to AWS CloudWatch and Braintrust

receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 10s
    send_batch_size: 512
    send_batch_max_size: 1024

  resource:
    attributes:
      - key: service.name
        value: $SERVICE_NAME
        action: upsert
      - key: service.version
        value: 1.0.0
        action: upsert
      - key: deployment.environment
        value: demo
        action: upsert

  memory_limiter:
    check_interval: 1s
    limit_mib: 512

exporters:
  # AWS CloudWatch Exporter
  awsxray:
    region: $AWS_REGION
    no_verify_ssl: false

  awsemf:
    region: $AWS_REGION
    namespace: AgentCore/Observability
    log_group_name: /aws/agentcore/traces
    log_stream_name: $SERVICE_NAME

  # Braintrust OTLP Exporter
  otlp/braintrust:
    endpoint: https://api.braintrust.dev/otel
    headers:
      Authorization: Bearer $BRAINTRUST_API_KEY
    tls:
      insecure: false
    compression: gzip
    timeout: 30s

  # Logging exporter for debugging
  logging:
    loglevel: info

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, resource, batch]
      exporters: [awsxray, otlp/braintrust, logging]

    metrics:
      receivers: [otlp]
      processors: [memory_limiter, resource, batch]
      exporters: [awsemf, otlp/braintrust, logging]

  telemetry:
    logs:
      level: info
EOF

echo "OTEL configuration saved to: $OTEL_CONFIG_FILE"

# Create usage instructions
INSTRUCTIONS_FILE="$SCRIPT_DIR/braintrust-usage.md"
cat > "$INSTRUCTIONS_FILE" << EOF
# Braintrust Integration - Usage Guide

## Configuration Complete

Your Braintrust integration is now configured and ready to use!

## Quick Start

1. **Load Environment Variables:**
   \`\`\`bash
   source $ENV_FILE
   \`\`\`

2. **Run the Demo:**
   \`\`\`bash
   cd $PARENT_DIR
   python simple_observability.py --agent-id YOUR_AGENT_ID
   \`\`\`

3. **View Traces in Braintrust:**
   - Open: https://www.braintrust.dev/app
   - Navigate to your project
   - View traces in the Observability dashboard

## Key Features

### In Braintrust Dashboard

1. **Trace Search:**
   - Filter by time range
   - Search by trace ID or session ID
   - Filter by status (success/error)

2. **LLM Metrics:**
   - Token usage (input/output)
   - Model performance
   - Cost analysis
   - Latency breakdown

3. **Quality Evaluation:**
   - Set up custom evaluators
   - Track quality scores over time
   - Compare different model versions

4. **Comparison with CloudWatch:**
   - CloudWatch: AWS-native, infrastructure metrics
   - Braintrust: AI-focused, LLM-specific metrics
   - Both receive same OTEL traces (vendor neutral!)

## Troubleshooting

### API Key Issues
If you get authentication errors:
1. Verify your API key: \`./setup_braintrust.sh --test\`
2. Regenerate key at: https://www.braintrust.dev/app/settings/api-keys
3. Set BRAINTRUST_API_KEY environment variable with new key

### No Traces Appearing
1. Check OTEL collector is running
2. Verify API key is set: \`echo \$BRAINTRUST_API_KEY\`
3. Check network connectivity to api.braintrust.dev
4. Review OTEL collector logs for errors

### Traces in CloudWatch but not Braintrust
1. Check OTEL config has both exporters enabled
2. Verify Braintrust API key is valid
3. Check OTEL collector logs for export errors

## Advanced Configuration

### Custom Project Setup
1. Create project in Braintrust UI
2. Note the project ID
3. Add to OTEL config under \`resource.attributes\`

### Sampling Configuration
To reduce costs, configure sampling in OTEL config:
\`\`\`yaml
processors:
  probabilistic_sampler:
    sampling_percentage: 10  # Sample 10% of traces
\`\`\`

## Resources

- Braintrust Documentation: https://www.braintrust.dev/docs
- OTEL Integration Guide: https://www.braintrust.dev/docs/integrations/opentelemetry
- API Reference: https://www.braintrust.dev/docs/api

## Support

For Braintrust-specific issues:
- Email: support@braintrust.dev
- Documentation: https://www.braintrust.dev/docs
- Community: https://discord.gg/braintrust
EOF

echo "Usage instructions saved to: $INSTRUCTIONS_FILE"

# Print completion message
echo ""
echo "========================================"
echo "BRAINTRUST SETUP COMPLETE"
echo "========================================"
echo ""
echo "Configuration saved to: $ENV_FILE"
echo "OTEL config saved to: $OTEL_CONFIG_FILE"
echo "Usage guide saved to: $INSTRUCTIONS_FILE"
echo ""
echo "Next Steps:"
echo ""
echo "1. Load environment variables:"
echo "   source $ENV_FILE"
echo ""
echo "2. Verify configuration:"
echo "   ./setup_braintrust.sh --test"
echo ""
echo "3. Run the observability demo:"
echo "   cd $PARENT_DIR"
echo "   python simple_observability.py --agent-id YOUR_AGENT_ID"
echo ""
echo "4. View traces in Braintrust:"
echo "   https://www.braintrust.dev/app"
echo ""
echo "Key Points:"
echo "- Traces will be sent to BOTH CloudWatch and Braintrust"
echo "- Same OTEL data, different platform strengths"
echo "- CloudWatch: AWS-native infrastructure monitoring"
echo "- Braintrust: AI-focused LLM performance tracking"
echo ""
echo "For detailed usage instructions, see: $INSTRUCTIONS_FILE"
echo ""
