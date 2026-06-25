# ADR-0004: Cognito M2M Over IAM Auth

**Status:** Accepted  
**Date:** 2025-06-17

## Context

The Runtime needs to authenticate to the Gateway (for tool calls), and external callers need to authenticate to the Runtime (for invocations). AWS provides two primary options: IAM SigV4 or Cognito JWT.

## Decision

The Runtime uses `CUSTOM_JWT` Cognito auth rather than `AWS_IAM` (SigV4). All callers — the Trigger Lambda, test scripts, and the Runtime itself (when calling Gateway tools) — obtain a JWT via the OAuth2 `client_credentials` flow.

## Reasoning

IAM SigV4 is the default for AWS service-to-service communication but doesn't generalize to external callers (web applications, CI/CD systems, partner integrations, mobile apps). Demonstrating the `client_credentials` OAuth2 flow shows how to authenticate realistic API consumers — not just AWS SDK calls.

It also demonstrates the **agent-as-principal** pattern: the Runtime itself obtains a Cognito token and presents it to the Gateway. This is how production agents authenticate to external APIs and tool registries.

## Alternatives Considered

- **IAM SigV4:** Simpler for AWS-internal use (just use boto3). But doesn't demonstrate external integration patterns and limits the sample's teaching value.
- **API Key (x-api-key):** Even simpler but less secure (no rotation, no expiry, no scoping).

## Consequences

Callers authenticate with the standard OAuth2 `client_credentials` flow — the same pattern any external app, partner, or CI system would use to call the agent. It's ~15-20 lines, and the sample includes ready-to-copy implementations:
- `scripts/test_invoke.py` → `get_cognito_token()` for a caller reaching the Runtime
- `app/claimsagent/main.py` → `_get_gateway_token()` for the Runtime reaching the Gateway

The payoff: a portable, real-world auth pattern that works for callers far beyond AWS-internal SigV4.
