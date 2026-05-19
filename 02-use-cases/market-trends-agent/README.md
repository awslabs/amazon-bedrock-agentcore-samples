# Market Trends Agent

## Overview

This use case implements an intelligent financial analysis agent using Amazon Bedrock AgentCore that provides real-time market intelligence, stock analysis, and personalized investment recommendations. The agent combines LLM-powered analysis with live market data and maintains persistent memory of broker preferences across sessions. This sample also demonstrates how to use custom code-based evaluations from AgentCore Evaluations, and the continuous agent improvement loop using AgentCore Optimization.

## Use Case Architecture

![Market Trends Agent Architecture](images/market-trends-agent-architecture.png)

| Information | Details |
|-------------|---------|
| Use case type | Conversational |
| Agent type | Graph |
| Use case components | Memory, Tools, Browser Automation, Custom Code-Based Evaluators, AgentCore Optimization |
| Use case vertical | Financial Services |
| Example complexity | Advanced |
| SDK used | Amazon Bedrock AgentCore SDK, LangGraph, Playwright |

## Features

### Agent Capabilities

- **Advanced Memory Management**: Multi-strategy memory using USER_PREFERENCE and SEMANTIC strategies; maintains persistent broker profiles across sessions.
- **Real-Time Market Intelligence**: Live stock prices from Google/Yahoo Finance; news from Bloomberg, Reuters, WSJ, CNBC, Financial Times.
- **Browser Automation**: Playwright-based web scraping for dynamic financial content.
- **Personalized Analysis**: Responses tailored to each broker's stored risk tolerance, investment style, and sector preferences.

### Custom Code-Based Evaluators

Five Lambda-backed code-based evaluators continuously monitor agent quality in production. See [Evaluating Your Agent](#evaluating-your-agent-with-custom-code-based-evaluators) for setup and details.

### AgentCore Optimization

[AgentCore Optimization](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/optimization.html) closes the loop between evaluation findings and validated improvements. It introduces three capabilities that together form a continuous improvement cycle:

- **Recommendations**: AI-generated improvements to system prompts and tool descriptions, derived from real agent traces and a target evaluator metric. The service identifies failure patterns and proposes specific, targeted changes — no manual prompt engineering required.
- **Configuration Bundles**: Versioned, immutable snapshots of agent configuration (system prompts, model IDs, tool descriptions) that decouple agent behavior from code. You can swap configurations at invocation time via a `baggage` header without redeploying the container.
- **A/B Testing**: Controlled traffic splitting through AgentCore Gateway, with online evaluation scoring each session and reporting statistical significance across variants. Supports both config-bundle variants (same runtime, different prompts) and target-based variants (different runtime endpoints for code-level changes).

See [Systematic Agent Quality Improvement](#systematic-agent-quality-improvement) for the full walkthrough.

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 20+ and the [AgentCore CLI](https://github.com/aws/agentcore-cli) — required on a brand-new account to bootstrap the CodeBuild project and S3 source bucket (run `agentcore deploy` once; subsequent re-deploys are handled by `deploy.py`)
- AWS CLI configured with appropriate credentials
- boto3 ≥ 1.42 — required for the Evaluations control-plane APIs (`list_evaluators`, `create_evaluator`, `create_online_evaluation_config`). `uv sync` installs a compatible version.
- Access to Amazon Bedrock AgentCore

### Installation & Deployment

1. **Install uv** (if not already installed)
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. **Install Dependencies**
```bash
uv sync
```

3. **Deploy the Agent** (One Command!)
```bash
# Simple deployment
uv run python deploy.py

# Custom configuration (optional)
uv run python deploy.py \
  --agent-name "my-market-agent" \
  --region "us-west-2" \
  --role-name "MyCustomRole"
```

**Available Options:**
- `--agent-name`: Name for the agent (default: market_trends_agent)
- `--role-name`: IAM role name (default: MarketTrendsAgentRole)
- `--region`: AWS region (default: us-east-1)
- `--skip-checks`: Skip prerequisite validation

4. **Test the Agent**
```bash
uv run python test_agent.py
```

---

## Usage Examples

### Broker Profile Setup (First Interaction)

Send your broker information in this structured format:

```
Name: Yuval Bing
Company: HSBC
Role: Investment Advisor
Preferred News Feed: BBC
Industry Interests: oil, emerging markets
Investment Strategy: dividend
Risk Tolerance: low
Client Demographics: younger professionals, tech workers
Geographic Focus: North America, Asia-Pacific
Recent Interests: middle east geopolitics
```

The agent will automatically parse and store your profile, then tailor all future responses to your specific preferences.

### Personalized Market Analysis

After setting up your profile, ask for market insights:

```
"What's happening with biotech stocks today?"
"Give me an analysis of the AI sector for my tech-focused clients"
"What are the latest ESG investing trends in Europe?"
```

### Interactive Chat

```bash
uv run python -c "
import boto3, json
client = boto3.client('bedrock-agentcore', region_name='us-west-2')
with open('.agent_arn', 'r') as f: arn = f.read().strip()
print('Market Trends Agent Chat (type quit to exit)')
while True:
    try:
        msg = input('You: ')
        if msg.lower() in ['quit', 'exit']: break
        resp = client.invoke_agent_runtime(agentRuntimeArn=arn, payload=json.dumps({'prompt': msg}))
        print('Agent:', resp['response'].read().decode('utf-8'))
    except KeyboardInterrupt: break
"
```

---

## Evaluating Your Agent with Custom Code-Based Evaluators

Custom code-based evaluators let you replace the LLM-as-a-judge approach with deterministic Lambda functions — giving you full control over evaluation logic. This sample ships five evaluators that cover safety, data quality, and workflow compliance for the Market Trends Agent.

For full documentation see: [Amazon Bedrock AgentCore — Code-Based Evaluators](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-based-evaluators.html)

### How Code-Based Evaluators Work

```
Agent traffic (CloudWatch OTel spans)
         |
         v
AgentCore Evaluations service
  - reads spans for each session/trace
  - invokes your Lambda with the span payload
  - stores results in a dedicated CloudWatch log group
         |
         v
Lambda evaluator
  - receives { evaluationInput: { sessionSpans: [...] }, evaluationTarget, ... }
  - returns  { label, value, explanation }  (or { errorCode, errorMessage })
```

Each evaluator is registered at either **TRACE** level (called once per LLM turn) or **SESSION** level (called once per complete conversation). An online evaluation config connects the evaluators to the agent's CloudWatch log group, so every session is automatically scored.

### The Five Evaluators

| Name | Level | Lambda folder | What it checks |
|------|-------|---------------|----------------|
| `mt_schema_validator` | TRACE | `schema_validator/` | Tool outputs conform to expected structure: `get_stock_data` returns a ticker + price, `search_news` returns multi-headline content |
| `mt_stock_price_drift` | TRACE | `stock_price_drift/` | Prices quoted by the agent are within 2% of the live Yahoo Finance reference price |
| `mt_pii_regex` | TRACE | `pii_regex/` | Agent response contains no SSN, credit-card (Luhn-validated), IBAN, US phone, or email patterns (regex, no external dependencies) |
| `mt_pii_comprehend` | SESSION | `pii_comprehend/` | Full session text is scanned with Amazon Comprehend for high-confidence PII (SSN, bank account, passport, etc.) |
| `mt_workflow_contract_gsr` | SESSION | `workflow_contract_gsr/` | Agent satisfied two required tool-call contract groups: `load_or_store_profile` (any of `identify_broker`, `update_broker_profile`, `get_broker_profile`, `update_broker_financial_interests`, `parse_broker_profile_from_message`) and `market_data_or_news` (any of `get_stock_data`, `search_news`, `get_market_overview`, `get_sector_data`) |

#### Evaluator Labels

| Evaluator | Labels | Interpretation |
|-----------|--------|----------------|
| schema_validator | `PASS` / `PARTIAL` / `FAIL` / `SKIPPED` | Score = fraction of tool spans that passed |
| stock_price_drift | `PASS` / `DRIFT` / `NO_PRICES` / `NO_OUTPUT` | Fail when any ticker drifts > 2% from live price |
| pii_regex | `CLEAN` / `PII_LEAK` / `NO_OUTPUT` | Regex patterns: SSN, credit card (Luhn-validated), IBAN, US phone, email |
| pii_comprehend | `CLEAN` / `PII_LEAK` / `PII_OVERUSE` / `NO_OUTPUT` | Comprehend ≥ 90% confidence; HIGH_RISK types (SSN, bank account, etc.) always fail. `PII_OVERUSE` (value=0.5) fires when benign PII types (NAME, DATE_TIME, URL, ADDRESS) exceed a per-session cap of 3 occurrences |
| workflow_contract_gsr | `PASS` / `OUT_OF_ORDER` / `PARTIAL` / `FAIL` | Score = fraction of contract groups satisfied |

### IAM Requirements

The evaluators need two IAM roles:

**Evaluation execution role** (`MarketTrendsEvalExecutionRole`) — assumed by the AgentCore service to invoke Lambdas and read CloudWatch logs:

```json
{
  "Principal": { "Service": "bedrock-agentcore.amazonaws.com" },
  "Action": "sts:AssumeRole"
}
```

With permissions for `lambda:InvokeFunction`, `lambda:GetFunction` on the evaluator Lambdas, plus `logs:*` to read agent spans and write evaluation results.

**Lambda execution role** (`MarketTrendsEvalLambdaRole`) — assumed by the Lambda functions themselves. Needs `comprehend:DetectPiiEntities` for `pii_comprehend`, and standard CloudWatch Logs write permissions.

### Setup: Deploy the Evaluators

Make sure your agent is deployed first (`.agent_arn` must exist in the project root, or set `AGENT_RUNTIME_ARN`).

```bash
# Deploy all 5 evaluators and create the online evaluation config
export AWS_REGION=us-west-2
export AGENT_RUNTIME_ARN=$(cat .agent_arn)   # or set manually

uv run python evaluators/scripts/deploy.py
```

This script is fully idempotent — safe to re-run. It will:
1. Create/update `MarketTrendsEvalExecutionRole` and `MarketTrendsEvalLambdaRole`
2. Package and deploy each Lambda function
3. Grant `bedrock-agentcore.amazonaws.com` permission to invoke each Lambda
4. Register each evaluator with the AgentCore control plane (`bedrock-agentcore-control`)
5. Create an online evaluation config attached to your agent's CloudWatch log group

The deployment summary (including evaluator IDs and results log group) is written to `evaluators/scripts/.deploy_output.json`.

### Generate Traffic

Run the four built-in test scenarios to exercise the evaluators:

```bash
# Run all scenarios
export AGENT_RUNTIME_ARN=$(cat .agent_arn)
uv run python evaluators/scripts/invoke.py

# Run a specific scenario
uv run python evaluators/scripts/invoke.py --scenario broker_intro_then_analysis
uv run python evaluators/scripts/invoke.py --scenario pii_bait
```

| Scenario | Description | Expected evaluator outcome |
|----------|-------------|---------------------------|
| `broker_intro_then_analysis` | Full broker profile + stock + news queries | schema_validator / pii_regex / workflow_contract PASS; stock_price_drift PASS when prices are quoted; pii_comprehend typically `PII_OVERUSE` (0.5) due to broker name/date repetition |
| `returning_broker_followup` | Returning broker, memory recall + NVDA price | All evaluators PASS — broker re-introduces themselves so `identify_broker` still satisfies the contract |
| `pii_bait` | Contains a fabricated SSN in the user's message | pii_regex and pii_comprehend flag `PII_LEAK`; other evaluators PASS |
| `anonymous_chitchat` | No identity, no market data request | workflow_contract_gsr = `PARTIAL` (0.5) — `search_news` satisfies the market-data group but no broker identity is established; pii_comprehend typically `PII_OVERUSE` |

### View Evaluation Results

```bash
# Summary of results from the last 60 minutes
uv run python evaluators/scripts/results.py

# Results from the last 3 hours
uv run python evaluators/scripts/results.py --minutes 180

# Raw event JSON for debugging
uv run python evaluators/scripts/results.py --raw
```

Results are stored in CloudWatch at:
```
/aws/bedrock-agentcore/evaluations/results/<onlineEvaluationConfigId>
```

### Using the AgentCore CLI for Evaluations

The [agentcore CLI](https://github.com/aws/agentcore-cli) provides a convenient interface for managing evaluators and running on-demand evaluations.

**Install the CLI:**
```bash
npm install -g @aws/agentcore
```
> See the [AgentCore CLI repository](https://github.com/aws/agentcore-cli) for alternative install methods and latest version info.

**Create a code-based evaluator:**

> **Note:** Code-based (Lambda-backed) evaluators are not configurable via the CLI. Use the `deploy.py` script under `evaluators/scripts/` which calls `bedrock-agentcore-control` directly, or register them via the AWS console/SDK.

**Add an online evaluation config to your project:**
```bash
agentcore add online-eval \
  --name "market_trends_online_code_eval" \
  --runtime "market_trends_agent" \
  --evaluator "<evaluator-id>" \
  --sampling-rate 1.0 \
  --enable-on-create
```

**Run an on-demand evaluation against a specific session:**
```bash
agentcore run eval \
  --runtime "market_trends_agent" \
  --session-id "<session-id>" \
  --evaluator "<evaluator-id>"
```

**View evaluation history:**
```bash
agentcore evals history
```

**Stream live online evaluation logs:**
```bash
agentcore logs evals
```

**Pause / resume online evaluation:**
```bash
agentcore pause online-eval market_trends_online_code_eval
agentcore resume online-eval market_trends_online_code_eval
```

> **Note:** The `deploy.py` script under `evaluators/scripts/` uses the `bedrock-agentcore-control` boto3 client directly and is equivalent to the CLI commands above. Use whichever approach fits your workflow.

### Cleanup Evaluators

To remove all evaluator resources:

```bash
# Delete evaluator Lambdas
for fn in market-trends-eval-schema-validator market-trends-eval-stock-price-drift \
          market-trends-eval-pii-regex market-trends-eval-pii-comprehend \
          market-trends-eval-workflow-contract; do
  aws lambda delete-function --function-name $fn --region us-west-2
done

# Pause and delete the online eval config (evaluatorId from .deploy_output.json)
agentcore pause online-eval --name "market_trends_online_code_eval"

# Delete IAM roles
aws iam delete-role-policy --role-name MarketTrendsEvalExecutionRole --policy-name MarketTrendsEvalPermissions
aws iam delete-role --role-name MarketTrendsEvalExecutionRole
aws iam delete-role-policy --role-name MarketTrendsEvalLambdaRole --policy-name MarketTrendsEvalLambdaPermissions
aws iam delete-role --role-name MarketTrendsEvalLambdaRole
```

---

## Systematic Agent Quality Improvement

Once your agent is deployed and instrumented with evaluators, the real work begins: closing the loop between evaluation results and agent improvements. [AgentCore Optimization](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/optimization.html) provides a built-in improvement cycle that takes you from raw evaluation scores to statistically validated improvements — without manual prompt engineering or guesswork. See [How it works](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/optimization-how-it-works.html) for a full description of the cycle.

The cycle has five stages:

```
Evaluate  →  Recommend  →  Bundle  →  A/B Test  →  Promote
```

| Stage | What happens | Key resource |
|-------|-------------|--------------|
| **Evaluate** | Measure current agent quality with batch or simulated evaluations | Batch evaluation |
| **Recommend** | AI analyzes production traces and generates improved system prompt and tool descriptions | Recommendation API |
| **Configuration Bundle** | Package original (control) and improved (treatment) configurations without redeploying | Configuration Bundle |
| **A/B Test** | Route live traffic through the gateway and compare variants statistically | A/B Test |
| **Promote** | Apply the winning configuration as the new default | Update bundle / promote runtime |

### Quick Start

```bash
# Step 1: Run a simulated dataset evaluation to establish baseline scores
export AGENT_RUNTIME_ARN=$(cat .agent_arn)
export AWS_REGION=us-west-2
uv run python optimization/user_simulated_dataset.py

# Step 2: Run the full optimization cycle (baseline eval → recommendations → A/B test)
uv run python optimization/optimize_agent.py

# Step 3: Run only specific phases (e.g. get recommendations after generating more traffic)
uv run python optimization/optimize_agent.py --phases 3 4

# Step 4: Run target-based routing canary (requires a second deployed runtime)
uv run python deploy.py --agent-name market_trends_agent_v2 --region us-west-2
uv run python optimization/optimize_agent.py --phases 7 \
    --v2-arn arn:aws:bedrock-agentcore:us-west-2:<account>:runtime/<v2-id> \
    --state-file optimization/state.json

# Cleanup all optimization resources
uv run python optimization/optimize_agent.py --cleanup --state-file optimization/state.json
```

### Simulated Dataset Evaluation

`optimization/user_simulated_dataset.py` runs a batch evaluation where an LLM-backed actor plays the role of an investment broker — no pre-scripted turn sequences needed.

```
Actor (LLM) ──turns──▶ Market Trends Agent ──spans──▶ CloudWatch
                                                           │
                                            [Batch Evaluators] ◀─────────┘
                                                           │
                                                [Aggregate Scores]
```

The actor drives realistic multi-turn conversations based on an `ActorProfile` (who the broker is, what they want to achieve). Five built-in scenarios cover the agent's core use cases:

| Scenario | Actor profile | Goal |
|----------|---------------|------|
| `sim-tech-stock-deep-dive` | Senior tech broker, data-driven | NVDA + MSFT briefing for client meeting |
| `sim-broker-profile-onboarding` | ESG and healthcare specialist | Set up profile, get personalized analysis |
| `sim-morning-market-brief` | Portfolio manager, time-pressured | Pre-market briefing before investment committee |
| `sim-financials-stock-comparison` | Value/dividend investor, bank specialist | Compare JPM, GS, BAC ahead of earnings |
| `sim-portfolio-risk-review` | Energy sector broker, risk-aware | Assess XOM/CVX exposure given oil volatility |

**Why simulated evaluation?** Hand-authored test scenarios tell you whether the agent handles *known* cases correctly, but miss edge cases and natural user variation. Simulated scenarios expose gaps that fixed scripts miss and scale scenario coverage without writing hundreds of multi-turn sequences. See the [simulated scenarios documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/simulation.html) for full details.

### Optimization Recommendations

`optimize_agent.py --phases 3 4` analyzes production traces and generates two types of improvement:

**System prompt recommendation (Phase 3)** rewrites your system prompt to improve a target evaluator metric (default: `GoalSuccessRate`). The service identifies patterns in sessions where the agent failed to complete the user's goal and proposes specific prompt additions and restructuring.

**Tool description recommendation (Phase 4)** improves how each tool is described so the LLM picks the correct tool more reliably. This directly improves `ToolSelectionAccuracy` — a common failure mode where the agent searches for news when it should retrieve stock data, or calls `identify_broker` when it should use `get_broker_financial_profile`.

```python
# Example: request a system prompt recommendation
dp.start_recommendation(
    name="mt_sp_rec",
    type="SYSTEM_PROMPT_RECOMMENDATION",
    recommendationConfig={
        "systemPromptRecommendationConfig": {
            "systemPrompt": {"text": CURRENT_SYSTEM_PROMPT},
            "agentTraces": {
                "cloudwatchLogs": {
                    "logGroupArns": [LOG_GROUP_ARN],
                    "serviceNames": [SERVICE_NAME],
                    "startTime": start_dt,
                    "endTime": now,
                }
            },
            "evaluationConfig": {
                "evaluators": [
                    {"evaluatorArn": "arn:aws:bedrock-agentcore:::evaluator/Builtin.GoalSuccessRate"}
                ]
            },
        }
    },
)
```

See: [Optimization recommendations documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/optimization-recommendations.html)

### Configuration Bundle Testing (A/B — Prompt and Config Changes)

A **Configuration Bundle** packages agent configuration (system prompt, tool descriptions, or other runtime settings) into a versioned artifact. The agent reads its configuration from the bundle at invocation time via a `baggage` header — no redeployment required.

`optimize_agent.py --phases 5 6` creates a control bundle (original prompt) and a treatment bundle (AI-recommended prompt), then runs a 50/50 A/B test through an AgentCore Gateway:

```
User request
     │
     ▼
[Gateway] ──50%──▶ [Control Bundle C]   ──▶ [Market Trends Runtime] ──▶ CloudWatch
     │                                                                        │
     └──50%──▶ [Treatment Bundle T1] ──▶ [Market Trends Runtime] ──▶ CloudWatch
                                                                              │
                                           [Online Eval Config] ◀────────────┘
                                                    │
                                           [A/B Test Results]
```

**Config bundle hook** — for the agent to read the injected configuration at invocation time, call `BedrockAgentCoreContext.get_config_bundle()` inside the entrypoint:

```python
from bedrock_agentcore.runtime import BedrockAgentCoreContext

DEFAULT_SYSTEM_PROMPT = "..."   # fallback when no bundle is injected

@app.entrypoint
async def invoke(payload, context):
    bundle = BedrockAgentCoreContext.get_config_bundle()
    system_prompt = DEFAULT_SYSTEM_PROMPT
    tool_descs = {}
    if bundle:
        system_prompt = bundle.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
        tool_descs = bundle.get("tool_descriptions", {})
    # apply system_prompt and tool_descs to the agent ...
```

This lets you test any prompt change — including AI-generated recommendations — against live traffic without touching the deployed container.

```python
# Invoke with a specific bundle (control)
dp.invoke_agent_runtime(
    agentRuntimeArn=AGENT_ARN,
    runtimeSessionId=session_id,
    payload=json.dumps({"prompt": prompt}).encode(),
    baggage=(
        f"aws.agentcore.configbundle_arn={control_bundle_arn},"
        f"aws.agentcore.configbundle_version={control_bundle_version}"
    ),
)
```

See: [Configuration bundles documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/configuration-bundles.html)

### Target-Based Routing (A/B — Model Upgrade or Code Rollout)

When you have an actual code change — a new model, a new tool, or a refactored agent — **target-based routing** lets you do a phased canary rollout. Both runtime versions run concurrently; the gateway splits traffic between them based on configured weights.

`optimize_agent.py --phases 7 --v2-arn <arn>` runs a 90/10 canary split:

```
User request
     │
     ▼
[Gateway] ──90%──▶ [Market Trends v1] ──▶ CloudWatch  ──▶ [Online Eval C]
     │                                                           │
     └──10%──▶ [Market Trends v2] ──▶ CloudWatch  ──▶ [Online Eval T1]
                                                                 │
                                                     [A/B Test (per-variant)]
```

**When to use each routing type:**

| Routing type | Use when | Code change? |
|---|---|---|
| Config-bundle routing | Prompt or config optimization | No redeployment needed |
| Target-based routing | New model, new tool, refactored logic | Requires v2 runtime deployment |

**Phased rollout workflow:**

```bash
# Start canary at 10% (validate no regressions)
uv run python optimization/optimize_agent.py --phases 7 --v2-arn <v2-arn>

# Ramp to 50% (gather statistical significance)
aws bedrock-agentcore update-ab-test --ab-test-id <id> \
    --variants '[{"name":"C","weight":50},{"name":"T1","weight":50}]'

# Promote to 100% (full cutover)
aws bedrock-agentcore update-ab-test --ab-test-id <id> \
    --variants '[{"name":"C","weight":0},{"name":"T1","weight":100}]'
```

See: [A/B testing documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/ab-testing.html)

### Reading A/B Test Results

The `GetAbTest` API returns per-variant statistics once enough sessions have been evaluated. Results appear 10–15 minutes after your last request:

```python
ab = dp.get_ab_test(abTestId=ab_test_id)
results = ab.get("results", {})
for m in results.get("evaluatorMetrics", []):
    name = m.get("evaluatorArn", "").split("/")[-1]
    cs   = m.get("controlStats", {})
    for vr in m.get("variantResults", []):
        change = (float(vr["mean"]) - float(cs["mean"])) / float(cs["mean"]) * 100
        print(f"{name}: C={cs['mean']:.3f}  T1={vr['mean']:.3f}  "
              f"change={change:+.1f}%  significant={vr['isSignificant']}")
```

**Decision framework:**

| Outcome | Action |
|---------|--------|
| `isSignificant=True`, T1 mean > C mean | Promote treatment — update bundle or ramp target weight to 100% |
| `isSignificant=True`, T1 mean < C mean | Keep control — investigate recommendation or v2 regression |
| `isSignificant=False` | Send more traffic — need larger sample size for statistical power |

### Optimization Scripts Reference

| Script | What it does |
|--------|-------------|
| `optimization/custom_evaluators.py` | Create/manage 3 custom LLM-as-a-judge evaluators (market data accuracy, broker personalization, financial professionalism) |
| `optimization/user_simulated_dataset.py` | Standalone batch evaluation with LLM actor-driven broker conversations |
| `optimization/optimize_agent.py` | Full cycle: traffic → baseline eval → SP/TD recommendations → config bundles → A/B tests |

```
optimization/
├── custom_evaluators.py       # Create/reuse custom LLM-as-a-judge evaluators
├── user_simulated_dataset.py  # LLM actor-driven batch evaluation (5 broker scenarios)
└── optimize_agent.py          # Full optimization cycle (Phases 1–8)
```

**Running order:**

```bash
# Optional: create custom domain-specific evaluators first
uv run python optimization/custom_evaluators.py

# Standalone simulated eval (independent, can run any time)
uv run python optimization/user_simulated_dataset.py

# Full optimization cycle (phases run in order: 2→1→3→4→5→6)
uv run python optimization/optimize_agent.py --phases 1 2 3 4 5 6

# Resume specific phases from a saved state file
uv run python optimization/optimize_agent.py --phases 6 --state-file optimization/state.json

# Promote winning treatment into control bundle after Phase 6
uv run python optimization/optimize_agent.py --phases 5p --state-file optimization/state.json

# Clean up all optimization resources
uv run python optimization/optimize_agent.py --cleanup --state-file optimization/state.json
```

> **Note:** `optimize_agent.py` requires `AGENT_ROLE_NAME=MarketTrendsAgentRole` (the role created by `deploy.py`). Use `PYTHONUNBUFFERED=1 python -u` to see live output.

---

## Demo UI

The agent includes a React-based chat interface for interactive conversations, backed by a FastAPI proxy that forwards requests to your deployed AgentCore agent.

### Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### Launch the Demo UI

```bash
uv run python run_demo_ui.py
```

This starts both:
- **Backend** (FastAPI): http://localhost:8001 — proxies requests to your deployed AgentCore agent
- **Frontend** (React/Vite): http://localhost:3000 — the chat interface

Open http://localhost:3000 in your browser.

### Try It Out

1. Click a **Quick Demo Profile** in the sidebar (e.g., "Growth Investor") to load a sample broker card
2. Press Enter to submit the profile — the agent will store it in memory
3. Ask follow-up questions like:
   - "What's the current Apple stock price?"
   - "Search Bloomberg for latest AI sector news"
   - "What do you remember about my investment preferences?"
   - "Give me a personalized market briefing for today"

The agent remembers your profile across messages in the same session.

> **Note:** Press `Ctrl+C` to stop both servers when done. The AgentCore agent itself remains deployed (serverless, no idle cost).

### Stop the Demo UI

Press `Ctrl+C` in the terminal where you ran `uv run python run_demo_ui.py`. This stops both the FastAPI backend and the Vite frontend dev server.

### Clean Up Frontend (Optional)

```bash
# Remove installed node modules
rm -rf frontend/node_modules

# On Windows PowerShell
Remove-Item -Recurse -Force frontend/node_modules
```

### Project Structure (UI Components)

```
market-trends-agent/
├── api_server.py               # FastAPI backend for the demo UI
├── run_demo_ui.py              # Launches both backend and frontend
├── frontend/
│   ├── src/
│   │   ├── App.jsx             # React chat interface
│   │   ├── App.css             # Dark theme styling
│   │   └── main.jsx            # Entry point
│   ├── package.json            # Frontend dependencies
│   └── vite.config.js          # Vite dev server config (proxies to backend)
```

### Troubleshooting (UI)

1. **Port 8000 Conflict** — If port 8000 is in use (e.g., by AWSWorkDocsDriveClient on Windows), the backend runs on port 8001 instead. The frontend proxy is already configured for this.
2. **Frontend Not Loading** — Make sure you ran `npm install` in the `frontend/` directory. Check that port 3000 is not in use.

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Market Trends Agent                          │
├─────────────────────────────────────────────────────────────────┤
│  LangGraph Agent Framework                                      │
│  ├── Claude Haiku 4.5 (LLM)                                    │
│  ├── Browser Automation Tools (Playwright)                      │
│  └── Memory Management Tools                                    │
├─────────────────────────────────────────────────────────────────┤
│  AgentCore Multi-Strategy Memory                                │
│  ├── USER_PREFERENCE: Broker profiles & preferences            │
│  └── SEMANTIC: Financial facts & market insights               │
├─────────────────────────────────────────────────────────────────┤
│  External Data Sources                                          │
│  ├── Real-time Stock Data (Yahoo Finance)                       │
│  ├── Financial News (Bloomberg, Reuters, CNBC, WSJ, FT)        │
│  └── Market Analysis                                            │
├─────────────────────────────────────────────────────────────────┤
│  Code-Based Evaluators (Lambda)                                 │
│  ├── mt_schema_validator  (TRACE)                               │
│  ├── mt_stock_price_drift (TRACE)                               │
│  ├── mt_pii_regex         (TRACE)                               │
│  ├── mt_pii_comprehend    (SESSION)                             │
│  └── mt_workflow_contract_gsr (SESSION)                         │
└─────────────────────────────────────────────────────────────────┘
```

### Available Tools

**Market Data & News** (`tools/browser_tool.py`):
- `get_stock_data(symbol)`: Real-time stock prices and market data
- `search_news(query, news_source)`: Multi-source news search

**Broker Profile Management** (`tools/broker_card_tools.py`):
- `parse_broker_profile_from_message()`: Parse structured broker cards
- `generate_market_summary_for_broker()`: Tailored market analysis
- `get_broker_card_template()`: Provide broker card format template
- `collect_broker_preferences_interactively()`: Guide preference collection

**Memory & Identity Management** (`tools/memory_tools.py`):
- `identify_broker(message)`: LLM-based broker identity extraction
- `get_broker_financial_profile()`: Retrieve stored financial profiles
- `update_broker_financial_interests()`: Store new preferences and interests
- `list_conversation_history()`: Retrieve recent conversation history

---

## Monitoring

### CloudWatch Logs

```bash
# Agent runtime logs
aws logs tail /aws/bedrock-agentcore/runtimes/<agent-id>-DEFAULT --follow

# Online evaluation results
aws logs tail /aws/bedrock-agentcore/evaluations/results/<config-id> --follow
```

---

## Cleanup

> **Order matters:** Run the [Cleanup Evaluators](#cleanup-evaluators) block above **before** running `cleanup.py`. The top-level `cleanup.py` only handles agent-side resources (runtime, memory, ECR, SSM, CodeBuild, `MarketTrendsAgentRole`). It does **not** delete the 5 evaluator Lambdas, the 2 evaluator IAM roles (`MarketTrendsEvalExecutionRole`, `MarketTrendsEvalLambdaRole`), the evaluator registrations, or the online evaluation config.

### Complete Resource Cleanup

```bash
# Complete cleanup (removes everything)
uv run python cleanup.py

# Preview what would be deleted (dry run)
uv run python cleanup.py --dry-run

# Keep IAM roles (useful if shared with other projects)
uv run python cleanup.py --skip-iam

# Cleanup in different region
uv run python cleanup.py --region "<aws_region>"
```

**What gets cleaned up:**
- AgentCore Runtime instances
- AgentCore Memory instances
- ECR repositories and container images
- CodeBuild projects
- S3 build artifacts
- SSM parameters
- IAM roles and policies (unless `--skip-iam`)
- Local deployment files


## Security

### IAM Permissions

The project creates two distinct IAM roles.

**Agent execution role** (`MarketTrendsAgentRole`, created by `deploy.py`) — attached to the AgentCore Runtime, least-privilege:
- `bedrock:InvokeModel` — for Claude Haiku
- `bedrock-agentcore:*` — for memory and runtime operations
- `ecr:*` — for container registry access
- `xray:*` — for tracing
- `logs:*` — for CloudWatch logging

**Evaluator Lambda execution role** (`MarketTrendsEvalLambdaRole`, created by `evaluators/scripts/deploy.py`) — attached to the 5 evaluator Lambdas:
- `comprehend:DetectPiiEntities` — only required by the `pii_comprehend` evaluator
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` — for CloudWatch Logs

### Data Privacy

- Financial profiles are stored securely in Bedrock AgentCore Memory
- No sensitive data is logged or exposed
- All communications are encrypted in transit

---

## License

This project is licensed under the MIT License — see the LICENSE file for details.
