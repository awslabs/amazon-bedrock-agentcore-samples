#!/bin/bash
set -e

echo "Checking Python compilation..."
find app/ lambdas/ scripts/ tests/ -name "*.py" -exec python3 -m py_compile {} \;
echo "  ✓ All Python files compile"

echo "Running ruff..."
ruff check app/ lambdas/ scripts/ tests/
echo "  ✓ ruff passed"

echo "Running unit tests..."
python3 -m unittest discover -s tests
echo "  ✓ unit tests passed"

echo "All checks passed!"
