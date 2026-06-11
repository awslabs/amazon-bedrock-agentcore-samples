# Online Evaluation Configuration

Online evaluation is configured declaratively in `agentcore/agentcore.json` under `onlineEvalConfigs[]`:

```json
"onlineEvalConfigs": [{
  "name": "ITIncidentAgentEval",
  "agent": "ITIncidentAgent",
  "evaluators": [
    "Builtin.Correctness",
    "Builtin.Helpfulness",
    "Builtin.ToolSelectionAccuracy",
    "Builtin.GoalSuccessRate"
  ],
  "samplingRate": 100,
  "description": "Online evaluation for IT incident response agent (4 built-in evaluators)"
}]
```

The `AgentCoreApplication` L3 construct handles the full lifecycle:
- Creates an IAM execution role with least-privilege permissions
- Creates the `OnlineEvaluationConfig` CloudFormation resource
- Adds dependency ordering on the Runtime (ensuring the log group exists first)

## Prerequisite: CloudWatch Transaction Search (auto-enabled)

Online evaluation requires **CloudWatch Transaction Search** so OTEL spans are
ingested into the `aws/spans` log group. The stack **enables this automatically**:
when `onlineEvalConfigs` is non-empty, a custom resource
(`lambdas/infra/transaction_search.py`, wired via `enableTransactionSearch()` in
`cdk-stack.ts`) calls the X-Ray control plane to route trace segments to
CloudWatch Logs and set the span indexing percentage (100% by default, override
with `TXN_SEARCH_INDEXING_PERCENTAGE`).

On stack delete, Transaction Search is intentionally **left enabled** — it is an
account/region-level setting other agents may depend on.

The first deploy may take 10-15 minutes for the log group to provision. Verify:
```bash
aws logs describe-log-groups --log-group-name-prefix "/aws/spans" --region us-west-2
# Should return a log group; if empty, wait longer
```

> Manual enablement (`aws application-signals start-monitoring`) is no longer
> required — it is kept here only as a fallback if you deploy with
> `onlineEvalConfigs: []` and later enable eval out of band.

## Disabling Online Evaluation

To deploy without online evaluation (e.g., if Transaction Search is not enabled):

1. Set `onlineEvalConfigs` to `[]` in `agentcore/agentcore.json`
2. Redeploy: `./scripts/deploy.sh`

## Evaluators

| Evaluator                | What it measures                         |
|--------------------------|------------------------------------------|
| `GoalSuccessRate`        | Did the agent achieve its stated goal?   |
| `Correctness`            | Was the information provided accurate?   |
| `Helpfulness`            | Was the response useful to the user?     |
| `ToolSelectionAccuracy`  | Did the agent pick the right tools?      |

A custom `IncidentResolutionQuality` evaluator is also available for on-demand domain-specific scoring via `scripts/evaluate.py`.

## Cost

Typical workload (100 requests/day): **$5-15/month** for CloudWatch Transaction Search + evaluation.
