# AgentCore Policy for Healthcare Appointment Agent

This is the companion code sample for the blog post [Secure AI Agents with Policy in Amazon Bedrock AgentCore](https://aws.amazon.com/blogs/machine-learning/). It implements the four Cedar policy use cases from the blog — identity-based access, scope-based read/write separation, time-based clinic hours, and forbid rules — as runnable Python scripts that deploy policies, attach them to an AgentCore Gateway, and test them against a live healthcare appointment scheduling agent.

> **Quick start:** Run `python policy/setup_policy.py` to deploy all four policies, then `python policy/test_policy.py` to see each use case tested in isolation with real FHIR tools. See [Setup](#setup) below for prerequisites.

Deterministic, tool-level access control for AI agents using [Cedar policies](https://docs.cedarpolicy.com/) enforced at the [AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html).

```
User/Agent → Gateway (Custom JWT auth) → Policy Engine (Cedar) → FHIR Tools
                                              │
                                         ALLOW / DENY
```

## Setup

```bash
cd 02-use-cases/healthcare-appointment-agent
source .venv/bin/activate

# 1. Configure Cognito to inject role + patient_id into JWT tokens
python policy/setup_cognito_claims.py --role patient --sub adult-patient-001

# 2. Deploy all four policies and attach to gateway
python policy/setup_policy.py

# 3. Run the automated test suite (output → policy/test_output.txt)
python policy/test_policy.py

# 4. Clean up
python policy/setup_policy.py --cleanup
```

## Use Cases

Each use case is tested in isolation — only its policies are deployed during testing.

---

### Use Case 1: Identity-Based Access

Patients can only read their own records. The tool input must match the JWT `patient_id` claim.

```cedar
permit(principal, action == AgentCore::Action::"Target1___getPatient",
       resource == AgentCore::Gateway::"<arn>")
when {
  principal.getTag("role") == "patient" &&
  context.input has patient_id &&
  context.input.patient_id == principal.getTag("patient_id")
};
```

| Test | Result |
|------|--------|
| Patient reads own record | ✅ Allowed |
| Patient reads other patient | ❌ Denied |

**Try it manually** (as patient `adult-patient-001`):
```bash
python strands_agent.py --gateway_id <your-gateway-id>
```
- `Get patient information for patient ID adult-patient-001` → ✅ own data returned
- `Get patient information for patient ID pediatric-patient-001` → ❌ denied by policy

---

### Use Case 2: Scope-Based Read/Write

OAuth scopes gate which tools are available. `healthcare.read` → read tools, `healthcare.write` → write tools.

```cedar
permit(principal, action in [AgentCore::Action::"Target1___getPatient",
       AgentCore::Action::"Target1___searchImmunization",
       AgentCore::Action::"Target1___getSlots"],
       resource == AgentCore::Gateway::"<arn>")
when { principal.getTag("scope") like "*healthcare.read*" };
```

> Cognito scope names use dots (`healthcare.read`) because Cognito doesn't allow `/` in scope names.

| Test | Result |
|------|--------|
| Read scope → getSlots | ✅ Allowed |
| Read scope → bookAppointment | ❌ Denied (tool hidden) |
| Read+Write scope → bookAppointment | ✅ Allowed |

**Try it manually** (switch to scheduler role to avoid forbid interference):
```bash
python policy/setup_cognito_claims.py --role scheduler --sub scheduler-001 --update-only
python strands_agent.py --gateway_id <your-gateway-id>
```
- `Check available appointment slots for 2025-09-15` → ✅ slots returned
- `Book an appointment for patient adult-patient-001 on 2025-09-15 at 14:00` → ❌ denied (no write scope)

---

### Use Case 3: Time-Based Access

`getSlots` restricted to clinic hours (9 AM – 9 PM UTC) using the gateway's system clock. The agent cannot manipulate this value.

```cedar
permit(principal, action == AgentCore::Action::"Target1___getSlots",
       resource == AgentCore::Gateway::"<arn>")
when {
  (!(((context.system.now).toTime()) < (duration("9h")))) &&
  ((((context.system.now).toTime()) <= (duration("21h"))))
};
```

| Test | Result |
|------|--------|
| During 9 AM – 9 PM UTC | ✅ Allowed |
| Outside 9 AM – 9 PM UTC | ❌ Denied |

**Try it manually** (run during clinic hours):
```bash
python strands_agent.py --gateway_id <your-gateway-id>
```
- `Check available appointment slots for 2025-09-15` → ✅ slots returned (if within 9 AM – 9 PM UTC)

---

### Use Case 4: Forbid Rules (Before/After)

`forbid` always overrides `permit`. Even with a write scope, patients cannot book.

```cedar
forbid(principal, action == AgentCore::Action::"Target1___bookAppointment",
       resource == AgentCore::Gateway::"<arn>")
when { principal.getTag("role") == "patient" };
```

| Test | Result |
|------|--------|
| BEFORE (scope only): patient books | ✅ Allowed |
| AFTER (scope + forbid): patient books | ❌ Denied (tool hidden) |

**Try it manually:**
```bash
# BEFORE — detach policy, patient can book freely
python policy/detach_policy.py
python strands_agent.py --gateway_id <your-gateway-id>
```
- `Book an appointment for patient adult-patient-001 on 2025-09-15 at 10:00` → ✅ booking succeeds

```bash
# AFTER — re-attach policy, forbid rule blocks booking
python policy/attach_policy.py
python strands_agent.py --gateway_id <your-gateway-id>
```
- `Book an appointment for patient adult-patient-001 on 2025-09-15 at 10:00` → ❌ denied

---

## Reference

**Utility commands:**
```bash
python policy/setup_cognito_claims.py --verify                                              # check JWT claims
python policy/setup_cognito_claims.py --role patient --sub adult-patient-001 --update-only   # restore patient role
```

**Files:**

| File | Purpose |
|------|---------|
| `setup_policy.py` | Deploy engine + 4 policies (`--cleanup` to remove) |
| `test_policy.py` | Automated test suite → `test_output.txt` |
| `setup_cognito_claims.py` | Configure JWT claims via Cognito Lambda |
| `attach_policy.py` / `detach_policy.py` | Toggle policy enforcement |
| `cedar/` | Standalone Cedar policy files (1–4) |

**JWT Claims:**

| Claim | Cedar Access | Source |
|-------|-------------|--------|
| `role` | `principal.getTag("role")` | Cognito Lambda trigger |
| `patient_id` | `principal.getTag("patient_id")` | Cognito Lambda trigger |
| `scope` | `principal.getTag("scope")` | Cognito client_credentials flow |

**Troubleshooting:**

| Problem | Fix |
|---------|-----|
| All requests denied | Check engine is ACTIVE: `python policy/setup_policy.py` |
| Cross-patient access works | Verify JWT claims: `python policy/setup_cognito_claims.py --verify` |
| Scope tests fail | `test_policy.py` auto-configures scopes; check Cognito permissions |

**Resources:**
[AgentCore Policy Docs](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html) · [Cedar Language](https://docs.cedarpolicy.com/) · [Policy Tutorial](../../../01-tutorials/08-AgentCore-policy/)
