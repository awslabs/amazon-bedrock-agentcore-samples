# System Design and Architecture

## Overview

This document provides a comprehensive explanation of the Simple Dual Observability Tutorial architecture, component interactions, and OpenTelemetry trace flow.

## Architecture Overview

The tutorial demonstrates two deployment modes for the same agent:

### Mode 1: Local Testing (Development)

Used for development and debugging before deploying to production.

```
Developer Machine
    |
    v
agent/weather_time_agent.py (runs locally)
    |
    v (calls Bedrock Converse API)
Amazon Bedrock (Claude 3.5 Haiku)
    |
    v (tool calls)
tools/*.py (execute locally)
    |
    v
Response back to terminal

Observability: None (local testing only)
Purpose: Test agent logic before deployment
```

### Mode 2: AgentCore Runtime Deployment (Production/Demo)

The main tutorial flow - demonstrates automatic observability in production.

```
Developer Laptop
    |
    v (runs simple_observability.py)
Python CLI Script (boto3 client)
    |
    v (API call: invoke_agent)
Amazon Bedrock AgentCore Runtime (Managed Service)
    |
    v (your agent runs here with automatic OTEL)
agent/weather_time_agent.py (deployed and hosted)
    |
    v (tool calls via MCP)
MCP Tools (weather, time, calculator)
    |
    v (traces exported automatically)
    |
    +------------------+------------------+
    |                  |
    v                  v
CloudWatch Logs    Braintrust
(AWS-native)     (AI platform)

Observability: FULL - automatic OTEL tracing
Purpose: Production deployment with zero-code observability
```

## Component Interactions

### 1. Client Script (simple_observability.py)

**Purpose**: Invokes deployed agent and manages demo scenarios

**Responsibilities**:
- Creates boto3 client for AgentCore Runtime
- Generates unique session IDs for trace correlation
- Invokes agent via `invoke_agent` API
- Prints observability links and guidance
- Manages scenario execution (success, error, dashboard)

**Key Operations**:
```python
# Create client
client = boto3.client("bedrock-agentcore-runtime", region_name=region)

# Invoke agent
response = client.invoke_agent(
    agentId=agent_id,
    sessionId=session_id,
    inputText=query,
    enableTrace=True  # Enables detailed tracing
)
```

### 2. AgentCore Runtime (Managed Service)

**Purpose**: Hosts and executes agent code with automatic instrumentation

**Responsibilities**:
- Loads deployed agent code
- Injects automatic OTEL instrumentation
- Manages agent lifecycle
- Routes tool calls to MCP tools
- Exports traces to configured platforms

**Automatic Instrumentation**:
- Wraps agent code with OTEL spans
- Captures timing, parameters, and results
- Records errors and exceptions
- Correlates distributed traces
- Exports to multiple backends simultaneously

**No code changes required** - instrumentation is automatic.

### 3. Weather/Time Agent (agent/weather_time_agent.py)

**Purpose**: Core agent logic using Bedrock Converse API

**Responsibilities**:
- Receives user queries
- Calls Bedrock Converse API with tools
- Implements agentic loop (tool calling)
- Executes tools and aggregates responses
- Returns final answer to user

**Key Features**:
- Uses Amazon Bedrock Converse API
- Supports tool calling via Claude
- Implements standard agentic loop pattern
- Graceful error handling

**Agentic Loop**:
```
1. User query -> Send to Claude with tools
2. Claude decides to use tool -> Execute tool
3. Tool result -> Send back to Claude
4. Claude provides final answer -> Return to user
```

### 4. MCP Tools (tools/*.py)

**Purpose**: Tool implementations executed by agent

**Tools Available**:

**Weather Tool** (`tools/weather_tool.py`):
```python
def get_weather(city: str) -> Dict[str, Any]:
    """Returns simulated weather data for demo purposes."""
    return {
        "city": city,
        "temperature": "72F",
        "condition": "Partly cloudy",
        "humidity": "65%"
    }
```

**Time Tool** (`tools/time_tool.py`):
```python
def get_time(timezone: str) -> Dict[str, Any]:
    """Returns current time for timezone."""
    return {
        "timezone": timezone,
        "current_time": datetime.now(pytz.timezone(tz)).isoformat(),
        "utc_offset": "+/-X hours"
    }
```

**Calculator Tool** (`tools/calculator_tool.py`):
```python
def calculator(
    operation: str,
    a: float,
    b: Optional[float] = None
) -> Dict[str, Any]:
    """Performs mathematical calculations."""
    # Supports: add, subtract, multiply, divide, factorial
    # Demonstrates error handling (factorial of negative number)
```

### 5. Telemetry Instrumentation (Strands Library)

**Purpose**: Automatically instruments agent code and exports traces to multiple platforms

**Configuration**:

The Strands telemetry library automatically configures:

**Processors**:
- Batch processor (groups spans for efficiency)
- Resource processor (adds service metadata)
- Memory limiter (prevents OOM)

**Exporters**:
1. **OTLP/Braintrust**: Exports to Braintrust platform (when BRAINTRUST_API_KEY is configured)
2. **CloudWatch Logs**: Captured automatically by AgentCore Runtime
3. **Logging**: Debug output to stdout (optional)

**Configuration**:
All configuration is handled via environment variables:
- `BRAINTRUST_API_KEY`: API key for Braintrust platform
- `OTEL_*`: Standard OpenTelemetry environment variables
- `BEDROCK_*`: Bedrock-specific configuration

The agent uses the Strands telemetry library which automatically configures OTLP exporters based on these environment variables. No static YAML configuration file is needed.

### 6. CloudWatch Logs

**Purpose**: AWS-native application logging and observability

**Capabilities**:
- Real-time log stream viewing
- Structured logging with timestamps
- Tool execution tracking
- Error and exception logging
- Integration with CloudWatch Alarms

**Data Captured**:
- Trace IDs and span IDs
- Service names and operations
- Timing information (start, duration)
- HTTP status codes
- Error messages and stack traces
- Custom attributes (model, tokens, etc.)

### 7. Braintrust

**Purpose**: AI-focused observability and quality monitoring

**Capabilities**:
- LLM-specific metrics
- Token and cost tracking
- Prompt version comparison
- Quality evaluations
- Hallucination detection

**Data Captured**:
- All OTEL trace data
- Token counts (input, output, total)
- Model parameters (temperature, max tokens)
- Cost calculations
- Custom AI metrics

## OTEL Flow Diagrams

### Trace Creation Flow

```
Agent Invocation
    |
    v
AgentCore Runtime creates ROOT SPAN
    |
    +-- Span: agent.invocation
        |  Attributes: agent_id, session_id, query
        |  Start time: T0
        |
        +-- Span: llm.call (Bedrock Converse)
        |   |  Attributes: model_id, temperature, max_tokens
        |   |  Start time: T0 + 50ms
        |   |  Duration: 800ms
        |   |  Events: token_usage (input: 120, output: 45)
        |
        +-- Span: tool.selection
        |   |  Attributes: tools_available, tools_selected
        |   |  Start time: T0 + 900ms
        |   |  Duration: 50ms
        |
        +-- Span: gateway.execution (weather tool)
        |   |  Attributes: tool_name, tool_input
        |   |  Start time: T0 + 1000ms
        |   |  Duration: 200ms
        |   |  Events: tool_result
        |
        +-- Span: gateway.execution (time tool)
        |   |  Attributes: tool_name, tool_input
        |   |  Start time: T0 + 1250ms
        |   |  Duration: 150ms
        |
        +-- Span: llm.call (final answer)
        |   |  Attributes: model_id
        |   |  Start time: T0 + 1450ms
        |   |  Duration: 600ms
        |
        +-- Span: response.formatting
            |  Start time: T0 + 2100ms
            |  Duration: 50ms
            |  End time: T0 + 2150ms

Total Duration: 2150ms
Status: OK
```

### Error Flow (Scenario 2)

```
Agent Invocation: "Calculate factorial of -5"
    |
    v
AgentCore Runtime creates ROOT SPAN
    |
    +-- Span: agent.invocation
        |
        +-- Span: llm.call
        |   |  Claude decides to use calculator tool
        |
        +-- Span: tool.selection
        |   |  Selected: calculator
        |
        +-- Span: gateway.execution (calculator)
        |   |  Attributes: operation=factorial, a=-5
        |   |  Status: ERROR
        |   |  Error: "Cannot calculate factorial of negative number"
        |   |  Exception: ValueError
        |
        +-- Span: llm.call (error handling)
        |   |  Claude receives error message
        |   |  Generates helpful response
        |
        +-- Span: response.formatting
            |  Final response explains the error

Total Duration: 1800ms
Status: OK (gracefully handled error)
Root Span Status: OK
Child Span Status: ERROR (calculator span)
```

## Dual-Platform Observability Strategy

### Why Dual-Platform Observability?

This tutorial demonstrates two distinct observability mechanisms that work together:

**CloudWatch Observability (Automatic, from AgentCore Runtime)**:
- Always enabled with zero configuration
- Receives vended traces from AgentCore Runtime infrastructure
- Native AWS integration with CloudWatch Logs
- CloudWatch Alarms for alerting
- Long-term retention policies
- VPC integration

**Braintrust Observability (Optional, from Strands Agent)**:
- Opt-in via `BRAINTRUST_API_KEY` environment variable
- Receives OpenTelemetry traces directly from the Strands agent
- AI-specific metrics (LLM tokens, costs, quality)
- Better LLM-focused visualizations
- Evaluations and prompt management
- Independent of AWS infrastructure

**Key Difference**: CloudWatch traces come from AgentCore Runtime infrastructure (vended format), while Braintrust traces come from your Strands agent code (OTEL format). These are complementary, not redundant.

### Export Architecture

```
AgentCore Runtime (with Strands telemetry)
    |
    v
OTLP Exporter (environment variable configured)
    |
    +------------------+------------------+
    |                  |                  |
    v                  v                  v
CloudWatch Logs   OTLP/Braintrust    Logging
(AgentCore)       Exporter           Exporter
    |                  |                  |
    v                  v                  v
CloudWatch Logs   Braintrust API     stdout
(OTEL traces)     Platform           (debug)
```

**Note**: Configuration is purely environment variable-based using the Strands telemetry library. No external OTEL Collector or static YAML configuration is required.

### Trace Correlation

All traces share common identifiers for correlation:

**Trace ID**: Unique identifier for entire request
**Span ID**: Unique identifier for each operation
**Parent Span ID**: Links spans hierarchically
**Session ID**: Groups multiple invocations
**Custom Attributes**: Additional correlation data

**Example**:
```
Trace ID: 1-67891011-abcdef1234567890
Session ID: demo_session_a1b2c3d4
Agent ID: agent-xyz123

CloudWatch Query:
Filter traces by Trace ID or Session ID

Braintrust Query:
Filter traces by same Trace ID or Session ID

Results: Identical spans visible in both platforms
```

## Data Flow Summary

1. **User runs script**: `simple_observability.py --scenario success`
2. **Script invokes agent**: boto3 call to AgentCore Runtime
3. **Runtime starts trace**: Creates root span with trace ID
4. **Agent code executes**: Calls Bedrock Converse API
5. **Claude selects tools**: Instrumented as child spans
6. **Tools execute via MCP**: Each tool call is a span
7. **Agent aggregates results**: Final response span
8. **CloudWatch logging**: AgentCore Runtime automatically exports application logs to CloudWatch Logs
9. **Braintrust export** (optional): If BRAINTRUST_API_KEY is set, Strands agent exports OTEL traces to Braintrust
10. **User views traces**: CloudWatch (always available) and optionally Braintrust (if configured)

## Performance Characteristics

### Latency Breakdown

Typical successful request (2 tools):
- Agent invocation overhead: 50ms
- LLM call (tool selection): 800ms
- Tool execution (2 tools): 350ms
- LLM call (final answer): 600ms
- Response formatting: 50ms
- **Total**: ~1850ms

### Trace Export Overhead

- Trace generation: <5ms (automatic)
- OTEL collection: <10ms (batched)
- Export to CloudWatch: <50ms (async)
- Export to Braintrust: <50ms (async)
- **User-facing impact**: <5ms (exports are async)

### Scale Considerations

This tutorial is designed for learning and demonstration:
- **Request rate**: 1-10 requests per minute
- **Trace volume**: 3-30 traces per demo run
- **Data retention**: 7 days (Braintrust free tier)

For production scale, see production deployment guides.

## Security Considerations

### Authentication

**AgentCore Runtime**: Uses IAM permissions
**MCP Tools**: Executed with agent permissions
**Braintrust**: API key in OTEL config
**CloudWatch**: IAM role permissions

### Data Privacy

**Trace data contains**:
- User queries (potentially sensitive)
- Tool inputs and outputs
- Model responses

**Recommendations**:
- Use Amazon Bedrock Guardrails for PII filtering
- Review Braintrust data retention policies
- Configure CloudWatch log retention
- Implement trace sampling in production

### Network Security

**AgentCore Runtime**: Private AWS network
**MCP Tools**: Local execution within runtime
**OTEL Export**: HTTPS to CloudWatch and Braintrust
**No public endpoints exposed** by default

## Monitoring the Monitoring

### OTEL Collector Health

The OTEL collector exposes health endpoints:

```bash
# Health check
curl http://localhost:13133

# Metrics endpoint
curl http://localhost:8888/metrics

# Debug endpoint (zpages)
curl http://localhost:55679/debug/tracez
```

### Trace Export Validation

Verify traces are reaching both platforms:

```bash
# Check CloudWatch Logs for export
aws logs tail /aws/agentcore/traces --follow

# Check OTEL collector logs
docker logs otel-collector --follow

# Verify in Braintrust UI
# Navigate to project and check trace count
```

## Troubleshooting Common Issues

### Traces Not Appearing

**Symptom**: No traces in CloudWatch or Braintrust

**Causes**:
1. OTEL collector not running
2. Invalid API keys
3. Sampling rate set to 0
4. Network connectivity issues

**Resolution**: See [docs/troubleshooting.md](troubleshooting.md)

### Incomplete Traces

**Symptom**: Missing spans or partial traces

**Causes**:
1. Agent timeout
2. Tool execution failure
3. OTEL collector buffer overflow

**Resolution**: Check agent logs and increase timeouts

### Trace Correlation Issues

**Symptom**: Cannot find related spans

**Causes**:
1. Session ID not propagated
2. Different trace IDs used
3. Clock skew between services

**Resolution**: Verify session ID in API calls

## Next Steps

After understanding the architecture:

1. Review [Braintrust Setup](braintrust-setup.md) for Braintrust platform configuration
2. Review [Development Guide](development.md) for agent customization
3. Review [Troubleshooting](troubleshooting.md) for CloudWatch and common issues
