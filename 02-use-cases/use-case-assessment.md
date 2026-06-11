# AgentCore Use-Case Samples — Assessment & Restructuring Plan

**Date:** June 11, 2026
**Scope:** 27 projects in `02-use-cases/`
**Purpose:** Multi-criteria evaluation to determine which samples to keep, update, or remove — and how to restructure into three category subfolders.

---

## New Folder Structure

```
02-use-cases/
  01-conversational-agents/    # User-facing chat, Q&A, interactive assistants
  02-automation-agents/        # Event-driven, background, multi-agent pipelines
  03-coding-assistants/        # Developer tools, code generation, IDE integration
```

---

## Scoring System

| Dimension | Weight | Scale | Notes |
|-----------|--------|-------|-------|
| **Existing Tier** | — | S=4, A=3, B=2, C=1 | From prior quality analysis |
| **Blog Post** | +2 | 0 or 2 | Confirmed AWS blog post references this sample |
| **AgentCore Features** | 1 pt/feature | 0–13 | Runtime, Memory, Gateway, Policy, Registry, Evaluations, Optimization, Observability, Payments, Browser, Code Interpreter, Identity, Harness |
| **Unique Customer Problem** | 1–5 | 5=enterprise must-have | Clarity, specificity, real-world relevance |
| **README Quality** | 1–5 | 5=production-grade docs | Depth, quickstart, architecture, troubleshooting |
| **Starter Toolkit Flag** | –2 penalty | yes/no | Needs migration to native SDK |

**Recommendation tiers:**
- **KEEP AS-IS**: Score ≥ 20, no blocking issues
- **UPDATE**: Score 12–19, or uses starter toolkit, or has specific gaps
- **MAJOR OVERHAUL**: Score < 12, foundational issues to fix

---

## Sample Assessments

### Category: 01 — Conversational Agents

---

#### 1. customer-support-assistant

**Category:** Conversational
**Starter Toolkit:** YES — needs migration
**README Lines:** 416
**Prior Tier:** B (21/40)

**Summary:** Multi-modal customer support agent with knowledge base retrieval, Google Calendar integration for appointment booking, and warranty checking. Clean FastAPI + Strands implementation with a Streamlit UI. Solid mid-tier sample with a realistic enterprise use case.

**AgentCore Features (7):** Runtime, Memory, Gateway, Policy, Evaluations, Observability, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (B=2) | 2 |
| Blog Post | 0 |
| Feature Count (7) | 7 |
| Unique Customer Problem | 4 |
| README Quality | 4 |
| Starter Toolkit Penalty | –2 |
| **Total** | **15** |

**Recommendation:** UPDATE

**TODO:**
1. Migrate from `bedrock-agentcore-starter-toolkit` to native `bedrock-agentcore` SDK (deploy.py pattern)
2. Add `agentcore.json` for CLI v2 deploy workflow
3. Add evaluation harness using AgentCore Evaluations API
4. Improve README with architecture diagram (currently only partial)
5. Add `.env.example` with all required variables documented
6. Add cost estimate section

---

#### 2. customer-support-assistant-vpc

**Category:** Conversational
**Starter Toolkit:** NO
**README Lines:** 305
**Prior Tier:** B (21/40)

**Summary:** VPC private networking variant of the customer support assistant — demonstrates deploying AgentCore Runtime inside a VPC with private endpoints. Narrow scope but fills a critical enterprise networking pattern gap. Shares much code with `customer-support-assistant`.

**AgentCore Features (5):** Runtime, Gateway, Observability, Browser, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (B=2) | 2 |
| Blog Post | 0 |
| Feature Count (5) | 5 |
| Unique Customer Problem | 3 |
| README Quality | 3 |
| Starter Toolkit Penalty | 0 |
| **Total** | **13** |

**Recommendation:** UPDATE

**TODO:**
1. Clearly differentiate from `customer-support-assistant` — the README should open with "This sample demonstrates VPC deployment; see the base sample for the full feature set"
2. Add a comparison table: public endpoint vs VPC private endpoint (latency, cost, security)
3. Add network diagram showing VPC, private endpoints, and AgentCore Runtime placement
4. Add terraform/CDK for VPC + endpoint provisioning (currently manual)
5. Consider merging into a single "customer-support-assistant" sample with a `--vpc` deployment flag rather than a separate duplicate sample

---

#### 3. device-management-agent

**Category:** Conversational
**Starter Toolkit:** YES — needs migration
**README Lines:** 421
**Prior Tier:** B (21/40)

**Summary:** Smart home / IoT device management agent with a Cognito-powered React frontend. Users can query and control devices conversationally. Demonstrates AgentCore Gateway with Cognito authentication and a realistic consumer IoT scenario.

**AgentCore Features (6):** Runtime, Gateway, Policy, Optimization, Observability, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (B=2) | 2 |
| Blog Post | 0 |
| Feature Count (6) | 6 |
| Unique Customer Problem | 4 |
| README Quality | 4 |
| Starter Toolkit Penalty | –2 |
| **Total** | **14** |

**Recommendation:** UPDATE

**TODO:**
1. Migrate from starter toolkit to native SDK
2. Add actual IoT device mock/simulator so users can run the full demo without real hardware
3. Add AgentCore Memory to persist device state/history across sessions
4. Streamline the Cognito setup (currently requires many manual console steps) — add a CDK or CloudFormation stack
5. Add a section on scaling to thousands of devices

---

#### 4. AWS-operations-agent

**Category:** Conversational
**Starter Toolkit:** YES — needs migration
**README Lines:** 484
**Prior Tier:** B (21/40)

**Summary:** Conversational AWS operations assistant that can query AWS services, describe resources, check health, and help with day-to-day cloud operations. Uses Strands + ADK + OpenAI Agents SDK, demonstrating AgentCore-hosted agents across frameworks. Broad AWS service coverage.

**AgentCore Features (8):** Runtime, Memory, Gateway, Policy, Evaluations, Optimization, Observability, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (B=2) | 2 |
| Blog Post | 0 |
| Feature Count (8) | 8 |
| Unique Customer Problem | 4 |
| README Quality | 4 |
| Starter Toolkit Penalty | –2 |
| **Total** | **16** |

**Recommendation:** UPDATE

**TODO:**
1. Migrate from starter toolkit to native SDK
2. The multi-framework aspect (ADK, OpenAI Agents, Strands) is a key strength — make this more prominent in the README with a framework comparison section
3. Add AgentCore Policy Engine to enforce which AWS operations the agent can perform (principle of least privilege)
4. Add evaluation scripts using AgentCore Evaluations
5. Add `agentcore.json` CLI v2 config

---

#### 5. finance-personal-assistant

**Category:** Conversational
**Starter Toolkit:** YES — needs migration
**README Lines:** 71
**Prior Tier:** C (7/40)

**Summary:** Workshop notebook-only sample for a personal finance assistant. Extremely minimal — no deployment scripts, no README architecture, no standalone runnable code. Almost purely educational material that belongs in the tutorials section.

**AgentCore Features (3):** Gateway, Policy, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (C=1) | 1 |
| Blog Post | 0 |
| Feature Count (3) | 3 |
| Unique Customer Problem | 3 |
| README Quality | 1 |
| Starter Toolkit Penalty | –2 |
| **Total** | **6** |

**Recommendation:** MAJOR OVERHAUL

**TODO:**
1. Either promote to a proper standalone sample (full README, deploy script, native SDK) or move content to `01-tutorials/`
2. If kept as a use case: add architecture diagram, deploy.py, eval scripts, and expand to 300+ line README
3. Migrate from starter toolkit to native SDK
4. Add AgentCore Memory for portfolio history, Runtime for deployment, Evaluations for response quality
5. Consider connecting to real financial data APIs (via Gateway) to make it a stronger demo
6. Add Guardrails for financial compliance

---

#### 6. healthcare-appointment-agent

**Category:** Conversational
**Starter Toolkit:** NO
**README Lines:** 268
**Prior Tier:** B (18/40)

**Summary:** Healthcare appointment booking agent with HealthLake FHIR R4 integration. Uses OpenAPI Gateway for FHIR APIs. Unique vertical (healthcare) and the only FHIR/HealthLake integration in the repo. Good concept, moderate implementation.

**AgentCore Features (5):** Runtime, Gateway, Policy, Evaluations, Observability

| Criterion | Score |
|-----------|-------|
| Existing Tier (B=2) | 2 |
| Blog Post | 0 |
| Feature Count (5) | 5 |
| Unique Customer Problem | 5 |
| README Quality | 3 |
| Starter Toolkit Penalty | 0 |
| **Total** | **15** |

**Recommendation:** UPDATE

**TODO:**
1. Expand README to 400+ lines: add FHIR data model explanation, appointment flow walkthrough, compliance notes (HIPAA considerations)
2. Add HealthLake setup automation (currently manual)
3. Add AgentCore Identity (Cognito) for patient authentication — critical for healthcare
4. Add AgentCore Memory for patient history and follow-up context
5. Add evaluation harness testing appointment booking accuracy
6. Add guardrails for PHI data protection
7. Add `agentcore.json` CLI v2 config

---

#### 7. lakehouse-agent

**Category:** Conversational
**Starter Toolkit:** YES — needs migration
**README Lines:** 837 (longest)
**Prior Tier:** A (25/40)

**Summary:** Natural language querying over a lakehouse (S3 Tables + Athena) with row-level security via OAuth claims. Includes a Streamlit UI, 8 notebooks, and an AgentCore Policy Engine interceptor. The only sample with OAuth-based row-level data access control. Companion for an AWS blog post (mentioned in README).

**AgentCore Features (8):** Runtime, Memory, Gateway, Policy, Registry, Evaluations, Optimization, Observability

| Criterion | Score |
|-----------|-------|
| Existing Tier (A=3) | 3 |
| Blog Post | 2 |
| Feature Count (8) | 8 |
| Unique Customer Problem | 5 |
| README Quality | 5 |
| Starter Toolkit Penalty | –2 |
| **Total** | **21** |

**Recommendation:** UPDATE (starter toolkit migration only)

**TODO:**
1. Migrate from starter toolkit to native SDK — this is the only required change
2. Add `agentcore.json` for CLI v2 deploy
3. Consider extracting the Policy Engine interceptor pattern into a reusable module (many samples could benefit)
4. The notebook-driven deployment is great for learning; consider adding a `deploy.py` script for production use
5. Link the AWS blog post prominently at the top of the README

---

#### 8. slide-deck-generator-memory-agent

**Category:** Conversational
**Starter Toolkit:** YES — needs migration
**README Lines:** 404
**Prior Tier:** B (18/40)

**Summary:** Presentation generator agent that demonstrates the difference between basic memory and AgentCore enhanced memory. Shows how persistent memory improves multi-session continuity for content creation tasks. Strong memory-focused use case but limited feature breadth.

**AgentCore Features (5):** Runtime, Memory, Policy, Registry, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (B=2) | 2 |
| Blog Post | 0 |
| Feature Count (5) | 5 |
| Unique Customer Problem | 3 |
| README Quality | 4 |
| Starter Toolkit Penalty | –2 |
| **Total** | **12** |

**Recommendation:** UPDATE

**TODO:**
1. Migrate from starter toolkit to native SDK
2. The basic vs. enhanced memory comparison is the core value — make this more visually compelling (side-by-side screenshots/output examples)
3. Add AgentCore Observability to show memory read/write traces
4. Add AgentCore Gateway for slide template/theme APIs (e.g., Google Slides, PowerPoint)
5. Add evaluation scripts measuring content coherence across sessions
6. Add `agentcore.json` for CLI v2

---

#### 9. video-games-sales-assistant

**Category:** Conversational
**Starter Toolkit:** YES — needs migration
**README Lines:** 139
**Prior Tier:** B (16/40)

**Summary:** E-commerce sales assistant built with Next.js + AWS Amplify Gen 2 frontend. The only sample with an Amplify Gen 2 + Next.js frontend, which is a common enterprise stack. Weak documentation but interesting frontend pattern.

**AgentCore Features (10):** Runtime, Memory, Gateway, Policy, Registry, Evaluations, Optimization, Observability, Browser, Code Interpreter

| Criterion | Score |
|-----------|-------|
| Existing Tier (B=2) | 2 |
| Blog Post | 0 |
| Feature Count (10) | 10 |
| Unique Customer Problem | 3 |
| README Quality | 1 |
| Starter Toolkit Penalty | –2 |
| **Total** | **14** |

**Recommendation:** UPDATE

**TODO:**
1. **Critical: README needs complete rewrite** — currently 139 lines with no architecture, no quickstart, no troubleshooting
2. Migrate from starter toolkit to native SDK
3. The Amplify Gen 2 + Next.js frontend is the differentiating factor — document this pattern thoroughly
4. Add architecture diagram showing Amplify → AgentCore Gateway → Runtime flow
5. Add seed data for the video games catalog
6. Add evaluation scripts for recommendation quality
7. Feature count (10) looks inflated due to broad grep — audit actual feature usage vs. mentions in docs

---

#### 10. auth0-multi-agent-obo

**Category:** Conversational
**Starter Toolkit:** NO
**README Lines:** 475
**Prior Tier:** A (27/40)

**Summary:** Multi-agent financial assistant demonstrating RFC 8693 Token Exchange (On-Behalf-Of). Coordinator mints attenuated tokens per sub-agent rather than forwarding user JWTs. Auth0 as the identity provider. The only RFC 8693 OBO implementation in the repo — a critical enterprise identity pattern.

**AgentCore Features (11):** Runtime, Memory, Gateway, Policy, Registry, Evaluations, Optimization, Observability, Browser, Payments, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (A=3) | 3 |
| Blog Post | 0 |
| Feature Count (11) | 11 |
| Unique Customer Problem | 5 |
| README Quality | 4 |
| Starter Toolkit Penalty | 0 |
| **Total** | **23** |

**Recommendation:** KEEP AS-IS (minor improvements)

**TODO:**
1. Add `agentcore.json` for CLI v2 deploy — currently CDK only
2. Add a sequence diagram showing the token exchange flow (this is the core complexity and deserves visual explanation)
3. Add AgentCore Evaluations to measure financial Q&A accuracy
4. Simplify the Auth0 setup — consider adding Terraform for the Auth0 tenant configuration
5. Add a "Why OBO matters" section explaining the security implications vs. naive JWT forwarding

---

#### 11. local-prototype-to-agentcore

**Category:** Conversational
**Starter Toolkit:** YES — needs migration
**README Lines:** 413
**Prior Tier:** B (20/40)

**Summary:** Step-by-step tutorial migrating an insurance assistant from local Strands prototype to full AgentCore deployment. Unique as the only "how to migrate to production" sample. Covers Runtime + Gateway + Identity in a journey format. Cross-references LICENSE at repo root (path will need updating after restructure).

**AgentCore Features (9):** Runtime, Memory, Gateway, Policy, Registry, Optimization, Observability, Browser, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (B=2) | 2 |
| Blog Post | 0 |
| Feature Count (9) | 9 |
| Unique Customer Problem | 4 |
| README Quality | 4 |
| Starter Toolkit Penalty | –2 |
| **Total** | **15** |

**Recommendation:** UPDATE

**TODO:**
1. Migrate from starter toolkit to native SDK — this sample is literally about the migration journey, so it should model best practices
2. Update LICENSE links after folder restructure: `../../LICENSE` → `../../../LICENSE` (and similarly in sub-READMEs)
3. Add `agentcore.json` showing the final production state
4. Add a "before/after" comparison table: local prototype metrics vs. AgentCore deployment metrics
5. Add evaluation section showing how to validate the cloud agent matches the local prototype
6. Consider adding a video walkthrough or animated GIF

---

### Category: 02 — Automation Agents

---

#### 12. event-driven-claims-agent

**Category:** Automation
**Starter Toolkit:** NO
**README Lines:** 605
**Prior Tier:** S (29/40)

**Summary:** Event-driven insurance claims processing system. Claims arrive via email, trigger S3 → EventBridge → Lambda → AgentCore Runtime pipeline. Dual-agent architecture (Claims Processor + Validation Agent). Uses ALL 7 AgentCore services. CDK + Lambda. Confidence-based routing. Production-realistic with error handling, DLQ, and seed data. Has demo video.

**AgentCore Features (8):** Runtime, Memory, Gateway, Policy, Evaluations, Optimization, Observability, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (S=4) | 4 |
| Blog Post | 0 |
| Feature Count (8) | 8 |
| Unique Customer Problem | 5 |
| README Quality | 5 |
| Starter Toolkit Penalty | 0 |
| **Total** | **22** |

**Recommendation:** KEEP AS-IS (minor improvements)

**TODO:**
1. Add `agentcore.json` for CLI v2 — this is the last gap vs. `it-incident-response-agent`
2. Add a cost estimate section (CDK + Lambda + AgentCore pricing breakdown)
3. Add architecture PNG for GitHub rendering
4. The demo video is excellent — make it more prominent in the README

---

#### 13. market-trends-agent

**Category:** Automation
**Starter Toolkit:** NO
**README Lines:** 812
**Prior Tier:** A (28/40)

**Summary:** Market research agent with browser automation, custom evaluators, and an optimization loop. The only sample with both AgentCore Browser automation and a full EVO optimization cycle. Graph-based agent architecture using LangGraph. Strong breadth of features. Companion sample for the EVO Champions benchmark.

**AgentCore Features (12):** Runtime, Memory, Gateway, Policy, Registry, Evaluations, Optimization, Observability, Payments, Browser, Code Interpreter, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (A=3) | 3 |
| Blog Post | 0 |
| Feature Count (12) | 12 |
| Unique Customer Problem | 5 |
| README Quality | 5 |
| Starter Toolkit Penalty | 0 |
| **Total** | **25** |

**Recommendation:** KEEP AS-IS (minor improvements)

**TODO:**
1. Add `agentcore.json` for CLI v2 deploy — currently manual steps
2. Improve onboarding: the setup requires many manual steps; add a single `deploy.py` that handles all prerequisites
3. Add architecture diagram showing the LangGraph → AgentCore integration
4. Add a "Results" section showing sample optimization output (before/after system prompt)
5. Add cost estimate

---

#### 14. SRE-agent

**Category:** Automation
**Starter Toolkit:** NO
**README Lines:** 404
**Prior Tier:** A (26/40)

**Summary:** Multi-agent SRE system with specialized agents for log analysis, metrics, runbook execution, and incident management. Uses MCP-based tools, Makefile + Docker for local dev, and a comprehensive docs/ directory. The only sample with operational runbook execution patterns. Strong code organization (136 files).

**AgentCore Features (10):** Runtime, Memory, Gateway, Policy, Registry, Evaluations, Optimization, Observability, Browser, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (A=3) | 3 |
| Blog Post | 0 |
| Feature Count (10) | 10 |
| Unique Customer Problem | 5 |
| README Quality | 4 |
| Starter Toolkit Penalty | 0 |
| **Total** | **22** |

**Recommendation:** KEEP AS-IS (minor improvements)

**TODO:**
1. Add `agentcore.json` for CLI v2 — missing despite strong overall quality
2. Add AgentCore Evaluations integration (currently missing formal eval harness)
3. Add a pre-built incident scenario with seed data so users can run an end-to-end demo without real infrastructure
4. Add `.env.example` — current setup requires significant manual env var hunting
5. Add cost estimate for the multi-agent setup

---

#### 15. visa-b2b-account-payable-agent

**Category:** Automation
**Starter Toolkit:** YES — needs migration
**README Lines:** 461
**Prior Tier:** A (26/40)

**Summary:** The largest sample (341 files). Multi-agent B2B accounts payable system using real Visa B2B Connect APIs. Supervisor + IDP + Match + Payment sub-agents. CDK + seeders. Deep real-world payment processing scenario. Narrow vertical but impressive depth.

**AgentCore Features (8):** Runtime, Gateway, Policy, Registry, Optimization, Observability, Payments, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (A=3) | 3 |
| Blog Post | 0 |
| Feature Count (8) | 8 |
| Unique Customer Problem | 5 |
| README Quality | 4 |
| Starter Toolkit Penalty | –2 |
| **Total** | **18** |

**Recommendation:** UPDATE

**TODO:**
1. Migrate from starter toolkit to native SDK
2. Update LICENSE cross-references after folder restructure: `../../LICENSE` → `../../../LICENSE`
3. Add AgentCore Memory for invoice/payment history across sessions
4. Add AgentCore Evaluations for payment processing accuracy
5. The DEPLOYMENT-GUIDE.md is excellent but long (935 lines) — add a quick-start that gets users running in 30 minutes
6. Add a mock Visa API mode for users without Visa B2B credentials

---

#### 16. role-based-hr-data-agent

**Category:** Automation
**Starter Toolkit:** YES — needs migration
**README Lines:** 370
**Prior Tier:** A (25/40)

**Summary:** HR data agent with Cedar authorization + Lambda interceptors for field-level DLP. Enforces role-based access (manager sees salary data; employee does not). The only sample demonstrating Cedar policy engine at field level within an agent workflow.

**AgentCore Features (7):** Runtime, Gateway, Policy, Evaluations, Optimization, Observability, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (A=3) | 3 |
| Blog Post | 0 |
| Feature Count (7) | 7 |
| Unique Customer Problem | 5 |
| README Quality | 3 |
| Starter Toolkit Penalty | –2 |
| **Total** | **16** |

**Recommendation:** UPDATE

**TODO:**
1. Migrate from starter toolkit to native SDK
2. Expand README to 500+ lines: add detailed Cedar policy explanation, role hierarchy diagram, example queries showing policy enforcement
3. Add a side-by-side demo: same question asked as manager vs. employee showing different results
4. Add more HR data scenarios (leave balance, performance reviews, org chart traversal)
5. Add evaluation harness measuring policy enforcement accuracy
6. Add `agentcore.json` for CLI v2

---

#### 17. A2A-multi-agent-incident-response

**Category:** Automation
**Starter Toolkit:** YES — needs migration
**README Lines:** 215
**Prior Tier:** B (18/40)

**Summary:** A2A protocol implementation with three agents built on different frameworks (Strands, OpenAI Agents SDK, Google ADK) for infrastructure monitoring and incident response. The only sample demonstrating three different agent frameworks in a single A2A workflow. Uses AgentCore Runtime for each agent separately.

**AgentCore Features (7):** Runtime, Memory, Gateway, Registry, Optimization, Observability, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (B=2) | 2 |
| Blog Post | 0 |
| Feature Count (7) | 7 |
| Unique Customer Problem | 5 |
| README Quality | 2 |
| Starter Toolkit Penalty | –2 |
| **Total** | **14** |

**Recommendation:** UPDATE

**TODO:**
1. Migrate from starter toolkit to native SDK
2. **Critical: README is 215 lines with minimal explanation** — needs 400+ lines with architecture diagram, agent interaction sequence diagram, framework comparison table
3. Add step-by-step quickstart for each of the three agents
4. Add AgentCore Policy Engine for controlling which agents can escalate incidents
5. Add evaluation harness for incident resolution accuracy
6. Add an incident simulation script with pre-built CloudWatch alarms

---

#### 18. A2A-realestate-agentcore-multiagents

**Category:** Automation
**Starter Toolkit:** YES — needs migration
**README Lines:** 216
**Prior Tier:** B (15/40)

**Summary:** A2A real estate multi-agent system with PropertySearch and PropertyBooking agents. Uses Cognito OAuth for A2A authentication. Sub-agent READMEs reference `../../README.md` which points to `02-use-cases/README.md` (paths will need updating post-restructure).

**AgentCore Features (10):** Runtime, Memory, Gateway, Policy, Registry, Optimization, Observability, Payments, Browser, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (B=2) | 2 |
| Blog Post | 0 |
| Feature Count (10) | 10 |
| Unique Customer Problem | 4 |
| README Quality | 2 |
| Starter Toolkit Penalty | –2 |
| **Total** | **16** |

**Recommendation:** UPDATE

**TODO:**
1. Migrate from starter toolkit to native SDK
2. **Fix cross-folder links after restructure:** In `propertybookingagent_strands/README.md` and `propertysearchagent_strands/README.md`, update `../../README.md` → `../../../README.md`
3. Expand main README to 400+ lines with property search/booking flow diagram
4. Add seed property data so users can run meaningful demos
5. Add real estate-specific evaluation scenarios (search accuracy, booking confirmation flow)
6. Add AgentCore Memory for user preferences and previous search history

---

#### 19. auth0-multi-agent-obo

*See entry #10 above — categorized under Conversational Agents.*

---

#### 20. cost-optimization-agent

**Category:** Automation
**Starter Toolkit:** YES — needs migration
**README Lines:** 211
**Prior Tier:** C (12/40)

**Summary:** AWS cost monitoring agent using Cost Explorer APIs. Minimal implementation — mostly notebook-driven. Some code interpreter usage for generating cost charts. The domain (cost optimization) is valuable but the sample is underdeveloped.

**AgentCore Features (8):** Runtime, Memory, Policy, Registry, Optimization, Observability, Code Interpreter, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (C=1) | 1 |
| Blog Post | 0 |
| Feature Count (8) | 8 |
| Unique Customer Problem | 4 |
| README Quality | 2 |
| Starter Toolkit Penalty | –2 |
| **Total** | **14** |

**Recommendation:** UPDATE

**TODO:**
1. Migrate from starter toolkit to native SDK
2. Add proper deploy.py and standalone Python agent (not just notebooks)
3. Expand README with architecture, cost Explorer API coverage, example queries
4. Add AgentCore Gateway to expose Cost Explorer APIs via MCP
5. Add evaluation scenarios (cost anomaly detection accuracy)
6. Add automated cost report scheduling (event-driven trigger via EventBridge)
7. Consider merging with `AWS-operations-agent` as a "cloud operations" sample

---

#### 21. DB-performance-analyzer

**Category:** Automation
**Starter Toolkit:** YES — needs migration
**README Lines:** 345
**Prior Tier:** B (20/40)

**Summary:** PostgreSQL database performance analyzer using AgentCore Runtime + VPC Lambda tools for DB access. Analyzes slow queries, index recommendations, and table statistics. Practical DevOps use case with VPC networking pattern.

**AgentCore Features (7):** Runtime, Memory, Gateway, Evaluations, Optimization, Observability, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (B=2) | 2 |
| Blog Post | 0 |
| Feature Count (7) | 7 |
| Unique Customer Problem | 4 |
| README Quality | 3 |
| Starter Toolkit Penalty | –2 |
| **Total** | **14** |

**Recommendation:** UPDATE

**TODO:**
1. Migrate from starter toolkit to native SDK
2. Add a pre-built PostgreSQL Docker image with sample slow queries for demo purposes
3. Add AgentCore Policy Engine to restrict which DB operations the agent can perform
4. Add evaluation harness measuring index recommendation quality
5. Expand README with PostgreSQL performance concepts overview
6. Add MySQL/Aurora support notes

---

#### 22. enterprise-web-intelligence-agent

**Category:** Automation
**Starter Toolkit:** NO
**README Lines:** 257
**Prior Tier:** C (9/40)

**Summary:** Web intelligence gathering agent with dual implementation comparison (Strands vs. another framework). Browser automation for web scraping. Minimal feature coverage. The dual implementation comparison is interesting but poorly documented.

**AgentCore Features (5):** Runtime, Registry, Evaluations, Browser, Code Interpreter

| Criterion | Score |
|-----------|-------|
| Existing Tier (C=1) | 1 |
| Blog Post | 0 |
| Feature Count (5) | 5 |
| Unique Customer Problem | 3 |
| README Quality | 2 |
| Starter Toolkit Penalty | 0 |
| **Total** | **12** |

**Recommendation:** MAJOR OVERHAUL

**TODO:**
1. Add deploy.py and proper deployment infrastructure
2. Expand to full AgentCore feature set: add Runtime, Gateway, Memory, Observability
3. The dual implementation comparison is valuable — create a proper comparison table with performance benchmarks
4. Add structured data extraction scenarios with evaluation metrics
5. Add AgentCore Memory for caching web intelligence results
6. Improve README significantly (currently 257 lines, needs architecture diagram and quickstart)

---

#### 23. farm-management-advisor

**Category:** Automation
**Starter Toolkit:** YES — needs migration
**README Lines:** 191
**Prior Tier:** C (12/40)

**Summary:** LangGraph multi-agent farm management system. Notebook-driven. The only AgriTech use case in the repo — unique vertical. Uses browser automation for weather/market data. Underdeveloped for a standalone use-case sample.

**AgentCore Features (12):** Runtime, Memory, Gateway, Policy, Registry, Evaluations, Optimization, Observability, Payments, Browser, Code Interpreter, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (C=1) | 1 |
| Blog Post | 0 |
| Feature Count (12) | 12 |
| Unique Customer Problem | 4 |
| README Quality | 2 |
| Starter Toolkit Penalty | –2 |
| **Total** | **18** |

**Recommendation:** UPDATE

**Note:** The feature count (12) appears inflated from broad grep matches — verify actual feature usage. The sample likely uses 4-5 features in practice.

**TODO:**
1. Migrate from starter toolkit to native SDK
2. Convert from notebooks to a proper standalone Python application
3. Add a realistic farm scenario with mock sensor data
4. Reduce over-feature-claiming: audit each feature and only list ones actually used
5. Add AgentCore Observability to trace the LangGraph multi-agent coordination
6. Expand README to 400+ lines with AgriTech context, data sources, and agent decision logic

---

#### 24. intelligent-event-agent

**Category:** Automation
**Starter Toolkit:** YES — needs migration
**README Lines:** 0 (NO README)
**Prior Tier:** C (1/40)

**Summary:** Notebook stub with no README, no documentation, no deployment guidance. Essentially a placeholder. Has some code (Python) but is completely undeveloped.

**AgentCore Features (6):** Runtime, Memory, Gateway, Policy, Observability, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (C=1) | 1 |
| Blog Post | 0 |
| Feature Count (6) | 6 |
| Unique Customer Problem | 2 |
| README Quality | 0 |
| Starter Toolkit Penalty | –2 |
| **Total** | **7** |

**Recommendation:** MAJOR OVERHAUL (or remove)

**TODO:**
1. **Decision required:** Either invest in making this a proper sample or remove it entirely
2. If keeping: write complete README from scratch (500+ lines), convert notebooks to deployable scripts, add proper infrastructure
3. Migrate from starter toolkit to native SDK
4. Define a clear use case: what "intelligent event" is being handled? (Calendar events? S3 events? EventBridge events?)
5. If the event handling concept is covered by `event-driven-claims-agent`, consider retiring this sample

---

#### 25. okta-auth-three-tier-end-to-end-demo

**Category:** Automation
**Starter Toolkit:** YES — needs migration
**README Lines:** 213
**Prior Tier:** B (17/40)

**Summary:** Three-tier identity demo with Okta, showing per-tier JWT isolation across frontend → AgentCore Gateway → Runtime. Important enterprise identity pattern but primarily a demo/walkthrough rather than a reusable sample.

**AgentCore Features (4):** Runtime, Gateway, Policy, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (B=2) | 2 |
| Blog Post | 0 |
| Feature Count (4) | 4 |
| Unique Customer Problem | 4 |
| README Quality | 2 |
| Starter Toolkit Penalty | –2 |
| **Total** | **10** |

**Recommendation:** UPDATE

**TODO:**
1. Migrate from starter toolkit to native SDK
2. Expand README with per-tier architecture diagram showing token flows at each tier
3. Add a "token inspection" section showing the JWT claims at each tier boundary
4. Add AgentCore Memory and Observability to make it a more complete sample
5. Consider whether this should be merged with `auth0-multi-agent-obo` into a single "identity patterns" sample that covers both Auth0 (OBO) and Okta (three-tier)

---

### Category: 03 — Coding Assistants

---

#### 26. text-to-python-ide

**Category:** Coding
**Starter Toolkit:** NO
**README Lines:** 151
**Prior Tier:** B (18/40)

**Summary:** Full-stack text-to-Python code generation IDE with React (Cloudscape) frontend and FastAPI backend. Demonstrates Code Interpreter (sandboxed execution), Runtime, Memory, and Guardrails in an interactive developer tool. Clean architecture and good frontend implementation.

**AgentCore Features (9):** Runtime, Memory, Gateway, Policy, Registry, Optimization, Observability, Browser, Code Interpreter

| Criterion | Score |
|-----------|-------|
| Existing Tier (B=2) | 2 |
| Blog Post | 0 |
| Feature Count (9) | 9 |
| Unique Customer Problem | 5 |
| README Quality | 1 |
| Starter Toolkit Penalty | 0 |
| **Total** | **17** |

**Recommendation:** UPDATE

**TODO:**
1. **Critical: README is only 151 lines** — needs complete rewrite (500+ lines) given the complexity of the sample
2. Add architecture diagram showing React → FastAPI → AgentCore Runtime → Code Interpreter flow
3. Add screenshots/GIFs of the IDE in action
4. Add quickstart from `git clone` to running IDE in 10 commands
5. Add evaluation harness measuring code generation quality
6. Add `agentcore.json` for CLI v2 deploy
7. Document the Guardrails configuration (what's blocked by default)

---

#### 27. gateway-schema-support-agent

**Category:** Coding
**Starter Toolkit:** NO
**README Lines:** 82
**Prior Tier:** B (15/40)

**Summary:** ICARUS agent that automatically converts and repairs OpenAPI specifications for AgentCore Gateway compatibility. Transforms legacy specs to OpenAPI 3.0, resolves validation errors, reduces integration time. Developer tool targeting AgentCore adopters specifically — high utility for the target audience.

**AgentCore Features (5):** Gateway, Registry, Optimization, Observability, Browser

| Criterion | Score |
|-----------|-------|
| Existing Tier (B=2) | 2 |
| Blog Post | 0 |
| Feature Count (5) | 5 |
| Unique Customer Problem | 5 |
| README Quality | 1 |
| Starter Toolkit Penalty | 0 |
| **Total** | **13** |

**Recommendation:** UPDATE

**TODO:**
1. **Critical: README is only 82 lines** — needs major expansion
2. Add before/after examples showing an OpenAPI spec before ICARUS and after (the core value proposition)
3. Add a library of common OpenAPI validation errors and how ICARUS fixes them
4. Add deploy.py for proper deployment
5. Add AgentCore Runtime for the agent itself (currently unclear how the agent is hosted)
6. Add evaluation suite measuring fix success rate on a benchmark of broken specs
7. Link prominently from `claude-code-gateway-mcp-server` and `lakehouse-agent` as a companion tool

---

#### 28. claude-code-gateway-mcp-server

**Category:** Coding
**Starter Toolkit:** YES — needs migration
**README Lines:** 104
**Prior Tier:** C (9/40)

**Summary:** Demonstrates AgentCore Gateway as a single aggregated MCP server endpoint for Claude Code. Solves context window overhead and configuration sprawl in enterprise MCP setups. Notebook-based. Valuable concept with a strong architectural insight but extremely minimal implementation.

**AgentCore Features (6):** Runtime, Memory, Gateway, Policy, Observability, Identity

| Criterion | Score |
|-----------|-------|
| Existing Tier (C=1) | 1 |
| Blog Post | 0 |
| Feature Count (6) | 6 |
| Unique Customer Problem | 5 |
| README Quality | 1 |
| Starter Toolkit Penalty | –2 |
| **Total** | **11** |

**Recommendation:** MAJOR OVERHAUL

**TODO:**
1. Migrate from starter toolkit to native SDK
2. Convert from notebook to a proper deployable sample with deploy.py
3. **Critical: The concept is excellent — the execution doesn't match.** Invest in making this a flagship developer tools sample
4. Add a real multi-server scenario (e.g., Jira + GitHub + AWS Cost Explorer all unified behind one Gateway endpoint)
5. Add `CLAUDE.md` configuration showing how to set up the MCP server in Claude Code
6. Add `.env.example` with all required tokens
7. Add benchmark: context window size before Gateway (N servers) vs. after (1 endpoint)

---

## Summary Table

| # | Sample | Category | Tier | Score | Starter Toolkit | Blog | Features | Recommendation |
|---|--------|----------|------|-------|----------------|------|----------|----------------|
| 1 | event-driven-claims-agent | Automation | S | 22 | No | — | 8 | KEEP AS-IS |
| 2 | market-trends-agent | Automation | A | 25 | No | — | 12 | KEEP AS-IS |
| 3 | auth0-multi-agent-obo | Conversational | A | 23 | No | — | 11 | KEEP AS-IS |
| 4 | SRE-agent | Automation | A | 22 | No | — | 10 | KEEP AS-IS |
| 5 | lakehouse-agent | Conversational | A | 21 | YES | Yes | 8 | UPDATE (ST only) |
| 6 | visa-b2b-account-payable-agent | Automation | A | 18 | YES | — | 8 | UPDATE |
| 7 | role-based-hr-data-agent | Automation | A | 16 | YES | — | 7 | UPDATE |
| 8 | AWS-operations-agent | Conversational | B | 16 | YES | — | 8 | UPDATE |
| 9 | A2A-realestate-agentcore-multiagents | Automation | B | 16 | YES | — | 10 | UPDATE |
| 10 | customer-support-assistant | Conversational | B | 15 | YES | — | 7 | UPDATE |
| 11 | healthcare-appointment-agent | Conversational | B | 15 | YES | — | 5 | UPDATE |
| 12 | local-prototype-to-agentcore | Conversational | B | 15 | YES | — | 9 | UPDATE |
| 13 | A2A-multi-agent-incident-response | Automation | B | 14 | YES | — | 7 | UPDATE |
| 14 | cost-optimization-agent | Automation | C | 14 | YES | — | 8 | UPDATE |
| 15 | DB-performance-analyzer | Automation | B | 14 | YES | — | 7 | UPDATE |
| 16 | device-management-agent | Conversational | B | 14 | YES | — | 6 | UPDATE |
| 17 | video-games-sales-assistant | Conversational | B | 14 | YES | — | 10* | UPDATE |
| 18 | text-to-python-ide | Coding | B | 17 | No | — | 9 | UPDATE |
| 19 | slide-deck-generator-memory-agent | Conversational | B | 12 | YES | — | 5 | UPDATE |
| 20 | farm-management-advisor | Automation | C | 18* | YES | — | 12* | UPDATE |
| 21 | gateway-schema-support-agent | Coding | B | 13 | No | — | 5 | UPDATE |
| 22 | okta-auth-three-tier-end-to-end-demo | Automation | B | 10 | YES | — | 4 | UPDATE |
| 23 | enterprise-web-intelligence-agent | Automation | C | 12 | No | — | 5 | MAJOR OVERHAUL |
| 24 | claude-code-gateway-mcp-server | Coding | C | 11 | YES | — | 6 | MAJOR OVERHAUL |
| 25 | finance-personal-assistant | Conversational | C | 6 | YES | — | 3 | MAJOR OVERHAUL |
| 26 | intelligent-event-agent | Automation | C | 7 | YES | — | 6 | MAJOR OVERHAUL |
| 27 | cost-optimization-agent | Automation | C | 14 | YES | — | 8 | UPDATE |

*Feature counts marked with `*` may be inflated due to broad grep matching; verify actual feature usage.

---

## Starter Toolkit Migration Summary

18 out of 27 samples still use `bedrock-agentcore-starter-toolkit`. These must all be migrated to the native `bedrock-agentcore` SDK:

**HIGH PRIORITY** (high-quality samples that need immediate migration):
- `lakehouse-agent` (Tier A, score 21)
- `visa-b2b-account-payable-agent` (Tier A, score 18)
- `role-based-hr-data-agent` (Tier A, score 16)

**MEDIUM PRIORITY** (Tier B samples):
- `customer-support-assistant`, `device-management-agent`, `AWS-operations-agent`
- `local-prototype-to-agentcore`, `A2A-multi-agent-incident-response`, `A2A-realestate-agentcore-multiagents`
- `DB-performance-analyzer`, `okta-auth-three-tier-end-to-end-demo`, `slide-deck-generator-memory-agent`
- `video-games-sales-assistant`

**LOW PRIORITY** (Tier C samples needing overhaul anyway):
- `finance-personal-assistant`, `farm-management-advisor`, `cost-optimization-agent`
- `intelligent-event-agent`, `claude-code-gateway-mcp-server`

### Migration Pattern

Replace starter toolkit usage with:
```python
# Before (starter toolkit)
from bedrock_agentcore_starter_toolkit import AgentCoreApp
app = AgentCoreApp()

# After (native SDK)
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()
```

And replace CDK-based deployment with `deploy.py`:
```python
from bedrock_agentcore.tools.bedrock_agentcore_client import BedrockAgentCoreClient
client = BedrockAgentCoreClient(region, account_id)
client.create_agent_runtime(...)
```

---

## Cross-Folder Link Fixes Required After Restructure

When moving samples into `01-conversational-agents/`, `02-automation-agents/`, or `03-coding-assistants/`, the following links in files go above the sample level and will need updating:

### `local-prototype-to-agentcore` → `01-conversational-agents/`

| File | Current Link | Updated Link |
|------|-------------|--------------|
| `README.md` | `../../LICENSE` | `../../../LICENSE` |
| `local_prototype/README.md` | `../../../LICENSE` | `../../../../LICENSE` |
| `local_prototype/local_strands_insurance_agent/README.md` | `../../../../LICENSE` | `../../../../../LICENSE` |

### `A2A-realestate-agentcore-multiagents` → `02-automation-agents/`

| File | Current Link | Updated Link |
|------|-------------|--------------|
| `propertybookingagent_strands/README.md` | `../../README.md` | `../../../README.md` |
| `propertysearchagent_strands/README.md` | `../../README.md` | `../../../README.md` |
| `propertybookingagent_strands/README.md` | `../../LOCAL_DEVELOPMENT.md` | `../../../LOCAL_DEVELOPMENT.md` |
| `propertysearchagent_strands/README.md` | `../../LOCAL_DEVELOPMENT.md` | `../../../LOCAL_DEVELOPMENT.md` |
| `propertybookingagent_strands/README.md` | `../../AGENTCORE_DEPLOYMENT.md` | `../../../AGENTCORE_DEPLOYMENT.md` |
| `propertysearchagent_strands/README.md` | `../../AGENTCORE_DEPLOYMENT.md` | `../../../AGENTCORE_DEPLOYMENT.md` |

### `visa-b2b-account-payable-agent` → `02-automation-agents/`

All internal links in `DEPLOYMENT-GUIDE.md` and `DEPLOYMENT-QUICK-START.md` that use `../` patterns are relative within the project and will not be affected.

---

## Restructuring Map

### `01-conversational-agents/` (11 samples)
```
01-conversational-agents/
  auth0-multi-agent-obo/
  AWS-operations-agent/
  customer-support-assistant/
  customer-support-assistant-vpc/
  device-management-agent/
  finance-personal-assistant/
  healthcare-appointment-agent/
  lakehouse-agent/
  local-prototype-to-agentcore/
  slide-deck-generator-memory-agent/
  video-games-sales-assistant/
```

### `02-automation-agents/` (13 samples)
```
02-automation-agents/
  A2A-multi-agent-incident-response/
  A2A-realestate-agentcore-multiagents/
  cost-optimization-agent/
  DB-performance-analyzer/
  enterprise-web-intelligence-agent/
  event-driven-claims-agent/
  farm-management-advisor/
  intelligent-event-agent/
  market-trends-agent/
  okta-auth-three-tier-end-to-end-demo/
  role-based-hr-data-agent/
  SRE-agent/
  visa-b2b-account-payable-agent/
```

### `03-coding-assistants/` (3 samples)
```
03-coding-assistants/
  claude-code-gateway-mcp-server/
  gateway-schema-support-agent/
  text-to-python-ide/
```

---

## Priority Action Plan

### Immediate (block releases)
1. Fix `intelligent-event-agent` — either build it out or remove it (currently a no-README stub)
2. Migrate all 18 starter-toolkit samples to native SDK (can be batched per category)

### Short-term (next sprint)
3. Add `agentcore.json` to `event-driven-claims-agent`, `market-trends-agent`, `SRE-agent` — these are the best samples and should lead by example
4. Expand READMEs for `text-to-python-ide` (151 lines), `gateway-schema-support-agent` (82 lines), `video-games-sales-assistant` (139 lines), `claude-code-gateway-mcp-server` (104 lines)

### Medium-term
5. Major overhaul of `finance-personal-assistant` and `claude-code-gateway-mcp-server` — strong concepts, weak execution
6. Add evaluation harnesses across Tier B samples
7. Standardize deploy.py pattern across all samples

### Ongoing
8. Update `02-use-cases/README.md` to reflect new category structure with links to each subfolder
9. Keep feature count claims honest — audit and remove inflated feature mentions
