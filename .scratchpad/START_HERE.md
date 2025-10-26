# START HERE - re:Invent Observability Demos

**Created:** 2025-10-25  
**Status:** Ready to implement

---

## 📋 Quick Reference

### GitHub Issues Created
- **Issue #547:** Demo 1 - Simple Observability (CloudWatch + Braintrust)
  - https://github.com/awslabs/amazon-bedrock-agentcore-samples/issues/547
  
- **Issue #548:** Demo 2 - Complex SRE Agent (CloudWatch only)
  - https://github.com/awslabs/amazon-bedrock-agentcore-samples/issues/548

### Key Documents
1. **FINAL_SUMMARY.md** ⭐ - Read this for complete overview
2. **UPDATED_PLAN.md** - Master plan with 60-min time allocation
3. **reinvent-observability-slides.md** - Complete 5-slide deck (DONE!)
4. **GITHUB_ISSUES_CREATED.md** - Issue details with timeline

---

## 🎯 What We're Building

### Demo 1 (10 minutes)
- **New tutorial:** `07-simple-dual-observability-demo/`
- **Stack:** Python CLI → AgentCore Runtime → AgentCore Gateway
- **Observability:** CloudWatch + Braintrust (dual OTEL export)
- **No Lambda!** (just managed services)
- **3 scenarios:** success, error, dashboard
- **Effort:** 3.5 days

### Demo 2 (20 minutes)
- **Enhance:** Existing SRE-agent use case
- **Add:** OTEL instrumentation + CloudWatch dashboard
- **Show:** 5 agents, 20 tools, 3 memory strategies
- **3 scenarios:** cross-domain, memory context, live error
- **Effort:** 10 days

---

## 🚀 Start Tomorrow (Monday)

### Morning Tasks
1. Create folder: `01-tutorials/06-AgentCore-observability/07-simple-dual-observability-demo/`
2. Start `simple_observability_demo.py`
3. Sign up: Braintrust free tier (no CC needed)
4. Test: AgentCore Runtime deployment

### This Week Goal
- Demo 1 complete by Friday
- Recorded (5 takes)
- Stakeholder review done

---

## ⏱️ 60-Minute Structure

```
0-15 min:  Slides (intro, challenges, AgentCore overview)
15-25 min: Demo 1 (Simple: CloudWatch + Braintrust)
25-45 min: Demo 2 (Complex: CloudWatch only, 3 scenarios)
45-60 min: Q&A (engaged discussion)
```

---

## 📊 Code Reuse

- **Demo 1:** 85% reusable → ~50 lines new code
- **Demo 2:** 60% reusable → ~950 lines new code
- **Total:** ~1,000 lines new code (very achievable!)

---

## ✅ All Decisions Made

- [x] Time allocation (60 min hard)
- [x] Demo 1: CloudWatch + Braintrust
- [x] Demo 2: CloudWatch only
- [x] Braintrust free tier confirmed
- [x] GitHub structure decided
- [x] Scenarios prioritized
- [x] Issues created and cleaned up
- [x] No Lambda in Demo 1 (clarified)

---

## 🎬 Next Steps

**Today:** Done! All planning complete.

**Tomorrow:** Start coding Demo 1

**Week 1:** Complete Demo 1  
**Week 2:** Demo 2 instrumentation  
**Week 3:** Demo 2 integration  
**Week 4:** Practice & polish  

**Ready to ship!** 🚀
