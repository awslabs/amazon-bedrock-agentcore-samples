#!/bin/bash
set -e

echo "=== Issue #443 Validation ==="
echo ""

echo "Check 1: Product Naming (AWS Bedrock -> Amazon Bedrock)"
ISSUE1=$(grep "AWS Bedrock" README.md pyproject.toml 2>/dev/null | wc -l || true)
if [ "$ISSUE1" -eq 0 ]; then
    echo "  PASS: No 'AWS Bedrock' found in key files"
else
    echo "  FAIL: Found $ISSUE1 instances of 'AWS Bedrock'"
    grep -n "AWS Bedrock" README.md pyproject.toml
    exit 1
fi
echo ""

echo "Check 2: IAM Permissions Documentation"
ISSUE2=$(grep -c "IAM Permissions" README.md || true)
if [ "$ISSUE2" -gt 0 ]; then
    echo "  PASS: IAM permissions section exists"
    grep -n "IAM Permissions" README.md | head -1
else
    echo "  FAIL: IAM permissions section not found"
    exit 1
fi
echo ""

echo "Check 3: Region Configuration Fallback"
ISSUE3=$(grep 'AWS_DEFAULT_REGION:-us-east-1' scripts/prereq.sh scripts/cleanup.sh scripts/list_ssm_parameters.sh 2>/dev/null | wc -l || true)
if [ "$ISSUE3" -eq 3 ]; then
    echo "  PASS: All 3 scripts have region fallback logic"
    echo "    - scripts/prereq.sh"
    echo "    - scripts/cleanup.sh"
    echo "    - scripts/list_ssm_parameters.sh"
else
    echo "  FAIL: Only $ISSUE3/3 scripts have region fallback"
    exit 1
fi
echo ""

echo "Check 4: Gateway Wait Logic"
ISSUE4_IMPORT=$(grep "^import time" scripts/agentcore_gateway.py 2>/dev/null | wc -l || true)
ISSUE4_WAIT=$(grep "Waiting for gateway to become ACTIVE" scripts/agentcore_gateway.py 2>/dev/null | wc -l || true)
if [ "$ISSUE4_IMPORT" -eq 1 ] && [ "$ISSUE4_WAIT" -gt 0 ]; then
    echo "  PASS: Gateway wait logic implemented"
    echo "    - time module imported"
    echo "    - Wait loop added"
else
    echo "  FAIL: Gateway wait logic incomplete"
    exit 1
fi
echo ""

echo "Check 5: UV Migration"
ISSUE5_TOML=$([ -f pyproject.toml ] && echo 1 || echo 0)
ISSUE5_LOCK=$([ -f uv.lock ] && echo 1 || echo 0)
ISSUE5_SCRIPTS=$(grep "uv run python" scripts/prereq.sh scripts/cleanup.sh 2>/dev/null | wc -l || true)
if [ "$ISSUE5_TOML" -eq 1 ] && [ "$ISSUE5_LOCK" -eq 1 ] && [ "$ISSUE5_SCRIPTS" -eq 2 ]; then
    echo "  PASS: UV migration complete"
    echo "    - pyproject.toml exists"
    echo "    - uv.lock exists"
    echo "    - Shell scripts use 'uv run python'"
else
    echo "  FAIL: UV migration incomplete"
    [ "$ISSUE5_TOML" -eq 0 ] && echo "    - Missing pyproject.toml"
    [ "$ISSUE5_LOCK" -eq 0 ] && echo "    - Missing uv.lock"
    [ "$ISSUE5_SCRIPTS" -ne 2 ] && echo "    - Shell scripts not using 'uv run python' ($ISSUE5_SCRIPTS/2)"
    exit 1
fi
echo ""

echo "=== Python Syntax Validation ==="
echo "Checking Python syntax..."
uv run python -m py_compile scripts/agentcore_gateway.py
echo "  PASS: scripts/agentcore_gateway.py"
uv run python -m py_compile scripts/utils.py
echo "  PASS: scripts/utils.py"
echo ""

echo "=== Summary ==="
echo "ALL CHECKS PASSED"
echo ""
echo "All 5 issues from #443 have been successfully addressed:"
echo "  1. Product naming fixed (AWS Bedrock -> Amazon Bedrock)"
echo "  2. IAM permissions documented"
echo "  3. Region configuration handles EC2 instances"
echo "  4. Gateway creation includes wait logic"
echo "  5. Migrated to uv package manager"
echo ""
echo "Ready to commit and push!"