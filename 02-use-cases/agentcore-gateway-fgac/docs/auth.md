# End-to-end authentication chain

This document traces a single tool call from an MCP client through to the
FastAPI backend, naming every component that inspects a credential and
exactly what it checks.

The chain has **four checkpoints** and **two distinct Okta-issued JWTs**.
Each JWT is signed by the same Okta authorization server (`agentcore-demo`)
and carries the same user identity (`sub`, `role`), but the **outbound**
JWT is freshly minted via RFC 8693 token exchange just before the gateway
calls the ALB.

```
MCP client (e.g. MCP Inspector)
    │  Authorization: Bearer <inbound JWT>
    ▼
[1] AgentCore Gateway — customJWTAuthorizer
    │     iss, aud, allowed_clients, signature, expiry
    │
    ▼
[2] AgentCore Policy — Cedar (tools/call only)
    │     principal.role tag → permit/deny on action+resource
    │
    │     RFC 8693 token exchange against Okta /v1/token:
    │       inbound JWT → exchanged JWT (same sub/role, scope=gateway.invoke,
    │                                     aud=agentcore-ecommerce)
    │
    │  Authorization: Bearer <exchanged JWT>
    ▼
[3] ALB — jwt-validation listener action
    │     iss, signature, aud=agentcore-ecommerce, expiry
    │
    ▼
[4] FastAPI app — claim parsing + per-route role gate
       trusts the validated bearer; reads sub/role; require_admin where needed
```

## The two JWTs

### Inbound JWT (presented by the MCP client to the gateway)

Issued by Okta via Authorization Code + PKCE for the **agent OIDC client**
(`okta_allowed_client_ids` in
[`terraform.tfvars`](../infra/envs/dev/agentcore/terraform.tfvars)). Carries
the user's identity and group-derived role.

```json
{
  "iss": "https://<tenant>.okta.com/oauth2/<authzServerId>",
  "aud": "agentcore-ecommerce",
  "cid": "<idp-client-id>",
  "scp": ["openid", "gateway.invoke"],
  "sub": "<okta user>",
  "role": "customer"
}
```

### Exchanged JWT (presented by the gateway to the ALB)

Issued by Okta via RFC 8693 token exchange. AgentCore Identity authenticates
to Okta's `/v1/token` as the **service-app OIDC client** (`okta_client_id` /
`okta_client_secret`) and submits the inbound JWT as the `subject_token`.
Same `sub` and `role`; new `cid` (the service app); narrower `scp`.

```json
{
  "iss": "https://<tenant>.okta.com/oauth2/<authzServerId>",
  "aud": "agentcore-ecommerce",
  "cid": "<idp-client-id>",
  "scp": ["gateway.invoke"],
  "sub": "<okta user>",
  "role": "customer"
}
```

The exchange happens between checkpoints [2] and [3] on every tool call —
no token caching at the gateway side, so revoking a user's group membership
in Okta takes effect on the next call.

## The four checkpoints

### [1] AgentCore Gateway — `customJWTAuthorizer`

Configured in
[`infra/modules/agentcore/main.tf`](../infra/modules/agentcore/main.tf):

```hcl
authorizer_configuration {
  custom_jwt_authorizer {
    discovery_url    = var.okta_discovery_url
    allowed_audience = [var.okta_audience]   # "agentcore-ecommerce"
    allowed_clients  = var.okta_allowed_clients
  }
}
```

Rejects with `401 Unauthorized` (no/invalid token) or `403 insufficient_scope`
if `allowedScopes` is set and not satisfied (we don't set it). The
`WWW-Authenticate` header advertises required scopes per RFC 6750.

### [2] AgentCore Policy — Cedar

A `policy-engine` is provisioned by Terraform; **attachment** to the gateway
is a post-apply CLI step (provider gap). Two Cedar statements:

```cedar
permit(principal is AgentCore::OAuthUser,
       action in [...customer tool actions...],
       resource == AgentCore::Gateway::"<arn>")
when { principal.getTag("role") == "customer" };

permit(principal is AgentCore::OAuthUser,
       action,
       resource == AgentCore::Gateway::"<arn>")
when { principal.getTag("role") == "admin" };
```

Cedar is default-deny. The `role` tag on `principal` is mapped from the
`role` claim on the inbound JWT.

Cedar fires on `tools/call` only — `tools/list` is unguarded (acceptable
PoC trade-off; admin tool *names* are visible to customers, but invocation
is denied).

### Outbound: RFC 8693 token exchange (between [2] and [3])

The gateway target is configured for token exchange:

```hcl
credential_provider_configuration {
  oauth {
    provider_arn = var.okta_oauth2_provider_arn
    grant_type   = "TOKEN_EXCHANGE"
    scopes       = ["gateway.invoke"]   # NOT "openid" — Okta rejects that
    custom_parameters = {
      audience           = var.okta_audience
      subject_token_type = "urn:ietf:params:oauth:token-type:access_token"
    }
  }
}
```

The OAuth2 credential provider has a corresponding `onBehalfOfTokenExchangeConfig`:

```json
{
  "grantType": "TOKEN_EXCHANGE",
  "tokenExchangeGrantTypeConfig": { "actorTokenContent": "NONE" }
}
```

`actorTokenContent: NONE` because Okta derives the actor identity from
`client_secret_basic` client authentication. `M2M` would force AgentCore
to make an extra `client_credentials` call.

This config field **isn't in the Terraform AWS provider schema (v6.47)** —
it's a third documented provider gap (alongside policy attachment and
Cedar policy text). Set via:

```bash
aws bedrock-agentcore-control update-oauth2-credential-provider \
  --name agentcore_ecommerce_dev_okta \
  --credential-provider-vendor CustomOauth2 \
  --oauth2-provider-config-input '{...}'
```

### [3] ALB — `jwt-validation` listener action

Configured in [`infra/modules/compute/alb.tf`](../infra/modules/compute/alb.tf):

```hcl
default_action {
  type = "jwt-validation"
  jwt_validation {
    issuer        = var.okta_issuer
    jwks_endpoint = var.okta_jwks_uri
    additional_claim {
      format = "single-string"
      name   = "aud"
      values = [var.okta_audience]   # "agentcore-ecommerce"
    }
  }
}
```

ALB fetches Okta's JWKS out-of-band (managed AWS networking, no VPC egress
required) and verifies on every request:
- RS256 signature against Okta's published keys
- `iss` matches the configured Okta authorization server
- `aud` matches `agentcore-ecommerce`
- token not expired

`role` is **not** asserted here — ALB's `additional_claim` requires
`string-array` format for multi-value matches; the demo's `role` is a
scalar by design. Layers [2] and [4] own role enforcement.

ALB returns 403 with `WWW-Authenticate: Bearer error="insufficient_scope"`
on any validation failure regardless of root cause.

### [4] FastAPI — claim parsing + role gate

[`app/src/ecommerce/auth/jwt.py`](../app/src/ecommerce/auth/jwt.py) trusts
the bearer token (already validated by ALB) and **decodes claims without
re-verifying the signature**. The app reads `sub` and `role`; per-route
gates use `require_admin` where appropriate:

| Endpoint | Required `role` |
|---|---|
| `GET /products`, `POST /cart/items`, `POST /checkout` | `customer` or `admin` |
| `POST /products`, `PATCH /products/{id}/price`, `PATCH /products/{id}/stock` | `admin` |

## Why two Okta clients

| Client | Role | Used by |
|---|---|---|
| Agent OIDC client (`okta_allowed_client_ids`) | Mints inbound user JWTs via Authorization Code + PKCE | The MCP client / agent host. `cid` claim of inbound JWT. |
| Service-app OIDC client (`okta_client_id` + `okta_client_secret`) | Authenticates AgentCore Identity to Okta's `/v1/token` for the exchange. Must have **Token Exchange** grant ticked. | AgentCore Identity (outbound only). |

Token Exchange in Okta requires a confidential client and the grant type
explicitly enabled both on the client and on the authorization server's
access policy rule. The agent client is typically PKCE/public; that's
why the demo uses a separate confidential client just for the exchange.

## Okta-side configuration (summary)

- **Authorization server**: `agentcore-demo`, audience `agentcore-ecommerce`.
- **`role` claim**: derived from group membership via Okta Expression
  Language: `isMemberOfGroupName("agentcore-demo-admins") ? "admin" : "customer"`,
  emitted on access tokens for **Any scope**.
- **Custom scope**: `gateway.invoke` defined on the authz server. Required
  because Okta rejects token-exchange requests that contain the `openid`
  scope (error code `openid_not_allowed_token_exchange`).
- **Access policy rule** must enable both `Authorization Code` (for
  inbound) and `Token Exchange` (for outbound) grant types.
- **Service-app client** must have `Token Exchange` ticked under Grant
  types on the application itself.

## Why the ALB's TLS cert must chain to a public CA

AgentCore Gateway is a managed AWS service with no custom-CA injection.
A self-signed cert (or any cert not anchored in a public root) will fail
PKIX validation when the gateway calls the OpenAPI target's HTTPS URL —
the error surfaces as `OpenAPIClientException - Error executing HTTP
request for unknown: (certificate_unknown) PKIX path building failed`.

The platform stack issues a DNS-validated public ACM cert against
`var.alb_fqdn` and creates a Route53 alias record so AgentCore can reach
the ALB at a publicly-trusted hostname. The cert covers exactly the FQDN;
the OpenAPI spec's `servers[0].url` is patched to use that hostname, not
the raw `*.elb.amazonaws.com` name.

## Failure-mode reference

| Symptom | Likely cause |
|---|---|
| `403 insufficient_scope` from gateway, no logs in identity log group | Inbound authorizer misconfig, `customJWTAuthorizer.allowedScopes` set without matching `scp` claim. |
| `OnBehalfOfTokenExchangeConfig is required in the OBO flow` | OAuth2 credential provider missing `onBehalfOfTokenExchangeConfig`. Apply via CLI shim. |
| Okta returns `openid_not_allowed_token_exchange` | Gateway target requesting `scopes = ["openid"]`. Use `gateway.invoke` instead. |
| Okta returns `unsupported_grant_type` | Token Exchange not enabled on the service-app OIDC client or on the authz server's access policy rule. |
| `PKIX path building failed` from gateway | ALB cert isn't publicly trusted. Use ACM with DNS validation against a real domain. |
| 401 from ALB but inbound JWT looks correct | Exchanged JWT's `aud` doesn't match `var.okta_audience`. Check `audience` custom parameter on the gateway target's credential config. |
