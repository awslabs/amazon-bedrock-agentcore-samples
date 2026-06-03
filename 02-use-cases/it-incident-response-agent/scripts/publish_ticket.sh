#!/usr/bin/env bash
# Publish a Jira issue-key event to the SNS topic to trigger the agent.
#
# The Jira issue must already exist in your configured site/project. The
# agent will fetch the issue body, comment + transition it via the
# Atlassian Remote MCP server.
#
# Usage:
#   scripts/publish_ticket.sh                     # uses seed-data/sample_ticket.json
#   scripts/publish_ticket.sh path/to/event.json  # custom {"issue_key": "...", "requester_id": "..."}
set -euo pipefail

cd "$(dirname "$0")/.."

set -a
# shellcheck disable=SC1091
source .env
set +a

STACK="${STACK_NAME:-ItIncidentResponseAgent}"
EVENT_FILE="${1:-seed-data/sample_ticket.json}"

if [[ ! -f "$EVENT_FILE" ]]; then
  echo "ERROR: event file $EVENT_FILE not found" >&2
  exit 1
fi

TOPIC_ARN=$(aws cloudformation describe-stacks \
  --stack-name "$STACK" \
  --region "$AWS_REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`TicketsTopicArn`].OutputValue' \
  --output text)

if [[ -z "$TOPIC_ARN" || "$TOPIC_ARN" == "None" ]]; then
  echo "ERROR: could not find TicketsTopicArn output on stack $STACK" >&2
  exit 1
fi

echo "==> Publishing $EVENT_FILE to $TOPIC_ARN"
aws sns publish \
  --topic-arn "$TOPIC_ARN" \
  --region "$AWS_REGION" \
  --message file://"$EVENT_FILE" \
  --query MessageId --output text
echo "==> Published. Tail the agent logs:"
echo "    aws logs tail /aws/bedrock-agentcore/runtimes --follow --region $AWS_REGION"
