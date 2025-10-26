# SRE Agent - Comprehensive Codebase Analysis & Observability Demo Scenarios

## Executive Summary

The **SRE Agent** is an advanced multi-agent system built on Amazon Bedrock AgentCore that demonstrates enterprise-grade AI infrastructure for Site Reliability Engineering (SRE) operations. It showcases three AgentCore primitives (Runtime, Gateway, Memory) working together with sophisticated multi-agent orchestration, long-term memory persistence, and user personalization.

**Complexity Level:** Advanced  
**Agent Count:** 5 (1 Supervisor + 4 Specialists)  
**Tool Count:** 20+ MCP-based tools across 4 domains  
**Code Scale:** 6,171 Python files (including dependencies), ~5,000 lines of core agent code  
**Key Innovation:** Seamless integration of multiple AgentCore components for production-ready agent deployment

---

## 1. Architecture Overview

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    AgentCore Runtime                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Multi-Agent System (LangGraph)                          │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  Supervisor Agent (Router & Coordinator)           │  │  │
│  │  │  - Analyzes incoming queries                        │  │  │
│  │  │  - Retrieves relevant user memories                │  │  │
│  │  │  - Creates investigation plans                      │  │  │
│  │  │  - Routes to specialist agents                      │  │  │
│  │  │  - Personalizes findings based on user preferences │  │  │
│  │  │  - Aggregates results into coherent reports         │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  │           │                                                │  │
│  │  ┌────────┴──────┬──────────┬──────────┬──────────┐       │  │
│  │  ▼              ▼          ▼          ▼          ▼        │  │
│  │┌──────────┐ ┌──────────┐ ┌────────┐ ┌──────────┐         │  │
│  ││  K8s     │ │  Logs    │ │Metrics │ │Runbooks  │         │  │
│  ││ Agent    │ │  Agent   │ │ Agent  │ │  Agent   │         │  │
│  │└────┬─────┘ └────┬─────┘ └───┬────┘ └────┬─────┘         │  │
│  └─────┼──────────────┼─────────────┼──────────┼─────────────┘  │
└────────┼──────────────┼─────────────┼──────────┼────────────────┘
         │              │             │          │
         └──────────────┼─────────────┼──────────┘
                        │             │
                        ▼             ▼
    ┌────────────────────────────────────────┐
    │     AgentCore Gateway                  │
    │  ┌──────────────┐  ┌────────────────┐  │
    │  │ MCP Tools    │  │ Auth/Security  │  │
    │  │ (20+ tools)  │  │ (JWT tokens)   │  │
    │  └──────┬───────┘  └────────────────┘  │
    └─────────┼──────────────────────────────┘
              │
    ┌─────────┴──────────────────────────────┐
    │   Backend API Servers (Mock/Demo)      │
    │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ │
    │  │ K8s  │ │ Logs │ │Metrics│Runbks│ │
    │  │ API  │ │ API  │ │  API  │ API  │ │
    │  └──────┘ └──────┘ └──────┘ └──────┘ │
    └────────────────────────────────────────┘

    ┌──────────────────────────────────────────┐
    │   AgentCore Memory                       │
    │  ┌───────────────────────────────────┐   │
    │  │ User Preferences (90-day)         │   │
    │  │ Infrastructure Knowledge (30-day) │   │
    │  │ Investigation History (30-day)    │   │
    │  │ Conversation Messages (session)   │   │
    │  └───────────────────────────────────┘   │
    └──────────────────────────────────────────┘
```

---

## 2. Multi-Agent System Components

### 2.1 Agent Hierarchy & Responsibilities

#### Supervisor Agent
**Location:** `sre_agent/supervisor.py`  
**Responsibility:** Central orchestrator and decision-maker

**Key Functions:**
- Analyzes user queries to determine investigation strategy
- Retrieves user preferences and past investigations from AgentCore Memory
- Creates investigation plans (3-5 investigation steps)
- Routes queries to specialist agents based on domain expertise
- Coordinates multi-agent investigations through LangGraph workflow
- Personalizes findings based on user role and preferences
- Aggregates specialist responses into comprehensive reports
- Directly manages all memory interactions (only agent with memory access)

**Memory Interactions:**
- Retrieves user preferences via `retrieve_user_preferences()` tool
- Retrieves investigation history via `retrieve_investigation_history()` tool
- Stores investigation summaries and findings for future reference

**Agent Flow Control:**
```
Query → Supervisor → Plan Creation → Memory Retrieval → 
Routing Decision → Agent Dispatch → Result Aggregation → 
Report Generation → Memory Storage → Final Response
```

#### Kubernetes Infrastructure Agent
**Location:** `sre_agent/agent_nodes.py` (create_kubernetes_agent)  
**Tools Access:** 5 Kubernetes-focused tools

**Domain Expertise:**
- Pod status and health monitoring across namespaces
- Deployment configurations and rollout history
- Cluster events and anomalies
- Resource utilization (CPU, memory, disk)
- Node health and capacity planning

**Key Tools:**
- `get_pod_status` - Pod health, state, resource usage
- `get_deployment_status` - Deployment rollout status and history
- `get_cluster_events` - Recent cluster events for anomaly detection
- `get_resource_usage` - Infrastructure resource metrics
- `get_node_status` - Node health and capacity information

**Typical Investigation Flow:**
1. Agent queries for pod status in specific namespace
2. Identifies unhealthy pods (CrashLoopBackOff, Pending, etc.)
3. Checks deployment configurations
4. Retrieves cluster events for context
5. Returns findings to supervisor

#### Application Logs Agent
**Location:** `sre_agent/agent_nodes.py` (create_logs_agent)  
**Tools Access:** 5 log analysis tools

**Domain Expertise:**
- Full-text search across log streams
- Error log aggregation and categorization
- Log pattern detection and correlation
- Event time-based correlation across services
- Statistical analysis of log volumes and patterns

**Key Tools:**
- `search_logs` - Full-text search with regex support
- `get_error_logs` - Error and exception log extraction
- `analyze_log_patterns` - Recurring issue pattern detection
- `get_recent_logs` - Latest log entries by service
- `count_log_events` - Log event statistics and aggregation

**Typical Investigation Flow:**
1. Searches for error patterns matching incident
2. Correlates errors with time window
3. Analyzes log patterns for root cause
4. Identifies affected services
5. Returns contextual error information

#### Performance Metrics Agent
**Location:** `sre_agent/agent_nodes.py` (create_metrics_agent)  
**Tools Access:** 5 metrics-focused tools

**Domain Expertise:**
- Application performance metrics (response times, throughput)
- Error rate analysis and trend detection
- Resource utilization monitoring
- Availability and SLA tracking
- Historical trend analysis for capacity planning

**Key Tools:**
- `get_performance_metrics` - API response times, throughput data
- `get_error_rates` - Error rate trends and spike detection
- `get_resource_metrics` - CPU, memory, disk utilization
- `get_availability_metrics` - Service uptime and SLA data
- `analyze_trends` - Historical trend analysis

**Typical Investigation Flow:**
1. Queries performance metrics for affected service
2. Analyzes error rate changes
3. Correlates with resource utilization spikes
4. Identifies performance degradation patterns
5. Returns metric-based findings and trends

#### Operational Runbooks Agent
**Location:** `sre_agent/agent_nodes.py` (create_runbooks_agent)  
**Tools Access:** 5 operational procedure tools

**Domain Expertise:**
- Incident-specific playbooks for common scenarios
- Step-by-step troubleshooting guides
- Escalation procedures with contact information
- Common resolution patterns and best practices
- Service recovery procedures

**Key Tools:**
- `search_runbooks` - Find relevant operational procedures
- `get_incident_playbook` - Incident response guides
- `get_troubleshooting_guide` - Step-by-step debugging instructions
- `get_escalation_procedures` - Contact info and escalation paths
- `get_common_resolutions` - Known issue solutions

**Typical Investigation Flow:**
1. Searches runbooks matching incident type
2. Retrieves appropriate incident playbook
3. Gets escalation procedures if needed
4. Provides common resolutions
5. Returns procedural guidance

---

## 3. Backend API Infrastructure

### 3.1 Four-Domain Backend System

All backend servers are **mock/demo implementations** using FastAPI, designed to showcase how real systems would integrate. Each server provides OpenAPI specs that are automatically converted to MCP tools by the AgentCore Gateway.

#### Kubernetes API Server
**Port:** 8011 (configurable)  
**Implementation:** `backend/servers/k8s_server.py`  
**Data Source:** `backend/data/k8s_data/` (JSON files)

**Endpoints:** (via OpenAPI spec `backend/openapi_specs/k8s_api.yaml`)
- `GET /pods/status` - Retrieve pod information
- `GET /deployments/status` - Deployment rollout status
- `GET /cluster/events` - Cluster events
- `GET /resources/usage` - Resource utilization
- `GET /nodes/status` - Node health information

**Sample Data Files:**
- `pods.json` - Pod definitions with status, resource usage
- `deployments.json` - Deployment configurations
- `nodes.json` - Node information and capacity
- `events.json` - Cluster events with timestamps
- `resource_usage.json` - CPU/memory metrics

#### Logs API Server
**Port:** 8012 (configurable)  
**Implementation:** `backend/servers/logs_server.py`  
**Data Source:** `backend/data/logs_data/` (JSON files)

**Endpoints:** (via OpenAPI spec `backend/openapi_specs/logs_api.yaml`)
- `GET /logs/search` - Full-text log search
- `GET /logs/errors` - Error log extraction
- `GET /logs/patterns` - Pattern analysis
- `GET /logs/recent` - Recent log entries
- `GET /logs/count` - Log event statistics

**Sample Data Files:**
- `log_counts.json` - Log volume statistics by service
- `log_patterns.json` - Common log patterns and recurring issues

#### Metrics API Server
**Port:** 8013 (configurable)  
**Implementation:** `backend/servers/metrics_server.py`  
**Data Source:** `backend/data/metrics_data/` (JSON files)

**Endpoints:** (via OpenAPI spec `backend/openapi_specs/metrics_api.yaml`)
- `GET /metrics/performance` - Application performance metrics
- `GET /metrics/errors` - Error rate metrics
- `GET /metrics/resources` - Resource utilization
- `GET /metrics/availability` - Uptime and SLA data
- `GET /metrics/trends` - Trend analysis

**Sample Data Files:**
- `response_times.json` - API response time metrics
- `error_rates.json` - Error rate by service
- `throughput.json` - Request throughput metrics
- `resource_usage.json` - CPU/memory/disk usage
- `availability.json` - Service availability and SLA
- `trends.json` - Historical trend data

#### Runbooks API Server
**Port:** 8014 (configurable)  
**Implementation:** `backend/servers/runbooks_server.py`  
**Data Source:** `backend/data/runbooks_data/` (JSON + Markdown)

**Endpoints:** (via OpenAPI spec `backend/openapi_specs/runbooks_api.yaml`)
- `GET /runbooks/search` - Search operational procedures
- `GET /runbooks/incidents/{type}` - Incident playbooks
- `GET /runbooks/troubleshooting` - Troubleshooting guides
- `GET /runbooks/escalation` - Escalation procedures
- `GET /runbooks/resolutions` - Common solutions

**Sample Data Files:**
- `incident_playbooks.json` - Incident response procedures
- `troubleshooting_guides.json` - Step-by-step debugging
- `escalation_procedures.json` - Escalation contacts
- `common_resolutions.json` - Known issue solutions
- `service_recovery.json` - Service recovery procedures
- `markdown/` - Markdown documentation versions

### 3.2 API Authentication Pattern

**Authentication Mechanism:** Bearer token + API key header

**Flow:**
```
Backend Server Startup
  → Request API key from AWS Secrets Manager (Credential Provider)
  → Validate X-API-Key header on every request
  → Return 401 if invalid

AgentCore Gateway
  → Holds bearer token for authentication
  → Includes Authorization: Bearer {token} in MCP requests
  → Translates OpenAPI specs to MCP tools

Agent Tool Calls
  → Uses MCP tool with parameters
  → Gateway translates to REST API call with auth headers
  → Backend validates and returns data
```

---

## 4. AgentCore Gateway Integration

### 4.1 Gateway Architecture

**File:** `gateway/main.py`  
**Purpose:** HTTP-to-MCP protocol bridge with OpenAPI-driven tool discovery

**Key Components:**
- **MCP Server:** Exposes HTTP endpoint that speaks MCP protocol
- **OpenAPI Integration:** Automatically generates MCP tools from OpenAPI specs
- **Authentication:** JWT bearer tokens + API key validation
- **Health Monitoring:** Periodic health checks for all backend APIs
- **Tool Registration:** Registers 20+ tools from 4 backend domains

**Tool Generation Process:**
```
OpenAPI Spec (k8s_api.yaml)
  ↓
Schema Parsing (operation IDs, parameters, responses)
  ↓
Tool Definition Creation
  ↓
MCP Tool Registration
  ↓
Agent Tool Availability
```

### 4.2 Observability Configuration

**File:** `gateway/observability.py`

**Capabilities:**
- Enable CloudWatch Logs for vended log delivery
- Enable AWS X-Ray for trace collection
- Create log group: `/aws/vendedlogs/bedrock-agentcore/{resource_id}`
- Create delivery sources and destinations
- Establish delivery pipelines for logs and traces

**Function:** `enable_observability_for_resource()`
```python
# Creates CloudWatch infrastructure for monitoring
# Enables both application logs and distributed traces
# Routes to X-Ray for analysis
```

---

## 5. Long-Term Memory System

### 5.1 Amazon Bedrock AgentCore Memory Integration

**Location:** `sre_agent/memory/` directory  
**Components:**
- `memory/client.py` - SREMemoryClient class for memory operations
- `memory/config.py` - Memory system configuration
- `memory/tools.py` - Memory-based tools for agent access
- `memory/strategies.py` - Three memory strategies
- `memory/hooks.py` - Event hooks for automatic pattern extraction
- `memory/conversation_manager.py` - Multi-turn conversation tracking

### 5.2 Three Memory Strategies

#### 1. User Preferences Memory (90-day retention)
**Namespace:** `/sre/users/{user_id}/preferences`  
**Purpose:** Remember user-specific operational preferences

**Captures:**
- Escalation contacts and procedures
- Notification channels (Slack, email, etc.)
- Investigation workflow preferences
- Communication style preferences
- Role and responsibility information

**Example Data:**
```json
{
  "user_id": "Alice",
  "role": "Technical SRE Engineer",
  "escalation_contact": "alice.manager@company.com",
  "notification_channels": ["#alice-alerts", "#sre-team"],
  "investigation_style": "detailed",
  "timezone": "UTC"
}
```

#### 2. Infrastructure Knowledge Memory (30-day retention)
**Namespace:** `/sre/infrastructure/{user_id}/{session_id}`  
**Purpose:** Build understanding of infrastructure patterns and relationships

**Captures:**
- Service dependencies and relationships
- Failure patterns and common issues
- Configuration insights and best practices
- Performance baselines and thresholds
- Known problematic services

**Example Data:**
```json
{
  "service": "web-api",
  "depends_on": ["postgres-db", "redis-cache"],
  "failure_mode": "connection_timeout",
  "recovery_time": "2-5 minutes",
  "performance_baseline": "95ms"
}
```

#### 3. Investigation History Memory (30-day retention)
**Namespace:** `/sre/investigations/{user_id}/{session_id}`  
**Purpose:** Track investigation outcomes and findings

**Captures:**
- Investigation findings and resolutions
- Root causes identified
- Executed remediation steps
- Investigation timestamps and duration
- Outcome (resolved, escalated, etc.)

**Example Data:**
```json
{
  "investigation_id": "inv_20250115_001",
  "service": "payment-service",
  "issue": "API response times degraded",
  "root_cause": "Database connection pool exhaustion",
  "resolution": "Scaled database connections from 50 to 100",
  "timestamp": "2025-01-15T10:30:00Z",
  "outcome": "RESOLVED"
}
```

### 5.3 Conversation Memory Management

**File:** `sre_agent/memory/conversation_manager.py`

**Purpose:** Track multi-turn conversations and agent interactions

**Tracks:**
- User queries
- Agent responses
- Tool executions
- Tool results
- Investigation progress

**Message Types:**
- `USER` - User queries and commands
- `ASSISTANT` - Agent responses and reasoning
- `TOOL` - Tool call results and data

**Storage Model:**
```python
# Each conversation stored with metadata
{
  "user_id": "Alice",
  "session_id": "investigation_2025_01_15",
  "messages": [
    {"type": "USER", "content": "Why is payment-service slow?", "timestamp": "..."},
    {"type": "ASSISTANT", "content": "[Agent: Supervisor] Analyzing...", "timestamp": "..."},
    {"type": "TOOL", "content": "[Agent: Metrics] [Tool: get_performance_metrics] response_times: 500ms", "timestamp": "..."}
  ]
}
```

### 5.4 User Personalization Example

**Pre-configured Personas:** `scripts/user_config.yaml`

**Alice (Technical SRE):**
```yaml
user_id: Alice
role: Technical SRE Engineer
investigation_style: detailed
communication_style: technical
escalation_contact: alice.manager@company.com
notification_channels:
  - '#alice-alerts'
  - '#sre-team'
timezone: UTC
report_format: technical_exposition
include_troubleshooting_steps: true
```

**Carol (Executive/Director):**
```yaml
user_id: Carol
role: Engineering Director
investigation_style: executive_summary
communication_style: business_focused
escalation_contact: carol.director@company.com
notification_channels:
  - '#carol-executive'
  - '#strategic-alerts'
timezone: EST
report_format: business_focused
include_troubleshooting_steps: false
business_impact_focus: true
```

**Personalization Impact:**
When investigating identical incident (e.g., "API response times degraded 3x"):
- **Alice** receives: Detailed technical analysis, step-by-step troubleshooting, full tool references, comprehensive metrics
- **Carol** receives: Executive summary, business impact analysis, rapid escalation timeline, strategic implications

---

## 6. LangGraph Multi-Agent Orchestration

### 6.1 Graph Structure

**File:** `sre_agent/graph_builder.py`

**Graph Flow:**
```
START
  ↓
PREPARE (Extract query, initialize state)
  ↓
SUPERVISOR (Analyze, plan, route)
  ↓ (routing decision)
  ├─→ KUBERNETES_AGENT → SUPERVISOR
  ├─→ LOGS_AGENT → SUPERVISOR
  ├─→ METRICS_AGENT → SUPERVISOR
  ├─→ RUNBOOKS_AGENT → SUPERVISOR
  └─→ AGGREGATE (final response)
  ↓
END
```

**Node Implementations:**
- `prepare` - Initial state preparation
- `supervisor` - Central orchestration (SupervisorAgent class)
- `kubernetes_agent` - K8s domain specialist
- `logs_agent` - Logs domain specialist
- `metrics_agent` - Metrics domain specialist
- `runbooks_agent` - Runbooks domain specialist
- `aggregate` - Result aggregation and report generation

### 6.2 Supervisor Orchestration Logic

**Class:** `SupervisorAgent` in `sre_agent/supervisor.py`

**Decision Process:**
1. **Query Analysis** - Understand investigation requirements
2. **Memory Retrieval** - Get user preferences and context
3. **Plan Creation** - Create 3-5 investigation steps
4. **Routing Decisions** - Determine which agents to invoke
5. **Result Aggregation** - Combine specialist findings
6. **Report Personalization** - Format based on user preferences

**Routing Algorithm:**
```python
# Determine which agents to invoke based on query
if "kubernetes" or "pod" or "deployment" in query:
    route_to = "kubernetes_agent"
elif "logs" or "error" or "exception" in query:
    route_to = "logs_agent"
elif "metrics" or "performance" or "latency" in query:
    route_to = "metrics_agent"
elif "procedure" or "runbook" or "escalation" in query:
    route_to = "runbooks_agent"
else:
    # Multi-agent collaboration for complex queries
    route_to = ["kubernetes_agent", "logs_agent", "metrics_agent"]
```

---

## 7. Tool Management & MCP Protocol

### 7.1 Tool Categories

**Total Tools:** 20+ across 4 domains

**By Domain:**
- Kubernetes: 5 tools (pod, deployment, events, resources, nodes)
- Logs: 5 tools (search, errors, patterns, recent, count)
- Metrics: 5 tools (performance, errors, resources, availability, trends)
- Runbooks: 5 tools (search, incidents, troubleshooting, escalation, resolutions)
- Memory Tools: Multiple tools (retrieve preferences, history, etc.)
- Local Tools: `get_current_time` for context

### 7.2 Tool Invocation Flow

**Agent to Tool Flow:**
```
Agent: "I need to check pod status"
  ↓
LangChain React Agent: Selects tool → get_pod_status
  ↓
Tool Definition: {
  "name": "get_pod_status",
  "description": "Retrieve pod information",
  "parameters": {"namespace": "string", "pod_name": "string"}
}
  ↓
MCP Protocol: Translate to REST API call
  ↓
Backend Server: Process request, validate API key
  ↓
Return Results: JSON response with pod data
  ↓
Agent: Process results, continue investigation
```

### 7.3 Tool Filtering per Agent

**Config File:** `sre_agent/config/agent_config.yaml`

**Agent Tool Assignment:**
```yaml
kubernetes_agent:
  tools:
    - get_pod_status
    - get_deployment_status
    - get_cluster_events
    - get_resource_usage
    - get_node_status

logs_agent:
  tools:
    - search_logs
    - get_error_logs
    - analyze_log_patterns
    - get_recent_logs
    - count_log_events

# ... similar for metrics_agent and runbooks_agent

global_tools:
  - x-amz-bedrock-agentcore-search  # Available to all agents
```

**Tool Filtering Function:** `_filter_tools_for_agent()` in `agent_nodes.py`

---

## 8. Execution Modes & Deployment

### 8.1 Local Development Mode (CLI)

**Entry Point:** `sre_agent/cli.py` (main function)  
**Command:** `sre-agent --prompt "Your query"`

**Flow:**
1. Load environment variables from `.env`
2. Create MCP client connection to AgentCore Gateway
3. Load all tools from gateway
4. Build multi-agent graph
5. Execute graph with user query
6. Stream results to console
7. Save markdown report to `reports/` directory

**Example Execution:**
```bash
USER_ID=Alice sre-agent --prompt "API response times have degraded 3x in the last hour"
```

### 8.2 Interactive Mode

**Command:** `sre-agent --interactive`

**Features:**
- Multi-turn conversation with state persistence
- Commands: `/save`, `/load`, `/clear`, `/history`, `/savereport`, `/exit`
- Conversation state saved to `.multi_agent_conversation_state.json`
- Manual report saving with `/savereport` command

### 8.3 AgentCore Runtime Deployment

**File:** `sre_agent/agent_runtime.py`  
**Wrapper:** FastAPI server with `/invocations` endpoint

**Endpoint:**
```
POST /invocations
Content-Type: application/json

{
  "input": {
    "prompt": "Your query",
    "user_id": "Alice",
    "session_id": "session_id"
  }
}
```

**Response:**
```json
{
  "output": {
    "final_response": "Investigation findings...",
    "agents_invoked": ["kubernetes_agent", "logs_agent"],
    "metadata": {...}
  }
}
```

**Deployment Process:**
1. Build Docker container (ARM64 for AgentCore)
2. Push to Amazon ECR
3. Deploy to AgentCore Runtime
4. Expose via gateway endpoint
5. Enable observability via CloudWatch

---

## 9. Current Observability Implementation

### 9.1 Logging System

**Configuration:** `sre_agent/logging_config.py`

**Log Format:**
```
%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s
```

**Example Log Output:**
```
2025-01-15 10:30:45,p12345,{supervisor.py:125},INFO,Supervisor: Routing to kubernetes_agent
2025-01-15 10:30:45,p12345,{agent_nodes.py:230},INFO,Kubernetes Agent: Making 2 tool calls
2025-01-15 10:30:46,p12345,{multi_agent_langgraph.py:250},INFO,Tool response: get_pod_status (id: tool_call_123)
```

**Log Levels:**
- INFO: Major events (agent invocation, tool calls, routing decisions)
- WARNING: Non-critical issues (fallback behaviors, missing data)
- ERROR: Failures requiring attention (tool failures, agent crashes)
- DEBUG: Detailed execution traces (only with --debug flag)

### 9.2 Debug Mode

**Enable:** `--debug` flag or `DEBUG=true` environment variable

**Additional Output:**
- Detailed tool call arguments and results
- Full message traces through agent
- Memory operation details
- MCP protocol interactions

### 9.3 Report Generation

**Location:** `reports/{YYYY-MM-DD}/` directory

**Filename Format:** `{query}_{timestamp}.md` or `{query}_user_id_{user_id}_{timestamp}.md`

**Report Contents:**
- Investigation query
- Agent routing decisions
- Specialist findings by agent
- Memory-personalized formatting
- Timestamp and metadata

---

## 10. Excellent Observability Demo Scenarios

These scenarios showcase multi-agent interactions, memory personalization, tool coordination, and distributed tracing opportunities:

### Scenario 1: Cross-Domain Infrastructure Degradation

**Query:** "API response times have degraded 3x in the last hour"

**Complexity:** HIGH (5-step investigation, 4 agents)

**Agent Sequence:**
1. **Supervisor** - Analyzes query, retrieves user preferences
2. **Metrics Agent** - Gets performance metrics, identifies degradation pattern
3. **Kubernetes Agent** - Checks pod health, resource allocation, node status
4. **Logs Agent** - Searches for correlation errors, exceptions
5. **Runbooks Agent** - Retrieves incident playbook and escalation procedures
6. **Supervisor** - Aggregates findings into user-personalized report

**Observability Points:**
- Track tool call sequence and inter-agent coordination
- Monitor latency of each agent's operations
- Trace memory retrievals (user preferences, past incidents)
- Observe decision making at supervisor level
- Measure aggregation time for final report

**Memory Interactions:**
- Retrieve user's past similar investigations
- Check infrastructure knowledge for services involved
- Store new findings for future reference
- Track investigation outcome

### Scenario 2: Database Pod Crash Loop

**Query:** "Our database pods are crash looping in production"

**Complexity:** HIGH (multi-agent investigation with recovery)

**Agent Sequence:**
1. **Supervisor** - Escalation check via memory
2. **Kubernetes Agent** - Get pod status → identifies CrashLoopBackOff
3. **Logs Agent** - Extract error logs from pod containers
4. **Metrics Agent** - Check resource constraints, memory limits
5. **Runbooks Agent** - Get troubleshooting guide and recovery procedures
6. **Supervisor** - Determine escalation based on user preferences

**Observability Points:**
- Track error cascade through multiple agents
- Monitor time to identify root cause
- Trace memory-based escalation decision
- Observe agent-to-agent dependency (K8s findings trigger Logs investigation)
- Measure tool coordination complexity

**Memory Interactions:**
- Store crash loop pattern in infrastructure knowledge
- Record resolution steps for future incidents
- Update user preferences for escalation contacts

### Scenario 3: Performance Investigation with User Personalization

**Same Query, Different Users:**

**Query:** "Why is the payment-service slow?"

**User A (Alice - Technical):** `USER_ID=Alice sre-agent --prompt "Why is the payment-service slow?"`

**User B (Carol - Executive):** `USER_ID=Carol sre-agent --prompt "Why is the payment-service slow?"`

**Complexity:** MEDIUM (3-agent investigation, significant personalization difference)

**Agents Involved:** Metrics, Kubernetes, Logs

**Observability Points:**
- Compare report generation flow for different users
- Trace memory retrieval of different user preferences
- Monitor report formatting changes based on user role
- Observe escalation decision differences (technical vs business impact)
- Measure personalization overhead in aggregation step

**Memory Interactions:**
- Alice: Retrieve detailed technical preferences, troubleshooting style
- Carol: Retrieve business-focused preferences, executive communication channels
- Both: Store investigation findings in separate memory namespaces

### Scenario 4: Multi-Service Incident Investigation

**Query:** "Investigate the state of my cluster - I'm getting errors in multiple services"

**Complexity:** VERY HIGH (full multi-agent system exercising all domains)

**Agent Sequence:**
1. **Supervisor** - Complex query → multi-step plan creation
2. **Kubernetes Agent** - Comprehensive cluster health check
3. **Metrics Agent** - Performance metrics across all services
4. **Logs Agent** - Cross-service error correlation
5. **Runbooks Agent** - Multi-incident escalation procedures
6. **Supervisor** - Correlate findings, determine affected services

**Observability Points:**
- Monitor parallel agent execution
- Track inter-agent communication through supervisor
- Measure aggregation of multiple specialist findings
- Observe error correlation across services
- Trace complex routing decisions

**Memory Interactions:**
- Retrieve infrastructure knowledge about service dependencies
- Cross-reference past multi-service incidents
- Identify common failure patterns
- Update infrastructure knowledge with new dependencies discovered

### Scenario 5: Long-Running Investigation with Progressive Findings

**Query:** "I need a comprehensive health check of all production services"

**Mode:** Interactive conversation with follow-up questions

**Complexity:** VERY HIGH (demonstrates conversation memory, progressive investigation)

**Conversation Flow:**
```
User: Comprehensive health check
  ↓ (Supervisor creates full plan, invokes all agents)
System: Reports initial findings
User: Which services have issues?
  ↓ (Supervisor filters findings from memory)
System: Lists problematic services
User: What's the status of payment-service specifically?
  ↓ (Supervisor routes to Kubernetes, Metrics agents)
System: Detailed payment-service analysis
User: Escalate this issue
  ↓ (Supervisor checks memory for escalation contacts)
System: Issues escalation notification
```

**Observability Points:**
- Monitor conversation state persistence
- Track memory updates across conversation turns
- Measure context retention efficiency
- Observe conversation memory growth
- Trace how supervisor uses conversation context for routing

**Memory Interactions:**
- Each turn stored in conversation memory
- Supervisor leverages conversation history for context-aware routing
- Infrastructure knowledge updated with each discovered issue
- Investigation summary stored after resolution

### Scenario 6: Performance Baseline Violation

**Query:** "What's the status of my API gateway - it seems slower than normal"

**Complexity:** MEDIUM (requires historical comparison)

**Agent Sequence:**
1. **Supervisor** - Retrieves historical performance baseline from memory
2. **Metrics Agent** - Gets current metrics, compares to baseline
3. **Kubernetes Agent** - Checks resource allocation changes
4. **Logs Agent** - Searches for change-related logs
5. **Supervisor** - Identifies when degradation started

**Observability Points:**
- Track baseline retrieval from infrastructure knowledge
- Monitor comparison logic in metrics agent
- Trace timeline correlation across agents
- Measure accuracy of degradation start time identification

**Memory Interactions:**
- Use historical metrics as baseline
- Identify when performance baseline changed
- Store new baseline after confirmation

---

## 11. Key Files & Code Locations

### Core Agent System
- **Supervisor:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/sre_agent/supervisor.py`
- **Agent Nodes:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/sre_agent/agent_nodes.py`
- **Graph Builder:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/sre_agent/graph_builder.py`
- **CLI Entry:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/sre_agent/cli.py`
- **Agent Runtime:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/sre_agent/agent_runtime.py`

### Memory System
- **Memory Client:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/sre_agent/memory/client.py`
- **Memory Tools:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/sre_agent/memory/tools.py`
- **Memory Strategies:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/sre_agent/memory/strategies.py`
- **Memory Hooks:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/sre_agent/memory/hooks.py`

### Gateway & Backend
- **Gateway Main:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/gateway/main.py`
- **Gateway Observability:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/gateway/observability.py`
- **K8s Server:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/backend/servers/k8s_server.py`
- **Logs Server:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/backend/servers/logs_server.py`
- **Metrics Server:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/backend/servers/metrics_server.py`
- **Runbooks Server:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/backend/servers/runbooks_server.py`

### Configuration & Data
- **Agent Config:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/sre_agent/config/agent_config.yaml`
- **User Config:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/scripts/user_config.yaml`
- **OpenAPI Specs:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/backend/openapi_specs/`
- **Sample Data:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/backend/data/`

### Documentation
- **System Components:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/docs/system-components.md`
- **Memory System:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/docs/memory-system.md`
- **Configuration:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/docs/configuration.md`
- **Example Reports:** `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/docs/examples/`

---

## 12. Observability Enhancement Opportunities

### 12.1 Current State
- Basic file logging with standardized format
- Debug mode with detailed traces
- Markdown report generation with findings
- Conversation state persistence

### 12.2 Enhancement Areas for Demos

**1. Distributed Tracing (X-Ray)**
- Trace requests from supervisor through agents to backend APIs
- Track tool execution latency
- Identify bottlenecks in multi-agent coordination

**2. CloudWatch Metrics**
- Agent invocation count and latency
- Tool call success/failure rates
- Memory operation latency
- Report generation time by user profile

**3. Memory Observability**
- Track memory strategy hits/misses
- Monitor namespace routing accuracy
- Observe memory growth patterns
- Analyze retrieval latency by strategy

**4. Agent Interaction Traces**
- Visualize supervisor routing decisions
- Track agent-to-agent dependencies
- Monitor parallel agent execution
- Measure aggregation efficiency

**5. Gateway Health Monitoring**
- Backend API health check results
- Tool availability status
- MCP protocol translation latency
- Authentication success rates

---

## Conclusion

The SRE Agent is a **production-ready demonstration** of sophisticated multi-agent AI systems using Amazon Bedrock AgentCore. Its complexity makes it ideal for observability demonstrations because it:

1. **Exercises multiple agents** with different responsibilities and tool access
2. **Involves complex routing logic** requiring trace visibility
3. **Integrates with memory systems** that need observability
4. **Coordinates tool execution** across multiple backend services
5. **Personalizes output** based on long-term preferences
6. **Supports both CLI and Runtime** deployment modes
7. **Handles real SRE use cases** with meaningful investigations

The six observability demo scenarios provided showcase everything from simple single-agent investigations to complex multi-turn conversations, making it an excellent reference system for understanding distributed AI agent systems in production environments.

