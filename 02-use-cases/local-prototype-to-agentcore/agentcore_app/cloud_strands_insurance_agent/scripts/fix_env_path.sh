#!/bin/bash

echo "Fixing GATEWAY_INFO_FILE path in .env..."

if [ -f .env ]; then
    # Update the path
    sed -i.bak 's|GATEWAY_INFO_FILE=.*|GATEWAY_INFO_FILE="../cloud_mcp_server/gateway_info.json"|g' .env
    echo "✓ Updated .env file"
    echo ""
    echo "Old path: ../cloud_mcp_server/1_pre_req_setup/gateway_info.json"
    echo "New path: ../cloud_mcp_server/gateway_info.json"
else
    echo "❌ .env file not found"
    echo "Please create it first: cp .env_example .env"
fi
