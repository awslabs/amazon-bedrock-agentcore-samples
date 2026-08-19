# Model Configuration Guide

This guide explains how to configure different foundation models with your Bedrock AgentCore Template, including cross-region inference profiles for improved availability.

## Default Configuration

This template uses **Claude Sonnet 4** with **cross-region inference profile**:

```typescript
// infrastructure/agent/src/agent.py
model_id = 'us.anthropic.claude-sonnet-4-20250514-v1:0'
```

### Cross-Region Inference Profiles

Cross-region inference profiles provide:
- **Higher availability** - Automatically routes to available regions
- **Better performance** - Uses the closest available region
- **Simplified configuration** - Works across all Bedrock-supported regions
- **Automatic failover** - Switches regions if one becomes unavailable

## Supported Models

### Anthropic Claude Models (Recommended)

| Model | Inference Profile | Description | Use Case |
|-------|------------------|-------------|----------|
| Claude Sonnet 4 | `us.anthropic.claude-sonnet-4-20250514-v1:0` | Latest Claude Sonnet (Default) | General purpose, best balance |
| Claude 3.5 Sonnet v2 | `us.anthropic.claude-3-5-sonnet-20241022-v2:0` | Previous generation | Legacy compatibility |
| Claude 3 Haiku | `us.anthropic.claude-3-haiku-20240307-v1:0` | Fast, cost-effective | Development, simple queries |
| Claude 3 Opus | `us.anthropic.claude-3-opus-20240229-v1:0` | Highest quality | Complex reasoning tasks |

### Amazon Titan Models

| Model | Inference Profile | Description |
|-------|------------------|-------------|
| Titan Text Premier | `us.amazon.titan-text-premier-v1:0` | Enterprise text generation |
| Titan Text Express | `us.amazon.titan-text-express-v1` | Fast text generation |

For the complete list, visit the [AWS Bedrock Model Catalog](https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html).

## Changing the Model

### Update the Stack Configuration

Edit `infrastructure/agent/src/agent.py`:

```python
# Change the default model
model_id = os.environ.get('MODEL_ID', 'us.anthropic.claude-3-haiku-20240307-v1:0')
```

Then redeploy:
```bash
./scripts/deploy.sh
```

### Using Environment Variables

Set in `infrastructure/.env`:
```bash
BEDROCK_MODEL_ID=us.anthropic.claude-3-haiku-20240307-v1:0
```

## Regional Availability

### Cross-Region Profile Coverage

| Profile Prefix | Regions Included |
|---------------|------------------|
| `us.*` | us-east-1, us-west-2, us-east-2, us-west-1 |
| `eu.*` | eu-west-1, eu-west-2, eu-west-3, eu-central-1 |
| `ap.*` | ap-southeast-1, ap-southeast-2, ap-northeast-1 |

### Model Access Requirements

Before using a model, request access in the Bedrock console:

1. Go to **Amazon Bedrock** → **Model access**
2. Click **Manage model access**
3. Select desired models (e.g., Claude 3.5 Sonnet)
4. Click **Request model access**
5. Wait for approval (usually instant)

**Note**: Model access is per-region. Request access in each deployment region.

## IAM Permissions

Cross-region inference profiles require permissions for all regions:

```typescript
new iam.PolicyStatement({
  effect: iam.Effect.ALLOW,
  actions: [
    'bedrock:InvokeModel',
    'bedrock:InvokeModelWithResponseStream'
  ],
  resources: [
    // IMPORTANT: Use wildcard for all regions
    'arn:aws:bedrock:*::foundation-model/*',
    // Inference profiles in your account region
    `arn:aws:bedrock:${region}:${account}:inference-profile/*`
  ],
})
```

## Troubleshooting

### Common Issues

**Access Denied Error**
- **Cause**: Model access not granted or IAM permissions scoped to single region
- **Solution**: Request model access in Bedrock console and update IAM policy to use `arn:aws:bedrock:*::foundation-model/*`

**Model Not Found Error**
- **Cause**: Wrong model ID or model not available in region
- **Solution**: Verify model ID spelling and check availability in AWS Console → Bedrock → Model catalog

**Slow Response Times**
- **Solution**: Use Claude Haiku for faster responses or deploy closer to users

### Checking Model Availability

```bash
# List available models in your region
aws bedrock list-foundation-models \
  --by-provider anthropic \
  --region us-west-2 \
  --query 'modelSummaries[].{ModelId:modelId,Status:modelLifecycle.status}' \
  --output table
```

## Best Practices

### Production Deployments
- ✅ Use cross-region inference profiles for high availability
- ✅ Request model access in all deployment regions
- ✅ Set up CloudWatch alarms for model invocation errors
- ✅ Test with multiple models to find the best fit

### Cost Optimization
- ✅ Start with Claude Haiku for development/testing
- ✅ Monitor token usage in CloudWatch
- ✅ Set up billing alerts for unexpected costs
- ✅ Cache common responses at the application layer

### Security
- ✅ Use IAM roles, never hardcode credentials
- ✅ Apply least privilege to model access
- ✅ Enable CloudTrail for audit logging

## Additional Resources

- [Amazon Bedrock Model Catalog](https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html)
- [Cross-Region Inference Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html)
- [Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)
- [Claude Model Comparison](https://docs.anthropic.com/claude/docs/models-overview)
