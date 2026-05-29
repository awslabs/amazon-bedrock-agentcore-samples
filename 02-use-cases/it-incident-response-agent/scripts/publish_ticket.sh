#!/usr/bin/env bash
# Publish a ticket to the SNS topic to trigger the agent.
# Usage:
#   scripts/publish_ticket.sh                       # uses seed-data/sample_ticket.json
#   scripts/publish_ticket.sh path/to/ticket.json   # custom ticket
set -euo pipefail

cd "$(dirname "$0")/.."

set -a
# shellcheck disable=SC1091
source .env
set +a

STACK="${STACK_NAME:-ItIncidentResponseAgent}"
TICKET_FILE="${1:-seed-data/sample_ticket.json}"

if [[ ! -f "$TICKET_FILE" ]]; then
  echo "ERROR: ticket file $TICKET_FILE not found" >&2
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

echo "==> Publishing $TICKET_FILE to $TOPIC_ARN"
aws sns publish \
  --topic-arn "$TOPIC_ARN" \
  --region "$AWS_REGION" \
  --message file://"$TICKET_FILE" \
  --query MessageId --output text
echo "==> Published. Tail the agent logs:"
echo "    aws logs tail /aws/bedrock-agentcore/runtimes --follow --region $AWS_REGION"
