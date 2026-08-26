# IAM policies attached to the runtime's execution role

`guardrail-iam.json` grants `bedrock:ApplyGuardrail`, which the agent needs because the
model is invoked with a `guardrailConfig`. Without it every turn fails with `AccessDenied`
from Bedrock rather than from our code.

It reaches the role through `additionalPolicies` on the runtime in `agentcore.json`:

```json
"additionalPolicies": ["policies/guardrail-iam.json"]
```

Three things about that line are worth knowing before you edit it.

**The path is relative to `codeLocation`** (`app/MultiTenantTravel/`), not to the project root or to
`agentcore.json`. A path that does not resolve is a hard synth error, which is the good case.

**The field is not in the CLI 0.14.1 schema.** The bundled `@aws/agentcore-cdk` reads it and
attaches the document; the CLI's own validation schema for a runtime does not declare it.
That schema is not `.strict()`, so zod **drops unknown keys silently** instead of failing —
meaning a future CLI could stop honouring this and the deploy would still go green with the
permission quietly absent. So the check is not "did the deploy succeed":

```bash
cd agent/MultiTenantTravel && AWS_REGION=us-east-1 npx --no-install agentcore deploy --dry-run
grep -c ApplyGuardrail agentcore/cdk/cdk.out/AgentCore-MultiTenantTravel-default.template.json  # expect >= 1
```

**Scoped to this account's guardrails, not `Resource: "*"`.** The AWS documentation for the
gateway-side equivalent uses `"*"`; there is no reason to here, since we know the ARN
prefix, and `bedrock:ApplyGuardrail` on `*` would let this role apply _any_ guardrail in the
account — including a permissive one — which defeats the point of pinning a version.

## `{{ACCOUNT}}` and `{{REGION}}` are placeholders, filled in at deploy time

These files ship with placeholders and are rendered in place by
`scripts/render_agent_spec.py`, from the account the deploy is actually going to. Do not
commit a rendered copy.

**The reason is the quietest bug in the repo.** Both documents exist to grant reads the agent
treats as _optional_: the guardrail id and version, and the inference-profile ARN. Those reads
are deliberately non-fatal, so a policy naming the wrong account does not fail — it produces a
working agent that is silently **unguarded**, with model spend attributed to nothing. Nothing
in a deploy log, a stack event or a health check says so.

Rendering is idempotent and recognises its own output, so it is safe to re-run and it corrects
a document left pointing at a previous account.

The wildcard ARN in `model-iam.json` (`arn:aws:bedrock:*::foundation-model/…`) is left alone on
purpose: the model id is `global.anthropic.…`, so its underlying foundation models live in
other regions and carry no account segment.
