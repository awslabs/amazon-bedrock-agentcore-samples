# Quick Start Guide - re:Invent AIM3314 Observability Chalk Talk

Created: 2025-10-25

## What's in This Folder?

```
.scratchpad/
├── README.md (265 lines)
│   └── Overview of all planning materials and quick reference
│
├── reinvent-observability-chalktalk-plan.md (759 lines)
│   └── MASTER PLAN: Detailed implementation timeline, code reuse analysis
│
├── reinvent-observability-slides.md (986 lines)
│   └── 5-SLIDE DECK: Complete presentation with code samples and diagrams
│
├── OBSERVABILITY_ANALYSIS.md (1031 lines)
│   └── TECHNICAL ANALYSIS: Deep dive on SRE-agent multi-agent system
│
└── QUICK_START.md (this file)
    └── Visual summary and immediate next steps
```

## The Plan in 30 Seconds

**Goal:** Create two observability demos for re:Invent 300-level chalk talk

**Demo 1 - Simple (15 min):**
- Hello World agent on AgentCore Runtime + Gateway
- Show automatic OTEL tracing with zero code changes
- 3 scenarios: success, error, dashboard
- Effort: 3 days, ~50 lines new code

**Demo 2 - Complex (30 min):**
- Multi-agent SRE system (5 agents, 20 tools, 3 memory strategies)
- Add custom OTEL instrumentation (~400 lines)
- 6 production scenarios showing distributed tracing
- Effort: 10 days, ~950 lines new code

**Total Timeline:** 4 weeks (development + practice)

## Code Reuse Analysis

### We Have EXCELLENT Foundation

**Demo 1 Sources (85% reusable):**
```
01-tutorials/06-AgentCore-observability/
├── 01-AgentCore-Runtime-hosted/Strands/
│   └── CrewAI-agentcore-observability-Strands.ipynb (847 lines)
├── 05-Lambda-AgentCore-invocation/
│   ├── lambda_agentcore_invoker.py (128 lines) ✓ Production-ready
│   └── mcp_agent_multi_server.py (69 lines) ✓ Multi-MCP pattern
```

**Demo 2 Sources (60% reusable, but 2000+ lines existing!):**
```
02-use-cases/SRE-agent/
├── sre_agent/
│   ├── supervisor.py (231 lines) ✓ Central orchestrator
│   ├── agent_nodes.py (166 lines) ✓ 4 specialist agents
│   ├── graph_builder.py (138 lines) ✓ LangGraph routing
│   ├── multi_agent_langgraph.py (189 lines) ✓ Main engine
│   └── memory/
│       ├── client.py (180 lines) ✓ Memory operations
│       ├── strategies.py (172 lines) ✓ 3 retention strategies
│       └── conversation_manager.py (211 lines) ✓ Session tracking
└── backend/servers/
    ├── k8s_server.py (362 lines) ✓ 5 K8s tools
    ├── logs_server.py (290 lines) ✓ 5 log tools
    ├── metrics_server.py (317 lines) ✓ 5 metrics tools
    └── runbooks_server.py (210 lines) ✓ 5 runbook tools
```

**Key Insight:** We're NOT building from scratch. We're enhancing existing production-ready code.

## What We Need to Build

### Demo 1: Simple (~3 days)

| File | Lines | Purpose | Effort |
|------|-------|---------|--------|
| simple_observability_demo.py | ~150 | CLI script (adapt from notebook) | 1 day |
| simple-dashboard.json | ~200 | CloudWatch dashboard template | 0.5 day |
| deploy_simple_demo.sh | ~50 | One-click deployment | 0.5 day |
| simple_demo_scenarios.md | ~100 | Demo script with expected outputs | 0.5 day |

**Total:** ~500 lines, 2.5 days development + 0.5 day testing

### Demo 2: Complex (~10 days)

| File | Lines | Purpose | Effort |
|------|-------|---------|--------|
| observability_enhancements.py | ~200 | Custom OTEL spans for agents/memory | 2 days |
| complex-dashboard.json | ~300 | Multi-panel CloudWatch dashboard | 1 day |
| trace_analyzer.py | ~150 | X-Ray trace query and visualization | 1 day |
| run_complex_demo.sh | ~100 | Orchestration script | 1 day |
| troubleshooting_guide.md | ~500 | RCA workflows and best practices | 1 day |

**Total:** ~1,250 lines, 6 days development + 4 days integration/testing

### Slide Deck (~2 days)

**DONE!** Already created in reinvent-observability-slides.md

5 slides with:
- Architecture diagrams
- Code samples
- Demo scenarios
- Best practices
- Q&A topics

Just need to add visuals and screenshots.

## The 6 Production Scenarios (Demo 2)

All documented in OBSERVABILITY_ANALYSIS.md:

1. **Cross-Domain Degradation** (8 min) - 4 agents, 10+ tools, parallel execution
2. **Database Crash Loop** (7 min) - Error cascade, memory-based escalation
3. **Performance Baseline** (6 min) - Historical comparison via infrastructure memory
4. **Multi-Turn Conversation** (5 min) - Session correlation across 3 requests
5. **Live Error Injection** (4 min) - Break backend, show real-time troubleshooting
6. **User Personalization** (bonus) - Alice vs Carol side-by-side comparison

**All scenarios use existing SRE-agent code!** We just add observability instrumentation.

## 4-Week Timeline

```
Week 1: Simple Demo (3 days) + Setup (2 days)
├── Mon-Wed: Build simple demo (script, dashboard, automation)
├── Thu: Validate SRE-agent runs locally
└── Fri: Stakeholder review checkpoint

Week 2: Complex Demo - Instrumentation (5 days)
├── Mon-Tue: Add OTEL spans to supervisor, agents, memory
├── Wed-Thu: Implement custom metrics
└── Fri: Test trace generation

Week 3: Complex Demo - Integration (5 days) + Slides (2 days)
├── Mon-Tue: Build CloudWatch dashboard
├── Wed-Thu: Create trace analyzer and orchestration
├── Fri: Stakeholder review checkpoint
└── Weekend: Slide deck visuals

Week 4: Practice & Refinement (5 days)
├── Mon-Tue: Full run-throughs (10+ practice sessions)
├── Wed-Thu: Backup plans, audience prep materials
└── Fri: Final dress rehearsal
```

## Immediate Next Steps (This Week)

### Day 1: Validation
```bash
# 1. Validate SRE-agent works locally
cd /home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent
uv sync
# Follow README to start backend servers and run agent

# 2. Test with Alice and Carol personas
# Document any issues or gaps
```

### Day 2: OTEL Spike
```bash
# 1. Add minimal OTEL to supervisor.py
# 2. Generate a single trace
# 3. View in CloudWatch X-Ray
# 4. Validate instrumentation pattern works
```

### Day 3: Simple Demo Kickoff
```bash
# 1. Start converting Strands notebook to simple_observability_demo.py
# 2. Setup AgentCore Runtime agent
# 3. Configure Gateway with 3 MCP tools
```

### Day 4-5: Continue Simple Demo
```bash
# 1. Finish simple demo script
# 2. Create CloudWatch dashboard template
# 3. Write deployment automation
```

## Key Metrics for Success

**Knowledge Transfer:**
- Attendees can explain 3 observability challenges in agentic systems ✓
- Attendees can identify where to add custom spans ✓
- Attendees can interpret X-Ray trace for multi-agent system ✓

**Audience Engagement:**
- 80%+ stay for full 60 minutes
- 10+ questions during Q&A
- Positive feedback in session survey

**Follow-Up Impact:**
- GitHub repo gets 100+ stars
- 50+ attendees request AWS contact
- 5+ blog posts reference session

## Critical Success Factors

### Technical
- [ ] Both demos work 100% of the time (practice 10+ times each)
- [ ] Pre-recorded backup videos ready
- [ ] Local backend servers (no internet dependency)
- [ ] CloudWatch access verified from venue

### Content
- [ ] Simple demo shows "zero code" value prop clearly
- [ ] Complex demo shows real production patterns
- [ ] Live error injection creates memorable moment
- [ ] Best practices are actionable (not theoretical)

### Delivery
- [ ] Use whiteboard for chalk talk feel (interactive!)
- [ ] Keep demos under time (15 min + 30 min = 45 min, leaving 15 for Q&A)
- [ ] Engage audience with questions throughout
- [ ] Have backup answers for common questions ready

## Resources at Your Fingertips

**Planning:**
- This folder: `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/.scratchpad/`
- Master plan: `reinvent-observability-chalktalk-plan.md`
- Slide deck: `reinvent-observability-slides.md`
- Technical analysis: `OBSERVABILITY_ANALYSIS.md`

**Existing Code:**
- Simple demo source: `01-tutorials/06-AgentCore-observability/`
- Complex demo source: `02-use-cases/SRE-agent/`

**Documentation:**
- AWS AgentCore Observability: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-service-provided.html
- OpenTelemetry Python: https://opentelemetry.io/docs/languages/python/

## Questions? Blockers?

**Stakeholder Questions:**
1. Is 60 minutes hard constraint or can we get 75?
2. AWS credits for testing?
3. Include partner observability (Braintrust/Langfuse) or AWS-only?
4. GitHub repo public before or after event?

**Technical Questions:**
1. CloudWatch access setup needed?
2. re:Invent venue dry run access?
3. Network reliability backup plan?

## Bottom Line

**We have 85-60% of the code already written and production-tested.**

**We need to add ~1,000 lines of:**
- OTEL instrumentation (observability layer)
- CloudWatch dashboards (visualization)
- Demo orchestration (automation)
- Documentation (best practices)

**This is VERY achievable in 4 weeks.**

**The existing SRE-agent is already an excellent foundation for a complex observability demo.**

---

## Start Here Tomorrow Morning

1. Read `reinvent-observability-chalktalk-plan.md` (759 lines)
2. Run SRE-agent locally to validate it works
3. Review `OBSERVABILITY_ANALYSIS.md` for the 6 scenarios
4. Start Week 1, Day 1 tasks

**You've got this!**
