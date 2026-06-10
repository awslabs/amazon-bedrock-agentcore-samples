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

## Prerequisite: CloudWatch Transaction Search

Online evaluation requires **CloudWatch Transaction Search** enabled at the account level (one-time setup):

```bash
aws application-signals start-monitoring --region us-west-2
# Wait 10-15 minutes for /aws/spans log group to provision
```

Verify it's ready:
```bash
aws logs describe-log-groups --log-group-name-prefix "/aws/spans" --region us-west-2
# Should return a log group; if empty, wait longer
```

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
