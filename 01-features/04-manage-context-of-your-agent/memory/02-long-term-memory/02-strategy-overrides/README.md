# Built-in strategies with prompt overrides

Built-in overrides keep the AgentCore-managed extraction pipeline but let you customise:

- the **prompt instructions** for any pipeline step (extraction, consolidation, reflection)
- the **Bedrock model** used for that step

The output **schema is fixed** — only instructions and model are override-able. If you need to change the schema, use a [self-managed strategy](../03-self-managed-strategy/) instead.

## What you learn

- Configure `customMemoryStrategy` with one of `semanticOverride`, `summaryOverride`, `userPreferenceOverride`, `episodicOverride`
- Required: `memoryExecutionRoleArn` — Bedrock invocations bill against your account
- Each step (`extraction` / `consolidation` / `reflection`) takes `appendToPrompt` and `modelId`

## Run

```bash
pip install boto3 bedrock-agentcore
export MEMORY_EXECUTION_ROLE_ARN=arn:aws:iam::<acct>:role/<role>
python strategies-with-overrides.py boto3   # default — direct service calls
python strategies-with-overrides.py sdk     # uses MemoryClient.gmcp_client (helper doesn't expose memoryExecutionRoleArn)
python strategies-with-overrides.py cli     # print equivalent AWS CLI commands
```

The role's trust policy must allow `bedrock-agentcore.amazonaws.com` to assume it, with `bedrock:InvokeModel` permission for the chosen model.

## Best practices

- **Be additive, not contradictory.** `appendToPrompt` is added to the system prompt — write instructions that *narrow* or *clarify* the built-in behaviour, not contradict it.
- **Pick a model that matches the workload.** Sonnet for nuanced extraction, Haiku for high-volume / low-margin extraction.
- **Test with realistic conversations.** Override behaviour is best validated by feeding it the actual transcripts you'll see in production.
- **Don't overfit.** If your schema needs are different, drop overrides and write a self-managed strategy — overrides cannot change the record shape.
- **Cost note.** Override Bedrock invocations bill against your account separately from AgentCore charges.
