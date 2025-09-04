#!/bin/bash
set -e

# Load configurations
source iam_config.env
source cognito_config.env

echo "Listing existing gateways..."

# Run the Python script with virtual environment
source vconfig/bin/activate
python list_gateways.py
deactivate

# Convert the JSON output to environment variables if the file exists
if [ -f gateway_config.json ]; then
    GATEWAY_ID=$(cat gateway_config.json | jq -r '.GATEWAY_ID')
    GATEWAY_ARN=$(cat gateway_config.json | jq -r '.GATEWAY_ARN')
    GATEWAY_ENDPOINT=$(cat gateway_config.json | jq -r '.GATEWAY_ENDPOINT')

    # Save Gateway configuration to file
    cat > gateway_config.env << EOF
export GATEWAY_ID=$GATEWAY_ID
export GATEWAY_ARN=$GATEWAY_ARN
export GATEWAY_ENDPOINT=$GATEWAY_ENDPOINT
EOF

    echo "Gateway configuration saved to gateway_config.env"
fi