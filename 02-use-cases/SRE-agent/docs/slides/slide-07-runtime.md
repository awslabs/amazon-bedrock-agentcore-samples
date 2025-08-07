# AgentCore Runtime: Production Deployment Made Simple

## Development to Production Flow

```
📦 LOCAL DEVELOPMENT          🐳 CONTAINERIZATION
Test with CLI                  Add FastAPI wrapper
↓                             ↓
🧪 LOCAL TESTING              ☁️ PRODUCTION DEPLOYMENT  
Docker run locally            Push to ECR → Deploy to Runtime
```

---

## Containerization: Any Agent to Production

```dockerfile
# ARM64 base image for AgentCore
FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Add agent code
COPY sre_agent/ ./sre_agent/

# Run with FastAPI wrapper
CMD ["uv", "run", "uvicorn", "sre_agent.agent_runtime:app", 
     "--host", "0.0.0.0", "--port", "8080"]
```

**Key insight**: Existing agent + FastAPI wrapper = AgentCore-ready

---

## Deploy and Invoke

### **Deploy to Runtime**
```python
response = client.create_agent_runtime(
    name="sre-agent-runtime",
    containerImage=ecr_image_uri,
    roleArn=runtime_role_arn,
    configuration={"model": "claude-sonnet-4"}
)
```

### **Production Invocation**
```python
response = client.invoke_agent_runtime(
    agentRuntimeId=agent_runtime_id,
    requestBody={
        "query": "Why are payment-service pods crash looping?",
        "user_id": "Alice"
    }
)
```

---

## Runtime Benefits

✅ **Auto-scaling**: Zero to thousands of concurrent sessions  
✅ **Session isolation**: Complete security between users  
✅ **Multi-LLM support**: Amazon Bedrock or Anthropic Claude  
✅ **Enterprise ready**: IAM authentication, CloudWatch monitoring  
✅ **Zero infrastructure management**: Serverless execution