#!/bin/bash

# Run all sre-agent prompt examples from README.md

set -e

echo "Running README.md example prompts..."
echo ""

# Configuration
SLEEP_BETWEEN_PROMPTS=10

# Array of prompts from README.md
PROMPTS=(
    "What's the status of the database pods?"
    "Why are the payment-service pods crash looping?"
    "Investigate high latency in the API gateway over the last hour"
    "Find all database connection errors in the last 24 hours"
    "How is the product catalog service performing?"
    "Our database pods are crash looping in production"
    "API response times have degraded 3x in the last hour"
    "Perform a comprehensive health check of all production services"
    "Analyze resource utilization trends and predict when we'll need to scale"
    "Check for any suspicious patterns in authentication logs"
)

# Run each prompt
for i in "${!PROMPTS[@]}"; do
    prompt="${PROMPTS[$i]}"
    echo "=========================================="
    echo "Running prompt $((i+1))/10: $prompt"
    echo "=========================================="
    
    # Record start time
    start_time=$(date +%s.%N)
    
    # Run the command
    sre-agent --prompt "$prompt"
    
    # Calculate and display execution time
    end_time=$(date +%s.%N)
    execution_time=$(echo "$end_time - $start_time" | bc -l)
    printf "Execution time: %.2f seconds\n" "$execution_time"
    
    # Sleep between prompts (except for the last one)
    if [ $((i+1)) -lt ${#PROMPTS[@]} ]; then
        echo "Waiting ${SLEEP_BETWEEN_PROMPTS} seconds before next prompt..."
        sleep $SLEEP_BETWEEN_PROMPTS
    fi
    echo ""
done

echo "All README prompts completed."