#!/bin/bash

# Wrapper script for load testing
# Makes it easy to run common load test scenarios

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

show_help() {
    cat << EOF
Run load tests against the deployed agent to generate observability data.

Usage: $0 [PRESET|OPTIONS]

Presets:
    quick          5 minutes, 2 req/min, balanced workload (default)
    standard       15 minutes, 4 req/min, balanced workload
    extended       30 minutes, 5 req/min, balanced workload
    high-rate      10 minutes, 10 req/min, mixed workload
    multi-tool     15 minutes, 3 req/min, focus on multi-tool queries
    errors         10 minutes, 3 req/min, include 30% errors
    stress         30 minutes, 10 req/min, high load test

Custom Options:
    Pass any arguments to the Python script:
    $0 --duration 20 --rate 5 --multi-tool 50

Examples:
    # Run quick test (5 min, 2 req/min)
    $0 quick

    # Run for 30 minutes at 5 requests/minute
    $0 --duration 30 --rate 5

    # Focus on multi-tool queries
    $0 multi-tool

    # Custom distribution
    $0 --duration 15 --rate 4 --weather-only 30 --time-only 30 --error-inducing 40

For full options, run:
    uv run python $SCRIPT_DIR/run_load_test.py --help

EOF
}

case "${1:-quick}" in
    -h|--help|help)
        show_help
        exit 0
        ;;

    quick)
        echo "Running QUICK load test (5 min, 2 req/min, balanced)"
        uv run python "$SCRIPT_DIR/run_load_test.py" \
            --duration 5 \
            --rate 2
        ;;

    standard)
        echo "Running STANDARD load test (15 min, 4 req/min, balanced)"
        uv run python "$SCRIPT_DIR/run_load_test.py" \
            --duration 15 \
            --rate 4
        ;;

    extended)
        echo "Running EXTENDED load test (30 min, 5 req/min, balanced)"
        uv run python "$SCRIPT_DIR/run_load_test.py" \
            --duration 30 \
            --rate 5
        ;;

    high-rate)
        echo "Running HIGH-RATE load test (10 min, 10 req/min, mixed)"
        uv run python "$SCRIPT_DIR/run_load_test.py" \
            --duration 10 \
            --rate 10 \
            --weather-only 20 \
            --time-only 20 \
            --calculator-only 10 \
            --weather-and-time 20 \
            --multi-tool 20 \
            --unanswerable 10
        ;;

    multi-tool)
        echo "Running MULTI-TOOL focused test (15 min, 3 req/min)"
        uv run python "$SCRIPT_DIR/run_load_test.py" \
            --duration 15 \
            --rate 3 \
            --multi-tool 60 \
            --weather-and-time 30 \
            --unanswerable 10
        ;;

    errors)
        echo "Running ERROR-INDUCING test (10 min, 3 req/min, 30% errors)"
        uv run python "$SCRIPT_DIR/run_load_test.py" \
            --duration 10 \
            --rate 3 \
            --weather-only 20 \
            --time-only 20 \
            --calculator-only 15 \
            --weather-and-time 15 \
            --error-inducing 30
        ;;

    stress)
        echo "Running STRESS test (30 min, 10 req/min, high load)"
        uv run python "$SCRIPT_DIR/run_load_test.py" \
            --duration 30 \
            --rate 10 \
            --weather-only 20 \
            --time-only 20 \
            --calculator-only 10 \
            --weather-and-time 20 \
            --multi-tool 15 \
            --error-inducing 10 \
            --unanswerable 5
        ;;

    *)
        # Pass all arguments to Python script
        uv run python "$SCRIPT_DIR/run_load_test.py" "$@"
        ;;
esac
