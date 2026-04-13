# AWS Agent Registry Kiro Power — Publisher Workflow

This Kiro Power enables the **publisher persona** to create, manage, and submit agent/MCP records to the AWS Agent Registry. 

**Publisher workflow assumes a registry already exists (created by an admin).**

---

## Prerequisites

### 1. AWS CLI installed

```bash
aws --version
# Expected: aws-cli/2.x.x ...
```

[Install AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html)

---

### 2. boto3 installed

```bash
pip install boto3
```

---

### 3. AWS Identity configured with publisher persona permissions

Your AWS identity needs permission to carry out registry operations. Use whichever method matches your setup:

Option A — named profile:
```bash
aws configure --profile <YOUR_PROFILE>
```

Option B — IAM user access keys (environment variables):
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=your_region
```

Option C — IAM role — credentials are picked up automatically 

Verify your identity resolves correctly:
```bash
aws sts get-caller-identity
# Expected: returns AccountId, Arn, UserId
```

---

### 4. Publisher persona policy

For carrying out AWS Agent Registry operations for publisher workflow, create an IAM role with the following policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "RegistryPublisherPermission",
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:ListRegistries",
        "bedrock-agentcore:GetRegistry",
        "bedrock-agentcore:CreateRegistryRecord",
        "bedrock-agentcore:ListRegistryRecords",
        "bedrock-agentcore:GetRegistryRecord",
        "bedrock-agentcore:DeleteRegistryRecord",
        "bedrock-agentcore:UpdateRegistryRecord",
        "bedrock-agentcore:SubmitRegistryRecordForApproval"
      ],
      "Resource": ["*"]
    }
  ]
}
```

> Note: Publishers cannot `CreateRegistry`, `DeleteRegistry`, or approve/reject records — those are admin-only operations.

---



## Next Steps

Once prerequisites are met, you are now ready to use **AWS Agent Registry** Kiro Power for the publisher workflow.

