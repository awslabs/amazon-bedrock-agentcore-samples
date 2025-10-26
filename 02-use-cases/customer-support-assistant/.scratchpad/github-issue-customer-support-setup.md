# Multiple Issues and Improvements for Customer Support Assistant Setup

## Summary

This issue documents several problems encountered during the setup of the Customer Support Assistant sample, along with proposed fixes and improvements.

## Issues Identified

### 1. Incorrect Product Naming in README

**Issue:** The README uses "AWS Bedrock" instead of the correct "Amazon Bedrock" product name.

**Fix Required:** Replace all instances of "AWS Bedrock" with "Amazon Bedrock" throughout the README.

---

### 2. Missing IAM Permissions Documentation

**Issue:** The README does not document the required IAM permissions needed to run the prerequisite scripts and deploy the infrastructure.

**Impact:** Users encounter multiple `AccessDeniedException` errors during setup, requiring trial-and-error to determine necessary permissions.

**Required Permissions (Discovered Through Testing):**

The following permissions are needed for successful deployment:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowS3VectorOperations",
            "Effect": "Allow",
            "Action": [
                "s3vectors:*"
            ],
            "Resource": "*"
        },
        {
            "Sid": "AllowSSMParameterOperations",
            "Effect": "Allow",
            "Action": [
                "ssm:PutParameter",
                "ssm:GetParameter",
                "ssm:GetParameters",
                "ssm:GetParametersByPath",
                "ssm:DeleteParameter",
                "ssm:DeleteParameters",
                "ssm:DescribeParameters",
                "ssm:AddTagsToResource"
            ],
            "Resource": "*"
        },
        {
            "Sid": "AllowDynamoDBOperations",
            "Effect": "Allow",
            "Action": [
                "dynamodb:DescribeTable",
                "dynamodb:CreateTable",
                "dynamodb:DeleteTable",
                "dynamodb:UpdateTable",
                "dynamodb:PutItem",
                "dynamodb:GetItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Query",
                "dynamodb:Scan",
                "dynamodb:BatchGetItem",
                "dynamodb:BatchWriteItem",
                "dynamodb:DescribeTimeToLive",
                "dynamodb:UpdateTimeToLive",
                "dynamodb:TagResource",
                "dynamodb:UntagResource",
                "dynamodb:ListTagsOfResource",
                "dynamodb:UpdateContinuousBackups",
                "dynamodb:DescribeContinuousBackups"
            ],
            "Resource": "*"
        },
        {
            "Sid": "AllowCognitoOperations",
            "Effect": "Allow",
            "Action": [
                "cognito-idp:CreateUserPool",
                "cognito-idp:DeleteUserPool",
                "cognito-idp:DescribeUserPool",
                "cognito-idp:UpdateUserPool",
                "cognito-idp:CreateUserPoolClient",
                "cognito-idp:DeleteUserPoolClient",
                "cognito-idp:DescribeUserPoolClient",
                "cognito-idp:UpdateUserPoolClient",
                "cognito-idp:CreateGroup",
                "cognito-idp:DeleteGroup",
                "cognito-idp:GetGroup",
                "cognito-idp:UpdateGroup",
                "cognito-idp:ListGroups",
                "cognito-idp:CreateResourceServer",
                "cognito-idp:DeleteResourceServer",
                "cognito-idp:DescribeResourceServer",
                "cognito-idp:UpdateResourceServer",
                "cognito-idp:SetUserPoolMfaConfig",
                "cognito-idp:TagResource",
                "cognito-idp:UntagResource",
                "cognito-idp:ListTagsForResource"
            ],
            "Resource": "*"
        }
    ]
}
```

**Note:** This list was determined through trial and error and may not be exhaustive. Additionally, users should consider adding `arn:aws:iam::aws:policy/AmazonBedrockFullAccess` managed policy for complete Amazon Bedrock access.

**Recommendation:** Add a "Prerequisites - IAM Permissions" section to the README documenting these requirements.

---

### 3. Missing AWS Region Configuration for EC2 Instances

**Issue:** When running on EC2 instances with IAM roles (where `aws configure` is not used), the shell scripts fail silently because `aws configure get region` returns empty.

**Affected Files:**
- `scripts/prereq.sh`
- `scripts/cleanup.sh`
- `scripts/list_ssm_parameters.sh`

**Error Symptom:** Scripts run but produce no output and fail silently.

**Root Cause:** The scripts use `REGION=$(aws configure get region)` which returns empty when the region is set via EC2 instance metadata (IMDS) rather than AWS config file.

**Fix Applied:**

Changed region detection in all three scripts from:
```bash
REGION=$(aws configure get region)
```

To:
```bash
REGION=$(aws configure get region || echo "${AWS_DEFAULT_REGION:-us-east-1}")
```

**Files and Line Numbers:**
- `scripts/prereq.sh` - Line 12
- `scripts/cleanup.sh` - Line 10
- `scripts/list_ssm_parameters.sh` - Line 7

**Workaround for Users:** Set the `AWS_DEFAULT_REGION` environment variable before running scripts:
```bash
export AWS_DEFAULT_REGION=us-east-1
```

---

### 4. Gateway Creation Script Missing Wait Logic

**Issue:** The `agentcore_gateway.py` script attempts to create a gateway target immediately after creating the gateway, without waiting for the gateway to reach a ready state. This causes a `ValidationException` error.

**Error:**
```
ValidationException: Cannot perform operation CreateGatewayTarget when gateway is in CREATING status
```

**Fix Applied:**

Added wait logic to `scripts/agentcore_gateway.py`:

1. **Line 7:** Added `import time`

2. **Lines 73-93:** Added gateway status polling loop:
```python
# Wait for gateway to become ACTIVE
gateway_id = create_response["gatewayId"]
click.echo(f"⏳ Waiting for gateway to become ACTIVE...")
max_retries = 30
retry_delay = 10

for attempt in range(max_retries):
    get_response = gateway_client.get_gateway(gatewayIdentifier=gateway_id)
    status = get_response.get("status")

    if status in ["ACTIVE", "READY"]:
        click.echo(f"✅ Gateway is now {status}")
        break
    elif status in ["FAILED", "DELETING", "DELETED"]:
        raise Exception(f"Gateway creation failed with status: {status}")

    if attempt < max_retries - 1:
        click.echo(f"   Gateway status: {status}, waiting {retry_delay}s... (attempt {attempt + 1}/{max_retries})")
        time.sleep(retry_delay)
    else:
        raise Exception(f"Gateway did not become ACTIVE after {max_retries * retry_delay} seconds")
```

This waits up to 5 minutes (30 retries × 10 seconds) for the gateway to reach ACTIVE or READY status before proceeding.

---

### 5. Recommendation: Migrate to `uv` Package Manager

**Issue:** The project currently uses `pip` and `requirements.txt` files, but the modern Python ecosystem and project guidelines recommend using `uv` with `pyproject.toml`. Additionally, the `prereq.sh` and `cleanup.sh` scripts call Python scripts using `python` directly instead of `uv run python`.

**Benefits:**
- Faster dependency resolution
- Better dependency locking
- Consistent with modern Python packaging standards
- Better handling of development vs. runtime dependencies

**Proposed Changes:**

**A. Shell Script Updates:**

Update `scripts/prereq.sh` and `scripts/cleanup.sh` to use `uv run python`:

**Affected Files:**
- `scripts/prereq.sh` - Line 100
- `scripts/cleanup.sh` - Line 62

Changed Python invocations from:
```bash
python prerequisite/knowledge_base.py --mode create
```

To:
```bash
uv run python prerequisite/knowledge_base.py --mode create
```

**B. Create pyproject.toml:**

Create a `pyproject.toml` file with the following content:

```toml
[project]
name = "customer-support-assistant"
version = "0.1.0"
description = "Customer support agent implementation using AWS Bedrock AgentCore framework"
requires-python = ">=3.10"
dependencies = [
    "bedrock-agentcore>=0.1.0",
    "bedrock-agentcore-starter-toolkit>=0.1.0",
    "boto3>=1.39.7",
    "botocore>=1.39.7",
    "click>=8.2.1",
    "fastmcp>=0.1.0",
    "google-api-python-client>=2.176.0",
    "google-auth>=2.40.3",
    "google-auth-httplib2>=0.2.0",
    "google-auth-oauthlib>=1.0.0",
    "opensearch-py>=3.0.0",
    "pandas>=2.3.1",
    "pydantic>=2.0.0",
    "pyyaml>=6.0.2",
    "requests>=2.31.0",
    "requests-aws4auth>=1.3.1",
    "retrying>=1.4.0",
    "strands-agents>=1.0.0",
    "strands-agents-tools>=0.2.0",
    "streamlit>=1.47.0",
    "streamlit-cookies-controller>=0.0.4",
]

[tool.uv]
dev-dependencies = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "flake8>=6.0.0",
    "mypy>=1.0.0",
    "pre-commit>=3.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["."]
```

**C. README Changes:**

Update all installation and execution commands in the README:

**Line 65-70:** Add `uv` installation instructions:
```markdown
5. **uv**: Modern Python package installer and resolver
   - [Install uv](https://github.com/astral-sh/uv)

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
```

**Line 80-81:** Change from:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r dev-requirements.txt
```

To:
```bash
# Install dependencies using uv
uv sync
```

**All `python` commands:** Prefix with `uv run`, for example:
- Line 96: `uv run python scripts/agentcore_gateway.py create --name customersupport-gw`
- Line 104: `uv run python scripts/cognito_credentials_provider.py create --name customersupport-gateways`
- Line 106: `uv run python test/test_gateway.py --prompt "Check warranty with serial number MNO33333333"`
- Line 114: `uv run python scripts/google_credentials_provider.py create --name customersupport-google-calendar`
- Line 116: `uv run python test/test_google_tool.py`
- Line 122: `uv run python scripts/agentcore_memory.py create --name customersupport`
- Line 124-126: All memory test commands
- Line 154: `uv run python test/test_agent.py customersupport<AgentName> -p "Hi"`
- Line 165: `uv run streamlit run app.py --server.port 8501 -- --agent=customersupport<AgentName>`
- Lines 187-188, 195-198, 206-207, 214-217, 225, 232-238, 246-247, 254-260, 269-275, 284-288: All script examples in the Scripts and Cleanup sections

---

## Proposed Solution

1. Replace "AWS Bedrock" with "Amazon Bedrock" throughout documentation
2. Create a comprehensive IAM permissions section in the README
3. Fix all shell scripts to handle EC2 IMDS region detection
4. Add wait logic to gateway creation script
5. Migrate to `uv` and `pyproject.toml` for better dependency management

## Testing

All fixes have been tested on an EC2 instance with IAM role-based credentials and confirmed working.
