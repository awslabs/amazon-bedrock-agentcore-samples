#!/bin/bash
# Send refresh or check status. Usage: bash test_refresh.sh <session-id> [action]
# Requires: AGENT_ARN, INBOUND_CLIENT_ID, USERNAME, PASSWORD env vars
set -e
export AWS_PROFILE=${AWS_PROFILE:-account-a}
REGION=${REGION:-us-east-1}

if [ -z "$AGENT_ARN" ] || [ -z "$INBOUND_CLIENT_ID" ]; then
  echo "ERROR: Set AGENT_ARN and run 'source setup_cognito.sh' first"
  exit 1
fi

SESSION_ID=${1:?"Usage: bash test_refresh.sh <session-id> [action]"}
ACTION=${2:-refresh}

ENCODED_ARN=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$AGENT_ARN', safe=''))")
ENDPOINT="https://bedrock-agentcore.${REGION}.amazonaws.com"

TOKEN=$(aws cognito-idp initiate-auth \
  --client-id "$INBOUND_CLIENT_ID" \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=${USERNAME:-testuser},PASSWORD=${PASSWORD:-TestPass123!} \
  --region $REGION --query 'AuthenticationResult.AccessToken' --output text)

echo "Token: ${TOKEN:0:30}..."
echo "Session: $SESSION_ID"
echo "Action: $ACTION"

curl -s -X POST \
  "${ENDPOINT}/runtimes/${ENCODED_ARN}/invocations?qualifier=DEFAULT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: ${SESSION_ID}" \
  -d "{\"action\":\"${ACTION}\"}" | python3 -m json.tool
