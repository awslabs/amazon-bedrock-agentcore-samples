# UPDATED re:Invent 2025 - AIM3314 Chalk Talk Plan
Debug, trace, improve: Observability for agentic applications

**Updated:** 2025-10-25
**Duration:** 60 minutes (HARD CONSTRAINT)

---

## Time Allocation (60 minutes total)

```
┌─────────────────────────────────────────────────────────────┐
│ Timeline Breakdown                                          │
├─────────────────────────────────────────────────────────────┤
│ 0-15 min:  Slides (intro, challenges, AgentCore overview)  │
│ 15-25 min: Demo 1 (Simple with CloudWatch + Braintrust)    │
│ 25-45 min: Demo 2 (Complex SRE multi-agent with CloudWatch)│
│ 45-60 min: Follow-up questions & discussion                │
└─────────────────────────────────────────────────────────────┘
```

**Key Changes from Original Plan:**
- Demo 1: 15 minutes → **10 minutes** (tighter, focused)
- Demo 2: 30 minutes → **20 minutes** (prioritize 3-4 scenarios, not all 6)
- Slides: More time for setup and context
- Q&A: Full 15 minutes for deep discussion
- Both demos will be **pre-recorded as backup**

---

## Observability Strategy by Demo

### Demo 1: CloudWatch + Braintrust (10 minutes)
**Purpose:** Show both AWS-native AND partner observability

**CloudWatch Focus:**
- Automatic OTEL tracing via AgentCore Runtime
- X-Ray trace visualization
- CloudWatch Logs with correlation

**Braintrust Focus:**
- Trace ingestion from same agent
- Braintrust dashboard view
- Comparison: CloudWatch vs Braintrust UX
- When to use each (AWS-native vs specialized AI observability)

**Why This Works:**
- Shows AgentCore works with multiple observability backends
- Partner ecosystem demonstration
- Attendees can choose what fits their needs
- Simple agent = easy to see both platforms clearly

### Demo 2: CloudWatch Only (20 minutes)
**Purpose:** Deep dive on AWS-native observability for production systems

**CloudWatch Focus:**
- Distributed tracing across 5 agents
- Custom OTEL instrumentation patterns
- Memory operation observability
- Multi-agent coordination visualization
- Production troubleshooting workflow

**Why CloudWatch Only:**
- Production AWS users typically use CloudWatch
- Complex multi-agent traces are easier to follow in one tool
- Shows advanced CloudWatch capabilities (dashboards, insights queries)
- Time constraint (20 min is already aggressive for this complexity)

---

## Braintrust Free Tier Analysis

### What's Included (Perfect for Demo!)

**Free Tier Limits:**
- 1 million Trace spans/month ✓ (way more than needed)
- 1 GB Processed data ✓ (sufficient for demos)
- 10,000 Scores and custom metrics ✓ (plenty)
- 14 days Data retention ✓ (enough for re:Invent prep)
- Unlimited Users ✓ (can share with team)

**No Credit Card Required:** Free tier signup appears to be immediate

**For Our Demo:**
- Demo 1 will generate ~50-100 spans per run
- We'll practice 50 times max = 5,000 spans
- Well within 1 million span limit
- Free tier is MORE than sufficient

### Setup Strategy

**Pre-Event (Week 2-3):**
1. Sign up for Braintrust free tier (no CC)
2. Configure OTEL export to both CloudWatch AND Braintrust
3. Run demo 1 queries to populate Braintrust dashboard
4. Create Braintrust dashboard view for demo
5. Take screenshots as backup

**During Demo:**
- Live view of both CloudWatch and Braintrust side-by-side
- Show same trace in both platforms
- Highlight: "AgentCore OTEL = vendor neutral, use what you want"

---

## Updated Demo 1: Simple + Dual Observability

### New Folder Structure

```
01-tutorials/06-AgentCore-observability/
└── 07-simple-dual-observability-demo/  ← NEW FOLDER
    ├── README.md (setup instructions)
    ├── simple_observability_demo.py (main demo script)
    ├── config/
    │   ├── otel_config.yaml (CloudWatch + Braintrust endpoints)
    │   └── braintrust_config.yaml (Braintrust-specific settings)
    ├── dashboards/
    │   ├── cloudwatch-dashboard.json
    │   └── braintrust-dashboard-export.json
    ├── scenarios/
    │   └── demo_scenarios.md (3 test queries)
    ├── scripts/
    │   ├── deploy_agent.sh (AgentCore Runtime deployment)
    │   ├── setup_cloudwatch.sh (CloudWatch Transaction Search)
    │   └── setup_braintrust.sh (Braintrust project setup)
    └── docs/
        └── DEMO_GUIDE.md (step-by-step presentation flow)
```

### Demo 1 Architecture (Updated)

```
┌─────────────────────────────────────────────────────────────┐
│                         User Query                          │
│          "What's the weather in Seattle?"                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│          AgentCore Runtime (Strands Agent)                  │
│          - Automatic OTEL instrumentation                   │
│          - Dual export configured                           │
└────────────┬────────────────────────────┬───────────────────┘
             │                            │
             │ OTEL Spans                 │ OTEL Spans
             ▼                            ▼
┌──────────────────────────┐  ┌─────────────────────────────┐
│   CloudWatch X-Ray       │  │   Braintrust Platform       │
│   + CloudWatch Logs      │  │   (braintrust.dev)          │
│   + CloudWatch Dashboard │  │   + Braintrust Dashboard    │
└──────────────────────────┘  └─────────────────────────────┘
             │                            │
             └────────────┬───────────────┘
                          │
                   Live Demo: Show Both!
```

### Demo 1 Flow (10 minutes, TIGHT)

**Minutes 15-17 (2 min): Setup & Context**
- "Now let's see observability in action"
- Show architecture diagram on whiteboard
- Explain: AgentCore Runtime + dual OTEL export
- "Same traces, two platforms - you choose"

**Minutes 17-20 (3 min): Successful Query**
- Execute: "What's the weather in Seattle?"
- **CloudWatch view (90 seconds):**
  - Show X-Ray trace tree
  - Agent span → tool selection → gateway → weather API
  - Point out: automatic, zero code
- **Braintrust view (90 seconds):**
  - Open same trace by trace_id
  - Show Braintrust's AI-focused UI
  - Highlight: token usage, latency, LLM call details

**Minutes 20-22 (2 min): Error Scenario**
- Execute: "Calculate factorial of -5"
- **CloudWatch:** Red error span, error details
- **Braintrust:** Error in timeline, exception recorded
- Point out: "Both caught it, different UX"

**Minutes 22-24 (2 min): Dashboard Comparison**
- CloudWatch dashboard: request rate, latency, error rate
- Braintrust dashboard: LLM-specific metrics (tokens, cost, quality scores)
- Explain: "CloudWatch = AWS-native, Braintrust = AI-specialized"

**Minutes 24-25 (1 min): Transition**
- "For simple agents, both work great"
- "But what about complex multi-agent systems?"
- "Let's look at a production SRE agent with 5 agents and 20 tools"

---

## Updated Demo 2: Complex SRE (CloudWatch Focus)

### File Locations (Update Existing Code)

```
02-use-cases/SRE-agent/
├── sre_agent/
│   ├── observability/  ← NEW MODULE
│   │   ├── __init__.py
│   │   ├── otel_instrumentation.py (custom spans)
│   │   ├── metrics.py (custom CloudWatch metrics)
│   │   └── trace_utils.py (correlation helpers)
│   ├── supervisor.py (ADD OTEL instrumentation)
│   ├── agent_nodes.py (ADD OTEL instrumentation)
│   └── memory/
│       └── client.py (ADD OTEL instrumentation)
├── dashboards/
│   └── complex-dashboard.json ← NEW FILE
├── scripts/
│   ├── run_observability_demo.sh ← NEW FILE
│   └── setup_cloudwatch_dashboard.sh ← NEW FILE
└── docs/
    ├── OBSERVABILITY_GUIDE.md ← NEW FILE
    └── TROUBLESHOOTING_PLAYBOOK.md ← NEW FILE
```

**Strategy:** Update existing code, don't restructure

### Demo 2 Flow (20 minutes, PRIORITIZED)

**Minutes 25-28 (3 min): Architecture Walkthrough**
- Draw system on whiteboard (chalk talk!)
- 5 agents, 4 backend servers, 3 memory strategies
- Explain complexity: "This is what production looks like"
- Show pre-configured CloudWatch dashboard

**Minutes 28-35 (7 min): Scenario 1 - Cross-Domain Investigation**
- Execute: "API response times degraded 3x" (Alice)
- Live CloudWatch dashboard: agent activity heatmap
- Navigate X-Ray trace tree:
  - Supervisor routes to K8s, Logs, Metrics agents
  - 10+ tool calls across 3 domains
  - Parallel execution visible
- Identify bottleneck: Metrics agent (3.2s)
- Show custom span attributes: user preferences, routing decisions
- Show CloudWatch Logs with correlation ID

**Minutes 35-40 (5 min): Scenario 2 - Error with Memory Context**
- Execute: "Database pods crash looping" (Carol)
- Compare to Scenario 1: different user persona
- Show memory retrieval span (Carol's escalation preferences)
- Error propagation across agents
- Custom metrics: escalation_triggered=true
- Dashboard: error rate spike, alert would trigger

**Minutes 40-43 (3 min): Scenario 3 - Live Troubleshooting**
- **Break something:** Kill K8s backend server
- Show real-time error in X-Ray
- Navigate to failure point: "Connection refused :8011"
- CloudWatch Logs: retry attempts visible
- "This is production debugging - 2 minutes to identify root cause"
- Restart server (or skip if time tight)

**Minutes 43-45 (2 min): Best Practices Summary**
- Show span naming conventions
- Show custom attributes strategy
- Show CloudWatch Insights query for session correlation
- "These patterns scale to any multi-agent system"

---

## Scenario Prioritization for Demo 2 (20 min constraint)

### Must Have (17 minutes)
1. **Scenario 1: Cross-Domain** (7 min) - Shows multi-agent coordination
2. **Scenario 2: Memory Context** (5 min) - Shows user personalization impact
3. **Scenario 3: Live Error** (3 min) - Shows troubleshooting workflow
4. **Wrap-up** (2 min) - Best practices

### Optional (If Time Allows)
5. **Scenario 4: Multi-Turn** - Session correlation (would add 4 min)
6. **Scenario 5: Baseline Comparison** - Infrastructure memory (would add 3 min)

**Strategy:**
- Practice to keep Scenarios 1-3 tight
- Have Scenarios 4-5 ready as "bonus" if running ahead
- Can mention Scenarios 4-5 verbally even if not demonstrated

---

## Recording Strategy

### Pre-Record Both Demos

**Demo 1 Recording (10 min):**
- Record 5 clean takes
- Choose best one with smooth transitions
- Include both CloudWatch and Braintrust views
- Add picture-in-picture if helpful
- Keep video file <100MB for quick loading

**Demo 2 Recording (20 min):**
- Record 3 full takes of 3-scenario version
- Record 2 full takes of 5-scenario version (backup)
- Choose cleanest execution
- Ensure all CloudWatch views are visible
- Keep video file <200MB

**Backup Plan:**
- Videos on local laptop + USB drive + cloud storage
- If live demo fails: "Let me show you a recording"
- Practice seamless transition to video
- Have videos queued and ready to play

---

## Code Structure Updates

### Demo 1: New Folder (Simple)

**New files to create:**
```python
# simple_observability_demo.py (~150 lines)
# - CLI script with 3 scenarios
# - Dual OTEL export (CloudWatch + Braintrust)
# - Clear logging for each step
# - Error handling

# config/otel_config.yaml
# - CloudWatch OTEL endpoint
# - Braintrust OTEL endpoint
# - Sampling strategy
# - Resource attributes
```

**Estimated effort:** 3 days
- Day 1: Core script with CloudWatch
- Day 2: Add Braintrust integration
- Day 3: Testing and dashboard setup

### Demo 2: Enhance Existing (Complex)

**Files to modify:**
```python
# sre_agent/supervisor.py (ADD ~40 lines OTEL)
# - Span for route_decision
# - Span for memory retrieval
# - Custom attributes: agents_selected, user_id

# sre_agent/agent_nodes.py (ADD ~60 lines OTEL)
# - Span per agent execution
# - Custom attributes: tools_invoked, execution_time_ms
# - Error recording

# sre_agent/memory/client.py (ADD ~80 lines OTEL)
# - Span for get_relevant_memories
# - Sub-spans: vector_search, post_process
# - Custom attributes: cache_hit, results_count
```

**New files to create:**
```python
# sre_agent/observability/otel_instrumentation.py (~200 lines)
# - Tracer setup and configuration
# - Common span utilities
# - Attribute naming conventions

# sre_agent/observability/metrics.py (~100 lines)
# - CloudWatch custom metrics
# - Agent invocation counters
# - Tool execution timers
# - Memory operation metrics
```

**Estimated effort:** 8 days
- Days 1-2: OTEL instrumentation
- Days 3-4: Custom metrics
- Days 5-6: Dashboard and testing
- Days 7-8: Documentation and polish

---

## Updated Timeline (4 weeks)

### Week 1: Demo 1 (Simple with Dual Observability)

**Monday:**
- [ ] Create new folder structure: `07-simple-dual-observability-demo/`
- [ ] Start `simple_observability_demo.py` with CloudWatch OTEL
- [ ] Test AgentCore Runtime deployment
- [ ] Verify CloudWatch X-Ray receives traces

**Tuesday:**
- [ ] Add Braintrust OTEL export configuration
- [ ] Sign up for Braintrust free tier
- [ ] Configure dual OTEL export (CloudWatch + Braintrust)
- [ ] Test same trace visible in both platforms

**Wednesday:**
- [ ] Complete 3 demo scenarios
- [ ] Create CloudWatch dashboard JSON
- [ ] Create Braintrust dashboard
- [ ] Write deployment scripts

**Thursday:**
- [ ] End-to-end testing (10+ runs)
- [ ] Document demo flow in DEMO_GUIDE.md
- [ ] Record demo (5 takes, choose best)
- [ ] Create backup video

**Friday:**
- [ ] Stakeholder review: show Demo 1 working
- [ ] Incorporate feedback
- [ ] Buffer for issues

### Week 2: Demo 2 Setup + Instrumentation

**Monday:**
- [ ] Validate SRE-agent runs locally end-to-end
- [ ] Start all 4 backend servers
- [ ] Test with Alice and Carol personas
- [ ] Document any issues

**Tuesday:**
- [ ] Create `sre_agent/observability/` module
- [ ] Implement `otel_instrumentation.py`
- [ ] Add OTEL to `supervisor.py`
- [ ] Test supervisor spans in CloudWatch

**Wednesday:**
- [ ] Add OTEL to `agent_nodes.py` (all 4 agents)
- [ ] Test multi-agent trace generation
- [ ] Verify parent-child span relationships

**Thursday:**
- [ ] Add OTEL to `memory/client.py`
- [ ] Implement custom metrics in `metrics.py`
- [ ] Test memory operation spans

**Friday:**
- [ ] Test all 6 scenarios generate clean traces
- [ ] Verify custom attributes appear correctly
- [ ] Stakeholder review: show instrumentation working

### Week 3: Demo 2 Dashboard + Integration

**Monday:**
- [ ] Design CloudWatch dashboard layout (5 panels)
- [ ] Create queries for agent routing heatmap
- [ ] Create queries for tool execution waterfall

**Tuesday:**
- [ ] Complete `complex-dashboard.json`
- [ ] Deploy dashboard to CloudWatch
- [ ] Test with real demo scenarios
- [ ] Iterate on layout and queries

**Wednesday:**
- [ ] Write `run_observability_demo.sh` orchestration script
- [ ] Write `setup_cloudwatch_dashboard.sh`
- [ ] Test one-command demo startup
- [ ] Document troubleshooting steps

**Thursday:**
- [ ] Write `OBSERVABILITY_GUIDE.md`
- [ ] Write `TROUBLESHOOTING_PLAYBOOK.md`
- [ ] End-to-end testing of 3-scenario flow (20 min)
- [ ] Time each scenario precisely

**Friday:**
- [ ] Record Demo 2 (3 takes, 3-scenario version)
- [ ] Record Demo 2 (2 takes, 5-scenario version as bonus)
- [ ] Stakeholder review: full demo run-through
- [ ] Incorporate feedback

### Week 4: Slides + Practice

**Monday:**
- [ ] Update slide deck with final screenshots
- [ ] Add architecture diagrams (draw and photograph/scan)
- [ ] Add code snippets to slides
- [ ] Practice slide delivery (15 min target)

**Tuesday:**
- [ ] Full run-through: Slides (15) + Demo 1 (10) + Demo 2 (20)
- [ ] Time each section
- [ ] Identify rough transitions
- [ ] Refine demo scripts

**Wednesday:**
- [ ] Practice 3 more full run-throughs
- [ ] Record practice session for self-review
- [ ] Refine timing and pacing
- [ ] Prepare Q&A responses for common questions

**Thursday:**
- [ ] Create handout with key commands and GitHub links
- [ ] Prepare backup slides for failure scenarios
- [ ] Test on different network conditions
- [ ] Verify all AWS resources deployed and accessible

**Friday:**
- [ ] Final dress rehearsal with stakeholders
- [ ] Pack demo checklist
- [ ] Verify backup videos play correctly
- [ ] Confirm CloudWatch access from multiple devices
- [ ] Buffer for last-minute issues

---

## GitHub Repo Structure (Public)

```
amazon-bedrock-agentcore-samples/
├── 01-tutorials/
│   └── 06-AgentCore-observability/
│       ├── 01-AgentCore-Runtime-hosted/
│       ├── 02-Agent-not-hosted-on-runtime/
│       ├── 03-Advanced-concepts/
│       ├── 04-Partner-observability/
│       ├── 05-Lambda-AgentCore-invocation/
│       └── 07-simple-dual-observability-demo/  ← NEW
│           ├── README.md
│           ├── simple_observability_demo.py
│           ├── config/
│           ├── dashboards/
│           ├── scenarios/
│           ├── scripts/
│           └── docs/
│               └── DEMO_GUIDE.md
│
└── 02-use-cases/
    └── SRE-agent/
        ├── sre_agent/
        │   ├── observability/  ← NEW MODULE
        │   ├── supervisor.py  ← ENHANCED
        │   ├── agent_nodes.py  ← ENHANCED
        │   └── memory/
        │       └── client.py  ← ENHANCED
        ├── dashboards/  ← NEW FOLDER
        │   └── complex-dashboard.json
        ├── scripts/
        │   ├── run_observability_demo.sh  ← NEW
        │   └── setup_cloudwatch_dashboard.sh  ← NEW
        └── docs/
            ├── OBSERVABILITY_GUIDE.md  ← NEW
            └── TROUBLESHOOTING_PLAYBOOK.md  ← NEW
```

**Public before re:Invent:**
- Ensure README files are polished
- Add LICENSE if needed
- No emojis in markdown files (per coding standards)
- Professional tone throughout
- Clear setup instructions
- Troubleshooting sections

---

## Updated Success Metrics

### Demo 1 Success
- [ ] Traces visible in both CloudWatch AND Braintrust
- [ ] Same trace_id correlates between platforms
- [ ] 3 scenarios execute in <10 minutes
- [ ] Clear value prop: "AgentCore works with your choice of observability"
- [ ] Attendees understand OTEL vendor neutrality

### Demo 2 Success
- [ ] Multi-agent trace shows all 5 agents clearly
- [ ] Custom spans visible with meaningful attributes
- [ ] CloudWatch dashboard shows real-time updates
- [ ] Can identify bottleneck in <30 seconds
- [ ] Live troubleshooting impresses audience
- [ ] Attendees can replicate patterns in their systems

### Overall Session Success
- [ ] Complete 60-minute session on time
- [ ] 15 minutes of Q&A with engaged questions
- [ ] 80%+ attendees stay for full session
- [ ] Positive feedback in survey
- [ ] GitHub repo gets 50+ stars within 2 weeks

---

## Critical Decisions Documented

### 1. Time Allocation ✓
**Decision:** 60 minutes hard constraint
- 15 min slides
- 10 min Demo 1
- 20 min Demo 2
- 15 min Q&A

### 2. Observability Platform Strategy ✓
**Decision:**
- Demo 1 = CloudWatch + Braintrust (show vendor neutrality)
- Demo 2 = CloudWatch only (deep dive)

**Rationale:**
- Simple demo is perfect for showing both platforms clearly
- Complex demo needs focus, CloudWatch is AWS-native choice
- Shows "choice" but doesn't dilute complex demo

### 3. Braintrust Free Tier ✓
**Decision:** Use Braintrust free tier (no cost)
- 1M spans/month (way more than needed)
- No credit card required
- 14-day retention (sufficient)

### 4. GitHub Repo Structure ✓
**Decision:** Public repo
- Demo 1 in new folder: `07-simple-dual-observability-demo/`
- Demo 2 updates existing SRE-agent code
- Public before event

### 5. Recording Strategy ✓
**Decision:** Pre-record both demos as backup
- Demo 1: 5 takes, choose best
- Demo 2: 3 takes (3-scenario), 2 takes (5-scenario)
- Videos <100-200MB each
- Have ready but prefer live

### 6. Scenario Prioritization ✓
**Decision:** Demo 2 shows 3 scenarios (17 min)
- Must have: Cross-domain, Memory context, Live error
- Bonus if time: Multi-turn, Baseline comparison
- Practice tight timing

---

## Open Questions (None - All Resolved!)

~~1. Is 60 minutes hard constraint?~~ **ANSWERED: Yes, 60 min hard constraint**

~~2. AWS credits for testing?~~ **NOT CRITICAL: Braintrust is free tier, CloudWatch cost is minimal for testing**

~~3. Include partner observability?~~ **ANSWERED: Yes, Demo 1 shows Braintrust + CloudWatch**

~~4. GitHub repo public before or after?~~ **ANSWERED: Public, code in appropriate folders**

~~5. Braintrust cost?~~ **ANSWERED: Free tier is sufficient (1M spans, no CC required)**

---

## Next Actions

### Tomorrow (Tuesday)
1. Create new folder: `01-tutorials/06-AgentCore-observability/07-simple-dual-observability-demo/`
2. Start `simple_observability_demo.py` with CloudWatch OTEL
3. Sign up for Braintrust free tier account
4. Test AgentCore Runtime deployment

### This Week
- Complete Demo 1 (Mon-Thu)
- Record Demo 1 (Thu)
- Stakeholder review (Fri)

### Week 2
- Validate SRE-agent (Mon)
- Add OTEL instrumentation (Tue-Thu)
- Test scenarios (Fri)

---

## Summary of Changes from Original Plan

| Aspect | Original | Updated | Rationale |
|--------|----------|---------|-----------|
| Duration | Unclear | 60 min (hard) | Confirmed constraint |
| Demo 1 time | 15 min | 10 min | Tighter focus, more Q&A |
| Demo 2 time | 30 min | 20 min | Feasible with 3 scenarios |
| Demo 1 observability | CloudWatch only | CloudWatch + Braintrust | Show vendor choice |
| Demo 2 observability | CloudWatch + custom | CloudWatch only | Deep dive AWS-native |
| Demo 2 scenarios | 6 scenarios | 3 must-have + 2 bonus | Time constraint |
| Braintrust cost | Unknown | Free tier sufficient | Confirmed available |
| GitHub structure | TBD | Demo 1 new folder, Demo 2 enhance existing | Clean organization |
| Recording | Mentioned | Pre-record both (5+3 takes) | Solid backup plan |

---

## Risks & Mitigations (Updated)

### Risk 1: 10 minutes too tight for Demo 1
**Mitigation:**
- Practice 20+ times
- Pre-record backup
- Can skip Braintrust view if running late (CloudWatch only still works)

### Risk 2: 20 minutes too tight for Demo 2
**Mitigation:**
- 3 scenarios tested to fit 17 minutes
- Have 2 bonus scenarios ready if ahead
- Pre-record 3-scenario and 5-scenario versions

### Risk 3: Braintrust setup issues
**Mitigation:**
- Set up in Week 1 (plenty of time to troubleshoot)
- Free tier = low risk
- Can fall back to CloudWatch-only for Demo 1 if needed

### Risk 4: Live demo failures
**Mitigation:**
- Pre-recorded backups for both demos
- Practiced transition to video
- Local backend servers (no internet dependency for Demo 2)

### Risk 5: Questions extend beyond 15 minutes
**Mitigation:**
- "Great questions, let's continue after the session"
- Provide contact info and GitHub repo
- Offer to schedule follow-up office hours

---

## Confidence Level: HIGH ✓

**Why we'll succeed:**
1. ✓ Clear time allocation (60 min hard constraint)
2. ✓ Realistic scope (3-4 scenarios per demo, not 6)
3. ✓ Excellent existing code (85% Demo 1, 60% Demo 2 reusable)
4. ✓ Free tier Braintrust (no cost/approval needed)
5. ✓ 4-week timeline is reasonable
6. ✓ Backup recordings for safety
7. ✓ Clear structure and next steps

**This is achievable and will be an excellent chalk talk!**
