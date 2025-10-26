# AIM3314: Debug, trace, improve: Observability for agentic applications

re:Invent 2025 - Chalk Talk - 300 Level

---

## Slide 1: The Observability Challenge in Agentic Systems

### Traditional Applications vs Agentic Systems

**Traditional Microservices:**
- Predictable request/response flow
- Well-defined service boundaries
- Linear execution paths
- Static performance baselines

**Agentic Systems:**
- Non-deterministic reasoning chains
- Dynamic tool selection and sequencing
- Multi-agent coordination and handoffs
- Context-dependent memory retrieval
- Variable token consumption
- Emergent failure modes

### The Questions We Can't Answer (Yet)

**Production Incidents:**
- "Why did my agent choose the wrong tool?"
- "Which agent in my multi-agent system is the bottleneck?"
- "Why did this query cost 10x more tokens than usual?"
- "How do I trace a user conversation across multiple agent invocations?"
- "Why did my agent hallucinate instead of using available tools?"
- "Which memory retrieval is slowing down my response time?"

### Today's Goal

**Build observability patterns that answer these questions using:**
- OpenTelemetry distributed tracing
- Amazon CloudWatch metrics and dashboards
- Structured logging with correlation
- Amazon Bedrock AgentCore automatic instrumentation

**Two Demos:**
1. Simple: Hello World agent - Learn the basics
2. Complex: Multi-agent SRE system - Production patterns

---

## Slide 2: Amazon Bedrock AgentCore Observability Overview

### What is AgentCore Observability?

**Service-Provided Instrumentation:**
- Automatic trace generation for agents, memory, gateway, tools
- CloudWatch generative AI observability page
- OpenTelemetry-compatible span export
- X-Ray integration for distributed tracing
- No code changes required for basic telemetry

**Custom Instrumentation:**
- Add your own spans for business logic
- Custom metrics for performance tracking
- Structured attributes for filtering
- Context propagation across async boundaries

### The Observability Stack

```
┌─────────────────────────────────────────────────────────┐
│                    CloudWatch Console                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Dashboard   │  │  X-Ray Trace │  │  Log Insights│  │
│  │   Metrics    │  │    Viewer    │  │   Queries    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
                           ▲
                           │ OTEL Spans + Metrics + Logs
                           │
┌─────────────────────────────────────────────────────────┐
│            Amazon Bedrock AgentCore Services            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │  Agent   │  │ Memory   │  │ Gateway  │  │  Tools  │ │
│  │ Runtime  │  │ Service  │  │   (MCP)  │  │         │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
└─────────────────────────────────────────────────────────┘
                           ▲
                           │ Your Agent Code
                           │
┌─────────────────────────────────────────────────────────┐
│              Your Agentic Application                   │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Agent Framework (Strands, LangGraph, etc.)     │   │
│  │  + Custom OTEL Instrumentation                  │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Key Capabilities

**Automatic Instrumentation:**
- Agent invocation spans (input, output, latency, tokens)
- Memory operations (retrieval, storage, namespace)
- Gateway tool calls (request, response, errors)
- Error propagation with stack traces

**What You Add (Custom Spans):**
- Business logic decision points
- Multi-agent routing logic
- Complex memory strategies
- Tool selection reasoning
- Performance-critical sections

**CloudWatch Integration:**
- Transaction Search for trace exploration
- Pre-built dashboards for gen AI workloads
- Log correlation via trace IDs
- Custom metrics for your KPIs

### Setup Required (One-Time)

```bash
# 1. Enable CloudWatch Transaction Search
aws bedrock-agentcore enable-transaction-search \
  --region us-east-1

# 2. Configure OTEL environment (for self-hosted agents)
export OTEL_EXPORTER_OTLP_ENDPOINT="https://your-collector.amazonaws.com"
export OTEL_SERVICE_NAME="my-agent-system"
export OTEL_TRACES_SAMPLER="parentbased_always_on"

# 3. Agent code (automatic for Runtime-hosted, manual for self-hosted)
# Runtime-hosted: Zero code changes
# Self-hosted: Add 5 lines of OTEL initialization
```

---

## Slide 3: Demo 1 - Simple Hello World Agent

### Architecture: The Basics

```
┌─────────────────────────────────────────────────────────┐
│                         User                            │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ "What's the weather in Seattle
                     │  and what time is it there?"
                     ▼
┌─────────────────────────────────────────────────────────┐
│          AgentCore Runtime (Managed Hosting)            │
│  ┌──────────────────────────────────────────────────┐   │
│  │         Strands Agent (Weather Assistant)        │   │
│  │  - Automatic OTEL span creation                  │   │
│  │  - Structured logging                            │   │
│  │  - Token usage tracking                          │   │
│  └────────────────────┬─────────────────────────────┘   │
└────────────────────────┼───────────────────────────────┘
                         │
                         │ Tool calls via MCP
                         ▼
┌─────────────────────────────────────────────────────────┐
│              AgentCore Gateway (MCP Tools)              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   Weather   │  │  World Time │  │ Calculator  │     │
│  │   Service   │  │   Service   │  │   Service   │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
              CloudWatch + X-Ray Traces
```

### What We'll Observe

**Scenario 1: Successful Query**
- Agent span: input prompt, model invocation, token count
- Tool selection span: reasoning, chosen tools
- Gateway spans: weather API call, time API call
- Total latency breakdown: reasoning vs tool execution
- Structured logs: correlation ID across all components

**Scenario 2: Tool Error**
- Query: "Calculate the factorial of -5"
- Agent selects calculator tool correctly
- Tool returns error (negative input invalid)
- Error propagated through spans with status code
- CloudWatch shows error in X-Ray trace tree
- Logs contain exception details

**Scenario 3: CloudWatch Dashboard**
- Request rate (requests/minute)
- P50/P90/P99 latency distribution
- Error rate by tool
- Token consumption over time
- Success rate by query type

### Key Observability Patterns

**Pattern 1: Trace Correlation**
```python
# Automatic in AgentCore Runtime
# Each request gets unique trace ID
# All spans linked via parent-child relationships
# Logs contain trace ID for correlation
```

**Pattern 2: Structured Attributes**
```python
# Agent span attributes (automatic)
{
  "agent.id": "weather-assistant",
  "agent.framework": "strands",
  "model.id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
  "input.tokens": 124,
  "output.tokens": 87,
  "latency_ms": 1234
}

# Tool span attributes (automatic)
{
  "tool.name": "get_weather",
  "tool.input": '{"city": "Seattle"}',
  "tool.status": "success",
  "tool.latency_ms": 234
}
```

**Pattern 3: Error Handling**
```python
# Errors automatically recorded in spans
{
  "error": true,
  "error.type": "ToolExecutionError",
  "error.message": "Invalid input: negative numbers not supported",
  "status": "ERROR"
}
```

### Demo Flow (15 minutes)

**Minutes 0-2: Setup**
- Show deployed architecture
- Explain AgentCore Runtime benefits (zero infra management)
- Show Gateway with 3 MCP tools pre-configured

**Minutes 2-5: Baseline Query**
- Execute: "What's the weather in Seattle and what time is it there?"
- Live view CloudWatch Logs streaming
- Open X-Ray trace viewer
- Walk through span hierarchy: agent → tool_selection → gateway → weather_tool
- Highlight: No code changes needed for this telemetry

**Minutes 5-10: Error Scenario**
- Execute: "Calculate the factorial of -5"
- Show error in CloudWatch real-time
- Navigate X-Ray trace to failure point
- Examine error attributes in span
- Show how to find root cause in 30 seconds
- Explain: This is what production debugging looks like

**Minutes 10-13: Dashboard Review**
- Open pre-configured CloudWatch dashboard
- Metrics: latency (P90 = 1.2s), success rate (98.7%), token usage (avg 210/request)
- Show how to set alarms: latency > 3s, error rate > 5%
- Discuss: What to monitor in production

**Minutes 13-15: Q&A / Transition**
- Key takeaway: "Zero code, full visibility"
- Transition: "But what about complex multi-agent systems?"

### Code Sample (What You Write)

```python
# File: simple_observability_demo.py
import logging
import boto3
from typing import Dict, Any

# Configure logging (automatically includes trace IDs)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def invoke_agent(query: str) -> Dict[str, Any]:
    """
    Invoke AgentCore Runtime-hosted agent.
    OTEL instrumentation is automatic - no additional code needed.
    """
    client = boto3.client("bedrock-agentcore-runtime")

    logger.info(f"Invoking agent with query: {query}")

    response = client.invoke_agent(
        agentId="weather-assistant-123",
        inputText=query,
        enableTrace=True,  # Enable detailed tracing
    )

    logger.info("Agent response received")
    return response


def main():
    # Scenario 1: Multi-tool query
    query1 = "What's the weather in Seattle and what time is it there?"
    result1 = invoke_agent(query1)
    print(f"Result: {result1['output']}")

    # Scenario 2: Error scenario
    query2 = "Calculate the factorial of -5"
    result2 = invoke_agent(query2)
    print(f"Result: {result2['output']}")


if __name__ == "__main__":
    main()
```

**That's it. 40 lines. Full observability.**

---

## Slide 4: Demo 2 - Complex Multi-Agent SRE System

### Architecture: Production Complexity

```
┌────────────────────────────────────────────────────────────────────┐
│                              User Query                            │
│          "API response times degraded 3x in last hour"             │
└───────────────────────────────┬────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│                        Supervisor Agent                            │
│  - Route query to appropriate specialist agents                   │
│  - Retrieve user preferences from memory (Alice: technical SRE)    │
│  - Coordinate multi-agent investigation                            │
│  - Aggregate findings and generate report                          │
└──┬──────────────────┬──────────────────┬──────────────────────┬────┘
   │                  │                  │                      │
   │ "Check K8s"      │ "Search logs"    │ "Get metrics"        │ "Escalate?"
   ▼                  ▼                  ▼                      ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐
│ Kubernetes  │  │ Application │  │ Performance │  │  Operational     │
│ Infra Agent │  │ Logs Agent  │  │ Metrics Agt │  │ Runbooks Agent   │
│             │  │             │  │             │  │                  │
│ 5 K8s tools │  │ 5 log tools │  │ 5 metric    │  │ 5 runbook tools  │
└──────┬──────┘  └──────┬──────┘  │   tools     │  └────────┬─────────┘
       │                │         └──────┬──────┘           │
       │                │                │                  │
       │         ┌──────┴────────────────┴──────────────────┘
       │         │
       ▼         ▼
┌────────────────────────────────────────────────────────────────────┐
│                 AgentCore Gateway (MCP Tools)                      │
│                      20 Tools Distributed                          │
└──┬──────────────────┬──────────────────┬──────────────────────┬───┘
   │                  │                  │                      │
   ▼                  ▼                  ▼                      ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ K8s API     │  │ Logs API    │  │ Metrics API │  │ Runbooks    │
│ Server      │  │ Server      │  │ Server      │  │ API Server  │
│ (FastAPI)   │  │ (FastAPI)   │  │ (FastAPI)   │  │ (FastAPI)   │
│ Port 8011   │  │ Port 8012   │  │ Port 8013   │  │ Port 8014   │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘

        ┌────────────────────────────────────────────────┐
        │      AgentCore Memory (3 Strategies)          │
        │  ┌─────────────┐  ┌─────────────┐  ┌────────┐ │
        │  │    User     │  │ Infra       │  │Investig│ │
        │  │ Preferences │  │ Knowledge   │  │History │ │
        │  │  (90-day)   │  │  (30-day)   │  │(30-day)│ │
        │  └─────────────┘  └─────────────┘  └────────┘ │
        └────────────────────────────────────────────────┘

              CloudWatch + X-Ray (Distributed Tracing)
```

### System Characteristics

**Complexity Dimensions:**
- 5 agents (1 supervisor + 4 specialists)
- 20 tools across 4 backend domains
- 3 memory strategies (user prefs, infrastructure knowledge, investigation history)
- 2 user personas (Alice: technical SRE, Carol: executive)
- 6 production scenarios (cross-domain, error cascade, personalization, multi-turn)

**Observability Challenges:**
- Which agent is the bottleneck?
- Why was agent X invoked but not agent Y?
- How does memory impact routing decisions?
- What's the critical path for this investigation?
- How do Alice vs Carol queries differ in execution?

### Custom Instrumentation: What We Added

**Supervisor Agent (40 lines of OTEL code):**
```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

def route_to_agents(self, query: str) -> List[str]:
    with tracer.start_as_current_span("supervisor.route_decision") as span:
        # Add context
        span.set_attribute("query", query)
        span.set_attribute("user_id", self.user_id)

        # Memory retrieval with sub-span
        with tracer.start_as_current_span("memory.get_preferences"):
            prefs = self.memory_client.get_user_preferences()
            span.set_attribute("preference_count", len(prefs))
            span.set_attribute("user_role", prefs.get("role"))

        # Routing logic
        agents = self._determine_agents(query, prefs)
        span.set_attribute("agents_selected", agents)
        span.set_attribute("agent_count", len(agents))

        logger.info(f"Routing to agents: {agents}")
        return agents
```

**Agent Nodes (60 lines of OTEL code):**
```python
def execute_k8s_agent(state: dict) -> dict:
    with tracer.start_as_current_span("agent.k8s.execute") as span:
        span.set_attribute("agent.type", "kubernetes")
        span.set_attribute("tools.available", 5)

        start_time = time.time()

        try:
            result = self._invoke_agent(state)

            # Performance metrics
            execution_time = time.time() - start_time
            span.set_attribute("execution_time_ms", execution_time * 1000)
            span.set_attribute("tools.invoked", len(result.get("tool_calls", [])))
            span.set_attribute("findings.count", len(result.get("findings", [])))

            span.set_status(Status(StatusCode.OK))
            return result

        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            logger.exception("K8s agent failed")
            raise
```

**Memory Client (80 lines of OTEL code):**
```python
def get_relevant_memories(self, query: str, strategy: str) -> List[dict]:
    with tracer.start_as_current_span("memory.retrieval") as span:
        span.set_attribute("memory.strategy", strategy)
        span.set_attribute("query.length", len(query))

        # Vector search
        with tracer.start_as_current_span("memory.vector_search"):
            results = self._search(query, strategy)
            span.set_attribute("results.count", len(results))

            # Cache metrics
            cache_hit = self._cache_hit(query)
            span.set_attribute("cache.hit", cache_hit)

        # Post-processing
        with tracer.start_as_current_span("memory.post_process"):
            filtered = self._filter_by_retention(results, strategy)
            span.set_attribute("results.filtered", len(filtered))

        logger.debug(f"Memory retrieval: {len(filtered)} results from {strategy}")
        return filtered
```

**Total Custom Code: ~400 lines across 8 files**

### Demo Scenarios (6 Production Patterns)

**Scenario 1: Cross-Domain Infrastructure Degradation (8 min)**
- Query: "API response times have degraded 3x in the last hour" (Alice)
- Complexity: HIGH - 4 agents, 10+ tools, parallel execution
- Observability Focus:
  - Supervisor routes to K8s, Logs, Metrics agents (not Runbooks)
  - Alice preferences: technical detail, Slack channel for team
  - X-Ray trace shows parallel agent execution
  - Metrics agent is bottleneck (3.2s vs 1.1s for others)
  - Custom span attributes reveal memory cache hit for Alice prefs
  - Findings aggregated from 3 domains

**Scenario 2: Database Crash Loop with Escalation (7 min)**
- Query: "Our database pods are crash looping in production" (Carol)
- Complexity: HIGH - Error cascade, memory-based escalation
- Observability Focus:
  - Carol preferences: executive summary, escalation to VP Engineering
  - K8s agent finds pod errors, Logs agent confirms crash patterns
  - Memory retrieval: past incident with same symptoms
  - Runbooks agent invoked for escalation procedure
  - X-Ray shows error propagation vs Scenario 1's success path
  - Custom metrics: investigation_time_ms, escalation_triggered=true

**Scenario 3: Performance Baseline Violation (6 min)**
- Query: "API gateway seems slower than normal"
- Complexity: MEDIUM - Historical comparison via infrastructure memory
- Observability Focus:
  - Memory span: retrieve historical baselines (infrastructure knowledge)
  - Metrics agent compares current vs baseline (custom span attribute)
  - Trace shows memory retrieval (650ms) as significant latency contributor
  - Dashboard: memory hit rate = 87%, cache helping performance

**Scenario 4: Multi-Turn Conversation (5 min)**
- Query 1: "Check production cluster health"
- Query 2: "What about auth-service specifically?"
- Query 3: "Show me the error logs"
- Complexity: VERY HIGH - Conversation memory, context across requests
- Observability Focus:
  - Session ID correlation across 3 X-Ray traces
  - Conversation memory spans show context retrieval
  - Query 2 references findings from Query 1 (stored in conversation history)
  - Query 3 narrows focus based on Query 2 (memory-driven)
  - CloudWatch Insights query: filter by session_id, see full conversation

**Scenario 5: Live Error Injection (4 min)**
- Action: Kill K8s backend server during investigation
- Observability Focus:
  - Real-time tool timeout in X-Ray (spans show pending status)
  - Error annotation appears in span: "Connection refused to :8011"
  - CloudWatch alarm triggers (error rate > 5%)
  - Logs show retry attempts (3 retries with exponential backoff)
  - How to identify failing backend from trace attributes
  - Recovery: restart server, see success in next query

**Scenario 6: User Personalization Comparison (time permitting)**
- Same query from Alice vs Carol side-by-side
- Show different execution paths due to memory preferences
- Different report formats (technical vs executive)

### Demo Flow (30 minutes)

**Minutes 0-3: Architecture Walkthrough**
- Draw system on whiteboard (chalk talk!)
- Explain 5 agents, 4 backends, 3 memory strategies
- Emphasize: This is a real production pattern

**Minutes 3-11: Scenario 1 (Cross-Domain)**
- Execute query from Alice
- Live CloudWatch dashboard: all 5 agents visible, 4 active
- Navigate X-Ray trace tree: supervisor → 4 agents → 10 tool calls
- Identify bottleneck: Metrics agent (3.2s)
- Show custom span attributes: routing decisions, memory cache hits
- Structured logs: correlation ID links all components

**Minutes 11-18: Scenario 2 (Error Cascade)**
- Execute same type of query from Carol
- Side-by-side comparison: Alice trace vs Carol trace
- Memory retrieval differences (technical vs executive preferences)
- Show escalation trigger in custom metrics
- Error propagation vs Scenario 1's success

**Minutes 18-24: Scenario 3 + 4 (Memory + Multi-Turn)**
- Performance baseline query (infrastructure memory in action)
- Multi-turn conversation (session correlation)
- CloudWatch Insights query: filter by session_id
- Show context evolution across 3 requests

**Minutes 24-28: Scenario 5 (Live Break/Fix)**
- Kill K8s backend server
- Show real-time error in X-Ray
- Navigate to failure point
- CloudWatch alarm notification
- Restart server, demonstrate recovery

**Minutes 28-30: Transition to Best Practices**

### CloudWatch Dashboard (Multi-Panel)

**Panel 1: Agent Routing Heatmap**
- Which agents invoked for each query type
- Frequency matrix: Supervisor → Specialist

**Panel 2: Tool Execution Waterfall**
- Timeline view of all 20 tools
- Identify parallel vs sequential execution
- Latency by tool type

**Panel 3: Memory Operation Timing**
- Breakdown: vector search, cache lookup, post-processing
- Hit rate by strategy (user prefs: 95%, infra knowledge: 78%, history: 62%)

**Panel 4: Error Correlation**
- Error rate by agent type
- Tool failure patterns
- Escalation triggers

**Panel 5: User Persona Comparison**
- Alice vs Carol execution time distribution
- Memory retrieval differences
- Report generation latency

**All pre-configured, one-click open during demo**

---

## Slide 5: Best Practices & Evaluation Pipelines

### Span Naming Conventions

**Follow Semantic Conventions:**
```python
# Good: Hierarchical, descriptive
"supervisor.route_decision"
"agent.k8s.execute"
"memory.retrieval.vector_search"
"tool.gateway.get_weather"

# Bad: Flat, vague
"process"
"handle_request"
"step1"
"function_call"
```

**Key Attributes to Always Include:**
```python
# Required for filtering and analysis
span.set_attribute("agent.id", agent_id)
span.set_attribute("agent.type", agent_type)
span.set_attribute("user_id", user_id)
span.set_attribute("session_id", session_id)

# Performance metrics
span.set_attribute("latency_ms", latency)
span.set_attribute("token_count", tokens)

# Business context
span.set_attribute("query_type", query_type)
span.set_attribute("investigation_domain", domain)
```

### Custom Metrics for Production

**Core Metrics:**
```python
# Request metrics
agent_invocations_total (by agent_type)
tool_calls_total (by tool_name, status)
memory_operations_total (by strategy, operation)

# Latency metrics (milliseconds)
agent_latency_ms (P50, P90, P99)
tool_execution_ms (by tool_name)
memory_retrieval_ms (by strategy)

# Business metrics
investigations_completed_total
escalations_triggered_total
tokens_consumed_total (by agent_type)

# Error metrics
agent_errors_total (by error_type)
tool_failures_total (by tool_name)
memory_cache_hit_rate (by strategy)
```

**CloudWatch Alarms:**
```python
# Critical
- agent_errors_total > 5% of requests
- tool_failures_total > 10% for any single tool
- agent_latency_ms P99 > 10 seconds

# Warning
- memory_cache_hit_rate < 70%
- token_consumption > 2x baseline
- escalations_triggered > 3 per hour
```

### Structured Logging Best Practices

**Always Include:**
```python
logger.info(
    "Agent invocation completed",
    extra={
        "trace_id": trace_id,
        "span_id": span_id,
        "agent_id": agent_id,
        "user_id": user_id,
        "latency_ms": latency,
        "status": "success"
    }
)
```

**For Complex Objects (Pretty Print):**
```python
import json

logger.debug(
    f"Memory retrieval results:\n{json.dumps(results, indent=2, default=str)}"
)
```

**Debug Mode:**
```python
# Add --debug flag to your application
if args.debug:
    logging.getLogger().setLevel(logging.DEBUG)
```

### Root Cause Analysis (RCA) Workflow

**Step 1: Identify the Failing Request**
- CloudWatch Logs Insights query: filter by error status
- Get trace_id from error log

**Step 2: Open X-Ray Trace**
- Navigate to CloudWatch X-Ray console
- Search by trace_id
- View trace tree

**Step 3: Find the Failure Point**
- Look for spans with error status (red)
- Check span attributes for error details
- Examine parent span for context

**Step 4: Correlate with Logs**
- Use trace_id to filter CloudWatch Logs
- See detailed error messages and stack traces
- Check logs before/after failure

**Step 5: Check Related Metrics**
- Dashboard: Was this an isolated incident or pattern?
- Compare to baseline: Is this normal behavior?
- Other users affected? Filter metrics by user_id

**Step 6: Remediation**
- For tool errors: Check backend service health
- For agent errors: Review prompt and context
- For memory errors: Check retention policy and indexing

**Average RCA Time: 2-5 minutes** (vs 30+ minutes without observability)

### Evaluation Pipelines Integration

**Continuous Evaluation Architecture:**
```
Production Traces (CloudWatch)
        ↓
Extract trace_ids for sample queries
        ↓
Replay queries in test environment
        ↓
Compare outputs (production vs test)
        ↓
Evaluate quality metrics:
  - Correctness (did it answer the question?)
  - Efficiency (token usage, latency)
  - Tool selection (right tools for the job?)
  - Memory usage (relevant context retrieved?)
        ↓
Detect regressions before deployment
```

**Implementation:**
```python
# File: evaluation_pipeline.py
import boto3
from typing import List, Dict

def extract_production_queries(
    log_group: str,
    time_range_hours: int = 24
) -> List[Dict]:
    """
    Extract representative queries from production CloudWatch Logs.
    """
    logs = boto3.client("logs")

    query = """
    fields @timestamp, trace_id, query, user_id, agent_id
    | filter status = "success"
    | sort @timestamp desc
    | limit 100
    """

    results = logs.start_query(
        logGroupName=log_group,
        startTime=int(time.time() - (time_range_hours * 3600)),
        endTime=int(time.time()),
        queryString=query,
    )

    return results


def replay_and_evaluate(queries: List[Dict]) -> Dict:
    """
    Replay production queries in test environment and evaluate.
    """
    evaluation_results = {
        "total": len(queries),
        "passed": 0,
        "failed": 0,
        "regressions": []
    }

    for query in queries:
        # Replay in test environment
        test_result = invoke_test_agent(query["query"])

        # Get production trace for comparison
        prod_trace = get_trace(query["trace_id"])

        # Evaluate
        eval_result = evaluate_response(
            prod_result=prod_trace,
            test_result=test_result,
            criteria={
                "max_latency_delta_pct": 20,  # 20% slower is regression
                "token_usage_delta_pct": 30,  # 30% more tokens is regression
                "output_similarity_min": 0.8,  # 80% semantic similarity
            }
        )

        if eval_result["is_regression"]:
            evaluation_results["regressions"].append({
                "query": query["query"],
                "reason": eval_result["reason"]
            })
            evaluation_results["failed"] += 1
        else:
            evaluation_results["passed"] += 1

    return evaluation_results


# Run nightly or before deployments
if __name__ == "__main__":
    queries = extract_production_queries("my-agent-logs", time_range_hours=24)
    results = replay_and_evaluate(queries)

    if results["failed"] > 0:
        print(f"REGRESSION DETECTED: {results['failed']} queries failed")
        sys.exit(1)
    else:
        print(f"EVALUATION PASSED: {results['passed']}/{results['total']}")
```

### Production Checklist

**Before Deploying Agents to Production:**

- [ ] OTEL instrumentation configured
- [ ] CloudWatch Transaction Search enabled
- [ ] Custom spans added for critical business logic
- [ ] Structured logging with trace_id in all logs
- [ ] CloudWatch dashboard created with key metrics
- [ ] Alarms configured for error rates and latency
- [ ] RCA runbook documented for common failures
- [ ] Evaluation pipeline setup for regression detection
- [ ] Load testing with observability validation
- [ ] Team trained on trace analysis and debugging

**Monitoring Strategy:**

**Real-Time (During Incidents):**
- CloudWatch Dashboard: live metrics
- X-Ray Trace Viewer: identify failing components
- CloudWatch Logs Insights: detailed error messages

**Daily/Weekly Review:**
- Token usage trends (cost optimization)
- Latency distribution changes (performance regression)
- Tool selection patterns (agent behavior drift)
- Memory cache hit rates (memory optimization)

**Continuous (Automated):**
- Evaluation pipeline (nightly)
- Alarms for SLA violations
- Cost anomaly detection

### Key Takeaways

**1. Start Simple, Add Incrementally**
- AgentCore Runtime gives you automatic tracing (Demo 1)
- Add custom spans for your business logic (Demo 2)
- Don't over-instrument - focus on decision points

**2. Think in Traces, Not Logs**
- Traces show relationships and causality
- Logs provide detailed context
- Use trace_id to correlate both

**3. Memory = Hidden Complexity**
- Memory operations can be 40%+ of latency
- Cache hit rates directly impact cost
- Instrument memory strategies early

**4. Multi-Agent = Distributed System**
- Apply distributed tracing best practices
- Each agent is a microservice
- Supervisor routing is your load balancer

**5. Evaluation Prevents Regressions**
- Production traces are your test cases
- Continuous evaluation catches drift
- Observability enables safe iteration

**6. Observability is Not Optional**
- In production, agents WILL behave unexpectedly
- Without traces, debugging takes hours
- With traces, RCA takes minutes

---

## Q&A Discussion Topics

**Common Questions to Prepare For:**

**Q: How much overhead does OTEL add?**
A: Typically <5% latency overhead, <2% cost overhead. Much less than the cost of production incidents without observability.

**Q: Can I use third-party observability tools (Datadog, New Relic)?**
A: Yes, OTEL is vendor-neutral. Export to any OTEL-compatible backend. We showed AWS-native for simplicity.

**Q: What about PII in traces?**
A: Configure sampling and filtering. AgentCore supports redaction policies. Don't log raw user inputs.

**Q: How do I handle high cardinality attributes (user_id)?**
A: Use tags for filtering, not grouping. Aggregate metrics by agent_type, not user_id.

**Q: Cost of CloudWatch at scale?**
A: Use sampling (e.g., 10% of requests). Focus on errors and slow requests (tail sampling). Cost scales with trace volume, not agent complexity.

**Q: How to debug agents that use external APIs?**
A: Add custom spans around API calls. Propagate trace context via HTTP headers. Use OTEL auto-instrumentation for popular libraries (requests, httpx).

**Q: Multi-region observability?**
A: CloudWatch is regional. Use cross-region log aggregation or centralized OTEL collector. X-Ray supports cross-region trace correlation.

**Q: What about async agents and background tasks?**
A: Propagate context manually via `attach()` and `detach()`. Example in troubleshooting guide.

---

## Resources & Next Steps

**GitHub Repository:**
- Code for both demos: github.com/aws-samples/amazon-bedrock-agentcore-samples
- Observability tutorials: `/01-tutorials/06-AgentCore-observability`
- SRE multi-agent system: `/02-use-cases/SRE-agent`

**Documentation:**
- AgentCore Observability Guide: docs.aws.amazon.com/bedrock-agentcore/observability
- OpenTelemetry Best Practices: opentelemetry.io/docs/
- CloudWatch Gen AI Observability: docs.aws.amazon.com/cloudwatch/generative-ai

**Try It Yourself:**
- Deploy Demo 1 in 10 minutes: Follow simple_demo_scenarios.md
- Run SRE agent locally: Follow SRE-agent README
- Join office hours: [time/location TBD]

**Contact:**
- Questions? Github Issues on aws-samples repo
- Feedback? Session survey link
- AWS Support: For production assistance

---

## Thank You!

**Let's make agentic systems observable, debuggable, and production-ready.**

**Bring your production challenges - let's discuss!**

[Contact information]
[GitHub repository]
[AWS Bedrock AgentCore documentation]
