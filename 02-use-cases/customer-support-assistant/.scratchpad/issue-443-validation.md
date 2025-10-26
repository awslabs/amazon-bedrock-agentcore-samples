# Issue #443 Validation Plan

*Created: 2025-10-16*
*Branch: issue-443-customer-support-improvements*

## Summary of Changes

All 5 issues from GitHub Issue #443 have been addressed:

### ✅ Issue 1: Product Naming (AWS Bedrock → Amazon Bedrock)
**Status**: FIXED
- [README.md:6](../README.md#L6) - Changed description from "AWS Bedrock" to "Amazon Bedrock"
- [pyproject.toml:4](../pyproject.toml#L4) - Updated package description

**Validation**:
```bash
# Should return 0 matches (all fixed)
grep -n "AWS Bedrock" README.md pyproject.toml
```

### ✅ Issue 2: IAM Permissions Documentation
**Status**: FIXED
- Added comprehensive IAM permissions section in [README.md:55-146](../README.md#L55-L146)
- Includes all required permissions for:
  - S3 Vector operations
  - SSM Parameter Store
  - DynamoDB
  - Cognito
- Added note about AmazonBedrockFullAccess managed policy
- Added production security best practice note

**Validation**:
```bash
# Should show the IAM permissions section
grep -A5 "IAM Permissions" README.md
```

### ✅ Issue 3: AWS Region Configuration for EC2
**Status**: FIXED
- [scripts/prereq.sh:12](../scripts/prereq.sh#L12) - Updated region detection
- [scripts/cleanup.sh:10](../scripts/cleanup.sh#L10) - Updated region detection
- [scripts/list_ssm_parameters.sh:7](../scripts/list_ssm_parameters.sh#L7) - Updated region detection

**Changed from**:
```bash
REGION=$(aws configure get region)
```

**Changed to**:
```bash
REGION=$(aws configure get region || echo "${AWS_DEFAULT_REGION:-us-east-1}")
```

**Validation**:
```bash
# Test without AWS_DEFAULT_REGION (should use us-east-1)
unset AWS_DEFAULT_REGION
./scripts/list_ssm_parameters.sh 2>&1 | grep "Region:"

# Test with AWS_DEFAULT_REGION
export AWS_DEFAULT_REGION=us-west-2
./scripts/list_ssm_parameters.sh 2>&1 | grep "Region:"
```

### ✅ Issue 4: Gateway Wait Logic
**Status**: FIXED
- [scripts/agentcore_gateway.py:7](../scripts/agentcore_gateway.py#L7) - Added `import time`
- [scripts/agentcore_gateway.py:73-93](../scripts/agentcore_gateway.py#L73-L93) - Added comprehensive wait logic

**Changes**:
- Waits up to 5 minutes (30 retries × 10 seconds) for gateway to become ACTIVE/READY
- Provides progress feedback during wait
- Handles failure states (FAILED, DELETING, DELETED)
- Timeout error if gateway doesn't become active

**Validation**:
```bash
# Check that time module is imported
grep "^import time" scripts/agentcore_gateway.py

# Check wait logic exists
grep -A5 "Waiting for gateway to become ACTIVE" scripts/agentcore_gateway.py

# Syntax check
uv run python -m py_compile scripts/agentcore_gateway.py
```

### ✅ Issue 5: Migration to uv Package Manager
**Status**: FIXED
- Created [pyproject.toml](../pyproject.toml) with all dependencies
- Generated [uv.lock](../uv.lock) file
- Updated all `python` commands to `uv run python` in README
- Updated shell scripts to use `uv run python`

**Files Updated**:
- [scripts/prereq.sh:100](../scripts/prereq.sh#L100) - Uses `uv run python`
- [scripts/cleanup.sh:62](../scripts/cleanup.sh#L62) - Uses `uv run python`
- [README.md](../README.md) - All Python command examples updated (30+ locations)

**Validation**:
```bash
# Verify pyproject.toml exists and is valid
cat pyproject.toml | grep "name = "

# Test uv sync
uv sync

# Verify all README commands use "uv run"
grep -n "^python " README.md  # Should return 0 matches in code blocks

# Verify scripts use uv run
grep "uv run python" scripts/prereq.sh scripts/cleanup.sh
```

## Quick Validation Script

Run this to validate all changes:

```bash
#!/bin/bash
set -e

echo "=== Issue #443 Validation ==="
echo ""

echo "✓ Issue 1: Product Naming"
ISSUE1=$(grep -c "AWS Bedrock" README.md pyproject.toml 2>/dev/null || true)
if [ "$ISSUE1" -eq 0 ]; then
    echo "  ✅ PASS: No 'AWS Bedrock' found in key files"
else
    echo "  ❌ FAIL: Found $ISSUE1 instances of 'AWS Bedrock'"
fi
echo ""

echo "✓ Issue 2: IAM Permissions Documentation"
ISSUE2=$(grep -c "IAM Permissions" README.md || true)
if [ "$ISSUE2" -gt 0 ]; then
    echo "  ✅ PASS: IAM permissions section exists"
else
    echo "  ❌ FAIL: IAM permissions section not found"
fi
echo ""

echo "✓ Issue 3: Region Configuration"
ISSUE3=$(grep -c 'AWS_DEFAULT_REGION:-us-east-1' scripts/prereq.sh scripts/cleanup.sh scripts/list_ssm_parameters.sh || true)
if [ "$ISSUE3" -eq 3 ]; then
    echo "  ✅ PASS: All 3 scripts have region fallback logic"
else
    echo "  ❌ FAIL: Only $ISSUE3/3 scripts have region fallback"
fi
echo ""

echo "✓ Issue 4: Gateway Wait Logic"
ISSUE4_IMPORT=$(grep -c "^import time" scripts/agentcore_gateway.py || true)
ISSUE4_WAIT=$(grep -c "Waiting for gateway to become ACTIVE" scripts/agentcore_gateway.py || true)
if [ "$ISSUE4_IMPORT" -eq 1 ] && [ "$ISSUE4_WAIT" -gt 0 ]; then
    echo "  ✅ PASS: Gateway wait logic implemented"
else
    echo "  ❌ FAIL: Gateway wait logic incomplete"
fi
echo ""

echo "✓ Issue 5: UV Migration"
ISSUE5_TOML=$([ -f pyproject.toml ] && echo 1 || echo 0)
ISSUE5_SCRIPTS=$(grep -c "uv run python" scripts/prereq.sh scripts/cleanup.sh || true)
if [ "$ISSUE5_TOML" -eq 1 ] && [ "$ISSUE5_SCRIPTS" -eq 2 ]; then
    echo "  ✅ PASS: UV migration complete"
else
    echo "  ❌ FAIL: UV migration incomplete"
fi
echo ""

echo "=== Syntax Validation ==="
echo "Checking Python syntax..."
uv run python -m py_compile scripts/agentcore_gateway.py
uv run python -m py_compile scripts/utils.py
echo "  ✅ PASS: Python syntax valid"
echo ""

echo "=== All Validations Complete ==="
```

## Testing Checklist

### Pre-Deployment Testing (No AWS Resources Required)

- [ ] Verify no "AWS Bedrock" in README or pyproject.toml
- [ ] Confirm IAM permissions section exists in README
- [ ] Check all shell scripts have region fallback logic
- [ ] Verify gateway script has wait logic and time import
- [ ] Confirm pyproject.toml exists and is valid
- [ ] Run `uv sync` successfully
- [ ] Python syntax validation passes for all scripts

### Deployment Testing (Requires AWS Account)

- [ ] Run `./scripts/prereq.sh` without region configured (tests Issue 3)
- [ ] Create gateway and verify wait logic works (tests Issue 4)
- [ ] Run all commands using `uv run python` (tests Issue 5)
- [ ] Verify IAM permissions allow all operations (tests Issue 2)

### Manual Code Review

- [ ] All Python commands in README use `uv run`
- [ ] Shell scripts use `uv run python` for Python invocations
- [ ] README lists prerequisites including uv installation
- [ ] IAM permissions are comprehensive and documented

## Additional Notes

### Files Modified
```
M  README.md                            (Issues 1, 2, 5)
M  scripts/agentcore_gateway.py         (Issue 4)
M  scripts/cleanup.sh                   (Issues 3, 5)
M  scripts/list_ssm_parameters.sh       (Issue 3)
M  scripts/prereq.sh                    (Issues 3, 5)
M  scripts/utils.py                     (Related changes)
M  test/test_gateway.py                 (Related changes)
M  pyproject.toml                       (Issues 1, 5)
```

### Untracked Files (Not to be committed)
```
.agentcore.json
.cognito_access_token
.scratchpad/
gateway-config.json
scripts/get_cognito_token.sh
```

### Files to Commit
```
uv.lock                                 (Generated by uv)
```

## Next Steps

1. **Run validation script** to ensure all changes are correct
2. **Test syntax** with `uv run python -m py_compile` on all modified Python files
3. **Stage changes** for commit
4. **Create commit** with message referencing Issue #443
5. **Push branch** to remote
6. **Create pull request** linking to Issue #443
