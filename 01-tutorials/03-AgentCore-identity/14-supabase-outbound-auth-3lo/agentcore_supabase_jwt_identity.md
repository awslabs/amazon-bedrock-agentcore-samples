# How AgentCore Uses the Supabase JWT to Identify a User

AgentCore uses the Supabase JWT to identify a user, but only to extract the `sub`
claim. The JWT itself is never stored or forwarded — it is used purely as a secure
carrier for the user's identity.

---

## During `complete_resource_token_auth`

AgentCore validates the Supabase JWT (signature, expiry, audience) and pulls out
the `sub` claim — e.g. `f264b5d6-6656-48c1-8d21-992751419eef`. That UUID becomes
the **user key** for the token vault entry. AgentCore does not store the JWT
itself, only the `sub`.

## After That — AgentCore Never Sees the Supabase JWT Again

The vault entry is keyed by `provider + sub`. When the agent later calls
`GetResourceOauth2Token`, AgentCore identifies the user from the inbound request
context (the Supabase JWT on the HTTP request), extracts `sub` again, and looks
up `google-cal-provider + <sub>` in the vault. The JWT is used purely as a `sub`
carrier — not stored, not forwarded anywhere.

---

## What AgentCore Actually Stores

```
vault key:   "google-cal-provider" + "f264b5d6-6656-48c1-8d21-992751419eef"
vault value: Google access token + refresh token
```

---

## The Two Roles of the Supabase JWT

| When | Role |
|---|---|
| At `complete_resource_token_auth` | Proof of identity — validates who consented and extracts their `sub` to key the vault |
| At every `GetResourceOauth2Token` call | Lookup key — `sub` is extracted to find the right Google token in the vault |

The identity system is entirely `sub`-based after the first call. The JWT is just
the mechanism to securely communicate that `sub` to AgentCore.

---

## Full Lifecycle

```
1. complete_resource_token_auth(session_uri, supabase_jwt)
        │
        ├── validates supabase_jwt (signature, expiry, aud)
        ├── extracts sub = "f264b5d6-..."
        ├── exchanges Google auth code for access token
        └── stores in vault: key = "google-cal-provider" + sub
                             value = Google access token + refresh token

2. Agent calls GetResourceOauth2Token (on every tool invocation)
        │
        ├── AgentCore reads sub from the inbound Supabase JWT
        ├── looks up vault: "google-cal-provider" + sub
        └── returns Google access token to the agent

3. Supabase JWT is never stored, never forwarded — used only to carry sub
```
