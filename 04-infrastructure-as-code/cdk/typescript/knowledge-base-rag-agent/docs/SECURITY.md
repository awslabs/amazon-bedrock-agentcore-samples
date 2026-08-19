# Security

## Security Features Implemented

This Bedrock AgentCore Template implements comprehensive security controls following AWS best practices and the Well-Architected Framework security pillar.

### 🔐 Authentication & Authorization
- **AWS Cognito User Pool** - Secure user authentication with email verification
- **Enhanced Password Policy** - 12-character minimum with complexity requirements
- **Advanced Security Mode** - Account lockout and risk-based authentication
- **API Gateway Authorizers** - JWT token validation for protected endpoints
- **IAM Least Privilege** - All roles scoped to minimum required permissions

### 🔒 Data Protection
- **Encryption at Rest** - S3, OpenSearch Serverless, and DynamoDB encrypted by default
- **Encryption in Transit** - HTTPS/TLS 1.2+ enforced everywhere
- **Short-lived Tokens** - 1-hour access tokens with refresh capability
- **Input Sanitization** - PII detection and masking in logs
- **No Hardcoded Secrets** - All credentials managed by AWS services

### 🛡️ Network Security
- **CloudFront OAC** - Modern origin access control (not deprecated OAI)
- **S3 Public Access Blocked** - All buckets secured with proper access policies
- **CORS Configuration** - Properly configured cross-origin resource sharing
- **Rate Limiting** - API Gateway throttling (100 req/sec, 200 burst)

### 📊 Monitoring & Compliance
- **CloudWatch Logging** - Comprehensive audit trails without sensitive data
- **Session Tracking** - User-scoped session management with DynamoDB
- **Resource-Level Authorization** - Users can only access their own data
- **Audit-Ready** - All security events logged for compliance

## Quick Security Validation

After deployment, validate that security controls are working properly:

### 1. Verify S3 Bucket Security
```bash
# Get bucket name from CloudFormation outputs
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name AgentCoreOpenSearchStack \
  --query 'Stacks[0].Outputs[?OutputKey==`KnowledgeBaseBucketName`].OutputValue' \
  --output text)

# Verify public access is blocked
aws s3api get-public-access-block --bucket $BUCKET_NAME

# Verify encryption is enabled
aws s3api get-bucket-encryption --bucket $BUCKET_NAME
```

### 2. Test API Authentication
```bash
# Get API endpoint
API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name AgentCoreApiStack \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
  --output text)

# Test unauthenticated access (should return 401/403)
curl -X POST $API_ENDPOINT/chat/invoke \
  -H "Content-Type: application/json" \
  -d '{"message":"test"}'

# Health check should work without auth
curl $API_ENDPOINT/health
```

### 3. Verify HTTPS Enforcement
```bash
# Get CloudFront domain
CLOUDFRONT_DOMAIN=$(aws cloudformation describe-stacks \
  --stack-name AgentCoreWebConsoleStack \
  --query 'Stacks[0].Outputs[?OutputKey==`WebsiteUrl`].OutputValue' \
  --output text)

# Test HTTP redirect (should redirect to HTTPS)
curl -I ${CLOUDFRONT_DOMAIN/https:/http:}
```

### 4. Check Cognito Password Policy
```bash
# Get User Pool ID
USER_POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name AgentCoreCognitoStack \
  --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
  --output text)

# Verify password policy (should show 12-character minimum)
aws cognito-idp describe-user-pool --user-pool-id $USER_POOL_ID \
  --query 'UserPool.Policies.PasswordPolicy'
```

## Production Hardening

For production deployments, consider implementing these additional security measures:

### 🔒 Enhanced Access Control
- **Multi-Factor Authentication (MFA)** - Enable MFA for all Cognito users
- **IP Allowlisting** - Restrict admin access to specific IP ranges
- **VPC Integration** - Deploy Lambda functions in private subnets
- **VPC Endpoints** - Use VPC endpoints for AWS service communication

### 🛡️ Advanced Threat Protection
- **AWS WAF** - Add Web Application Firewall to CloudFront and API Gateway
- **AWS GuardDuty** - Enable threat detection and monitoring
- **AWS Security Hub** - Centralized security findings and compliance
- **AWS Config** - Monitor configuration compliance

### 🔐 Enhanced Data Protection
- **Customer-Managed KMS Keys** - Use your own encryption keys for sensitive data
- **AWS Secrets Manager** - Migrate sensitive configuration to Secrets Manager
- **S3 Versioning** - Enable versioning for data recovery
- **Cross-Region Backup** - Implement disaster recovery procedures

### 📊 Advanced Monitoring
- **CloudWatch Alarms** - Set up alerts for security events
- **AWS CloudTrail Insights** - Detect unusual API activity patterns
- **Custom Metrics** - Monitor business-specific security metrics
- **Automated Response** - Use Lambda for automated incident response

### 🏢 Compliance & Governance
- **AWS Organizations** - Use Service Control Policies (SCPs) for account governance
- **AWS Audit Manager** - Automate compliance evidence collection
- **Resource Tagging** - Implement comprehensive tagging strategy
- **Cost Allocation** - Monitor security-related costs

## Compliance

This template implements security controls that align with major compliance frameworks:

- **SOC 2 Type II** - Logical access controls, encryption, monitoring
- **ISO 27001** - Information security management system controls
- **NIST Cybersecurity Framework** - Identify, Protect, Detect, Respond, Recover
- **GDPR/CCPA** - Data protection and privacy controls (PII sanitization)

All AWS services used are covered by AWS compliance programs including SOC, ISO, PCI DSS, HIPAA, and FedRAMP.

## Security Resources

### AWS Security Documentation
- [AWS Well-Architected Security Pillar](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/)
- [Amazon Bedrock Security](https://docs.aws.amazon.com/bedrock/latest/userguide/security.html)
- [AWS Cognito Security Best Practices](https://docs.aws.amazon.com/cognito/latest/developerguide/security.html)
- [IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)

### Security Tools
- [AWS Security Hub](https://aws.amazon.com/security-hub/) - Centralized security findings
- [AWS GuardDuty](https://aws.amazon.com/guardduty/) - Threat detection
- [AWS Config](https://aws.amazon.com/config/) - Configuration compliance
- [AWS CloudTrail](https://aws.amazon.com/cloudtrail/) - API activity logging

---

**Note:** This template provides a secure foundation following AWS best practices. For production use, review the "Production Hardening" section and implement additional controls based on your specific security requirements and compliance needs.
