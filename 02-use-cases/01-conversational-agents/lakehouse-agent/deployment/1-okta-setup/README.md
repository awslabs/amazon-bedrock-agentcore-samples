# Okta Setup — Two-Client OBO Topology (Optional Deep-Dive)

**This document is optional.** `setup_okta.py` (run by notebook `01-deploy-okta.ipynb`) automates everything described here — both Okta apps, the custom authorization server, scopes, groups, users, and the access policy. You do **not** need to read this to deploy the demo.

Read it if you want to:

- **understand** the two-app topology the OBO path depends on,
- **reproduce it by hand** in the Okta admin console (an alternative to running the script), or
- **troubleshoot** a failing OBO token exchange.

For the end-to-end concepts (the two identity-propagation patterns, the access-control scenarios) see the top-level [README.md](../../README.md) and [scenarios.md](../../scenarios.md). For the CLI deploy sequence see [../README.md](../README.md).

---

## The two-client topology (and why two apps)

This demo provisions **one** custom Okta authorization server fronted by **two** Okta applications:

| App | Name | Type | Role | SSM keys |
|---|---|---|---|---|
| **User-login app** | `lakehouse-agent-app` | OIDC web app | Issues the **subject token** users sign in with (Authorization Code + PKCE; also `client_credentials` for M2M and `password` for token inspection) | `okta-app-client-id`, `okta-app-client-secret` |
| **OBO exchange app** | `lakehouse-obo-exchange-client` | API Services (`client_secret_basic`) | Performs the RFC 8693 **token exchange** for the OBO_Gateway | `okta-obo-client-id`, `okta-obo-client-secret` |

**Rule: the client that performs the token exchange MUST be different from the client that issued the subject token.** Okta rejects a single app attempting both legs with `unsupported_token_exchange_flow`. This is why the demo ships two apps under one authorization server rather than one. (This is Okta-specific — see the Okta-vs-Entra note below.)

### Which app powers which OAuth2 credential provider

The demo creates two AgentCore Identity credential providers. They share the same authorization server but authenticate as **different** apps — do not conflate them:

| Provider | Used by | Grant / leg | Authenticates as |
|---|---|---|---|
| `lakehouse-mcp-okta-oauth-provider` | Interceptor_Gateway target | `client_credentials` (gateway → Claims MCP M2M) | **user-login app** (`okta-app-client-*`) |
| `lakehouse-obo-okta-provider` | OBO_Gateway target | `TOKEN_EXCHANGE` (RFC 8693, on-behalf-of) | **OBO exchange app** (`okta-obo-client-*`) |

Wiring the OBO provider to `okta-app-client-*` (the user-login app) reproduces the `unsupported_token_exchange_flow` failure. The shipped `5b-obo-gateway-setup/03_create_oauth_provider.py` reads `okta-obo-client-*` for exactly this reason.

---

## What `setup_okta.py` builds

### Custom authorization server

- **Audience:** `api://lakehouse-api` (the `aud` claim both gateway/runtime authorizers validate).
- **Scopes:** `claims.query`, `claims.submit`, `claims.update`, `claims.approve`, `opensearch.search`. None is marked `default` — every token request must declare its scope explicitly (the multi-tenant-correct posture).
- **`groups` claim:** a claim rule emits the user's group memberships (`value: '.*'`, always included) so the Interceptor_Gateway can map groups to tenant roles.

### Access policy + rule

Okta does **not** auto-create an access policy when you create a custom authorization server — without one, every token request returns `access_denied: Policy evaluation failed`. `setup_okta.py` creates a single policy + rule covering both apps:

- **`clients.include`** lists **both** client IDs — the user-login app **and** the OBO exchange app. The OBO exchange is evaluated against the *exchanging* client, so the exchange app must appear here.
- **rule `grantTypes.include`** lists `authorization_code`, `client_credentials`, `password`, and `urn:ietf:params:oauth:grant-type:token-exchange`. The token-exchange grant must be permitted at the policy-rule level **in addition to** being enabled on the exchange app itself.

> The shipped rule grants the built-in `EVERYONE` group access to all scopes as a tutorial simplification. A production deployment would tighten this to per-client / per-scope / per-group least-privilege rules.

### Groups + users

- **Groups:** `policyholders`, `adjusters`, `administrators`.
- **Users:** `policyholder001/002@example.com` (policyholders), `adjuster001/002@example.com` (adjusters), `admin@example.com` (administrators). Default password `TempPass123!`; Okta requires a password change (and may require authenticator/MFA enrollment) on first login.

### OBO provider `customParameters`

The OBO token-exchange request needs two extra body parameters, set on the **OBO_Gateway target** (`5b-obo-gateway-setup/04_create_obo_gateway.py`, not in this directory):

```
audience           = api://lakehouse-api
subject_token_type = urn:ietf:params:oauth:token-type:access_token
```

AgentCore forwards a target's `oauthCredentialProvider.customParameters` as token-request body params. See the [`5b-obo-gateway-setup`](../5b-obo-gateway-setup/) scripts.

---

## Troubleshooting: the four token-exchange gates

A working Okta OBO exchange must satisfy four conditions. If `GetResourceOauth2Token` (or the gateway's tool sync) fails, match the Okta error to the fix below:

| Okta error | Symptom / cause | Fix |
|---|---|---|
| `unauthorized_client` | The token-exchange grant is not permitted for the exchanging client — at the **app** level, the **policy-rule** level, or both. | Ensure `urn:ietf:params:oauth:grant-type:token-exchange` is on **both** the exchange app's grant types **and** the auth-server policy rule's `grantTypes.include`. |
| `missing_token_request_parameter` | The exchange request has no `audience`. | Set the OBO target's `customParameters.audience = api://lakehouse-api`. |
| `invalid_subject_token_type` | The default subject-token type (`...:token-type:jwt`) is not accepted for Okta OBO. | Set the OBO target's `customParameters.subject_token_type = urn:ietf:params:oauth:token-type:access_token`. |
| `unsupported_token_exchange_flow` | The exchanging client is the **same** app that issued the subject token. | Use the dedicated exchange app; point the OBO credential provider at `okta-obo-client-*`, not `okta-app-client-*`. |

> **Teaching callout — "provider created / READY" is not proof the exchange works.** `create_oauth2_credential_provider` validates only the AWS-side schema; **Okta is not contacted until the first live `GetResourceOauth2Token`**. A provider can sit at `READY` while the exchange still fails one of the four gates above. Always validate the OBO path with a real exchange (notebook `07-optional-multi-user-isolation-test` or a smoke call), never with provider creation alone.

---

## Okta vs Entra (sibling-IdP note)

The two-client requirement is **Okta-specific**. Okta uses `TOKEN_EXCHANGE` (RFC 8693) and needs **two** clients (user-login + dedicated exchange). Microsoft Entra ID uses `JWT_AUTHORIZATION_GRANT` (RFC 7523) and is **single-client**. A future Ping sibling is RFC 8693 like Okta (expect two-client). See the design doc's IdP family table (§6a) for the client-topology column.

---

## Verify your setup

After running notebook `01-deploy-okta.ipynb` (or building the topology by hand), run the read-only verifier:

```bash
cd deployment/1-okta-setup
python verify_okta_setup.py                  # Okta-only checks (no AWS gateway dependency)
python verify_okta_setup.py --check-provider # also cross-checks the 5b OBO provider wiring (after 05b deploys)
```

It confirms both apps exist, the exchange app carries the token-exchange grant, the policy includes the exchange client, the rule permits the token-exchange grant, and the scopes/groups/users are present. It is read-only and never modifies anything. Each ❌ points back to the gate table above.
