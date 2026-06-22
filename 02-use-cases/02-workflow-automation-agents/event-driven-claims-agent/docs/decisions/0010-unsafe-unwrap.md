# ADR-0010: Cognito Client Secret via CDK Injection

**Status:** Accepted  
**Date:** 2025-06-17

## Context

The AgentCore Runtime uses a Cognito client secret to authenticate to the MCP Gateway (OAuth2 `client_credentials` flow). CDK creates the Cognito app client and its secret at deploy time, and the Runtime reads it from an environment variable.

In CDK, `user_pool_client_secret` is a `SecretValue` — a wrapper that guards against accidental logging. Rendering it into a plain environment variable uses `.unsafe_unwrap()`, the explicit opt-in CDK provides for exactly this case.

## Decision

Use `app_client.user_pool_client_secret.unsafe_unwrap()` to pass the Cognito client secret directly as a Runtime environment variable.

## Reasoning

For a learning sample, injecting the secret directly keeps the spotlight on the AgentCore concepts — Runtime, Gateway, Memory, Policy Engine — rather than on secret-management plumbing. It's a sound choice here because:
- The secret is never in source code or git — Cognito generates it at deploy time
- It's passed via CDK environment variable injection (CloudFormation template)
- The deployed stack lives in the developer's own account

Moving to Secrets Manager for production is a small, well-trodden step (see Consequences) — AgentCore Runtime reads from it the same way it reads any other configuration.

## Alternatives Considered

- **AWS Secrets Manager:** Production-ready, supports rotation; adds a secret resource + IAM policy + a startup fetch. The recommended choice for production, and a natural next step once you take the sample further.
- **SSM Parameter Store (SecureString):** Simpler than Secrets Manager but still requires IAM + SDK calls in the Runtime.

## Consequences

The client secret is visible in:
- CloudFormation stack template (in the AWS Console under "Template" tab)
- Lambda/ECS environment variables (visible in the console)
- `aws cloudformation describe-stacks` output

**For production use:** Store the secret in AWS Secrets Manager, grant the Runtime role `secretsmanager:GetSecretValue`, and fetch it at startup in `config.py`. The code change is ~10 lines.
