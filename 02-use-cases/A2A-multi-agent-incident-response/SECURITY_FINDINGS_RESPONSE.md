# Security Findings Response

This document addresses security findings from static analysis tools (Bandit, detect-secrets, cfn-nag, Checkov).

---

## HIGH Severity Findings - REQUIRE FIXES

### Finding 1: B104 - Binding to all interfaces (monitoring_strands_agent/main.py)
**Status**: ✅ **VALID - REQUIRES FIX**
**Region**: `us-west-2`, `us-east-1`, `eu-west-1`

**Issue**:
```python
host, port = "0.0.0.0", 9000
```
Binding to `0.0.0.0` exposes the service on all network interfaces.

**Risk**:
- When running in Docker/container, this is accessible from outside the container
- In production, this could expose the service to the internet if not properly firewalled

**Recommended Fix**:
```python
# For local development only
host = os.environ.get("BIND_HOST", "127.0.0.1")
port = int(os.environ.get("BIND_PORT", "9000"))

# Or if must bind to all interfaces for container networking, document why:
# Binding to 0.0.0.0 is required for container inter-service communication
# Security is enforced via VPC security groups and network policies
host, port = "0.0.0.0", 9000
```

**Why binding to 0.0.0.0 may be needed**: When running in containers/ECS, the service needs to accept connections from other containers. However, this should be combined with proper network security (security groups, NACLs).

---

### Finding 2: B113 - Requests without timeout (test/connect_agent.py)
**Status**: ✅ **VALID - REQUIRES FIX**
**Region**: `us-west-2`, `us-east-1`, `eu-west-1`

**Issue**:
```python
response = requests.get(url, headers=headers)
```

**Risk**:
- Request can hang indefinitely
- Resource exhaustion if many requests hang
- Denial of Service vulnerability

**Recommended Fix**:
```python
# Add reasonable timeout
response = requests.get(url, headers=headers, timeout=30)
response.raise_for_status()
```

**Standard timeouts**:
- Connect timeout: 5-10 seconds
- Read timeout: 30-60 seconds
- Total: `timeout=(5, 30)` for (connect, read)

---

### Finding 3: B104 - Binding to all interfaces (web_search_openai_agents/main.py)
**Status**: ✅ **VALID - REQUIRES FIX**
**Region**: `us-west-2`, `us-east-1`, `eu-west-1`

Same as Finding 1. Apply the same fix.

---

### Findings 4-20: SECRET-SECRET-KEYWORD in CloudFormation YAML files
**Status**: ❌ **FALSE POSITIVE - NO ACTION REQUIRED**
**Region**: All regions

**Why False Positive**:
These are CloudFormation templates that reference Secrets Manager resources or use the word "secret" in variable names. The scanner is flagging keywords like:
- `ClientSecret` (CloudFormation resource name)
- `SecretArn` (ARN reference)
- `client_secret` (OAuth2 field name)
- `secretsmanager:GetSecretValue` (IAM action)

**Not actual secrets**: These are configuration files defining **where secrets are stored**, not the secrets themselves. The actual secret values are:
1. Stored in AWS Secrets Manager (encrypted)
2. Never in the YAML files
3. Retrieved at runtime with proper IAM permissions

**Suppression**: Add `.secrets.baseline` file to suppress these false positives:
```json
{
  "version": "1.4.0",
  "filters_used": [
    {
      "path": "detect_secrets.filters.allowlist.is_line_allowlist"
    }
  ],
  "results": {
    "cloudformation/cognito.yaml": [],
    "cloudformation/host_agent.yaml": [],
    "cloudformation/monitoring_agent.yaml": [],
    "cloudformation/web_search_agent.yaml": []
  }
}
```

---

## MEDIUM Severity Findings - OPTIONAL/CONTEXT-DEPENDENT

### Findings 21-22, 32-35, 43-48, 54-57: Lambda VPC and Concurrency
**Status**: ⚠️ **VALID BUT OPTIONAL**
**Region**: `us-west-2`, `us-east-1`, `eu-west-1`

**CFN_NAG_W89**: Lambda functions should be deployed inside a VPC
**CFN_NAG_W92**: Lambda functions should define ReservedConcurrentExecutions

**Context-Dependent Decision**:

**When VPC is NOT needed** (Current use case):
- Lambda only accesses AWS services (Bedrock, SSM, Secrets Manager, CodeBuild)
- AWS services are accessible via AWS PrivateLink from outside VPC
- No database or private resources in VPC
- ✅ **No action needed**

**When VPC IS needed**:
- Lambda needs to access RDS database in VPC
- Lambda needs to access resources in private subnets
- Compliance requirement for VPC isolation

**Reserved Concurrency**:
- Only needed if you want to prevent Lambda from consuming all account concurrency
- Useful for cost control or protecting downstream systems
- For this use case: ⚠️ **Consider adding for cost control**

**Recommended addition** (if desired):
```yaml
ReservedConcurrentExecutions: 10  # Limit concurrent executions
```

---

### Findings 23-26: Secrets Manager KMS Key
**Status**: ⚠️ **VALID BUT OPTIONAL**
**Region**: `us-west-2`, `us-east-1`, `eu-west-1`

**CFN_NAG_W77**: Secrets Manager Secret should explicitly specify KmsKeyId

**Current**: Uses AWS managed key `aws/secretsmanager`
**Recommended**: Use customer-managed KMS key for:
- Full control over key rotation
- Cross-account secret sharing
- Key policy for additional access controls
- CloudTrail logging of key usage

**Fix** (if enhanced security needed):
```yaml
Resources:
  SecretsKMSKey:
    Type: AWS::KMS::Key
    Properties:
      Description: KMS key for Secrets Manager
      KeyPolicy:
        Version: '2012-10-17'
        Statement:
          - Sid: Enable IAM User Permissions
            Effect: Allow
            Principal:
              AWS: !Sub 'arn:aws:iam::${AWS::AccountId}:root'
            Action: 'kms:*'
            Resource: '*'
          - Sid: Allow Secrets Manager
            Effect: Allow
            Principal:
              Service: secretsmanager.amazonaws.com
            Action:
              - 'kms:Decrypt'
              - 'kms:GenerateDataKey'
            Resource: '*'

  MonitorAgentClientSecret:
    Type: AWS::SecretsManager::Secret
    Properties:
      KmsKeyId: !Ref SecretsKMSKey  # Add this
```

**Decision**: ⚠️ **Add if you need cross-account access or enhanced audit**

---

### Findings 27, 36, 49: CodeBuild Encryption
**Status**: ⚠️ **VALID - RECOMMENDED FIX**
**Region**: `us-west-2`, `us-east-1`, `eu-west-1`

**CFN_NAG_W32**: CodeBuild project should specify an EncryptionKey value

**Current**: Uses AWS managed key
**Recommended**: Add customer-managed KMS key

**Fix**:
```yaml
AgentDockerBuildProject:
  Type: AWS::CodeBuild::Project
  Properties:
    EncryptionKey: !GetAtt CodeBuildKMSKey.Arn  # Add this
    # ... rest of config

CodeBuildKMSKey:
  Type: AWS::KMS::Key
  Properties:
    Description: KMS key for CodeBuild encryption
    KeyPolicy:
      Version: '2012-10-17'
      Statement:
        - Sid: Enable IAM User Permissions
          Effect: Allow
          Principal:
            AWS: !Sub 'arn:aws:iam::${AWS::AccountId}:root'
          Action: 'kms:*'
          Resource: '*'
        - Sid: Allow CodeBuild
          Effect: Allow
          Principal:
            Service: codebuild.amazonaws.com
          Action:
            - 'kms:Decrypt'
            - 'kms:DescribeKey'
            - 'kms:Encrypt'
            - 'kms:GenerateDataKey'
            - 'kms:ReEncrypt*'
          Resource: '*'
```

---

### Findings 28-31, 37-42, 50-53: IAM Wildcard Resources
**Status**: ✅ **VALID - REQUIRES REVIEW AND SCOPING**
**Region**: `us-west-2`, `us-east-1`, `eu-west-1`

**CFN_NAG_W11**: IAM role should not allow * resource on its permissions policy

**Locations requiring scoping**:
1. `ecr:GetAuthorizationToken` - Must be `*` (AWS requirement)
2. `xray:*` - Can be scoped to traces in account
3. `cloudwatch:PutMetricData` - Already has namespace condition ✅
4. `bedrock-agentcore:GetResourceOauth2Token` - Should scope to credential providers
5. `secretsmanager:GetSecretValue` - Should scope to specific secrets

**Fixes**:

```yaml
# REQUIRED: GetAuthorizationToken must be * (AWS API limitation)
- Sid: ECRTokenAccess
  Effect: Allow
  Action:
    - ecr:GetAuthorizationToken
  Resource: '*'  # Cannot be scoped - AWS requirement

# RECOMMENDED: Scope XRay
- Effect: Allow
  Action:
    - xray:PutTraceSegments
    - xray:PutTelemetryRecords
    - xray:GetSamplingRules
    - xray:GetSamplingTargets
  Resource:
    - !Sub 'arn:aws:xray:${AWS::Region}:${AWS::AccountId}:*'

# REQUIRED: Scope OAuth2
- Sid: Oauth2Token
  Effect: Allow
  Action:
    - bedrock-agentcore:GetResourceOauth2Token
  Resource:
    - !Sub 'arn:aws:bedrock-agentcore:${AWS::Region}:${AWS::AccountId}:oauth2-credential-provider/*'

# REQUIRED: Scope Secrets Manager
- Sid: SecretsManager
  Effect: Allow
  Action:
    - secretsmanager:GetSecretValue
  Resource:
    - Fn::ImportValue: !Sub '${CognitoStackName}-HostAgentClientSecretArn'
    - Fn::ImportValue: !Sub '${CognitoStackName}-MonitorAgentClientSecretArn'
    - Fn::ImportValue: !Sub '${CognitoStackName}-WebSearchAgentClientSecretArn'
```

---

### Finding 58: IAM Data Exfiltration (CKV_AWS_108)
**Status**: ✅ **VALID - REQUIRES FIX**
**Region**: `us-west-2`, `us-east-1`, `eu-west-1`

**Issue**: Same as discussed earlier - overly broad SSM and Secrets Manager access

**Fix**: Already covered in findings 28-31 above. Scope down to specific parameters/secrets needed.

---

### Finding 59: ECR KMS Encryption (CKV_AWS_136)
**Status**: ⚠️ **VALID - RECOMMENDED FIX**
**Region**: `us-west-2`, `us-east-1`, `eu-west-1`

**Issue**: ECR repository not using KMS encryption

**Current**: Uses AES-256 (AWS managed encryption)
**Recommended**: Use KMS for enhanced control

**Fix**:
```yaml
AgentECRRepository:
  Type: AWS::ECR::Repository
  Properties:
    EncryptionConfiguration:
      EncryptionType: KMS
      KmsKey: !GetAtt ECRKMSKey.Arn
    # ... rest of config

ECRKMSKey:
  Type: AWS::KMS::Key
  Properties:
    Description: KMS key for ECR repository encryption
    KeyPolicy:
      Version: '2012-10-17'
      Statement:
        - Sid: Enable IAM User Permissions
          Effect: Allow
          Principal:
            AWS: !Sub 'arn:aws:iam::${AWS::AccountId}:root'
          Action: 'kms:*'
          Resource: '*'
        - Sid: Allow ECR
          Effect: Allow
          Principal:
            Service: ecr.amazonaws.com
          Action:
            - 'kms:Decrypt'
            - 'kms:DescribeKey'
            - 'kms:Encrypt'
            - 'kms:GenerateDataKey'
            - 'kms:ReEncrypt*'
          Resource: '*'
```

---

### Finding 60: ECR Image Tag Immutability (CKV_AWS_51)
**Status**: ⚠️ **VALID - OPTIONAL**
**Region**: `us-west-2`, `us-east-1`, `eu-west-1`

**Issue**: ECR tags are mutable (can be overwritten)

**Immutability benefits**:
- Prevents accidental tag overwrites
- Better for production environments
- Image tags are permanent references

**Immutability drawbacks**:
- Cannot reuse tags (e.g., "latest")
- More images retained
- Need unique tags per build

**Fix** (if desired):
```yaml
AgentECRRepository:
  Type: AWS::ECR::Repository
  Properties:
    ImageTagMutability: IMMUTABLE  # Add this
```

**Decision**: For CI/CD with build numbers, immutability is recommended. ⚠️ **Consider enabling**

---

### Finding 61: IAM Write Access Without Constraints (CKV_AWS_111)
**Status**: ✅ **VALID - REQUIRES REVIEW**
**Region**: `us-west-2`, `us-east-1`, `eu-west-1`

**Issue**: CodeBuild role has write permissions without conditions

**Review needed**: Check if CodeBuildServiceRole has unconstrained write access to:
- S3 buckets
- DynamoDB tables
- Other AWS resources

**Best practice**: Add conditions limiting write operations:
```yaml
- Effect: Allow
  Action:
    - s3:PutObject
  Resource:
    - !Sub 'arn:aws:s3:::${ArtifactBucket}/*'
  Condition:
    StringEquals:
      's3:x-amz-server-side-encryption': 'AES256'
```

---

## Summary Table

| Finding | Severity | Action Required | Regions Affected |
|---------|----------|----------------|------------------|
| 1, 3: Bind to 0.0.0.0 | HIGH | ✅ Fix or document | us-west-2, us-east-1, eu-west-1 |
| 2: No request timeout | HIGH | ✅ Fix | us-west-2, us-east-1, eu-west-1 |
| 4-20: Secret keywords | HIGH | ❌ False positive | All |
| 21-57: Lambda VPC/Concurrency | MEDIUM | ⚠️ Optional | us-west-2, us-east-1, eu-west-1 |
| 23-26: Secrets KMS | MEDIUM | ⚠️ Recommended | us-west-2, us-east-1, eu-west-1 |
| 27, 36, 49: CodeBuild encryption | MEDIUM | ⚠️ Recommended | us-west-2, us-east-1, eu-west-1 |
| 28-42, 50-58: IAM wildcards | MEDIUM | ✅ Fix | us-west-2, us-east-1, eu-west-1 |
| 59: ECR KMS | HIGH | ⚠️ Recommended | us-west-2, us-east-1, eu-west-1 |
| 60: ECR immutability | HIGH | ⚠️ Optional | us-west-2, us-east-1, eu-west-1 |
| 61: IAM write constraints | HIGH | ✅ Review | us-west-2, us-east-1, eu-west-1 |

---

## Priority Fixes

### Must Fix (High Impact, Security Risk)
1. ✅ Add request timeouts (Finding 2)
2. ✅ Scope down IAM policies (Findings 28-42, 50-58)
3. ✅ Review/document 0.0.0.0 binding (Findings 1, 3)

### Should Fix (Best Practice, Compliance)
4. ⚠️ Add KMS encryption for ECR (Finding 59)
5. ⚠️ Add KMS encryption for CodeBuild (Findings 27, 36, 49)
6. ⚠️ Add KMS keys for Secrets Manager (Findings 23-26)

### Optional (Defense in Depth)
7. ⚠️ Enable ECR image immutability (Finding 60)
8. ⚠️ Add Lambda reserved concurrency (Findings 22, 34, 35, 46-48, 56-57)
9. ⚠️ Deploy Lambda in VPC if needed (Findings 21, 32-33, 43-45, 54-55)

---

## Suppression File for False Positives

Create `.secrets.baseline`:
```json
{
  "version": "1.4.0",
  "filters_used": [
    {
      "path": "detect_secrets.filters.allowlist.is_line_allowlist"
    }
  ],
  "results": {
    "cloudformation/cognito.yaml": [
      {"line_number": 71, "type": "Secret Keyword"},
      {"line_number": 259, "type": "Secret Keyword"},
      {"line_number": 260, "type": "Secret Keyword"},
      {"line_number": 318, "type": "Secret Keyword"},
      {"line_number": 327, "type": "Secret Keyword"}
    ],
    "cloudformation/host_agent.yaml": [
      {"line_number": 112, "type": "Secret Keyword"},
      {"line_number": 512, "type": "Secret Keyword"},
      {"line_number": 513, "type": "Secret Keyword"},
      {"line_number": 595, "type": "Secret Keyword"}
    ],
    "cloudformation/monitoring_agent.yaml": [
      {"line_number": 123, "type": "Secret Keyword"},
      {"line_number": 547, "type": "Secret Keyword"},
      {"line_number": 548, "type": "Secret Keyword"},
      {"line_number": 630, "type": "Secret Keyword"}
    ],
    "cloudformation/web_search_agent.yaml": [
      {"line_number": 121, "type": "Secret Keyword"},
      {"line_number": 539, "type": "Secret Keyword"},
      {"line_number": 540, "type": "Secret Keyword"},
      {"line_number": 622, "type": "Secret Keyword"}
    ]
  }
}
```
