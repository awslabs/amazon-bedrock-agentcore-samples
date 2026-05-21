# Security patterns

IAM, Cognito, and KMS patterns for production memory deployments.

| # | Folder / Notebook | Covers |
|---|---|---|
| 01 | [`01-iam-scoped-access/`](./01-iam-scoped-access/) | Scoping access with IAM conditions on `namespace`, `namespacePath`, `actorId`, `sessionId` |
| 02 | [`02-cognito-federated-identity/`](./02-cognito-federated-identity/) | Federating end-user identities into IAM via Cognito for per-user memory isolation |
| 03 | [`03-kms-encryption.py`](./03-kms-encryption.py) | Configuring a customer-managed KMS key on a memory resource (placeholder) |

## IAM-scoped actor isolation

![IAM-scoped actor isolation architecture](./01-iam-scoped-access/architecture.png)

The agent deploys to AgentCore runtime behind a Cognito JWT authorizer. The runtime execution role carries an IAM inline policy with a `StringEquals` condition on `bedrock-agentcore:actorId` — set to the authenticated user's Cognito `sub`. memory operations (read/write events, retrieve records) are permitted only for that actor. Swapping the allowed `actorId` in the policy immediately blocks access to a different user's memory. See [`01-iam-scoped-access/`](./01-iam-scoped-access/) for the end-to-end implementation.

## Cognito federated identity

![Cognito federated identity architecture](./02-cognito-federated-identity/architecture.png)

The Cognito-federated variant extends IAM scoping by dynamically obtaining per-user temporary credentials via the Cognito identity Pool + STS `AssumeRoleWithWebIdentity` flow. The user's Cognito JWT is exchanged for short-lived AWS credentials scoped to their `actorId`, so no long-lived service role credential touches the user's data. See [`02-cognito-federated-identity/`](./02-cognito-federated-identity/) for the implementation.

See also:
- Namespaces for scoping records: [`../02-long-term-memory/01-core-features/04-namespaces-and-organization.py`](../02-long-term-memory/01-core-features/04-namespaces-and-organization.py)

## Running the Python Scripts

Navigate into each sub-folder and run the scripts:

```bash
pip install -r requirements.txt  # if present
```

```bash
# 01-iam-scoped-access/
python 01-iam-scoped-access/runtime_memory_identity_integration.py
python 01-iam-scoped-access/runtime_identity_memory_agent.py
python 01-iam-scoped-access/utils.py
```

```bash
# 02-cognito-federated-identity/
python 02-cognito-federated-identity/runtime_memory_federated_identity_integration.py
python 02-cognito-federated-identity/runtime_identity_memory_agent.py
python 02-cognito-federated-identity/utils.py
```

