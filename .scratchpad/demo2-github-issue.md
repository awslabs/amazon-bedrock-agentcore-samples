# Add Production CloudWatch Observability to SRE-Agent Use Case

## Overview

Enhance the existing SRE-agent multi-agent system with comprehensive CloudWatch observability instrumentation to enable production-level monitoring, debugging, and performance analysis. This enhancement will add distributed tracing, custom metrics, and advanced dashboard capabilities to the complex 5-agent system.

## Objective

Add production-grade observability instrumentation to the SRE-agent use case to demonstrate best practices for monitoring complex multi-agent AI systems in production environments. The implementation will showcase how to instrument agent coordination, memory operations, tool executions, and cross-domain investigations using AWS-native observability tools.

## Background

The SRE-agent is an advanced multi-agent system with:
- 5 agents (1 Supervisor + 4 Specialists: Kubernetes, Logs, Metrics, Runbooks)
- 20+ MCP-based tools across 4 backend domains
- 3 memory strategies (User Preferences, Infrastructure Knowledge, Investigation History)
- 4 backend API servers
- LangGraph multi-agent orchestration
- AgentCore Gateway integration

Currently, the system has basic file logging and debug modes but lacks comprehensive distributed tracing and production observability capabilities.

## Scope

### Files to Create

```
02-use-cases/SRE-agent/
├── sre_agent/
│   └── observability/              NEW MODULE
│       ├── __init__.py
│       ├── otel_instrumentation.py  (OTEL tracer setup, span utilities)
│       ├── metrics.py               (CloudWatch custom metrics)
│       └── trace_utils.py           (Correlation helpers, attribute standards)
├── dashboards/                      NEW FOLDER
│   ├── cloudwatch-dashboard.json    (Dashboard definition)
│   └── insights-queries.json        (CloudWatch Insights queries)
├── scripts/
│   ├── run_observability_demo.sh    NEW FILE (Demo orchestration)
│   └── setup_cloudwatch_dashboard.sh NEW FILE (Dashboard deployment)
└── docs/
    ├── OBSERVABILITY_GUIDE.md       NEW FILE (Implementation guide)
    └── TROUBLESHOOTING_PLAYBOOK.md  NEW FILE (Production debugging)
```

### Files to Modify

Add OpenTelemetry instrumentation to existing code:
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/sre_agent/supervisor.py` (40 lines)
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/sre_agent/agent_nodes.py` (60 lines)
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/sre_agent/memory/client.py` (80 lines)

## Components to Build

### 1. Observability Module (`sre_agent/observability/`)

**File: `otel_instrumentation.py` (~200 lines)**

Core OTEL configuration and span management:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from typing import Any, Dict, Optional


def _setup_tracer() -> trace.Tracer:
    """
    Configure OpenTelemetry tracer for CloudWatch X-Ray.

    Sets up OTLP exporter with AWS X-Ray endpoint configuration.
    """
    pass


def _create_agent_span(
    tracer: trace.Tracer,
    span_name: str,
    agent_name: str,
    attributes: Optional[Dict[str, Any]] = None
) -> trace.Span:
    """
    Create standardized span for agent operations.

    Args:
        tracer: Configured OTEL tracer
        span_name: Name of the operation
        agent_name: Agent identifier (supervisor, kubernetes_agent, etc.)
        attributes: Custom span attributes

    Returns:
        Configured span with standard attributes
    """
    pass


def _add_tool_execution_span(
    parent_span: trace.Span,
    tool_name: str,
    parameters: Dict[str, Any],
    result: Any
) -> None:
    """
    Add child span for tool execution with timing.
    """
    pass


# Span naming conventions
SPAN_SUPERVISOR_ANALYZE = "supervisor.analyze_query"
SPAN_SUPERVISOR_ROUTE = "supervisor.route_decision"
SPAN_SUPERVISOR_AGGREGATE = "supervisor.aggregate_results"
SPAN_AGENT_EXECUTE = "agent.{agent_name}.execute"
SPAN_MEMORY_RETRIEVE = "memory.retrieve"
SPAN_TOOL_CALL = "tool.{tool_name}"
```

**File: `metrics.py` (~100 lines)**

CloudWatch custom metrics:

```python
import boto3
from typing import Dict, Any


class SREAgentMetrics:
    """
    CloudWatch custom metrics for SRE Agent monitoring.
    """

    def __init__(
        self,
        namespace: str = "SREAgent/Production"
    ):
        self.cloudwatch = boto3.client('cloudwatch')
        self.namespace = namespace


    def record_agent_invocation(
        self,
        agent_name: str,
        duration_ms: float,
        success: bool
    ) -> None:
        """Record agent invocation metrics."""
        pass


    def record_tool_execution(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool
    ) -> None:
        """Record tool execution metrics."""
        pass


    def record_memory_operation(
        self,
        operation_type: str,
        strategy: str,
        duration_ms: float,
        results_count: int
    ) -> None:
        """Record memory operation metrics."""
        pass


    def record_escalation(
        self,
        user_id: str,
        escalation_type: str
    ) -> None:
        """Record escalation events."""
        pass
```

**File: `trace_utils.py` (~50 lines)**

Helper utilities for correlation and attributes:

```python
import uuid
from typing import Dict, Any, Optional


def generate_trace_id() -> str:
    """Generate unique trace ID for investigation correlation."""
    return f"investigation_{uuid.uuid4().hex[:16]}"


def create_correlation_attributes(
    user_id: str,
    session_id: str,
    query: str
) -> Dict[str, Any]:
    """
    Create standard correlation attributes for spans.
    """
    return {
        "sre.user_id": user_id,
        "sre.session_id": session_id,
        "sre.query": query[:200],  # Truncate for span limits
        "sre.timestamp": datetime.utcnow().isoformat()
    }


def add_agent_routing_attributes(
    span: trace.Span,
    agents_selected: list,
    routing_reason: str
) -> None:
    """Add routing decision attributes to span."""
    span.set_attribute("sre.agents_selected", ",".join(agents_selected))
    span.set_attribute("sre.routing_reason", routing_reason)
```

### 2. Instrumentation Updates to Existing Code

**supervisor.py enhancements (~40 lines added):**

```python
# Add at top of file
from sre_agent.observability.otel_instrumentation import (
    _setup_tracer,
    _create_agent_span,
    SPAN_SUPERVISOR_ANALYZE,
    SPAN_SUPERVISOR_ROUTE
)
from sre_agent.observability.metrics import SREAgentMetrics

# In SupervisorAgent class
class SupervisorAgent:
    def __init__(self, ...):
        # Existing code...
        self.tracer = _setup_tracer()
        self.metrics = SREAgentMetrics()

    def __call__(self, state: AgentState) -> AgentState:
        # Add span for supervisor operation
        with self.tracer.start_as_current_span(SPAN_SUPERVISOR_ANALYZE) as span:
            span.set_attribute("sre.user_id", state.user_id)
            span.set_attribute("sre.query", state.query)

            start_time = time.time()

            # Existing supervisor logic...
            result = self._analyze_and_route(state)

            # Record metrics
            duration_ms = (time.time() - start_time) * 1000
            self.metrics.record_agent_invocation(
                "supervisor",
                duration_ms,
                success=True
            )

            # Add routing attributes
            span.set_attribute("sre.agents_selected", ",".join(result.next_agents))

            return result
```

**agent_nodes.py enhancements (~60 lines added):**

```python
# Add spans for each specialist agent execution
def kubernetes_agent_node(state: AgentState) -> AgentState:
    tracer = _setup_tracer()
    metrics = SREAgentMetrics()

    with tracer.start_as_current_span("agent.kubernetes.execute") as span:
        span.set_attribute("sre.agent_type", "kubernetes")
        span.set_attribute("sre.tools_available", len(kubernetes_tools))

        start_time = time.time()

        # Existing agent logic...
        result = _execute_kubernetes_agent(state)

        # Add tool execution details
        span.set_attribute("sre.tools_invoked", len(result.tool_calls))

        duration_ms = (time.time() - start_time) * 1000
        metrics.record_agent_invocation(
            "kubernetes_agent",
            duration_ms,
            success=not result.error
        )

        return result
```

**memory/client.py enhancements (~80 lines added):**

```python
# Add spans for memory operations
class SREMemoryClient:
    def get_relevant_memories(
        self,
        namespace: str,
        query: str
    ) -> list:
        tracer = _setup_tracer()
        metrics = SREAgentMetrics()

        with tracer.start_as_current_span("memory.retrieve") as span:
            span.set_attribute("memory.namespace", namespace)
            span.set_attribute("memory.query", query[:100])

            start_time = time.time()

            # Vector search sub-span
            with tracer.start_as_current_span("memory.vector_search") as search_span:
                results = self._vector_search(namespace, query)
                search_span.set_attribute("results.count", len(results))

            # Post-processing sub-span
            with tracer.start_as_current_span("memory.post_process") as process_span:
                processed = self._post_process_results(results)

            duration_ms = (time.time() - start_time) * 1000
            metrics.record_memory_operation(
                "retrieve",
                namespace.split('/')[2],  # Extract strategy from namespace
                duration_ms,
                len(processed)
            )

            span.set_attribute("memory.results_count", len(processed))

            return processed
```

### 3. CloudWatch Dashboard

**File: `dashboards/cloudwatch-dashboard.json`**

Dashboard with 5 panels:
1. Agent Routing Heatmap - Shows supervisor routing decisions over time
2. Tool Execution Waterfall - Timeline of tool executions across agents
3. Memory Operation Latency - Breakdown by strategy (user prefs, infrastructure, investigations)
4. Error Rate by Component - Errors segmented by agent, tool, memory
5. Investigation Timeline - End-to-end trace visualization

**File: `dashboards/insights-queries.json`**

Pre-built CloudWatch Insights queries:
- Find investigations by user
- Identify slowest operations
- Correlate errors across agents
- Track memory cache hit rates
- Analyze tool usage patterns

### 4. Demo Scripts

**File: `scripts/run_observability_demo.sh`**

Orchestration script for running demo scenarios:

```bash
#!/bin/bash
# Runs demo scenarios with CloudWatch observability

set -e

echo "Starting SRE Agent Observability Demo"
echo "======================================"

# Ensure CloudWatch dashboard is deployed
./scripts/setup_cloudwatch_dashboard.sh

# Scenario 1: Cross-domain investigation
echo "Scenario 1: Cross-Domain Investigation"
USER_ID=Alice uv run sre-agent --prompt "API response times have degraded 3x in the last hour"

# Wait for traces to propagate
sleep 10

# Display CloudWatch X-Ray link
echo "View trace in CloudWatch X-Ray:"
echo "https://console.aws.amazon.com/cloudwatch/xray/traces"

# Scenario 2: Memory context demonstration
echo "Scenario 2: Memory Context with Different Users"
USER_ID=Carol uv run sre-agent --prompt "Database pods are crash looping"

# Scenario 3: Live troubleshooting
echo "Scenario 3: Live Error Simulation"
# Kill backend server to trigger error
echo "Simulating backend failure..."
pkill -f "k8s_server.py"
sleep 2

USER_ID=Alice uv run sre-agent --prompt "Check cluster health"

echo "Demo complete! Check CloudWatch dashboard for traces and metrics."
```

**File: `scripts/setup_cloudwatch_dashboard.sh`**

Deploy CloudWatch dashboard:

```bash
#!/bin/bash
# Deploy CloudWatch dashboard for SRE Agent

set -e

DASHBOARD_NAME="${DASHBOARD_NAME:-SREAgentObservability}"
REGION="${AWS_REGION:-us-east-1}"

echo "Deploying CloudWatch Dashboard: $DASHBOARD_NAME"

aws cloudwatch put-dashboard \
  --dashboard-name "$DASHBOARD_NAME" \
  --dashboard-body "file://dashboards/cloudwatch-dashboard.json" \
  --region "$REGION"

echo "Dashboard deployed successfully!"
echo "View at: https://console.aws.amazon.com/cloudwatch/dashboards?region=$REGION#dashboards:name=$DASHBOARD_NAME"
```

### 5. Documentation

**File: `docs/OBSERVABILITY_GUIDE.md`**

Comprehensive guide covering:
- Observability architecture overview
- OTEL instrumentation patterns
- Custom metrics reference
- Span naming conventions
- Dashboard usage guide
- Best practices for production monitoring

**File: `docs/TROUBLESHOOTING_PLAYBOOK.md`**

Production troubleshooting guide:
- Common issues and CloudWatch queries
- Performance bottleneck identification
- Error correlation procedures
- Memory operation debugging
- Multi-agent coordination issues

## Technical Requirements

### Dependencies

Add to `pyproject.toml`:
```toml
dependencies = [
    # Existing dependencies...
    "opentelemetry-api>=1.20.0",
    "opentelemetry-sdk>=1.20.0",
    "opentelemetry-instrumentation-langchain>=0.10.0",
    "opentelemetry-exporter-otlp-proto-grpc>=1.20.0",
    "aws-opentelemetry-distro>=0.10.1",
    "boto3>=1.28.0",  # For CloudWatch metrics
]
```

### Environment Variables

Add to `.env.example`:
```bash
# Observability Configuration
OTEL_EXPORTER_OTLP_ENDPOINT=https://cloudwatch-otel.us-east-1.amazonaws.com
OTEL_SERVICE_NAME=sre-agent
OTEL_TRACES_SAMPLER=always_on
AWS_XRAY_DAEMON_ADDRESS=127.0.0.1:2000
CLOUDWATCH_METRICS_NAMESPACE=SREAgent/Production
```

### AWS Permissions

Required IAM permissions for CloudWatch:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData",
        "xray:PutTraceSegments",
        "xray:PutTelemetryRecords",
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

## Implementation Details

### Custom Span Attributes Standard

All spans should include:
```python
# Standard attributes
"sre.user_id": str
"sre.session_id": str
"sre.query": str
"sre.timestamp": str (ISO 8601)

# Agent-specific
"sre.agent_type": str  # supervisor, kubernetes, logs, metrics, runbooks
"sre.agents_selected": str  # Comma-separated list
"sre.routing_reason": str

# Tool-specific
"sre.tool_name": str
"sre.tool_params": str  # JSON-serialized
"sre.tools_invoked": int

# Memory-specific
"memory.namespace": str
"memory.strategy": str  # user_preferences, infrastructure, investigations
"memory.results_count": int
"memory.cache_hit": bool
```

### Metric Dimensions

CloudWatch metrics with dimensions:
```python
Namespace: SREAgent/Production

Metrics:
- AgentInvocation
  Dimensions: [AgentName, UserID]
  Unit: Milliseconds

- ToolExecution
  Dimensions: [ToolName, AgentName]
  Unit: Milliseconds

- MemoryOperation
  Dimensions: [Operation, Strategy]
  Unit: Milliseconds

- EscalationTriggered
  Dimensions: [UserID, EscalationType]
  Unit: Count
```

## Demo Scenarios (Must-Have for Demonstrations)

### Scenario 1: Cross-Domain Investigation (7 minutes)

**Query:** "API response times have degraded 3x in the last hour"

**Expected Trace:**
- Supervisor analyzes query (span: 1.2s)
- Retrieves Alice's user preferences from memory (span: 0.3s)
- Routes to 3 agents in parallel
  - Metrics Agent: Gets performance metrics (span: 3.2s)
  - Kubernetes Agent: Checks pod health (span: 2.1s)
  - Logs Agent: Searches for errors (span: 1.8s)
- Supervisor aggregates results (span: 0.8s)
- Total investigation time: ~5.5s

**Observable Points:**
- Multi-agent coordination visible in X-Ray
- Parallel execution of agents
- Memory retrieval timing
- Bottleneck identification (Metrics Agent slowest)
- Custom attributes show routing decision

### Scenario 2: Memory Context Impact (5 minutes)

**Query:** "Database pods are crash looping in production"

**Two Users:**
- Alice (Technical): Detailed technical analysis
- Carol (Executive): Business impact focus

**Expected Trace Comparison:**
- Same initial investigation steps
- Different memory retrieval (different user namespaces)
- Same technical findings
- Different report generation time (Alice: 1.2s, Carol: 0.6s)
- Custom metric: `escalation_triggered=true` for Carol only

**Observable Points:**
- Memory namespace routing
- User preference impact on processing
- Escalation decision trace
- Personalization overhead measurement

### Scenario 3: Live Error Troubleshooting (3 minutes)

**Setup:** Kill Kubernetes backend server before query

**Query:** "Check cluster health"

**Expected Trace:**
- Supervisor routes to Kubernetes Agent
- K8s tool execution fails (connection refused to port 8011)
- Error propagates with full context
- Retry attempts visible in sub-spans
- Fallback to available agents
- Error recorded in CloudWatch Logs with correlation ID

**Observable Points:**
- Real-time error visualization in X-Ray
- Error propagation across agents
- Retry logic visibility
- Time to identify root cause (<30 seconds)
- CloudWatch Logs correlation

## Acceptance Criteria

### Functionality
- [ ] OTEL instrumentation added to supervisor, all 4 specialist agents, and memory client
- [ ] Custom CloudWatch metrics published for agent invocations, tool executions, memory operations
- [ ] X-Ray traces show complete request flow from supervisor through agents to backend APIs
- [ ] CloudWatch dashboard displays all 5 panels correctly
- [ ] Span attributes follow naming conventions and include all required fields
- [ ] Error traces include full context and correlation IDs

### Demo Readiness
- [ ] All 3 demo scenarios execute successfully and generate clean traces
- [ ] Demo orchestration script runs end-to-end without manual intervention
- [ ] CloudWatch dashboard shows real-time updates during demo execution
- [ ] Can identify bottleneck in cross-domain investigation in <30 seconds
- [ ] Memory context differences visible in traces for Alice vs Carol
- [ ] Live error scenario shows failure point clearly in X-Ray

### Documentation
- [ ] OBSERVABILITY_GUIDE.md includes architecture diagrams and instrumentation patterns
- [ ] TROUBLESHOOTING_PLAYBOOK.md covers common issues with CloudWatch Insights queries
- [ ] Code comments explain span creation and metric recording
- [ ] README.md updated with observability setup instructions
- [ ] Dashboard JSON includes descriptions for each panel

### Code Quality
- [ ] All Python code follows project coding standards (CLAUDE.md)
- [ ] Private functions use underscore prefix
- [ ] Type hints on all function parameters
- [ ] Logging uses standard format from logging_config.py
- [ ] No hardcoded values (use constants or config)
- [ ] Code passes `uv run python -m py_compile` for all modified files

## Testing Checklist

### Unit Tests
- [ ] Test span creation with various attribute combinations
- [ ] Test metric recording with different dimensions
- [ ] Test trace ID generation and correlation
- [ ] Test error handling in instrumentation code
- [ ] Mock CloudWatch client for metric tests

### Integration Tests
- [ ] End-to-end trace generation for simple query
- [ ] Multi-agent trace with all 4 specialists
- [ ] Memory operation tracing with all 3 strategies
- [ ] Error propagation through agent chain
- [ ] Dashboard deployment and validation

### Performance Tests
- [ ] Instrumentation overhead <5% of total execution time
- [ ] No memory leaks in long-running investigations
- [ ] Trace propagation latency <50ms
- [ ] Metric publishing does not block agent execution

### Demo Validation
- [ ] Run each scenario 5 times to verify consistency
- [ ] Validate traces appear in CloudWatch X-Ray within 10 seconds
- [ ] Verify dashboard metrics update within 1 minute
- [ ] Test on fresh AWS account to validate IAM permissions
- [ ] Validate with both Amazon Bedrock and Anthropic Claude providers

## Documentation Requirements

### Code Documentation
- [ ] Docstrings for all public functions following Google style
- [ ] Inline comments explaining OTEL concepts for developers unfamiliar with observability
- [ ] Type hints for all parameters and return values
- [ ] Example code snippets in OBSERVABILITY_GUIDE.md

### User-Facing Documentation
- [ ] Step-by-step setup instructions for CloudWatch observability
- [ ] Screenshots of dashboard panels
- [ ] Troubleshooting section with common issues
- [ ] CloudWatch Insights query examples
- [ ] Best practices for production monitoring

### Reference Documentation
- [ ] Complete span attribute reference table
- [ ] Metric dimension reference table
- [ ] Dashboard panel descriptions
- [ ] CloudWatch IAM permission requirements
- [ ] OTEL configuration reference

## Success Metrics

### Technical Metrics
- Distributed traces show all 5 agents and tool executions
- Trace depth accurately represents agent hierarchy (supervisor -> specialists)
- Custom attributes appear correctly in X-Ray console
- Metrics publish to CloudWatch within 60 seconds
- Dashboard updates in real-time during investigations

### Demonstration Metrics
- Can execute all 3 scenarios in <20 minutes total
- Bottleneck identification time <30 seconds using X-Ray
- Error root cause identification time <2 minutes
- Dashboard provides actionable insights without manual log searching
- Demonstrates clear value of observability for production AI systems

### User Experience Metrics
- Setup instructions can be followed without AWS expertise
- CloudWatch dashboard is self-explanatory to SRE teams
- Troubleshooting playbook accelerates issue resolution
- Observability overhead does not impact agent response times
- Documentation enables teams to replicate patterns in their systems

## Dependencies

### Upstream
- Existing SRE-agent functionality must remain unchanged
- Backend API servers must continue to work without modification
- AgentCore Gateway integration must remain compatible
- Memory system functionality preserved

### External Services
- AWS CloudWatch (logs, metrics, X-Ray)
- AWS IAM (permissions for CloudWatch access)
- OpenTelemetry Collector (optional for local development)

### Blockers
None identified. Implementation can proceed immediately.

## Related Issues

This enhancement builds on the existing SRE-agent use case and complements:
- AgentCore Runtime deployment capabilities
- AgentCore Gateway observability primitives
- Amazon Bedrock Agent Memory integration

## Future Enhancements (Out of Scope)

The following are explicitly out of scope for this issue but could be future work:
- Braintrust integration (separate observability platform)
- Custom alerting rules based on metrics
- Automated performance regression detection
- Cost optimization recommendations based on trace data
- Integration with third-party APM tools
- Real-time dashboard streaming to browser
