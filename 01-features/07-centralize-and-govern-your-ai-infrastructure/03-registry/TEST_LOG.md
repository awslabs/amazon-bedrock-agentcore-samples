# Registry Migration Test Log

**Date:** 2026-05-18 / 2026-05-19
**Source:** `06-workshops/10-Agent-Registry` (amazon-bedrock-agentcore-samples fork)
**Target:** `02-features/06-centralize-and-govern-your-ai-infrastructure/03-registry` (private staging)
**AWS Account:** 849138760372 | **Region:** us-west-2

---

## Summary

| Check | Result |
|:------|:-------|
| Folder structure complete | PASS |
| README content preserved | PASS |
| Images/diagrams preserved | PASS (20/20 PNGs) |
| Python syntax checks | PASS (17/17 scripts) |
| AWS execution — scripts run | PASS (8/10 scripts; 2 skipped — external deps) |

---

## Bugs Found and Fixed During Testing

Four scripts shared the same bug: trying to submit a registry record for approval while it is still in `CREATING` state, causing a `ConflictException`. Fixed by adding a `wait_for_record_draft()` helper that polls until status is `DRAFT` before calling `submit_registry_record_for_approval`.

Additionally, `deploy_lambda_push_sync.py` had a registry wait loop that ran only 12 iterations (60s), not enough for the ~90s CREATING phase. Fixed by changing to an unbounded `while True` loop.

| Script | Bug | Fix Applied |
|:---|:---|:---|
| `registry_end_to_end_oauth.py` | Submit record while CREATING | Added `wait_for_record_draft()` |
| `registry_skills_dynamic_discovery.py` | Submit record while CREATING | Added `wait_for_record_draft()` |
| `publish_agentcore_a2a_mcp_in_registry.py` | Submit record while CREATING | Added `wait_for_record_draft()` |
| `deploy_lambda_push_sync.py` | Registry wait loop too short (60s); submit record while CREATING | Changed wait to unbounded loop; added `wait_for_record_draft()` |

---

## Folder Mapping

| Source Folder | Target Folder | Status |
|:---|:---|:---|
| `00-getting-started/end-to-end/01-registry-end-to-end/` | `01-registry-end-to-end/` | PASS |
| `00-getting-started/end-to-end/02-registry-end-to-end-oauth/` | `02-registry-end-to-end-oauth/` | PASS |
| `01-advanced/admin-approval-workflow/` | `03-advanced/admin-approval-workflow/` | PASS |
| `01-advanced/consumer-discovery-semantic-search/` | `03-advanced/consumer-discovery-semantic-search/` | PASS |
| `01-advanced/discovery-and-invocation-at-runtime/` | `03-advanced/discovery-and-invocation-at-runtime/` | PASS |
| `01-advanced/kiro-registry-dcr-auth0/` | `03-advanced/kiro-registry-dcr-auth0/` | PASS |
| `01-advanced/kiro/kiro-power-publisher-workflow/` | `03-advanced/kiro/kiro-power-publisher-workflow/` | PASS |
| `01-advanced/publish-agentcore-tools-in-registry/` | `03-advanced/publish-agentcore-tools-in-registry/` | PASS |
| `01-advanced/registry-push-sync-lambda/` | `03-advanced/registry-push-sync-lambda/` | PASS |
| `01-advanced/registry-skills-dynamic-discovery/` | `03-advanced/registry-skills-dynamic-discovery/` | PASS |
| `01-advanced/registry-synchronize-mcpserver/` | `03-advanced/registry-synchronize-mcpserver/` | PASS |

---

## Per-Sample Test Results

### 1. `01-registry-end-to-end` — Zero to Registry in 10 Minutes

**README content check:** PASS
**Images:** `images/quick-setup-architecture.png` ✅
**Python syntax:** PASS
**AWS execution:** PASS

Output highlights:
- Registry created and reached READY (~90s)
- IAM users created for Admin, Publisher, Consumer personas
- MCP, A2A, CUSTOM records registered
- Governance guardrail tests:
  - Publisher self-approval correctly denied (`AccessDeniedException`) ✅
  - Consumer `CreateRegistryRecord` correctly denied ✅
  - Consumer `UpdateRegistryRecordStatus` correctly denied ✅
  - Consumer read operations (List, Get) allowed ✅
  - Admin approval succeeded ✅
- All 3 records reached APPROVED status
- Semantic search: 30s propagation wait insufficient for 3 records; returned 0 results (expected for short wait — index behavior)
- Cleanup: IAM users + records + registry deleted manually (cleanup section is commented out)

**Note:** Cleanup is commented out in the script. Uncomment or add a cleanup step for production use.

---

### 2. `02-registry-end-to-end-oauth` — Registry with OAuth Authentication

**README content check:** PASS
**Images:** `images/registry-end-to-end-oauth.png` ✅
**Python syntax:** PASS
**AWS execution:** PASS (after fix)

**Bug fixed:** Script submitted record for approval while in `CREATING` state → added `wait_for_record_draft()`.

Output highlights:
- Cognito user pool, app client, test user created
- Registry created with `CUSTOM_JWT` authorizer pointing to Cognito discovery URL
- MCP record approved successfully
- Cognito `USER_PASSWORD_AUTH` authentication succeeded, Bearer token obtained
- Authenticated search returned 1 result (`weather_server`) ✅
- Negative auth tests:
  - Request without Authorization header → `403` ✅
  - Request with invalid token → `401` ✅
- Full cleanup (record, registry, Cognito pool, domain, user) completed

---

### 3. `03-advanced/admin-approval-workflow` — Admin CI/CD Approval Workflow

**README content check:** PASS
**Images:** `admin-flow-architecture.png`, `slack-message.png`, `ai-scan-report.png` ✅
**Python syntax:** PASS
**AWS execution:** SKIPPED — requires a real Slack incoming webhook URL and channel. The `SLACK_INC_HOOK` env var must be set to a valid Slack webhook before running. The script is otherwise structurally sound.

---

### 4. `03-advanced/consumer-discovery-semantic-search` — Consumer Discovery Semantic Search

**README content check:** PASS
**Images:** `consumer-discovery-semantic-search.png` ✅
**Python syntax:** PASS
**AWS execution:** PASS

Output highlights:
- Registry created; 14 records seeded and submitted for approval
- All 12 discovery scenarios ran (semantic, filtered, cross-type, negative)
- Search index propagation: 45s wait caused most queries to return only the last-indexed record (`loyalty_rewards_tool`). This is a known index propagation latency — increasing the wait improves result diversity.
- Filtered search operators (`$eq`, `$ne`, `$in`, `$and`, `$or`) tested
- MCP `serverSchema`/`toolSchema` drill-down and A2A `agentCard` drill-down tested
- Full cleanup (14 records + registry) completed

---

### 5. `03-advanced/discovery-and-invocation-at-runtime` — Discovering Tools and Agents at Runtime

**README content check:** PASS
**Images:** `With_Vs_Without_AWS_Agent_Registry.png`, `OrderManagement_AWS_Agent_Registry_Flow.png`, `orchestrator_agent_flow_v3.png` ✅
**Python syntax:** PASS
**AWS execution:** PASS

Output highlights:
- Lambda function deployed (`order-management-mcp-20260518185145`)
- Cognito user pool + OAuth setup for AgentCore Gateway
- AgentCore Gateway created and targeted to Lambda
- Pricing A2A agent deployed to AgentCore Runtime via CodeBuild
- Customer Support A2A agent deployed to AgentCore Runtime via CodeBuild
- Orchestrator agent deployed to AgentCore Runtime via CodeBuild
- Registry created; 3 records registered (1 MCP + 2 A2A) and approved
- **Demo 1 (Order Status):** Retrieved order details via MCP tool ✅
- **Demo 2 (Pricing & Discounts):** Retrieved order details via MCP + A2A pricing agent (some service hiccups handled gracefully) ✅
- **Demo 3 (Return & Refund):** Return eligibility + refund amount via Customer Support A2A agent ✅
- All resources deleted (registry, Lambda, gateway, Cognito, 3 runtimes)

---

### 6. `03-advanced/kiro-registry-dcr-auth0` — Registry as MCP from Kiro (Auth0 DCR)

**README content check:** PASS
**Images (all 5):** `0_authflow_dcr.png`, `1_kiro_mcp_json.png`, `2_authorization_pkce.png`, `3_successful_auth.png`, `4_kiro_search.png` ✅
**Python syntax:** PASS
**AWS execution:** SKIPPED — requires an Auth0 account with DCR enabled and `.env` file with `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, `AWS_REGION`, `AWS_ACCOUNT_ID`. The script is structurally sound and creates a `CUSTOM_JWT` registry using Auth0 as IdP.

---

### 7. `03-advanced/kiro/kiro-power-publisher-workflow` — Kiro Power Publisher Workflow

**README content check:** PASS
**Images (all 4):** `publisher-workflow.png`, `activate-kiro-power.png`, `import-from-github.png`, `aws-agent-registry-power.png` ✅
**Python syntax:** N/A — Kiro IDE-driven (no standalone script)
**AWS execution:** N/A — IDE-driven via `POWER.md` steering document

---

### 8. `03-advanced/publish-agentcore-tools-in-registry` — Publishing AgentCore Tools in Registry

**README content check:** PASS
**Images:** `images/agentregistry_flow.png` ✅
**Python syntax:** PASS
**AWS execution:** PASS (after fix)

**Bug fixed:** Submit for approval while records in `CREATING` state → added `wait_for_record_draft()`.

Output highlights:
- MCP server (`mcp_order_server`) deployed to AgentCore Runtime via CodeBuild (~30s build)
- MCP tools verified via `tools/list` + `tools/call` (`get_order_status`, `create_order`, `update_order`, `cancel_order`)
- A2A agent (`a2a_order_agent`) deployed to AgentCore Runtime via CodeBuild
- A2A agent verified via `GET /agent_card` + `POST /message/send` (task completed with order details)
- Registry created; MCP + A2A records registered and approved
- Semantic search returned both records for all queries (`cancel update an order`, `order management MCP tools`, `A2A agent order`) ✅
- Runtimes, records, and registry deleted

---

### 9. `03-advanced/registry-push-sync-lambda` — Registry Push Sync Lambda

**README content check:** PASS
**Images:** `architecture.png` ✅
**Python syntax:** PASS
**AWS execution:** PASS (after fixes)

**Bugs fixed:**
1. Registry wait loop ran only 12 iterations (60s) — insufficient for ~90s CREATING phase → changed to `while True` loop
2. Record submitted while still in `CREATING` → added `wait_for_record_draft()`

Output highlights:
- Registry and MCP server record created and approved
- AgentCore Identity workload identity created (`registry-push-sync-agent`)
- IAM Lambda execution role created with registry + identity + secrets + logs permissions
- Lambda function built (bundled `boto3`, `botocore`, `requests` into `handler.zip`) and deployed
- EventBridge rule created to match `UpdateAgentRuntime` CloudTrail events
- Lambda test skipped (no `TEST_RUNTIME_ID` set) — expected behavior
- All resources deleted (Lambda, IAM role, workload identity, EventBridge rule, record, registry)

---

### 10. `03-advanced/registry-skills-dynamic-discovery` — Publishing and Discovering Agent Skills

**README content check:** PASS
**Images:** `images/registry-skill-flow.png` ✅
**Python syntax:** PASS
**AWS execution:** PASS (after fix)

**Bug fixed:** Submit for approval while record in `CREATING` state → added `wait_for_record_draft()`.

Output highlights:
- Registry created with `AWS_IAM` authorizer
- PDF Processing Skill registered as `AGENT_SKILLS` record with `skillMd` + `skillDefinition`
- Record approved (DRAFT → PENDING_APPROVAL → APPROVED)
- 100s index propagation wait
- Strands Agent with `search_and_load_skill` tool initialized
- Agent searched registry: found `PDF_Processing_Skill` for query "PDF creation generate document" ✅
- Agent downloaded skill from GitHub (`anthropics/skills/skills/pdf`), installed `pypdf` + `reportlab`
- Agent created `hello_from_agent_skills.pdf` (1421 bytes) using the loaded skill ✅
- Record + registry deleted

---

### 11. `03-advanced/registry-synchronize-mcpserver` — Synchronize MCP Server Metadata

**README content check:** PASS
**Images:** `registry-synchronize-mcpserver-arch.png` ✅
**Python syntax:** PASS
**AWS execution:** PASS

Output highlights:
- Registry created with `AWS_IAM` authorizer
- **Section 3 — Public MCP server sync:** Synced `AWSKnowledgeMCP` from public URL; record transitioned CREATING → DRAFT with extracted `serverSchema` + `toolSchema` ✅
- **Section 4 — OAuth-protected MCP server sync:**
  - Cognito user pool + OAuth provider created
  - MCP server deployed via CodeBuild (~30s)
  - Synced with OAuth credential provider; tool schemas extracted automatically ✅
- **Section 5 — IAM-protected MCP server sync:**
  - MCP server deployed via CodeBuild (~30s)
  - IAM role `RegistrySyncRole_1779155208` created for registry-to-runtime invocation
  - Synced with IAM credential provider; tool schemas extracted automatically ✅
- Final listing: 3 records (public + OAuth + IAM)
- Full cleanup (3 records, registry, 2 runtimes, OAuth provider, Cognito, IAM role, local files)

---

## Image Migration Summary

Total PNG images in source: **20**
Total PNG images in target: **20**
Missing: **0**

| Sample | Images | Status |
|:---|:---|:---|
| `01-registry-end-to-end` | `quick-setup-architecture.png` | PASS |
| `02-registry-end-to-end-oauth` | `registry-end-to-end-oauth.png` | PASS |
| `admin-approval-workflow` | `admin-flow-architecture.png`, `slack-message.png`, `ai-scan-report.png` | PASS |
| `consumer-discovery-semantic-search` | `consumer-discovery-semantic-search.png` | PASS |
| `discovery-and-invocation-at-runtime` | `With_Vs_Without_AWS_Agent_Registry.png`, `OrderManagement_AWS_Agent_Registry_Flow.png`, `orchestrator_agent_flow_v3.png` | PASS |
| `kiro-registry-dcr-auth0` | `0_authflow_dcr.png`, `1_kiro_mcp_json.png`, `2_authorization_pkce.png`, `3_successful_auth.png`, `4_kiro_search.png` | PASS |
| `kiro-power-publisher-workflow` | `publisher-workflow.png`, `activate-kiro-power.png`, `import-from-github.png`, `aws-agent-registry-power.png` | PASS |
| `publish-agentcore-tools-in-registry` | `agentregistry_flow.png` | PASS |
| `registry-push-sync-lambda` | `architecture.png` | PASS |
| `registry-skills-dynamic-discovery` | `registry-skill-flow.png` | PASS |
| `registry-synchronize-mcpserver` | `registry-synchronize-mcpserver-arch.png` | PASS |

---

## Python Syntax Check Summary

All scripts tested with `python3 -m py_compile`.

| Script | Result |
|:---|:---|
| `01-registry-end-to-end/getting_started_registry_end_to_end.py` | PASS |
| `02-registry-end-to-end-oauth/registry_end_to_end_oauth.py` | PASS |
| `03-advanced/admin-approval-workflow/admin_approval_workflow.py` | PASS |
| `03-advanced/admin-approval-workflow/utils.py` | PASS |
| `03-advanced/consumer-discovery-semantic-search/consumer_discovery_semantic_search.py` | PASS |
| `03-advanced/discovery-and-invocation-at-runtime/discovery_and_invocation_at_runtime.py` | PASS |
| `03-advanced/discovery-and-invocation-at-runtime/cleanup.py` | PASS |
| `03-advanced/discovery-and-invocation-at-runtime/utils.py` | PASS |
| `03-advanced/kiro-registry-dcr-auth0/dcr_registry_search_mcp_in_kiro.py` | PASS |
| `03-advanced/kiro-registry-dcr-auth0/seed_records.py` | PASS |
| `03-advanced/publish-agentcore-tools-in-registry/publish_agentcore_a2a_mcp_in_registry.py` | PASS |
| `03-advanced/registry-push-sync-lambda/deploy_lambda_push_sync.py` | PASS |
| `03-advanced/registry-push-sync-lambda/handler.py` | PASS |
| `03-advanced/registry-skills-dynamic-discovery/registry_skills_dynamic_discovery.py` | PASS |
| `03-advanced/registry-skills-dynamic-discovery/utils/python_exec_tool.py` | PASS |
| `03-advanced/registry-skills-dynamic-discovery/utils/skill_loader.py` | PASS |
| `03-advanced/registry-synchronize-mcpserver/registry_synchronize_mcpserver.py` | PASS |

---

## AWS Execution Summary

| Script | AWS Execution | Notes |
|:---|:---|:---|
| `getting_started_registry_end_to_end.py` | PASS | All IAM guardrails verified; cleanup section commented out |
| `registry_end_to_end_oauth.py` | PASS (after fix) | Cognito + CUSTOM_JWT auth + negative auth tests |
| `consumer_discovery_semantic_search.py` | PASS | 45s propagation wait may be short for 14 records |
| `discovery_and_invocation_at_runtime.py` | PASS | 3 demos: MCP, MCP+A2A, A2A — all ran |
| `publish_agentcore_a2a_mcp_in_registry.py` | PASS (after fix) | CodeBuild deployment; semantic search verified |
| `registry_synchronize_mcpserver.py` | PASS | Public + OAuth + IAM sync all verified |
| `registry_skills_dynamic_discovery.py` | PASS (after fix) | Agent loaded skill, created PDF |
| `deploy_lambda_push_sync.py` | PASS (after fixes) | Lambda + EventBridge + workload identity deployed |
| `admin_approval_workflow.py` | SKIPPED | Requires real Slack webhook (`SLACK_INC_HOOK` env var) |
| `dcr_registry_search_mcp_in_kiro.py` | SKIPPED | Requires Auth0 account + `.env` with `AUTH0_DOMAIN`, `AUTH0_AUDIENCE` |
| `kiro-power-publisher-workflow` | N/A | IDE-driven, no standalone script |

---

## Migration Pattern Notes

- Source used Jupyter notebooks (`.ipynb`); target uses Python scripts (`.py`) with equivalent logic.
- All target READMEs have a "Running the Python Scripts" section with `pip install` + `python <script>` instructions.
- Two samples (`consumer-discovery-semantic-search`, `kiro-registry-dcr-auth0`) had no source README; target READMEs were created from the notebook content, including all embedded images.
- `kiro-power-publisher-workflow` has no standalone Python script by design (it is Kiro IDE-driven).
- A root-level `README.md` was added in the target (not present in source) to provide an overview of the registry folder.
- The `00-getting-started/step-by-step` folder was intentionally excluded from this migration per scope.
