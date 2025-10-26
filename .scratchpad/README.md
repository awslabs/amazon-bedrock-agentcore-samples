# re:Invent 2025 - AIM3314 Observability Chalk Talk Planning

Created: 2025-10-25

## Overview

This folder contains all planning materials for the re:Invent 300-level chalk talk:
**"Debug, trace, improve: Observability for agentic applications (AIM3314)"**

## Documents in This Folder

### 1. UPDATED_PLAN.md (NEW - READ THIS FIRST!)
**Updated master plan** with confirmed decisions:
- 60-minute hard constraint with precise time allocation
- Demo 1: CloudWatch + Braintrust (10 min)
- Demo 2: CloudWatch only (20 min)
- Braintrust free tier analysis (sufficient for demos)
- Updated 4-week timeline with daily tasks
- Scenario prioritization (3 must-have + 2 bonus)
- Recording strategy and backup plans
- All critical decisions documented

### 2. reinvent-observability-chalktalk-plan.md (25KB)
**Master planning document** containing:
- Detailed demo 1 (Simple Hello World) and demo 2 (Complex SRE System) plans
- Code reuse analysis (85% for simple, 60% for complex)
- 4-week implementation timeline
- Required new code (~950 lines total)
- Risk mitigation strategies
- Success metrics
- Complete file location references

**Key Sections:**
- Demo architectures and flows
- 6 production scenarios for complex demo
- Code enhancement strategy with examples
- Implementation phases with daily tasks
- Technical requirements and AWS resources
- Stakeholder review checkpoints

### 2. reinvent-observability-slides.md (37KB)
**5-slide presentation deck** in markdown format:

**Slide 1: The Observability Challenge in Agentic Systems**
- Traditional vs agentic systems comparison
- Questions we can't answer (yet)
- Demo overview

**Slide 2: Amazon Bedrock AgentCore Observability Overview**
- Service-provided instrumentation
- Observability stack diagram
- Key capabilities and setup

**Slide 3: Demo 1 - Simple Hello World Agent**
- Architecture diagram
- 3 demo scenarios (success, error, dashboard)
- Code sample (40 lines total)
- 15-minute demo flow with timestamps

**Slide 4: Demo 2 - Complex Multi-Agent SRE System**
- Production architecture (5 agents, 20 tools, 3 memory strategies)
- Custom instrumentation examples (~400 lines)
- 6 production scenarios with observability focus
- 30-minute demo flow with timestamps
- CloudWatch dashboard design (5 panels)

**Slide 5: Best Practices & Evaluation Pipelines**
- Span naming conventions
- Custom metrics for production
- Structured logging best practices
- RCA workflow (6 steps)
- Evaluation pipeline integration
- Production checklist
- Key takeaways (6 principles)
- Q&A discussion topics

### 3. OBSERVABILITY_ANALYSIS.md (39KB)
**Comprehensive technical analysis** of the SRE-agent use case:
- Multi-agent system architecture (5 agents)
- Backend infrastructure (4 FastAPI servers, 20 tools)
- Memory system (3 strategies with retention policies)
- 6 detailed demo scenarios with execution flows
- Current observability implementation
- Enhancement opportunities
- Why this system is ideal for observability demonstrations
- Complete file locations for all components

**6 Demo Scenarios:**
1. Cross-Domain Infrastructure Degradation (HIGH complexity)
2. Database Pod Crash Loop with Escalation (HIGH complexity)
3. Performance Investigation with User Personalization (MEDIUM)
4. Multi-Service Incident Investigation (VERY HIGH)
5. Long-Running Investigation with Progressive Findings (VERY HIGH)
6. Performance Baseline Violation (MEDIUM)

## Quick Reference

### Demo 1: Simple Hello World
**What We Have:**
- Lambda handler structure (128 lines) - reusable
- OTEL configuration patterns - reusable
- Strands notebooks - adaptable to CLI
- Session tracking - reusable

**What We Need to Create:**
- `simple_observability_demo.py` (~150 lines)
- `simple-dashboard.json` (CloudWatch dashboard)
- `deploy_simple_demo.sh` (deployment automation)
- `simple_demo_scenarios.md` (demo script)

**Estimated Effort:** 3 days

### Demo 2: Complex Multi-Agent SRE System
**What We Have (EXCELLENT):**
- Complete multi-agent system (2000+ lines) - use as-is
- 4 backend servers (1200+ lines) - use as-is
- Memory system (563 lines) - use as-is
- 6 documented scenarios - ready to demo

**What We Need to Create:**
- `observability_enhancements.py` (~200 lines OTEL instrumentation)
- `complex-dashboard.json` (~300 lines CloudWatch dashboard)
- `trace_analyzer.py` (~150 lines X-Ray trace analysis)
- `run_complex_demo.sh` (~100 lines orchestration)
- `troubleshooting_guide.md` (~500 lines documentation)

**Estimated Effort:** 10 days

### Implementation Timeline

**Week 1 (3 days):** Simple demo
- Day 1: Core script
- Day 2: CloudWatch setup
- Day 3: Automation

**Week 2-3 (10 days):** Complex demo
- Days 1-2: OTEL instrumentation
- Days 3-4: Custom metrics
- Days 5-6: Dashboard
- Days 7-8: Trace analysis
- Days 9-10: Orchestration & testing

**Week 3 (2 days):** Slide deck
- Day 1: Content
- Day 2: Design & review

**Week 4 (5 days):** Dry run & refinement
- Days 1-2: Practice sessions
- Days 3-4: Audience prep
- Day 5: Final prep

## Key Findings

### Code Reuse Assessment
- **Demo 1:** 85% reusable, ~50 lines new code
- **Demo 2:** 60% reusable, ~950 lines new code
- **Total New Code:** ~1000 lines across both demos

### Existing Assets Strengths
1. **Excellent foundation** in SRE-agent (production-ready)
2. **Complete tutorial examples** in 06-AgentCore-observability
3. **Multiple frameworks** demonstrated (CrewAI, LangGraph, LlamaIndex, Strands)
4. **Production patterns** already implemented (error handling, logging, memory)

### Gaps to Fill
1. Standalone Python scripts for live coding (everything is notebooks)
2. Custom OTEL instrumentation for multi-agent coordination
3. CloudWatch dashboard templates
4. Advanced troubleshooting workflows
5. Evaluation pipeline integration

## Critical Success Factors

### Technical Preparation
- Practice both demos 10+ times each
- Pre-record backup videos
- Test on venue network
- Have offline fallback (local backend servers)

### Audience Engagement
- Start with simple, build to complex
- Interactive chalk talk (use whiteboard)
- Real-time CloudWatch navigation
- Live error injection and troubleshooting

### Knowledge Transfer
- Clear documentation in GitHub repo
- Reusable code patterns
- Production-ready examples
- Follow-up resources

## Next Actions

### This Week
- [ ] Run SRE-agent end-to-end locally to validate
- [ ] Test OTEL integration with simple example
- [ ] Get stakeholder approval on plan
- [ ] Setup CloudWatch access for development

### Week 1 Checkpoint
- [ ] Simple demo working end-to-end
- [ ] OTEL instrumentation pattern validated
- [ ] Stakeholder review

### Week 2 Checkpoint
- [ ] Complex demo instrumentation complete
- [ ] Dashboard mockups ready
- [ ] Stakeholder review

### Week 3 Checkpoint
- [ ] Both demos fully functional
- [ ] Slide deck finalized
- [ ] Dry run with stakeholders

### Week 4 Checkpoint
- [ ] Final dress rehearsal
- [ ] Backup plans tested
- [ ] Ready for re:Invent

## Questions for Stakeholders (ALL RESOLVED!)

~~1. **Scope:** Is 60 minutes the hard constraint or can we request 75?~~
**ANSWERED:** 60 minutes HARD constraint

~~2. **Resources:** Can we get AWS credits for pre-event testing?~~
**NOT CRITICAL:** Braintrust free tier covers demos, CloudWatch testing cost is minimal

~~3. **Content:** Focus on AWS-native tools only, or include partner observability?~~
**ANSWERED:** Demo 1 shows CloudWatch + Braintrust, Demo 2 shows CloudWatch only

~~4. **Follow-Up:** GitHub repo public before or after event?~~
**ANSWERED:** Public repo, organized structure confirmed

## File Locations

### Existing Code
**Simple Demo Sources:**
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/01-tutorials/06-AgentCore-observability/01-AgentCore-Runtime-hosted/Strands/`
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/01-tutorials/06-AgentCore-observability/05-Lambda-AgentCore-invocation/`

**Complex Demo Sources:**
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/sre_agent/`
- `/home/ubuntu/repos/amazon-bedrock-agentcore-samples/02-use-cases/SRE-agent/backend/`

### New Files to Create
**Demo 1: NEW FOLDER (CloudWatch + Braintrust)**
- `01-tutorials/06-AgentCore-observability/07-simple-dual-observability-demo/` (NEW)
  - `README.md`
  - `simple_observability_demo.py`
  - `config/otel_config.yaml`
  - `dashboards/cloudwatch-dashboard.json`
  - `dashboards/braintrust-dashboard-export.json`
  - `scenarios/demo_scenarios.md`
  - `scripts/deploy_agent.sh`
  - `scripts/setup_cloudwatch.sh`
  - `scripts/setup_braintrust.sh`
  - `docs/DEMO_GUIDE.md`

**Demo 2: ENHANCE EXISTING (CloudWatch only)**
- `02-use-cases/SRE-agent/sre_agent/observability/` (NEW MODULE)
  - `__init__.py`
  - `otel_instrumentation.py`
  - `metrics.py`
  - `trace_utils.py`
- `02-use-cases/SRE-agent/dashboards/complex-dashboard.json`
- `02-use-cases/SRE-agent/scripts/run_observability_demo.sh`
- `02-use-cases/SRE-agent/docs/OBSERVABILITY_GUIDE.md`
- `02-use-cases/SRE-agent/docs/TROUBLESHOOTING_PLAYBOOK.md`

## Resources

**AWS Documentation:**
- Amazon Bedrock AgentCore Observability: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-service-provided.html
- CloudWatch Gen AI Observability: https://docs.aws.amazon.com/cloudwatch/
- X-Ray Tracing: https://docs.aws.amazon.com/xray/

**GitHub Repository:**
- AgentCore Samples: https://github.com/aws-samples/amazon-bedrock-agentcore-samples

**OpenTelemetry:**
- OTEL Python SDK: https://opentelemetry.io/docs/languages/python/
- Semantic Conventions: https://opentelemetry.io/docs/specs/semconv/

## Change Log

**2025-10-25:**
- Created planning document with 4-week timeline
- Analyzed existing code (tutorials + SRE-agent)
- Documented 6 production scenarios for complex demo
- Created 5-slide presentation deck
- Estimated code reuse: 85% simple, 60% complex
- Total new code required: ~1000 lines

**Next Update:** After stakeholder review and Week 1 checkpoint
