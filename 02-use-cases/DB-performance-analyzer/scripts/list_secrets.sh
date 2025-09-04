#!/bin/bash
# List all secrets in the AWS account

# Default region
REGION=${AWS_REGION:-"us-west-2"}
FILTER=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --region)
            REGION="$2"
            shift
            shift
            ;;
        --filter)
            FILTER="$2"
            shift
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--region <region>] [--filter <filter_text>]"
            exit 1
            ;;
    esac
done

echo "Listing all secrets in region $REGION..."

# List all secrets
ALL_SECRETS=$(aws secretsmanager list-secrets \
    --region "$REGION" \
    --query "SecretList[].{Name:Name,ARN:ARN}" \
    --output json)

# Display results
if [ -z "$FILTER" ]; then
    echo "$ALL_SECRETS" | jq -r '.[] | "Name: \(.Name)\nARN: \(.ARN)\n"'
    echo "Total secrets: $(echo "$ALL_SECRETS" | jq '. | length')"
else
    echo "Filtering secrets containing: $FILTER"
    FILTERED=$(echo "$ALL_SECRETS" | jq -r --arg FILTER "$FILTER" '[.[] | select(.Name | contains($FILTER))]')
    echo "$FILTERED" | jq -r '.[] | "Name: \(.Name)\nARN: \(.ARN)\n"'
    echo "Total matching secrets: $(echo "$FILTERED" | jq '. | length')"
fi