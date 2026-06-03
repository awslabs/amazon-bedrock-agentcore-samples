# Okta setup

These steps configure an Okta tenant to issue tokens that the rest of the
stack expects. Replace `<tenant>` with your Okta tenant subdomain throughout.

The end state is:

- Two Okta groups (`agentcore-demo-customers`, `agentcore-demo-admins`) that
  control role membership for the demo.
- Two Okta applications:
  - A **Web Application** (OIDC) for **inbound** user sign-in. The two demo
    groups are assigned here; its client id is what the gateway authorizer
    accepts (`okta_allowed_client_ids`).
  - An **API Services** application for the gateway's **outbound** token
    exchange. API Services is the only app type whose **Grant type** panel
    exposes **Token Exchange** (RFC 8693); its client id + secret are what
    the gateway uses to call `/oauth2/v1/token`
    (`okta_client_id` / `okta_client_secret`).
- A custom authorization server (`agentcore-demo`) with audience
  `agentcore-ecommerce` and a derived `role` claim. Both apps share this
  authz server.

## Prerequisites

- An Okta account ([Developer Edition](https://developer.okta.com/signup/) is
  sufficient).
- Admin access to `https://<tenant>-admin.okta.com`.
- At least two Okta users (one per role).

## 1. Create the two groups

Admin Console → **Directory** → **Groups** → **Add group**:

| Group | Description |
|---|---|
| `agentcore-demo-customers` | Read / cart / checkout role for the demo. |
| `agentcore-demo-admins` | Product / price / stock-management role for the demo. |

Assign your test users — the customer user to `agentcore-demo-customers`,
the admin user to `agentcore-demo-admins`.

## 2. Create the two applications

The demo needs two separate Okta apps because no single app type covers both
sides cleanly: the inbound user sign-in flow wants a regular OIDC web client,
while the gateway's outbound RFC 8693 exchange requires the **Token Exchange**
grant which only **API Services** apps expose.

### 2a. Inbound: Web Application (user sign-in)

Admin Console → **Applications** → **Create App Integration** →
**OIDC – OpenID Connect** → **Web Application**.

- **Name**: `AgentCore Demo` (inbound).
- **Grant type**: `Authorization Code` (default).
- **Sign-in redirect URIs**: e.g. `http://localhost:8080/callback` (must
  match what your demo client uses;
  [scripts/get_token.py](../scripts/get_token.py) defaults to this).
- **Assignments**: select **Limit access to selected groups** and assign
  **both** demo groups. Users outside these groups cannot obtain a token.

Save the **Client ID** — this is the value for `okta_allowed_client_ids` in
the agentcore stack's tfvars (the gateway authorizer uses it to validate the
`cid` claim on inbound user JWTs). The web app's secret is only needed by
[scripts/get_token.py](../scripts/get_token.py) at sign-in time
(`OKTA_CLIENT_SECRET`); Terraform does not consume it.

### 2b. Outbound: API Services (gateway token exchange)

Admin Console → **Applications** → **Create App Integration** →
**API Services**.

- **Name**: `AgentCore Demo` (outbound).
- After creation, on the **General** tab → **General Settings** → **Edit**:
  - **Grant type**: tick **Token Exchange**. See step 7. (No user assignment
    is needed — API Services apps don't take group assignments; the role
    claim resolves from the *subject's* group membership during the exchange.)
- On the **General** tab → **Client Credentials**: copy the **Client ID** and
  **Client secret**.

These map to `okta_client_id` and `okta_client_secret` in the agentcore stack's
tfvars. The gateway's outbound credential provider authenticates as this app
to swap the inbound user JWT for a target-scoped JWT.

## 3. Create a custom authorization server

Admin Console → **Security** → **API** → **Authorization Servers** →
**Add Authorization Server**.

- **Name**: `agentcore-demo`.
- **Audience**: `agentcore-ecommerce` (this becomes the `aud` claim and
  matches `okta_audience` in tfvars).

Save and note the **Issuer URI** (`https://<tenant>.okta.com/oauth2/<authzServerId>`).

## 4. Add the access-token claims

Same authz server → **Claims** → **Add Claim**. Add two claims:

### 4a. `role` — derived from group membership

- **Name**: `role`
- **Include in token type**: **Access Token**, **Always**
- **Value type**: **Expression**
- **Value**:
  ```
  isMemberOfGroupName("agentcore-demo-admins") ? "admin" : "customer"
  ```
- **Include in**: **Any scope**

Admin membership wins (a user in both groups gets `role = "admin"`). Users
in neither group cannot reach this claim because the Web Application's group
assignment in step 2a blocks token issuance for them.

### 4b. `client_id` — mirror of `cid`

- **Name**: `client_id`
- **Include in token type**: **Access Token**, **Always**
- **Value type**: **Expression**
- **Value**:
  ```
  app.clientId
  ```
- **Include in**: **Any scope**

AgentCore's JWT authorizer matches a top-level `client_id` claim against
`okta_allowed_client_ids`, but Okta only emits the issuing client as `cid`
by default. This claim mirrors `cid` into `client_id` so the authorizer
accepts the token.

## 5. Add the `gateway.invoke` scope

Same authz server → **Scopes** → **Add Scope**.

- **Name**: `gateway.invoke`
- **Display name**: `Invoke AgentCore Gateway tools`
- Leave "Default scope" unchecked.

This scope is required because Okta rejects token-exchange requests that
include the `openid` scope (`openid_not_allowed_token_exchange`). The
gateway's outbound credential provider requests `gateway.invoke` only.

## 6. Configure the access policy

Same authz server → **Access Policies** → **Add New Access Policy**.

- **Name**: `Default policy`
- **Assign to**: `All clients` (so both apps from step 2 are covered).

Add a rule:

- **Name**: `Allow demo users`
- **Grant types**: enable **both** of:
  - `Authorization Code` — initial user sign-in (Web Application, step 2a).
  - `Token Exchange` — gateway swap (API Services, step 2b).
- **User**: `Any user assigned the app`.
- **Scopes**: `Any scopes`.

## 7. Confirm Token Exchange is enabled on the API Services app

Token Exchange must be enabled both on the authz server (step 6) **and** on
the API Services client itself. If you ticked it during step 2b you can skip
this — verify by visiting Admin Console → **Applications** →
`AgentCore Demo (outbound)` → **General** → **General Settings**:
**Token Exchange** should be ticked under **Grant type**.

Without this the gateway's outbound exchange fails with
`unsupported_grant_type`. The grant only appears on **API Services** apps; if
you can't see it, you're looking at the inbound Web Application from step 2a
instead of the API Services app from step 2b.

## 8. Verify token issuance

Same authz server → **Token Preview**.

- **OAuth/OIDC client**: `AgentCore Demo (inbound)` (the Web Application).
- **Grant type**: `Authorization Code`.
- **Scopes**: `openid` (the `role` claim is configured for **Any scope**).
- **User**: pick your customer user → **Preview Token**.

In the access token JSON confirm:
- `iss` matches the issuer URI from step 3.
- `aud` is `agentcore-ecommerce`.
- `role` is `customer`.

Repeat with the admin user; `role` should be `admin`.

## Values to copy into tfvars

The configuration lives in two stacks. Each has its own `terraform.tfvars`.

| Stack | Okta values it needs | Source |
|---|---|---|
| `platform/` | `okta_issuer`, `okta_audience`, `okta_jwks_uri` | step 3 |
| `agentcore/` | `okta_issuer`, `okta_audience` | step 3 |
| `agentcore/` | `okta_allowed_client_ids` | step 2a (Web Application client id) |
| `agentcore/` | `okta_client_id`, `okta_client_secret` | step 2b (API Services credentials) |

`okta_issuer` and `okta_audience` appear in both — keep them in sync.
`okta_jwks_uri` is `<issuer>/v1/keys`.

The client secret is declared `ephemeral` and `sensitive` in Terraform — it
never enters state, but does live in `terraform.tfvars` on disk (gitignored).
To keep it off disk entirely, override at apply time:

```bash
TF_VAR_okta_client_secret=<client-secret> terraform apply
```
