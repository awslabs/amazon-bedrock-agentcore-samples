# Troubleshooting Guide

## Overview

This guide provides solutions to common issues encountered when running the Simple Dual Observability Tutorial.

## Common Misunderstandings

### Agent Code Cannot Run Locally

**Problem**:
```
ModuleNotFoundError: No module named 'strands'
```

When trying to run the agent code directly:
```bash
python agent/weather_time_agent.py --help  # This will NOT work
uv run python agent/weather_time_agent.py  # This will NOT work
```

**Explanation**:
The `agent/weather_time_agent.py` file is **not meant to run locally**. It's containerized and deployed to Amazon Bedrock AgentCore Runtime, where:
- All dependencies (including `strands-agents`) are pre-installed in the Docker image
- Automatic OpenTelemetry instrumentation is applied by the runtime
- The agent executes with full instrumentation and tool access

**Correct Way to Use the Agent**:

**Option 1: Test the deployed agent** (recommended)
```bash
# Run predefined tests
scripts/tests/test_agent.sh --test weather
scripts/tests/test_agent.sh --test calculator
scripts/tests/test_agent.sh --test combined

# Test with custom prompt
scripts/tests/test_agent.sh --prompt "Calculate the factorial of -5"

# Interactive mode
scripts/tests/test_agent.sh --interactive
```

**Option 2: Run the observability demo**
```bash
# Run all observability scenarios
python simple_observability.py --scenario all

# Or specific scenarios
python simple_observability.py --scenario success
python simple_observability.py --scenario error
```

**How It Works**:
1. You deploy the agent using `scripts/deploy_agent.sh`
2. Your test script invokes the deployed agent on AgentCore Runtime (via API)
3. The runtime automatically instruments it with OpenTelemetry
4. Results are collected by CloudWatch and/or Braintrust

The agent code is never executed locally - only the test scripts and deployment tools run on your laptop.

## Agent Invocation Errors

### Agent Not Found Error

**Error Message**:
```
ClientError: An error occurred (ResourceNotFoundException) when calling the InvokeAgent operation:
Agent with ID 'abc123xyz' not found
```

**Causes**:
1. Agent ID is incorrect
2. Agent not deployed to AgentCore Runtime
3. Wrong AWS region specified
4. Agent was deleted

**Solutions**:

```bash
# 1. List all agents in region
aws bedrock-agentcore list-agents --region us-east-1

# 2. Verify agent exists
aws bedrock-agentcore describe-agent \
  --agent-id $AGENTCORE_AGENT_ID \
  --region $AWS_REGION

# 3. Check region matches
echo $AWS_REGION  # Should match agent deployment region

# 4. Redeploy agent if needed
cd scripts
./deploy_agent.sh --region us-east-1
```

### Permission Denied Error

**Error Message**:
```
ClientError: An error occurred (AccessDeniedException) when calling the InvokeAgent operation:
User is not authorized to perform: bedrock-agentcore-runtime:InvokeAgent
```

**Causes**:
1. Missing IAM permissions
2. Wrong IAM role assumed
3. AWS credentials not configured

**Solutions**:

```bash
# 1. Verify AWS credentials
aws sts get-caller-identity

# 2. Check IAM permissions
aws iam get-user-policy \
  --user-name your-username \
  --policy-name your-policy

# 3. Add required permissions
# Attach policy with these permissions:
# - bedrock-agentcore-runtime:InvokeAgent
# - bedrock-agentcore:DescribeAgent
# - bedrock:InvokeModel

# 4. Verify Bedrock access
aws bedrock list-foundation-models --region $AWS_REGION
```

### Agent Timeout Error

**Error Message**:
```
ClientError: An error occurred (TimeoutException) when calling the InvokeAgent operation:
Agent invocation timed out
```

**Causes**:
1. Agent processing taking too long
2. Tool execution timeout
3. Network latency issues
4. Model throttling

**Solutions**:

```bash
# 1. Increase timeout in client code
# Edit simple_observability.py:
client._client_config.read_timeout = 300  # 5 minutes

# 2. Check tool execution times in logs
aws logs tail /aws/agentcore/observability --follow

# 3. Verify model quotas
aws bedrock get-model-invocation-metrics \
  --model-id us.anthropic.claude-haiku-4-5-20251001-v1:0 \
  --region $AWS_REGION

# 4. Request quota increase if needed
# Navigate to Service Quotas console
```

## Tool Execution Failures

### Tool Not Available Error

**Error Message**:
```
ToolExecutionError: Tool 'get_weather' not found in gateway
```

**Causes**:
1. MCP tools not configured in agent
2. Tool server not accessible
3. Tool name mismatch
4. Tool authentication failure

**Solutions**:

```bash
# 1. Verify agent configuration
aws bedrock-agentcore describe-agent \
  --agent-id $AGENTCORE_AGENT_ID \
  --region $AWS_REGION

# 2. Check tool implementation
ls -la tools/*.py

# 3. Redeploy agent with correct tool configuration
cd scripts
./deploy_agent.sh

# 4. Test tool execution directly
python -c "from tools import get_weather; print(get_weather('Paris'))"
```

### Tool Returns Error

**Error Message**:
```
ToolExecutionError: Calculator tool failed: Cannot calculate factorial of negative number
```

**Causes**:
1. Invalid tool input
2. Tool logic error
3. Tool dependency failure

**Expected Behavior**:
- This is normal for Scenario 2 (error handling demo)
- Agent should handle error gracefully
- Error should appear in traces with proper status

**Solutions**:

```bash
# 1. Verify this is Scenario 2 (expected error)
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario error

# 2. Check tool implementation
cat tools/calculator_tool.py

# 3. View error in logs
# CloudWatch Logs: Error message should be in runtime-logs
# Braintrust: Error annotation should be visible

# 4. Test tool directly
python -c "from tools import calculator; print(calculator('factorial', -5, None))"
```

## Logs and Metrics Issues

### Logs Not Appearing in CloudWatch

**Problem**: CloudWatch Logs show no entries after running the agent

**Causes**:
1. Agent not deployed
2. Log group doesn't exist
3. IAM permissions missing
4. Agent execution failed

**Solutions**:

```bash
# 1. Verify agent exists and is deployed
aws bedrock-agentcore describe-agent \
  --agent-id $AGENTCORE_AGENT_ID \
  --region $AWS_REGION

# 2. Check that log group exists
aws logs describe-log-groups --region $AWS_REGION | grep bedrock-agentcore

# 3. View recent log streams
aws logs describe-log-streams \
  --log-group-name /aws/bedrock-agentcore/runtimes/<agent-id>-DEFAULT \
  --region $AWS_REGION

# 4. Tail logs in real-time
aws logs tail /aws/bedrock-agentcore/runtimes/<agent-id>-DEFAULT --follow --region $AWS_REGION

# 5. Run test to generate logs
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario success
```

### Observability Configuration

**Understanding CloudWatch Logs Streams**:

When Braintrust is **NOT configured**:
- CloudWatch receives both runtime-logs and structured OTEL data
- Full operational visibility available in logs
- Good for debugging and development

When Braintrust **IS configured** (BRAINTRUST_API_KEY set):
- CloudWatch receives application logs (runtime-logs stream)
- Detailed OTEL data goes to Braintrust instead
- CloudWatch Logs still show agent activity and status
- This is expected behavior to avoid duplicate log storage

**Verification**:

```bash
# 1. Check that CloudWatch Logs are being written
aws logs tail /aws/bedrock-agentcore/runtimes/<agent-id>-DEFAULT --since 5m

# Expected output:
# [runtime-logs] Agent invoked with prompt: ...
# [runtime-logs] Agent initialized with tools: ...
# [runtime-logs] Agent invocation completed successfully

# 2. Verify agent execution completed
aws logs filter-log-events \
  --log-group-name /aws/bedrock-agentcore/runtimes/<agent-id>-DEFAULT \
  --filter-pattern "completed" \
  --region $AWS_REGION

# 3. If using Braintrust, verify traces are in Braintrust dashboard
# Navigate to https://www.braintrust.dev/app and check your project
# Traces should appear within 1-2 minutes of running the agent
```

### Traces Not Appearing in Braintrust

**Problem**: No traces in Braintrust dashboard

**Causes**:
1. Invalid Braintrust API key
2. BRAINTRUST_API_KEY environment variable not set
3. Network connectivity issues
4. Project name mismatch

**Solutions**:

```bash
# 1. Verify API key is set
echo "BRAINTRUST_API_KEY: $BRAINTRUST_API_KEY"

# 2. Verify API key is valid
curl -H "Authorization: Bearer $BRAINTRUST_API_KEY" \
  https://api.braintrust.dev/v1/auth/verify

# 3. Test connectivity to Braintrust OTEL endpoint
curl -I https://api.braintrust.dev/otel/v1/traces

# 4. Verify project exists
# Navigate to https://www.braintrust.dev/app
# Check project: agentcore-observability-demo exists

# 5. Check agent logs for telemetry initialization
uv run python -m weather_time_agent 2>&1 | grep -i "telemetry\|braintrust\|initialized"

# 6. For deployed agents, verify BRAINTRUST_API_KEY is in environment
aws bedrock-agentcore get-agent --agent-id $AGENT_ID --region $AWS_REGION | jq '.agent.envVars'
```

### Incomplete Traces

**Problem**: Traces missing spans or showing partial data

**Causes**:
1. Agent timeout during execution
2. Batch processor not flushing spans
3. Span attribute size limits exceeded
4. Network interruption during export

**Solutions**:

```bash
# 1. Check agent execution completed
aws logs filter-log-events \
  --log-group-name /aws/agentcore/observability \
  --filter-pattern '"COMPLETED"' \
  --region $AWS_REGION

# 2. Force span flush by checking logs
# The agent automatically flushes spans on completion
# Check for "Strands telemetry initialized successfully" in logs

# 3. Check for dropped spans in CloudWatch
aws logs filter-log-events \
  --log-group-name /aws/agentcore/observability \
  --filter-pattern '"dropped_spans"' \
  --region $AWS_REGION

# 4. Reduce span attribute size
# Attributes should be < 1000 characters
# Check agent code for large attributes in logger statements
# Use logging.basicConfig to limit message size

# 5. Increase agent timeout if spans are missing due to premature termination
# Update agent configuration in AgentCore console
```

## Performance Problems

### High Latency

**Problem**: Agent responses taking longer than expected

**Causes**:
1. Model selection (larger models slower)
2. Complex tool execution
3. Network latency
4. Cold start delays

**Solutions**:

```bash
# 1. Check logs to identify bottleneck
# Review CloudWatch Logs for timing messages
# Look for operations taking longest time

# 2. Use faster model
# Edit agent/weather_time_agent.py:
# model_id = "us.anthropic.claude-haiku-4-5-20251001-v1:0"  # Fast
# vs
# model_id = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"  # Slower but better

# 3. Optimize tool execution
# Review tools/*.py for slow operations

# 4. Enable caching
# Add response caching to reduce repeated calls

# 5. Monitor latency over time
aws cloudwatch get-metric-statistics \
  --namespace AgentCore/Observability \
  --metric-name Latency \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,p99 \
  --region $AWS_REGION
```

### High Token Usage

**Problem**: Token consumption higher than expected

**Causes**:
1. Verbose system prompts
2. Large tool descriptions
3. Long conversation history
4. Inefficient tool calling

**Solutions**:

```bash
# 1. Review token usage in Braintrust
# Dashboard > Traces > Select trace > View token breakdown

# 2. Optimize system prompt
# Edit agent/weather_time_agent.py:
# Keep system_prompt concise

# 3. Reduce tool schema verbosity
# Simplify tool descriptions in TOOL_SCHEMAS

# 4. Monitor token trends
# Braintrust Dashboard > Metrics > Token Usage Over Time

# 5. Set token limits
# Edit agent invocation:
# inferenceConfig:
#   maxTokens: 1024  # Reduce from 2048 if appropriate
```

### High Costs

**Problem**: AWS/LLM costs higher than expected

**Causes**:
1. High invocation rate
2. Expensive model selected
3. Large token consumption
4. Long CloudWatch retention

**Solutions**:

```bash
# 1. Review cost breakdown in Braintrust
# Dashboard > Costs > View by model/operation

# 2. Use cheaper model
# Haiku is 10x cheaper than Sonnet

# 3. Reduce CloudWatch retention
aws logs put-retention-policy \
  --log-group-name /aws/agentcore/observability \
  --retention-in-days 1 \
  --region $AWS_REGION

# 4. Adjust CloudWatch log retention
aws logs put-retention-policy \
  --log-group-name /aws/agentcore/observability \
  --retention-in-days 7 \
  --region $AWS_REGION

# 5. Enable AWS Cost Explorer
# Monitor daily spend on Bedrock and CloudWatch
```

## Environment Issues

### Python Dependencies

**Problem**: Import errors or missing modules

**Causes**:
1. Dependencies not installed
2. Wrong Python version
3. Virtual environment not activated

**Solutions**:

```bash
# 1. Verify Python version
python --version  # Should be 3.11+

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Install/reinstall dependencies
uv pip install boto3 botocore

# 4. Verify imports work
python -c "import boto3; print(boto3.__version__)"

# 5. Clean and reinstall if needed
rm -rf .venv
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
```

### Environment Variables Not Set

**Problem**: Script fails with missing environment variable errors

**Causes**:
1. .env file not loaded
2. Variables not exported
3. Wrong variable names

**Solutions**:

```bash
# 1. Check if variables are set
echo $AGENTCORE_AGENT_ID
echo $AWS_REGION
echo $BRAINTRUST_API_KEY

# 2. Load .env file
source .env  # or
source scripts/.env

# 3. Manually export if needed
export AGENTCORE_AGENT_ID=abc123xyz
export AWS_REGION=us-east-1
export BRAINTRUST_API_KEY=bt-xxxxx

# 4. Verify with
env | grep AGENTCORE
```

### AWS Region Mismatch

**Problem**: Resources not found despite correct IDs

**Causes**:
1. Agent deployed in different region
2. AWS_REGION not set correctly
3. Multiple regions configured

**Solutions**:

```bash
# 1. Check current region
echo $AWS_REGION
aws configure get region

# 2. Verify agent region
aws bedrock-agentcore describe-agent \
  --agent-id $AGENTCORE_AGENT_ID \
  --region us-east-1

# 3. Ensure consistency
export AWS_REGION=us-east-1  # Match agent deployment region

# 4. Update all scripts to use same region
```

## Script Failures

### Setup Script Fails

**Problem**: `./setup_all.sh` exits with error

**Causes**:
1. Missing prerequisites
2. Invalid AWS credentials
3. Insufficient permissions
4. Network issues

**Solutions**:

```bash
# 1. Run prerequisites check
cd scripts
./check_prerequisites.sh

# 2. Run setup steps individually
./deploy_agent.sh
./setup_cloudwatch.sh
./setup_braintrust.sh

# 3. Check logs for specific error
# Review script output for error messages

# 4. Enable debug mode
bash -x ./setup_all.sh
```

### Demo Script Fails

**Problem**: `simple_observability.py` exits with error

**Causes**:
1. Agent ID not set
2. Agent not deployed
3. Network issues
4. Invalid arguments

**Solutions**:

```bash
# 1. Run with debug logging
python simple_observability.py \
  --agent-id $AGENTCORE_AGENT_ID \
  --scenario success \
  --debug

# 2. Verify agent ID
aws bedrock-agentcore describe-agent \
  --agent-id $AGENTCORE_AGENT_ID \
  --region $AWS_REGION

# 3. Test with simple query
python simple_observability.py \
  --agent-id $AGENTCORE_AGENT_ID \
  --scenario dashboard

# 4. Check Python path
which python
python --version
```

## Data Issues

### No Metrics in Dashboard

**Problem**: CloudWatch dashboard shows no data

**Causes**:
1. No agent invocations yet
2. Metric filters not created
3. Wrong time range selected
4. Dashboard region mismatch

**Solutions**:

```bash
# 1. Run demo to generate data
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario all

# 2. Verify metrics exist
aws cloudwatch list-metrics \
  --namespace AgentCore/Observability \
  --region $AWS_REGION

# 3. Check metric filters
aws logs describe-metric-filters \
  --log-group-name /aws/agentcore/observability \
  --region $AWS_REGION

# 4. Recreate dashboard
cd scripts
./setup_cloudwatch.sh --region $AWS_REGION

# 5. Check time range in dashboard
# Set to "Last 5 minutes" or "Last hour"
```

### Logs Empty or Missing

**Problem**: CloudWatch Logs shows no entries

**Causes**:
1. Agent not invoked
2. Log group doesn't exist
3. IAM permissions missing
4. Logging disabled

**Solutions**:

```bash
# 1. Verify log group exists
aws logs describe-log-groups \
  --log-group-name-prefix /aws/agentcore \
  --region $AWS_REGION

# 2. Check recent log streams
aws logs describe-log-streams \
  --log-group-name /aws/agentcore/observability \
  --order-by LastEventTime \
  --descending \
  --max-items 5 \
  --region $AWS_REGION

# 3. Tail logs in real-time
aws logs tail /aws/agentcore/observability --follow --region $AWS_REGION

# 4. Run demo and watch logs
# Terminal 1:
aws logs tail /aws/agentcore/observability --follow --region $AWS_REGION

# Terminal 2:
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario success
```

## Getting Help

### Collect Diagnostic Information

When requesting help, provide:

```bash
# 1. Agent information
aws bedrock-agentcore describe-agent \
  --agent-id $AGENTCORE_AGENT_ID \
  --region $AWS_REGION > agent-info.json

# 2. Recent logs
aws logs filter-log-events \
  --log-group-name /aws/agentcore/observability \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --region $AWS_REGION > recent-logs.json

# 3. Environment info
echo "Python: $(python --version)" > environment.txt
echo "AWS CLI: $(aws --version)" >> environment.txt
echo "Region: $AWS_REGION" >> environment.txt
echo "Agent ID: $AGENTCORE_AGENT_ID" >> environment.txt

# 4. Error messages
# Copy full error output from terminal
```

### Support Channels

- **AWS Support**: https://console.aws.amazon.com/support
- **AWS re:Post**: https://repost.aws/tags/TA4IvCeWI1TE-69RURudUzbw/amazon-bedrock
- **GitHub Issues**: https://github.com/awslabs/amazon-bedrock-agentcore-samples/issues
- **Braintrust Discord**: https://discord.gg/braintrust (for Braintrust-specific issues)

## Common Error Messages Reference

### Error: "Rate limit exceeded"

**Cause**: Too many API calls to Bedrock
**Solution**: Wait 1 minute and retry, or request quota increase

### Error: "Model not found"

**Cause**: Model ID incorrect or not available in region
**Solution**: Verify model ID and region support

### Error: "Validation error"

**Cause**: Invalid parameters in API call
**Solution**: Check API documentation for parameter formats

### Error: "Connection timeout"

**Cause**: Network connectivity issues
**Solution**: Check internet connection and AWS service health

### Error: "Access denied to S3"

**Cause**: S3 permissions missing (if using S3 for artifacts)
**Solution**: Add S3 read/write permissions to IAM role

## Preventive Measures

### Before Running Tutorial

1. Verify all prerequisites
2. Check AWS service health dashboard
3. Ensure sufficient AWS quotas
4. Test AWS credentials
5. Review IAM permissions

### During Tutorial

1. Monitor CloudWatch Logs in real-time
2. Check dashboard for data appearing
3. Verify each step before proceeding
4. Save trace IDs for later reference

### After Tutorial

1. Review all traces in both platforms
2. Check for any errors or warnings
3. Verify cleanup completed successfully
4. Document any issues encountered

## Braintrust Observability Issues

### OTEL Traces Not Appearing in Braintrust

**Error Message in Logs**:
```
ERROR,Failed to export metrics to api.braintrust.dev, error code: StatusCode.PERMISSION_DENIED
```

**Note**: This error message says "metrics" but it's actually about OTEL traces/spans export.

**Causes**:
1. Invalid or expired Braintrust API key
2. Wrong Braintrust project ID
3. API key and project ID don't belong to same Braintrust account
4. Braintrust API endpoint changed or is unreachable

**Solutions**:

**Step 1: Verify Braintrust Credentials**
```bash
# 1. Log into Braintrust: https://www.braintrust.dev/app
# 2. Navigate to Settings → API Keys
# 3. Copy your active API key (starts with 'sk-')
# 4. Get your Project ID from your project URL:
#    https://www.braintrust.dev/app/ORG/p/PROJECT_ID

# Update .env with correct credentials
BRAINTRUST_API_KEY=sk-your-real-api-key
BRAINTRUST_PROJECT_ID=your-real-project-id
```

**Step 2: Test Braintrust Connectivity**
```bash
# Use curl to test direct OTEL connection
curl -X POST https://api.braintrust.dev/otel \
  -H "Authorization: Bearer sk-your-real-api-key" \
  -H "x-bt-parent: project_id:your-real-project-id" \
  -H "Content-Type: application/x-protobuf" \
  -d "" -v
```

**Step 3: Redeploy Agent with Updated Credentials**
```bash
# Edit .env with correct Braintrust credentials
# Then redeploy
./scripts/deploy_agent.sh

# Run a test to generate observability data
./scripts/tests/test_agent.sh --test weather

# Check logs for export errors
./scripts/check_logs.sh --time 5m | grep -i "export\|permission"
```

**Step 4: Verify in Braintrust**
```bash
# 1. Go to https://www.braintrust.dev/app
# 2. Select your project
# 3. Look for traces from the last few minutes
# 4. If still no traces appear, credentials are invalid
```

**If Error Persists**:
- Confirm API key is not expired (regenerate in Settings if needed)
- Confirm project still exists (may have been deleted)
- Try creating new API key and project
- Check Braintrust status page for service issues

### CloudWatch Traces Appear But Braintrust Traces Don't

**Scenario**: You see CloudWatch logs but nothing in Braintrust

**Cause**: Braintrust credentials are invalid or endpoint is unreachable

**Solution**: Follow "OTEL Traces Not Appearing in Braintrust" section above to verify and test your credentials

**Note**: When Braintrust is misconfigured:
- CloudWatch logs still appear (this always works)
- Braintrust receives no traces (credential/network issue)
- The agent continues to function normally

## Next Steps

If issues persist after troubleshooting:

1. Review [System Design](design.md) for architecture understanding
2. Review [Braintrust Setup](braintrust-setup.md) for platform configuration
3. Review [Development Guide](development.md) for code customization
4. Check [Observability Options](observability-options.md) for alternative approaches
5. Contact AWS Support or open GitHub issue with diagnostic information
