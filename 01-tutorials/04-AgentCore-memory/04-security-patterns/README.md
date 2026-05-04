# Security patterns

IAM, Cognito, and KMS patterns for production memory deployments.

| # | Folder / Notebook | Covers |
|---|---|---|
| 01 | [`01-iam-scoped-access/`](./01-iam-scoped-access/) | Scoping access with IAM conditions on `namespace`, `namespacePath`, `actorId`, `sessionId` |
| 02 | [`02-cognito-federated-identity/`](./02-cognito-federated-identity/) | Federating end-user identities into IAM via Cognito for per-user memory isolation |
| 03 | [`03-kms-encryption.ipynb`](./03-kms-encryption.ipynb) | Configuring a customer-managed KMS key on a memory resource (placeholder) |

See also:
- Actor / session isolation at the API level: [`../01-short-term-memory/01-core-features/03-actor-session-isolation.ipynb`](../01-short-term-memory/01-core-features/03-actor-session-isolation.ipynb)
- Namespaces for scoping records: [`../02-long-term-memory/01-core-features/04-namespaces-and-organization.ipynb`](../02-long-term-memory/01-core-features/04-namespaces-and-organization.ipynb)
