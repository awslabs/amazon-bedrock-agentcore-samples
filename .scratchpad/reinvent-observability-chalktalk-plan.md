# re:Invent 2025 - AIM3314 Chalk Talk Planning Document
Debug, trace, improve: Observability for agentic applications

**Created:** 2025-10-25
**Level:** 300 - Advanced
**Format:** Interactive Chalk Talk
**Duration:** 60 minutes

---

## Executive Summary

This chalk talk will demonstrate Amazon Bedrock AgentCore Observability through two progressive demos:
1. **Simple Demo** - Hello World agent with AgentCore Runtime and Gateway showing basic tracing
2. **Complex Demo** - Multi-agent SRE system with 5 agents, 20+ tools, memory strategies, and distributed tracing

Both demos leverage OpenTelemetry traces, CloudWatch dashboards, and structured logging to demonstrate production observability patterns.

---

## Session Abstract Analysis

**Key Topics to Cover:**
- Observability challenges unique to agentic systems
- Practical solutions using Amazon Bedrock AgentCore Observability
- OpenTelemetry traces for distributed tracing
- Structured logging for debugging
- CloudWatch dashboards for visualization
- Identifying bottlenecks and troubleshooting tool errors
- Root Cause Analysis (RCA) with user context
- Creating meaningful alerts and evaluation pipelines
- Real-world production scenarios

**Target Audience:**
- Developer Community, Enterprise, ISV
- Developer/Engineer, IT Professional, Technical Manager, Business Executive
- 300-level (Advanced) - expect deep technical knowledge

---

## Demo 1: Simple Hello World (15 minutes)

### Objective
Show basic AgentCore observability with minimal complexity - perfect for "I want to add observability to my first agent"

### Architecture
- **Agent Framework:** Strands (simplest deployment)
- **Deployment:** AgentCore Runtime (managed)
- **Tools:** 2-3 MCP tools via AgentCore Gateway
- **Observability:** OpenTelemetry auto-instrumentation, CloudWatch Logs, X-Ray traces

### Current Assets in 01-tutorials/06-AgentCore-observability

**What We Have:**
- `01-AgentCore-Runtime-hosted/Strands/CrewAI-agentcore-observability-Strands.ipynb` (847 lines)
- `02-Agent-not-hosted-on-runtime/Strands/AgentCore-observability-otel-Strands.ipynb` (1107 lines)
- `05-Lambda-AgentCore-invocation/lambda_agentcore_invoker.py` (128 lines, production-ready)
- `05-Lambda-AgentCore-invocation/mcp_agent_multi_server.py` (69 lines, multi-MCP example)
- OTEL configuration patterns (consistent across all frameworks)
- Session tracking patterns for trace correlation

**What We Need to Create:**

1. **Standalone Python Script** (`simple_observability_demo.py`)
   - Convert Strands notebook to CLI script
   - Use AgentCore Runtime-hosted deployment
   - 2-3 MCP tools (weather, time, calculator via Gateway)
   - Basic OTEL instrumentation (reuse pattern from tutorials)
   - ~150 lines total

2. **CloudWatch Dashboard Template** (`simple-dashboard.json`)
   - Pre-configured CloudWatch dashboard
   - Key metrics: request count, latency, error rate, token usage
   - Visual layout optimized for live demo

3. **Deployment Script** (`deploy_simple_demo.sh`)
   - One-click deployment of agent + gateway
   - Setup CloudWatch Transaction Search
   - Configure OTEL collector

4. **Demo Scenario Script** (`simple_demo_scenarios.md`)
   - 3 test queries showing different trace patterns
   - Expected CloudWatch views for each
   - Common errors and how they appear in traces

### Demo Flow

1. **Setup (2 min)**
   - Show deployed architecture diagram
   - Explain AgentCore Runtime benefits
   - Show pre-deployed Gateway with MCP tools

2. **Baseline Query (3 min)**
   - Run: "What's the weather in Seattle and what time is it there?"
   - Live view CloudWatch Logs appearing
   - Show X-Ray trace with agent → gateway → MCP tool spans
   - Highlight automatic instrumentation (no code changes)

3. **Error Scenario (5 min)**
   - Run: "Calculate the factorial of -5"
   - Show tool error in CloudWatch
   - Navigate X-Ray trace to identify failure point
   - Demonstrate structured logging for debugging

4. **Dashboard Review (3 min)**
   - Open CloudWatch dashboard
   - Show metrics: latency distribution, success rate, token usage
   - Explain what to monitor in production

5. **Q&A / Transition (2 min)**

### Code Reuse Strategy

**Reuse from Lambda Tutorial (85%):**
```python
# From lambda_agentcore_invoker.py (lines 30-50)
# - Error handling pattern
# - Logging configuration
# - Session tracking
# - Response formatting

# From mcp_agent_multi_server.py (lines 1-30)
# - Gateway tool configuration
# - MCP server setup
```

**Reuse from Strands Notebooks (70%):**
```python
# From CrewAI-agentcore-observability-Strands.ipynb
# - Agent configuration
# - OTEL setup (environment variables)
# - Bedrock client initialization
```

**New Code Required (~50 lines):**
- CLI argument parsing
- Test scenario orchestration
- Dashboard configuration automation

---

## Demo 2: Complex Multi-Agent SRE System (30 minutes)

### Objective
Show advanced observability in production-grade multi-agent system with real complexity challenges

### Architecture
- **5 Agents:** Supervisor, K8s Infrastructure, App Logs, Performance Metrics, Operational Runbooks
- **4 Backend Services:** Mock FastAPI servers (K8s API, Logs API, Metrics API, Runbooks API)
- **20+ Tools:** Distributed across 4 domains via AgentCore Gateway
- **3 Memory Strategies:** User preferences, infrastructure knowledge, investigation history
- **User Personas:** Alice (technical SRE), Carol (executive)

### Current Assets in 02-use-cases/SRE-agent

**What We Have (EXCELLENT FOUNDATION):**

**Core Multi-Agent System:**
- `sre_agent/supervisor.py` (231 lines) - Central orchestrator with memory integration
- `sre_agent/agent_nodes.py` (166 lines) - 4 specialized agent implementations
- `sre_agent/graph_builder.py` (138 lines) - LangGraph routing logic
- `sre_agent/multi_agent_langgraph.py` (189 lines) - Main execution engine

**Memory System (PRODUCTION-READY):**
- `sre_agent/memory/client.py` (180 lines) - Memory operations with error handling
- `sre_agent/memory/strategies.py` (172 lines) - 3 strategies with retention policies
- `sre_agent/memory/conversation_manager.py` (211 lines) - Session state tracking

**Backend Infrastructure:**
- `backend/servers/k8s_server.py` (362 lines) - 5 K8s tools with realistic data
- `backend/servers/logs_server.py` (290 lines) - 5 log analysis tools
- `backend/servers/metrics_server.py` (317 lines) - 5 metrics tools
- `backend/servers/runbooks_server.py` (210 lines) - 5 operational tools
- `backend/openapi_specs/*.yaml` - Auto-convert to MCP via Gateway

**Configuration:**
- `sre_agent/config/agent_config.yaml` - Agent prompts and routing logic
- `scripts/user_config.yaml` - Alice/Carol personas with preferences
- `scripts/deploy_gateway.sh` - Gateway deployment automation

**Demo Scenarios (PRE-BUILT):**
- 6 production scenarios documented in OBSERVABILITY_ANALYSIS.md
- Cross-domain investigations
- Memory-based personalization
- Multi-turn conversations
- Error cascades and escalation

**What We Need to Create:**

1. **Enhanced Observability Instrumentation** (`observability_enhancements.py`)
   - Add custom OTEL spans for:
     - Agent routing decisions (supervisor logic)
     - Memory operations (retrieval, storage)
     - Tool execution timing
     - Multi-agent coordination
   - Custom metrics:
     - Agent invocation counts by type
     - Memory hit/miss rates
     - Tool execution latencies by domain
     - Investigation completion times
   - ~200 lines

2. **CloudWatch Dashboard for Multi-Agent** (`complex-dashboard.json`)
   - Multi-panel layout:
     - Agent routing heatmap
     - Tool execution waterfall
     - Memory operation timing
     - Error correlation view
     - User persona comparison
   - Pre-configured queries for 6 demo scenarios
   - ~300 lines JSON

3. **Distributed Trace Visualization Script** (`trace_analyzer.py`)
   - Query X-Ray traces programmatically
   - Generate visual trace trees for chalk talk
   - Highlight critical path analysis
   - Compare Alice vs Carol execution patterns
   - ~150 lines

4. **Live Demo Orchestration** (`run_complex_demo.sh`)
   - One-command startup of all 4 backend servers
   - Deploy Gateway with 20 tools
   - Initialize memory with personas
   - Run scenario and auto-open CloudWatch views
   - ~100 lines

5. **Troubleshooting Playbook** (`troubleshooting_guide.md`)
   - Common failure patterns and their traces
   - How to identify bottlenecks in multi-agent systems
   - Memory performance analysis
   - RCA workflow examples
   - ~500 lines

### Demo Scenarios (Prioritized for 30min)

**Scenario 1: Cross-Domain Investigation (8 min)**
- **Query:** "API response times degraded 3x in last hour" (Alice)
- **Complexity:** HIGH - 4 agents, 10+ tools
- **Observability Focus:**
  - Show supervisor routing to multiple agents
  - Visualize parallel tool executions
  - Highlight memory retrieval (Alice preferences)
  - Identify bottleneck in metrics agent
  - Demonstrate structured logging for correlation

**Scenario 2: Database Crash Loop with Escalation (7 min)**
- **Query:** "Database pods crash looping in production" (Carol)
- **Complexity:** HIGH - Error cascade, escalation via memory
- **Observability Focus:**
  - Show error propagation across agents
  - Memory-based escalation decision (Carol's exec contacts)
  - Compare trace depth vs Scenario 1
  - CloudWatch alerts based on error patterns
  - RCA with user context (executive summary format)

**Scenario 3: Performance Baseline Violation (6 min)**
- **Query:** "API gateway slower than normal"
- **Complexity:** MEDIUM - Historical comparison
- **Observability Focus:**
  - Infrastructure knowledge memory retrieval (past baselines)
  - Custom metrics for trend analysis
  - Show how memory impacts investigation depth
  - Dashboard view of historical vs current performance

**Scenario 4: Multi-Turn Conversation Tracing (5 min)**
- **Query:** "Check cluster health" → "What about auth-service?" → "Show me logs"
- **Complexity:** VERY HIGH - Conversation memory across requests
- **Observability Focus:**
  - Session ID correlation across 3 traces
  - Conversation state evolution in CloudWatch
  - Context propagation through memory
  - Progressive investigation pattern

**Scenario 5: Live Troubleshooting (4 min)**
- **Introduce Error:** Break K8s backend server
- **Observability Focus:**
  - Show tool timeout in real-time
  - X-Ray error annotation
  - CloudWatch alarm triggering
  - How to identify failing backend from trace
  - Recovery and retry patterns

### Demo Flow

1. **Architecture Overview (3 min)**
   - Draw system on whiteboard
   - 5 agents, 4 backends, 3 memory strategies
   - Explain complexity challenges for observability

2. **Baseline Scenario 1 (8 min)**
   - Run cross-domain investigation
   - Live CloudWatch dashboard showing all components
   - Navigate X-Ray trace tree
   - Show structured logs with correlation IDs

3. **Scenario 2: User Context Impact (7 min)**
   - Same query, different user (Alice vs Carol)
   - Side-by-side trace comparison
   - Memory retrieval differences
   - Output personalization

4. **Scenario 3: Historical Analysis (6 min)**
   - Performance baseline query
   - Show memory strategy in action
   - Custom metrics dashboard

5. **Scenario 4: Multi-Turn (5 min)**
   - Interactive conversation
   - Session correlation
   - Context evolution

6. **Live Break/Fix (4 min)**
   - Introduce error
   - Show troubleshooting workflow
   - Demonstrate RCA process

7. **Best Practices Discussion (5 min)**
   - Span naming conventions
   - Custom attributes strategy
   - Alert configuration
   - Evaluation pipeline integration

8. **Audience Q&A (7 min)**

### Code Enhancement Strategy

**Current Observability (Estimated 20%):**
- Basic logging with `logging.basicConfig()`
- Timestamps, process ID, file location
- Debug mode flag
- No OTEL, no custom spans, no metrics

**Enhancements Needed:**

```python
# Add to supervisor.py (40 new lines)
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer(__name__)

def route_to_agents(self, query: str) -> List[str]:
    with tracer.start_as_current_span("supervisor.route_decision") as span:
        span.set_attribute("query", query)
        span.set_attribute("user_id", self.user_id)

        # Memory retrieval for preferences
        with tracer.start_as_current_span("memory.get_preferences"):
            prefs = self.memory_client.get_user_preferences()
            span.set_attribute("preference_count", len(prefs))

        # Routing logic
        agents = self._determine_agents(query, prefs)
        span.set_attribute("agents_selected", agents)
        span.set_attribute("agent_count", len(agents))

        return agents
```

```python
# Add to agent_nodes.py (60 new lines)
def execute_k8s_agent(state: dict) -> dict:
    with tracer.start_as_current_span("agent.k8s.execute") as span:
        span.set_attribute("agent.type", "kubernetes")
        span.set_attribute("tools.available", 5)

        start_time = time.time()

        try:
            result = self._invoke_agent(state)

            # Custom metrics
            execution_time = time.time() - start_time
            span.set_attribute("execution_time_ms", execution_time * 1000)
            span.set_attribute("tools.invoked", len(result.get("tool_calls", [])))

            span.set_status(Status(StatusCode.OK))
            return result

        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
```

```python
# Add to memory/client.py (80 new lines)
def get_relevant_memories(
    self,
    query: str,
    strategy: str
) -> List[dict]:
    with tracer.start_as_current_span("memory.retrieval") as span:
        span.set_attribute("memory.strategy", strategy)
        span.set_attribute("query.length", len(query))

        # Vector search
        with tracer.start_as_current_span("memory.vector_search"):
            results = self._search(query, strategy)
            span.set_attribute("results.count", len(results))

            # Cache metrics
            if self._cache_hit(query):
                span.set_attribute("cache.hit", True)
            else:
                span.set_attribute("cache.hit", False)

        # Post-processing
        with tracer.start_as_current_span("memory.post_process"):
            filtered = self._filter_by_retention(results, strategy)
            span.set_attribute("results.filtered", len(filtered))

        return filtered
```

**Total New Code Required: ~400 lines** (mostly instrumentation)

---

## Code Reuse Assessment

### Demo 1: Simple (85% Reusable)

**Directly Reusable:**
- Lambda handler structure (128 lines) → adapt to CLI
- OTEL configuration pattern → copy verbatim
- Session tracking → copy verbatim
- Error handling → copy verbatim

**Adaptation Required:**
- Convert notebook cells to functions (~3 hours)
- CLI argument parsing (~1 hour)
- Dashboard JSON creation (~2 hours)

**Net New Code:** ~50 lines

### Demo 2: Complex (60% Reusable)

**Directly Reusable:**
- Entire multi-agent system (2000+ lines) → use as-is
- All backend servers (1200+ lines) → use as-is
- Memory system (563 lines) → use as-is
- Demo scenarios → already documented

**Enhancement Required:**
- OTEL instrumentation (~400 lines, 2 days)
- Custom metrics (~100 lines, 1 day)
- Dashboard configuration (~300 lines JSON, 1 day)
- Trace analyzer script (~150 lines, 1 day)

**Net New Code:** ~950 lines

---

## Implementation Plan

### Phase 1: Simple Demo (Week 1) - 3 Days

**Day 1: Core Script**
- [ ] Convert Strands notebook to `simple_observability_demo.py`
- [ ] Add CLI argument parsing
- [ ] Test with AgentCore Runtime deployment
- [ ] Validate OTEL instrumentation

**Day 2: CloudWatch Setup**
- [ ] Create `simple-dashboard.json` template
- [ ] Configure Transaction Search
- [ ] Test 3 demo scenarios
- [ ] Document expected CloudWatch views

**Day 3: Automation**
- [ ] Write `deploy_simple_demo.sh`
- [ ] Create `simple_demo_scenarios.md`
- [ ] End-to-end testing
- [ ] Record backup demo video

### Phase 2: Complex Demo (Week 2-3) - 10 Days

**Days 1-2: OTEL Instrumentation**
- [ ] Add custom spans to supervisor.py
- [ ] Add custom spans to agent_nodes.py
- [ ] Add custom spans to memory client
- [ ] Test trace generation locally

**Days 3-4: Custom Metrics**
- [ ] Implement agent invocation counters
- [ ] Implement memory operation metrics
- [ ] Implement tool execution timing
- [ ] Push metrics to CloudWatch

**Days 5-6: Dashboard**
- [ ] Design multi-panel layout
- [ ] Create queries for 6 scenarios
- [ ] Build `complex-dashboard.json`
- [ ] Test visualization with real data

**Days 7-8: Trace Analysis**
- [ ] Write `trace_analyzer.py` for X-Ray queries
- [ ] Generate visual trace trees
- [ ] Compare Alice vs Carol patterns
- [ ] Critical path analysis

**Days 9-10: Orchestration & Testing**
- [ ] Write `run_complex_demo.sh`
- [ ] Test all 6 scenarios end-to-end
- [ ] Create `troubleshooting_guide.md`
- [ ] Record backup demo videos

### Phase 3: Slide Deck (Week 3) - 2 Days

**Day 1: Content**
- [ ] Slide 1: Title & Observability Challenges
- [ ] Slide 2: AgentCore Observability Overview
- [ ] Slide 3: Demo 1 Architecture
- [ ] Slide 4: Demo 2 Architecture
- [ ] Slide 5: Best Practices & Q&A

**Day 2: Design & Review**
- [ ] Add architecture diagrams
- [ ] Add code snippets
- [ ] Add CloudWatch screenshots
- [ ] Dry run presentation (60 min)

### Phase 4: Dry Run & Refinement (Week 4) - 5 Days

**Days 1-2: Practice Sessions**
- [ ] Full 60-minute run-through
- [ ] Time each section
- [ ] Identify rough transitions
- [ ] Refine demo scripts

**Days 3-4: Audience Prep**
- [ ] Create handout with key commands
- [ ] Prepare backup slides for failure scenarios
- [ ] Test on different network conditions
- [ ] Load test backend servers

**Day 5: Final Prep**
- [ ] Pack demo checklist
- [ ] Verify all AWS resources deployed
- [ ] Test CloudWatch access from venue
- [ ] Prepare Q&A responses

---

## Technical Requirements

### AWS Resources

**Demo 1:**
- AgentCore Runtime agent deployment (Strands)
- AgentCore Gateway with 3 MCP tools
- CloudWatch Logs group
- CloudWatch dashboard
- X-Ray tracing enabled

**Demo 2:**
- 4 EC2 instances (t3.medium) for backend servers
- AgentCore Gateway with 20 MCP tools
- 3 Memory namespaces in AgentCore Memory
- CloudWatch Logs group
- CloudWatch dashboard (multi-panel)
- X-Ray tracing enabled

### Local Development

- Python 3.11+
- uv package manager
- AWS CLI configured
- Docker (for backend containers)
- JQ (for JSON parsing in scripts)

### Demo Environment

- Reliable internet (backup: mobile hotspot)
- Projector resolution: 1920x1080
- CloudWatch accessible via browser
- Whiteboard + markers for chalk talk
- Backup: Pre-recorded videos for both demos

---

## Risk Mitigation

### Technical Risks

**Risk 1: Live Demo Failure**
- **Mitigation:** Pre-recorded backup videos
- **Mitigation:** Local backend servers (no internet required)
- **Mitigation:** Practice 10+ times before event

**Risk 2: CloudWatch Lag**
- **Mitigation:** Pre-populate dashboard with recent data
- **Mitigation:** Screenshots of expected views
- **Mitigation:** Explain typical latency to audience

**Risk 3: Agent Unpredictability**
- **Mitigation:** Test queries 50+ times to find stable ones
- **Mitigation:** Pre-seeded memory for consistent routing
- **Mitigation:** Explain non-determinism as teachable moment

**Risk 4: Complex Demo Too Complex**
- **Mitigation:** 6 scenarios prioritized by time
- **Mitigation:** Can skip Scenarios 4-5 if running late
- **Mitigation:** Focus on 2-3 key observability patterns

### Audience Risks

**Risk 5: Questions Derail Timeline**
- **Mitigation:** "Great question, let's discuss after demo"
- **Mitigation:** Reserve 7 min for Q&A at end
- **Mitigation:** Handout with contact info for follow-up

**Risk 6: Audience Skill Mismatch**
- **Mitigation:** Start with simple demo to assess level
- **Mitigation:** Adjust complex demo depth based on reactions
- **Mitigation:** Provide both beginner and advanced resources

---

## Success Metrics

**Audience Engagement:**
- 80%+ stay for full session
- 10+ questions during Q&A
- Positive feedback in session survey

**Knowledge Transfer:**
- Attendees can explain 3 observability challenges in agentic systems
- Attendees can identify where to add custom spans
- Attendees can interpret an X-Ray trace for multi-agent system

**Follow-Up:**
- GitHub repo with code gets 100+ stars
- 50+ attendees request AWS contact for POC
- 5+ blog posts reference this session

---

## Next Steps

### Immediate Actions (This Week)

1. **Validate Existing Code**
   - [ ] Run SRE-agent end-to-end locally
   - [ ] Confirm all 4 backend servers work
   - [ ] Test memory strategies with Alice/Carol
   - [ ] Document any gaps or bugs

2. **Setup Development Environment**
   - [ ] Clone repo to clean environment
   - [ ] Install all dependencies via uv
   - [ ] Deploy AgentCore Gateway locally
   - [ ] Configure CloudWatch access

3. **Spike OTEL Integration**
   - [ ] Add OTEL to supervisor.py (minimal)
   - [ ] Generate first trace
   - [ ] View in CloudWatch X-Ray
   - [ ] Validate instrumentation pattern

4. **Create Slide Deck Outline**
   - [ ] Draft 5 slides (see below)
   - [ ] Get stakeholder feedback
   - [ ] Iterate based on input

### Stakeholder Review

**Week 1 Checkpoint:**
- Review simple demo script
- Review OTEL instrumentation approach
- Approve timeline and resource allocation

**Week 2 Checkpoint:**
- Demo 1 working end-to-end
- Complex demo instrumentation progress
- Dashboard mockups for feedback

**Week 3 Checkpoint:**
- Both demos working
- Slide deck complete
- Dry run with stakeholders

**Week 4 Checkpoint:**
- Final dress rehearsal
- Backup plans tested
- Ready to ship

---

## Appendix: File Locations

### Existing Code (Absolute Paths)

**Demo 1 Sources:**
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/01-tutorials/06-AgentCore-observability/01-AgentCore-Runtime-hosted/Strands/CrewAI-agentcore-observability-Strands.ipynb`
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/01-tutorials/06-AgentCore-observability/05-Lambda-AgentCore-invocation/lambda_agentcore_invoker.py`
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/01-tutorials/06-AgentCore-observability/05-Lambda-AgentCore-invocation/mcp_agent_multi_server.py`

**Demo 2 Sources:**
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/sre_agent/supervisor.py`
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/sre_agent/agent_nodes.py`
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/sre_agent/memory/client.py`
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/backend/servers/k8s_server.py`
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/backend/servers/logs_server.py`
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/backend/servers/metrics_server.py`
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/backend/servers/runbooks_server.py`

### New Files to Create

**Demo 1:**
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/01-tutorials/06-AgentCore-observability/simple_observability_demo.py`
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/01-tutorials/06-AgentCore-observability/simple-dashboard.json`
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/01-tutorials/06-AgentCore-observability/deploy_simple_demo.sh`
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/01-tutorials/06-AgentCore-observability/simple_demo_scenarios.md`

**Demo 2:**
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/sre_agent/observability_enhancements.py`
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/complex-dashboard.json`
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/trace_analyzer.py`
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/run_complex_demo.sh`
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/troubleshooting_guide.md`

**Slide Deck:**
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/.scratchpad/reinvent-observability-slides.md`

---

## Questions for Stakeholders

1. **Scope:**
   - Is 60 minutes the hard constraint or can we request 75?
   - Should we prioritize breadth (6 scenarios) or depth (2-3 scenarios)?

2. **Resources:**
   - Can we get AWS credits for pre-event testing?
   - Do we have access to re:Invent venue for dry run?

3. **Content:**
   - Should we include partner observability (Braintrust/Langfuse) or focus only on AWS-native?
   - How much time for audience participation vs demo?

4. **Follow-Up:**
   - GitHub repo public before or after event?
   - Office hours or workshop after chalk talk?

---

## Change Log

**2025-10-25:**
- Initial planning document created
- Analyzed existing code in tutorials and SRE-agent
- Documented 6 demo scenarios for complex demo
- Estimated 85% code reuse for simple demo, 60% for complex
- Created 4-week implementation timeline
- Identified ~950 lines of new code required

**Next Update:** After stakeholder review (Week 1)
