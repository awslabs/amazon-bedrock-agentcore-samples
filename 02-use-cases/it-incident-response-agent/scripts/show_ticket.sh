#!/usr/bin/env bash
# Show the resolved state of a ticket.
# Usage: scripts/show_ticket.sh INC-1042
set -euo pipefail

cd "$(dirname "$0")/.."

set -a
# shellcheck disable=SC1091
source .env
set +a

STACK="${STACK_NAME:-ItIncidentResponseAgent}"
TICKET_ID="${1:?ticket_id required, e.g. INC-1042}"

TABLE=$(aws cloudformation describe-stacks \
  --stack-name "$STACK" \
  --region "$AWS_REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`TicketsTableName`].OutputValue' \
  --output text)

aws dynamodb get-item \
  --table-name "$TABLE" \
  --region "$AWS_REGION" \
  --key "{\"ticket_id\":{\"S\":\"$TICKET_ID\"}}" \
  --output json
