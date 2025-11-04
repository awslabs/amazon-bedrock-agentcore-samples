#!/bin/bash

# Exit on error
set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Load agent metadata
if [ -f "$SCRIPT_DIR/.deployment_metadata.json" ]; then
    AGENT_ID=$(jq -r '.agent_id' "$SCRIPT_DIR/.deployment_metadata.json")
    REGION=$(jq -r '.region' "$SCRIPT_DIR/.deployment_metadata.json")
else
    echo "Error: No deployment metadata found"
    exit 1
fi

LOG_GROUP="/aws/bedrock-agentcore/runtimes/$AGENT_ID-DEFAULT"

echo "========================================"
echo "CLOUDWATCH LOGS FOR AGENT"
echo "========================================"
echo "Agent ID: $AGENT_ID"
echo "Log Group: $LOG_GROUP"
echo "Region: $REGION"
echo "========================================"
echo ""

# Parse arguments
TIME_RANGE="15m"
FILTER_PATTERN=""
FOLLOW=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--time)
            TIME_RANGE="$2"
            shift 2
            ;;
        -e|--errors)
            FILTER_PATTERN="ERROR"
            shift
            ;;
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        -h|--help)
            cat << EOF
Usage: $0 [OPTIONS]

Options:
    -t, --time RANGE    Time range (default: 15m)
                        Examples: 15m, 1h, 2h, 1d
    -e, --errors        Show only ERROR messages
    -f, --follow        Follow logs in real-time
    -h, --help          Show this help message

Examples:
    # Show last 15 minutes of logs
    ./check_logs.sh

    # Show only errors from last hour
    ./check_logs.sh --time 1h --errors

    # Follow logs in real-time
    ./check_logs.sh --follow

EOF
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Build command
CMD="aws logs tail \"$LOG_GROUP\" --since $TIME_RANGE --region $REGION"

if [ -n "$FILTER_PATTERN" ]; then
    CMD="$CMD --filter-pattern $FILTER_PATTERN"
fi

if [ "$FOLLOW" = true ]; then
    CMD="$CMD --follow"
fi

echo "Running: $CMD"
echo ""

# Execute command
eval "$CMD"
