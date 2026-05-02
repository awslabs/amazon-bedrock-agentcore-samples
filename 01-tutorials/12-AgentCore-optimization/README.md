# AgentCore Optimization Tutorial — HR Assistant

## Overview

This tutorial demonstrates the complete **Amazon Bedrock AgentCore Optimization** workflow: measure your agent's baseline performance, generate AI-driven recommendations, package them into Configuration Bundles, and validate improvements with live A/B testing.

The demo agent is an **HR Assistant** that handles PTO requests, policy lookups, benefits questions, and pay stub retrieval for Acme Corp employees.

### What You Will Learn

| Stage | Concepts Covered |
|-------|-----------------|
| **Baseline Evaluation** | Batch evaluations on agent sessions |
| **Recommendations** | System prompt optimization, tool description optimization from production traces |
| **Configuration Bundles** | Versioned config containers, runtime config hooks, baggage-based injection |
| **A/B Test: Config-Bundle Routing** | Prompt-level A/B testing without redeployment, online evaluation, statistical analysis |
| **A/B Test: Target-Based Routing** | Code-level A/B testing, phased rollout (90/10 canary), multi-runtime comparison |

---

## Architecture

```
                        ┌─────────────────────────────────────────────────────────────┐
                        │                  AgentCore Optimization Loop                 │
                        │                                                               │
                        │  1. Invoke Agent ──────────► CloudWatch Logs (OTel spans)   │
                        │                                         │                     │
                        │  2. Batch Evaluate ◄────────────────────┘                   │
                        │     GoalSuccessRate / Helpfulness / Correctness              │
                        │                │                                              │
                        │  3. Recommend ─┘  ──► Improved System Prompt                │
                        │                        Improved Tool Descriptions            │
                        │                                │                              │
                        │  4. Bundle ───────────────────►│  Configuration Bundle (C)   │
                        │                                 │  Configuration Bundle (T1)  │
                        │                                 │                             │
                        │  5a. A/B Test ─────────────────┘                             │
                        │      Config-Bundle Routing: same runtime, different prompts  │
                        │                                                               │
                        │  5b. A/B Test (target-based)                                 │
                        │      Target Routing: different runtimes (v1 vs v2)           │
                        └─────────────────────────────────────────────────────────────┘

Config-Bundle A/B Architecture:

  User ──► [Gateway] ──50%──► [Config Bundle C  → HR Runtime v1] ──► CloudWatch
                  │                                                         │
                  └──50%──► [Config Bundle T1 → HR Runtime v1] ──► CloudWatch
                                                                            │
                                                              [Online Eval] ┘ ──► A/B Results

Target-Based A/B Architecture (Phased Rollout):

  User ──► [Gateway] ──90%──► [Target HRAgentV1 → HR Runtime v1 (stable)] ──► CloudWatch
                  │                                                                    │
                  └──10%──► [Target HRAgentV2 → HR Runtime v2 (canary)]  ──► CloudWatch
                                                                                       │
                                                                 [Online Eval v1+v2] ──┘ ──► A/B Results
```

### Key Components

| Component | Service | Purpose |
|-----------|---------|---------|
| AgentCore Runtime | `bedrock-agentcore-control` | Hosts the HR Assistant container |
| Configuration Bundle | `bedrock-agentcore-control` | Versioned system prompt storage |
| Batch Evaluation | `bedrock-agentcore` (DP) | Off-line scoring of historical sessions |
| Recommendation | `bedrock-agentcore` (DP) | AI-generated prompt/tool improvements |
| Gateway + Targets | `bedrock-agentcore-control` | Traffic routing for A/B tests |
| Online Eval Config | `bedrock-agentcore-control` | Continuous automatic session scoring |
| A/B Test | `bedrock-agentcore` (DP) | Traffic split + statistical comparison |

---

## Getting Started

### Prerequisites

- AWS account with Bedrock AgentCore access enabled
- AWS CLI configured: `aws configure` (or set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`)
- IAM permissions: `bedrock-agentcore:*`, `bedrock:InvokeModel`, `iam:*`, `s3:*`, `logs:*`, `xray:*`
- Python 3.10 or later

### Option 1: Jupyter Notebook

Run the full tutorial interactively:

```bash
# Install Jupyter if needed
pip install jupyter

# Install dependencies (also done in the notebook's first cell)
pip install "bedrock-agentcore>=1.7.0" "boto3>=1.43.0" requests

# Launch the notebook
jupyter notebook optimization_tutorial.ipynb
```

Then run all cells from top to bottom. The notebook streams deployment and evaluation output as it runs.

### Option 2: AgentCore CLI

The same workflow can be driven entirely from the command line. Install the CLI:

```bash
npm install -g @aws/agentcore
agentcore --version   # should print 0.11.0 or later
```

See the [CLI Examples](#agentcore-cli-examples) section below for the full command sequence.

---

## AgentCore CLI Examples

The following commands reproduce the notebook workflow from the command line.

### Step 1: Deploy the HR Assistant

```bash
# Scaffold a new AgentCore project
agentcore create --name HRAssistant --framework Strands --model-provider Bedrock --defaults

# Copy the HR assistant implementation
cp hr_assistant_agent.py app/HRAssistant/main.py

# Test locally before deploying
agentcore dev

# Deploy to AWS (builds container, pushes to ECR, creates AgentCore Runtime)
agentcore deploy
# Note the Runtime ID and ARN from the output.
```

### Step 2: Run Baseline Evaluation

```bash
# Invoke the agent to generate traffic
agentcore invoke \
  --runtime HRAssistant \
  --payload '{"prompt": "Employee ID: EMP-001. What is my PTO balance?"}' \
  --session-id $(python3 -c "import uuid; print(uuid.uuid4())")

# Run batch evaluation against recent sessions
agentcore run eval \
  --runtime HRAssistant \
  --evaluator Builtin.GoalSuccessRate \
  --evaluator Builtin.Helpfulness \
  --evaluator Builtin.Correctness
```

### Step 3: Get Recommendations

```bash
# System prompt recommendation (optimize for GoalSuccessRate)
agentcore run recommendation \
  --runtime HRAssistant \
  --type system-prompt \
  --evaluator Builtin.GoalSuccessRate

# Tool description recommendation
agentcore run recommendation \
  --runtime HRAssistant \
  --type tool-description
```

### Step 4: Create Configuration Bundles

```bash
# Create control bundle (original prompt)
agentcore create bundle \
  --name HRControl \
  --runtime HRAssistant \
  --system-prompt "$(cat original_prompt.txt)"

# Create treatment bundle (recommended prompt)
agentcore create bundle \
  --name HRTreatment \
  --runtime HRAssistant \
  --system-prompt "$(cat recommended_prompt.txt)"
```

### Step 5a: A/B Test — Config-Bundle Routing

```bash
# Create gateway
agentcore create gateway --name HRGateway --authorizer-type AWS_IAM

# Create gateway target
agentcore create gateway-target \
  --gateway HRGateway \
  --name HRAgentV1 \
  --runtime HRAssistant

# Create online evaluation config
agentcore add online-eval \
  --name HROnlineEval \
  --runtime HRAssistant \
  --evaluator Builtin.GoalSuccessRate \
  --evaluator Builtin.Helpfulness \
  --sampling-rate 100 \
  --enable-on-create

# Create A/B test with config-bundle routing (50/50 split)
agentcore create ab-test \
  --name HRBundleABTest \
  --gateway HRGateway \
  --control-bundle HRControl \
  --treatment-bundle HRTreatment \
  --control-weight 50 \
  --treatment-weight 50 \
  --online-eval HROnlineEval

# Monitor results
agentcore get ab-test --name HRBundleABTest --watch
```

### Step 5b: A/B Test — Target-Based Routing (Phased Rollout)

```bash
# Deploy v2 of the agent (with new code changes)
agentcore create --name HRAssistantV2 --framework Strands --model-provider Bedrock --defaults
cp hr_assistant_agent.py app/HRAssistantV2/main.py
# (Apply v2 code changes to main.py)
agentcore deploy --project HRAssistantV2

# Add v2 gateway target
agentcore create gateway-target \
  --gateway HRGateway \
  --name HRAgentV2 \
  --runtime HRAssistantV2

# Create online eval config for v2
agentcore add online-eval \
  --name HROnlineEvalV2 \
  --runtime HRAssistantV2 \
  --evaluator Builtin.GoalSuccessRate \
  --evaluator Builtin.Helpfulness \
  --sampling-rate 100 \
  --enable-on-create

# Create A/B test with target-based routing (90/10 canary)
agentcore create ab-test \
  --name HRTargetABTest \
  --gateway HRGateway \
  --control-target HRAgentV1 \
  --treatment-target HRAgentV2 \
  --control-weight 90 \
  --treatment-weight 10 \
  --online-eval-control HROnlineEval \
  --online-eval-treatment HROnlineEvalV2

# Monitor canary results
agentcore get ab-test --name HRTargetABTest --watch

# If v2 wins, ramp up traffic (update weights)
agentcore update ab-test --name HRTargetABTest --control-weight 50 --treatment-weight 50
agentcore update ab-test --name HRTargetABTest --control-weight 0  --treatment-weight 100
```

### Step 6: Cleanup

```bash
agentcore delete ab-test --name HRBundleABTest
agentcore delete ab-test --name HRTargetABTest
agentcore delete online-eval --name HROnlineEval
agentcore delete online-eval --name HROnlineEvalV2
agentcore delete bundle --name HRControl
agentcore delete bundle --name HRTreatment
agentcore delete gateway-target --gateway HRGateway --name HRAgentV1
agentcore delete gateway-target --gateway HRGateway --name HRAgentV2
agentcore delete gateway --name HRGateway
agentcore delete --name HRAssistant
agentcore delete --name HRAssistantV2
```

---

## File Reference

| File | Description |
|------|-------------|
| `hr_assistant_agent.py` | HR Assistant Strands agent with Configuration Bundle hook. Handles PTO, policies, benefits, and pay stubs. |
| `deploy_agent.py` | Standalone deploy script: creates IAM role, packages dependencies, uploads to S3, and creates an AgentCore Runtime. Supports `--version v1` and `--version v2`. |
| `optimization_tutorial.ipynb` | End-to-end tutorial notebook covering all optimization features. |

---

## Key Concepts

### Config-Bundle vs. Target-Based A/B Testing

| | Config-Bundle Routing | Target-Based Routing |
|---|---|---|
| **What changes** | System prompt, config (no code change) | Agent binary, tools, model |
| **Redeployment needed** | No — config applied at request time | Yes — new runtime required |
| **Best for** | Prompt tuning, config experiments | Code releases, version upgrades |
| **Traffic split** | Typically 50/50 | Typically 90/10 canary |
| **Rollback** | Instant — update bundle version | Runtime still running; shift weights back |

### Phased Rollout Workflow (Target-Based)

```
10% canary  →  validate no regressions (errors, latency, quality drop)
      ↓
50% ramp    →  gather statistical significance
      ↓
100% promote →  complete cutover; decommission old runtime
```

### Configuration Bundle Hook

The HR agent reads its system prompt from the bundle on every model call:

```python
from bedrock_agentcore.runtime import BedrockAgentCoreContext
from strands.hooks.events import BeforeModelCallEvent

def _config_bundle_hook(event: BeforeModelCallEvent) -> None:
    bundle = BedrockAgentCoreContext.get_config_bundle()
    if bundle:
        event.agent.system_prompt = bundle.get("system_prompt", DEFAULT_SYSTEM_PROMPT)

agent.hooks.add_callback(BeforeModelCallEvent, _config_bundle_hook)
```

This pattern allows live prompt updates and A/B testing without redeployment.

---

## Next Steps

- **Add custom evaluators**: Implement Lambda-based code evaluators for deterministic HR policy compliance checks (see tutorial `01-tutorials/07-AgentCore-evaluations/06-programmatic_evaluators`)
- **Automate the loop**: Run batch evaluations in CI/CD to catch regressions before deployment (see tutorial `01-tutorials/07-AgentCore-evaluations/05-groundtruth-based-evalautions`)
- **Use recommendations iteratively**: Re-run recommendations after each traffic batch to compound improvements
- **Multi-metric optimization**: Run separate recommendation jobs targeting different evaluators, then pick the prompt that best balances between the metrics you care about
- **Increase canary exposure**: When target-based test shows improvement, use `update_ab_test` to increase treatment weight gradually (10% → 25% → 50% → 100%)
- **Explore online evaluation**: Keep online eval configs enabled in production for continuous quality monitoring with zero explicit API calls per session
