# Observability Options Guide

This guide compares three observability approaches you can use when deploying your AgentCore agent:

1. **CloudWatch Only** - Complete visibility into agent internals, no external dependencies
2. **Braintrust + CloudWatch** - External observability platform with LLM-specific insights and cost tracking
3. **CloudWatch APM** - Built-in agent dashboards and performance monitoring

Each option provides different capabilities. This guide explains what you can see and do with each approach to help you choose the right one for your needs.

## Option 1: CloudWatch Only (No Braintrust)

Deploy your agent **without** Braintrust credentials to see full observability in CloudWatch.

### How to Deploy

```bash
# Ensure Braintrust credentials are commented out or empty in .env
# (Lines 13-14 in .env.example)
# BRAINTRUST_API_KEY=your-api-key-here
# BRAINTRUST_PROJECT_ID=your-project-id-here

# Deploy with CloudWatch observability
./scripts/deploy_agent.sh
```

### What You Can See

#### Agent-Level Metrics

CloudWatch displays agent invocation metrics:

- **Invocation Count**: Total number of times the agent was called
- **Success Rate**: Percentage of successful invocations
- **Average Duration**: How long each invocation takes
- **Error Rate**: Percentage of failed invocations

![CloudWatch Agent Metrics](./img/demo1-cw-1.gif)

#### Agent Sessions

View conversation history and session context:

- **Session ID**: Unique identifier for each conversation
- **Messages**: Full conversation history
- **Memory**: Agent's short-term memory state
- **Context**: What information the agent has access to



#### Full Traces with All Details

See complete trace of everything that happens inside an invocation:

- **LLM Calls**: Each call to the language model
  - Prompt sent
  - Response received
  - Token count
  - Latency

- **Tool Invocations**: Each tool the agent calls
  - Tool name and parameters
  - Tool output
  - Execution time

- **Agent Decision Points**: Where the agent decides what to do next
  - Reasoning
  - Next action selected

- **Span Timing**: Exact timing for each operation



#### Detailed Trajectory View

See the step-by-step trajectory of the agent's thinking:

- Step 1: Agent receives query
- Step 2: Agent calls LLM to decide action
- Step 3: Agent calls tool
- Step 4: Agent processes tool result
- Step 5: Agent calls LLM again
- Step 6: Agent provides final response

Each step shows:
- Operation type (LLM call, tool call, etc.)
- Input and output
- Timing information
- Error details (if any)

![CloudWatch Sessions](./img/demo1-cw-2.gif)

#### Live Log Examples

When you view CloudWatch logs for a CloudWatch-only deployment, you see both runtime and OTEL logs:

**Runtime Logs** (human-readable):
```
2025-11-02T20:02:42.861000+00:00 2025/11/02/[runtime-logs]3f6d959d-9b0a-4f1b-8894-ad142233fc6e 2025-11-02 20:02:42,861,p1,{weather_time_agent.py:105},INFO,Initializing Strands agent with model: us.anthropic.claude-haiku-4-5-20251001-v1:0
```

**OTEL Logs** (structured JSON):
```json
{
  "resource": {
    "attributes": {
      "service.name": "weather_time_observability_agent.DEFAULT",
      "cloud.region": "us-east-1",
      "cloud.platform": "aws_bedrock_agentcore",
      "cloud.resource_id": "arn:aws:bedrock-agentcore:us-east-1:015469603702:runtime/weather_time_observability_agent-dWTPGP46D4/..."
    }
  },
  "scope": {"name": "__main__"},
  "timeUnixNano": 1762113762861725952,
  "severityText": "INFO",
  "body": "Initializing Strands agent with model: us.anthropic.claude-haiku-4-5-20251001-v1:0",
  "attributes": {
    "code.file.path": "/app/agent/weather_time_agent.py",
    "code.function.name": "<module>",
    "code.line.number": 105,
    "otelTraceID": "68fe3f82667cdc015abcd1d779d96d56",
    "otelSpanID": "49dbfa0650a0f03d"
  }
}
```

**The same log message appears in both formats**:
- Runtime logs are easy to read
- OTEL logs have structured metadata for correlation and automated analysis
- Both include trace IDs to link logs with traces

### Advantages

✅ See everything happening inside your agent
✅ No external dependencies or API keys needed
✅ Free (CloudWatch costs are minimal)
✅ AWS native integration
✅ Easy debugging of agent internals

### Best For

- Development and debugging
- Understanding agent behavior
- Troubleshooting agent issues
- Learning how agents work

---

## Option 2: Braintrust + CloudWatch (Dual Observability)

Deploy your agent **with** Braintrust credentials to get external observability platform insights.

### How to Deploy

```bash
# Add your Braintrust credentials to .env (lines 13-14)
BRAINTRUST_API_KEY=sk-your-actual-api-key
BRAINTRUST_PROJECT_ID=your-actual-project-id

# Deploy with dual observability
./scripts/deploy_agent.sh
```

### What You Can See

#### CloudWatch Agent-Level Metrics (Still Available)

Same as CloudWatch-only:

- **Invocation Count**: Total invocations
- **Success Rate**: Success percentage
- **Average Duration**: Invocation timing
- **Error Rate**: Failure percentage

*Note: Detailed traces are NOT available in CloudWatch when Braintrust is enabled.*

#### CloudWatch Session Information (Still Available)

- Session ID and conversation history
- Agent memory state
- Context available to agent

#### Braintrust: Low-Level Operational Details

Braintrust receives all the detailed OTEL spans and traces that CloudWatch doesn't show:

- **LLM Calls**: Every call to the language model
  - Exact prompts and completions
  - Token usage and costs
  - Latency for each call
  - Model selection and parameters

- **Tool Invocations**: Every tool the agent calls
  - Tool execution timing
  - Input parameters
  - Output results
  - Any errors during execution



- **Full Request Trace**: Complete trace of an invocation
  - Start to finish span tree
  - All nested operations
  - Timing for each span
  - Correlation with logs

![Braintrust Full Trace](./img/demo1-bt-1.gif)

#### Braintrust: LLM-Specific Insights

Features unique to Braintrust for AI/LLM workloads:

- **Cost Tracking**: Track API costs across different models and calls
- **Quality Scores**: Rate invocation quality for model improvement
- **Custom Metrics**: Define and track custom observability metrics
- **Model Performance**: Compare performance across different models
- **Feedback Integration**: Record user feedback and ground truth


### Key Trade-Off

**What CloudWatch shows**: ❌ No traces (traces only in Braintrust), only metrics

**What Braintrust shows**: ✅ All low-level operational details

**Result**: When you need detailed trace debugging, you must check Braintrust (not available in CloudWatch)

### Advantages

✅ External observability platform backup
✅ LLM-specific metrics and cost tracking
✅ Quality scoring for model improvement
✅ Custom metric support
✅ Cross-platform consistency (OTEL standard)

### Best For

- Production deployments
- Cost tracking and optimization
- Model performance monitoring
- External audit trails
- Multi-platform observability

### When to Use This Setup

Use Braintrust observability when:

1. You need external observability
2. You want to track LLM API costs in detail
3. You're evaluating model quality
4. You need vendor-independent observability
5. You have SLAs requiring external backup

---

## Option 3: CloudWatch APM (Agent Services)

CloudWatch provides built-in service-level dashboards for quick operational monitoring.

### What You Can See

#### Built-in Agent Dashboards

CloudWatch automatically creates dashboards for your agent:

- **Agent Name**: Your agent's identifier
- **Status**: Running, stopped, or error state
- **Performance Metrics**: Response times and throughput
- **Error Tracking**: Error rates and types
- **Resource Usage**: CPU and memory utilization

![CloudWatch Agent Services Dashboard](./img/demo1-cw-3.gif)

#### Agent Performance Over Time

Monitor trends:

- **Invocation Trend**: How many times agent was called (hourly, daily)
- **Latency Trend**: How response times change
- **Error Trend**: Error rate changes
- **Success Rate Trend**: Success rate over time



#### Error Analysis

Built-in error dashboard shows:

- **Error Types**: What kinds of errors occurred
- **Error Frequency**: How often each error happens
- **Error Timeline**: When errors occurred
- **Affected Invocations**: How many invocations were affected



### Advantages

✅ Built-in, no setup needed
✅ Quick operational overview
✅ Automatic dashboards
✅ Real-time monitoring
✅ Integrated with CloudWatch

### Best For

- Operational monitoring
- Quick health checks
- Trend analysis
- Executive dashboards
- Alerting and notifications

### Access APM Dashboards

```bash
# Open AWS Console
# Navigate to: CloudWatch → APM → Services → Agents
# Select your agent to view dashboards
```

---

## Comparison Summary

| Feature | CloudWatch Only | Braintrust | CloudWatch APM |
|---------|-----------------|-----------|----------------|
| **Agent Metrics** | ✅ Full details | ✅ At invocation level | ✅ Aggregated |
| **Trace Details** | ✅ All operations | ✅ In Braintrust only | ❌ No traces |
| **Session/Memory** | ✅ Full history | ✅ Available | ❌ No |
| **LLM Cost Tracking** | ❌ No | ✅ Yes | ❌ No |
| **Troubleshooting** | ✅ Best | ⚠️ Limited in CW | ❌ Limited |
| **Operational Monitoring** | ✅ Good | ✅ Good | ✅ Best |
| **Setup Complexity** | ✅ Simple | ⚠️ Moderate | ✅ Automatic |
| **External Backup** | ❌ AWS only | ✅ Yes | ❌ AWS only |

---

## Recommended Approach

### Development/Debugging
Start with **CloudWatch Only**:
- See everything happening inside your agent
- Easy to understand behavior
- No setup needed

### Production
Use **Braintrust + CloudWatch** or just **CloudWatch APM**:
- Braintrust: If you need detailed tracing and LLM cost tracking
- CloudWatch APM: If you want simple operational monitoring

### Monitoring & Alerting
Use **CloudWatch APM** for:
- Quick health checks
- Performance trends
- Error rate monitoring
- Automated alerting

---

## Next Steps

1. **Try CloudWatch Only first** - Deploy without Braintrust credentials
2. **Explore metrics and traces** - Use the scripts in `scripts/check_*.sh`
3. **If needed, add Braintrust** - Edit `.env` with Braintrust credentials and redeploy
4. **Set up CloudWatch APM** - Access via AWS Console for operational monitoring

See [Observability Architecture](./observability-architecture.md) for technical details about how OTEL logging works.
