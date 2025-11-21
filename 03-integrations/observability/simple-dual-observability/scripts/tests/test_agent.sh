#!/bin/bash

# Exit on error
set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# Change to parent directory to use venv
cd "$PARENT_DIR"

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"

# Help text
show_help() {
    cat << EOF
Test the deployed AgentCore Runtime agent.

Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -r, --region REGION     AWS region (default: us-east-1)
    -t, --test TEST         Run predefined test (weather|time|calculator|combined)
    -p, --prompt "TEXT"     Run custom prompt
    -i, --interactive       Run in interactive mode
    -f, --full              Show full response including traces

Examples:
    # Test weather tool
    ./test_agent.sh --test weather

    # Custom prompt
    ./test_agent.sh --prompt "What is 15 plus 27?"

    # Interactive mode
    ./test_agent.sh --interactive

    # Show full response
    ./test_agent.sh --test combined --full

EOF
}

# Parse arguments
TEST_TYPE=""
CUSTOM_PROMPT=""
INTERACTIVE=false
FULL_FLAG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -r|--region)
            AWS_REGION="$2"
            shift 2
            ;;
        -t|--test)
            TEST_TYPE="$2"
            shift 2
            ;;
        -p|--prompt)
            CUSTOM_PROMPT="$2"
            shift 2
            ;;
        -i|--interactive)
            INTERACTIVE=true
            shift
            ;;
        -f|--full)
            FULL_FLAG="--full"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Build command
CMD="uv run python \"$SCRIPT_DIR/test_agent.py\" --region \"$AWS_REGION\""

if [ "$INTERACTIVE" = true ]; then
    CMD="$CMD --interactive"
elif [ -n "$TEST_TYPE" ]; then
    CMD="$CMD --test $TEST_TYPE"
elif [ -n "$CUSTOM_PROMPT" ]; then
    CMD="$CMD --prompt \"$CUSTOM_PROMPT\""
else
    echo "Error: Must specify --test, --prompt, or --interactive"
    echo ""
    show_help
    exit 1
fi

if [ -n "$FULL_FLAG" ]; then
    CMD="$CMD $FULL_FLAG"
fi

# Run the test
eval "$CMD"
