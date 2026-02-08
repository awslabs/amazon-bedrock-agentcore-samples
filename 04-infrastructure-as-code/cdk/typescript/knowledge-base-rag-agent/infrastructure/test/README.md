# Test Suite

This directory contains a focused test suite for the Bedrock AgentCore Template infrastructure, designed for open-source contribution and AWS Labs submission.

## Philosophy

This test suite follows a **minimal but meaningful** approach:
- ✅ Test critical infrastructure components
- ✅ Validate request/response logic
- ✅ Keep tests fast and maintainable
- ❌ Avoid over-testing for a template project

## Test Structure

```
test/
├── unit/                    # Unit tests for Lambda logic
│   └── functions/
│       └── chat.test.ts    # Request validation and response building
├── stacks/                  # CDK stack synthesis tests
│   ├── api-stack.test.ts   # API stack class structure validation
│   └── bedrock-agent-stack.test.ts  # Bedrock resources synthesis tests
├── setup.ts                 # Global test configuration
└── README.md               # This file
```

## Running Tests

### All Tests (Fast)
```bash
npm run test --workspace=infrastructure
```

### With Coverage Report
```bash
npm run test:coverage --workspace=infrastructure
```

### Watch Mode (Development)
```bash
npm run test:watch --workspace=infrastructure
```

### Specific Test Suites
```bash
# Unit tests only
npm run test:unit --workspace=infrastructure

# Stack tests only
npm run test:stacks --workspace=infrastructure
```

## What We Test

### ✅ Unit Tests
- **Request Validation**: Ensures proper validation of chat requests
- **Response Building**: Validates response structure and CORS headers
- **Error Handling**: Tests error scenarios and edge cases

### ✅ Stack Tests
- **BedrockStack**: Full CDK synthesis tests for Bedrock Agent, Knowledge Base, S3, and SSM resources
- **ApiStack**: Class structure validation only (full synthesis skipped due to VPC/Cognito dependencies)

### ❌ What We Don't Test
- **Real AWS Integration**: Requires deployed resources (see manual testing below)
- **End-to-End Flows**: Better suited for manual testing
- **Complex Stack Dependencies**: Avoided for test speed and simplicity

## Manual Testing

For full integration testing with real AWS resources:

1. **Deploy the stack**:
   ```bash
   cd infrastructure
   npm run deploy
   ```

2. **Test the API endpoints**:
   ```bash
   # Health check
   curl https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/v1/api/health
   
   # Chat endpoint (requires authentication)
   curl -X POST https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/v1/api/chat/invoke \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR-TOKEN" \
     -d '{"message": "Hello", "sessionId": "test-123"}'
   ```

3. **Check CloudWatch Logs**:
   ```bash
   aws logs tail /aws/lambda/AgentCoreApi-Chat --follow
   ```

## Test Coverage

Current coverage targets are set to **50%** for:
- Statements
- Branches
- Functions
- Lines

This is appropriate for an open-source template project where:
- Infrastructure is defined declaratively (CDK)
- Full integration requires deployed AWS resources
- Focus is on demonstrating patterns, not exhaustive testing

## Adding New Tests

When adding new functionality:

1. **Add unit tests** for business logic in `test/unit/`
2. **Add stack tests** for new CDK resources in `test/stacks/`
3. **Keep tests simple** - focus on critical paths
4. **Document manual testing** for integration scenarios

## CI/CD Integration

Tests run automatically on:
- Pull requests
- Commits to main branch
- Pre-deployment validation

```bash
# Run all validation checks
npm run validate --workspace=infrastructure
```

This includes:
- Linting
- Type checking
- Tests
- Security scanning (cfn-nag)

## Troubleshooting

### Tests Timing Out
- ApiStack tests are simplified to avoid VPC/Cognito synthesis (which is slow)
- BedrockStack tests do full synthesis and may take 20-30 seconds
- If you need full ApiStack synthesis tests, create VPC/Cognito mocks and increase timeout in `jest.config.js`

### Coverage Threshold Failures
- Coverage is disabled by default for faster tests
- Run `npm run test:coverage` to check coverage
- Adjust thresholds in `jest.config.js` if needed

### Mock Issues
- AWS SDK mocks are configured in `setup.ts`
- Individual tests can override mocks as needed

## Resources

- [Jest Documentation](https://jestjs.io/)
- [AWS CDK Testing](https://docs.aws.amazon.com/cdk/v2/guide/testing.html)
- [AWS Lambda Testing Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/testing-functions.html)
