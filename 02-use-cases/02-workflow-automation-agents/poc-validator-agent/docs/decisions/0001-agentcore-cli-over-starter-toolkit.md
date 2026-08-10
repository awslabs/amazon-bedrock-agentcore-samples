# 0001 — AgentCore CLI over the Starter Toolkit

## Status
Accepted.

## Context
Two ways exist to declare AgentCore resources: the Bedrock AgentCore Starter Toolkit
(`.bedrock_agentcore.yaml`) and the AgentCore CLI (`agentcore/agentcore.json`).

## Decision
Use the AgentCore CLI exclusively.

## Rationale
The Starter Toolkit is deprecated upstream. `02-use-cases/use-case-assessment.md` applies
a −2 penalty to samples that depend on it, and no sample in the repository still contains
a `.bedrock_agentcore.yaml`. Building against it would land a contribution that is
already flagged for migration.

## Consequences
The sample declares Runtime, Memory, Gateway, Identity credentials, Policy Engine and
Evaluators in one `agentcore.json`, deployed with `agentcore deploy`. A test asserts no
Starter Toolkit config file exists.
