# Online Evaluation: Dependency Ordering Workaround

## The Problem

The `@aws/agentcore-cdk` L3 construct for online evaluation (`AgentCoreApplication`
with `onlineEvalConfigs` in `agentcore.json`) has a **dependency ordering bug**:
it attempts to create the `OnlineEvaluationConfig` resource simultaneously with
the Runtime, before the Runtime's CloudWatch log group exists.

This causes a CloudFormation `CREATE_FAILED`:
```
ApplicationOnlineEvalITIncidentEval: Properties validation failed
```

The eval config requires a valid `logGroupName` and `serviceName` that only
exist after the Runtime is ACTIVE and has emitted at least one trace.

## How v1 Solved It

The v1 sample uses a **custom resource Lambda** (`online_eval_provider_lambda.py`)
with explicit CDK dependencies:

```python
self.online_eval_cr.node.add_dependency(self.runtime_log_group)
self.online_eval_cr.node.add_dependency(self.agent_runtime)
```

This ensures CloudFormation creates the eval config ONLY after both the
log group and runtime exist.

## How v3 Solves It

We follow the same dependency pattern as v1, but use CDK's **Provider framework**
instead of raw `cfnresponse`:

1. **Remove** `onlineEvalConfigs` from `agentcore.json` (don't let the L3
   construct manage it)
2. **Create** a handler Lambda (`lambdas/infra/online_eval_provider.py`)
   that returns a dict on success or raises on failure (no cfnresponse needed)
3. **Wrap with CDK Provider**: `new cr.Provider(this, 'OnlineEvalProvider', { onEventHandler: fn })`
4. **Add explicit dependency**: `evalCr.node.addDependency(this.application)`

The Provider framework guarantees CloudFormation always receives a response —
even if the handler throws an ImportError, unhandled exception, or timeout.
This prevents the 1-hour hang that occurs with raw `serviceToken`.

### Files involved:
- `agentcore/cdk/lib/cdk-stack.ts` → `createOnlineEvaluation()` method + Provider
- `lambdas/infra/online_eval_provider.py` → Handler (returns dict, no cfnresponse)
- `agentcore/agentcore.json` → `onlineEvalConfigs: []` (empty, managed by CDK)

## Why Not Use `agentcore add online-eval`?

The CLI command `agentcore add online-eval` adds the config to `agentcore.json`,
which the L3 construct then deploys. But the L3 construct doesn't properly
chain the CloudFormation dependency on the Runtime resource. Until this is
fixed in `@aws/agentcore-cdk`, we manage it manually with a CDK Provider.

## Why CDK Provider Instead of Raw cfnresponse?

The `cfnresponse` module is NOT a pip package — it's only available for
CloudFormation inline Lambda code. When using `Code.fromAsset`, the Lambda
can't import it. If the handler throws an ImportError, CloudFormation never
receives a response and **hangs for 1 full hour**.

CDK's `Provider` framework (`aws-cdk-lib/custom-resources`) wraps your handler
and guarantees a response is always sent — even on import errors, unhandled
exceptions, or timeouts. This is now an org-level standard:
`std.cdk.use-provider-framework` (must).

## When This Gets Fixed

Once `@aws/agentcore-cdk` properly adds a `DependsOn` relationship between
the `OnlineEvaluationConfig` and the `AgentRuntime` in the synthesized
template, you can:

1. Remove the `createOnlineEvaluation()` method from `cdk-stack.ts`
2. Delete `lambdas/infra/online_eval_provider.py`
3. Re-add via CLI: `agentcore add online-eval --name ITIncidentEval --runtime ITIncidentAgent --evaluator Builtin.GoalSuccessRate Builtin.Correctness Builtin.Helpfulness Builtin.ToolSelectionQuality --sampling-rate 100 --enable-on-create`
4. Redeploy: `agentcore deploy -y`

## Evaluators Configured

| Evaluator | What it measures |
|-----------|-----------------|
| `GoalSuccessRate` | Did the agent achieve its stated goal? |
| `Correctness` | Was the information provided accurate? |
| `Helpfulness` | Was the response useful to the user? |
| `ToolSelectionAccuracy` | Did the agent pick the right tools? |

Plus the custom `IncidentResolutionQuality` evaluator in `scripts/evaluate.py`
for on-demand domain-specific scoring.
