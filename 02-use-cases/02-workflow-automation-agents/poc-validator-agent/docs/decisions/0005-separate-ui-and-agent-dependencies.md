# 0005 — Separate UI and agent dependency sets

## Status
Accepted.

## Context
The sample ships a Streamlit UI and an AgentCore Runtime agent.

## Decision
`ui/requirements.txt` and `app/pocvalidator/requirements.txt` are installed into separate
environments. `core/` depends on neither and is importable from both.

## Rationale
They are genuinely incompatible, discovered by installing rather than by reading:
`bedrock-agentcore` resolves `starlette 1.6.0` and `websockets 17.0.1`, while
`streamlit 1.61` requires `starlette < 1.4` and `websockets < 17`. A single environment
produces a broken install of one or the other.

## Consequences
The README documents two install steps. A test asserts neither requirements file
mentions the other's package. `core/` staying dependency-free is what makes this
workable — the UI runs a full review locally without importing any AgentCore code.
