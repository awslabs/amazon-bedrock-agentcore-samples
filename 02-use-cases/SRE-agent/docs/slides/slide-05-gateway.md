# AgentCore Gateway: API to MCP Tool Transformation

## The Power of Protocol Standardization

### **Traditional Approach**
❌ Write custom connectors for every API  
❌ Manage authentication for each service  
❌ Handle different data formats and protocols  
❌ **Result**: 4-6 weeks per integration

### **AgentCore Gateway Approach**  
✅ Upload OpenAPI specifications to S3  
✅ Configure gateway with credential providers  
✅ Instantly available as MCP tools  
✅ **Result**: 2 days for all integrations

---

## Gateway Configuration Example

```python
# Create gateway with JWT authorization
response = client.create_gateway(
    name="sre-agent-gateway",
    roleArn=role_arn,
    protocolType="MCP",
    authorizerType="CUSTOM_JWT",
    authorizerConfiguration={"customJWTAuthorizer": {"discoveryUrl": discovery_url}}
)

# Add S3 target with OpenAPI spec
s3_target_config = {"mcp": {"openApiSchema": {"s3": {"uri": s3_uri}}}}
```

### **Result: 21 MCP Tools Ready**
```
• k8s-api___get_pod_status
• logs-api___search_logs  
• metrics-api___get_performance_metrics
• runbooks-api___get_incident_playbook
... and 17 more tools instantly available
```

---

## Universal Framework Compatibility

Works with **any MCP-compatible agent framework**:
- LangGraph (used in SRE Agent)
- AWS Strands
- CrewAI
- Custom implementations