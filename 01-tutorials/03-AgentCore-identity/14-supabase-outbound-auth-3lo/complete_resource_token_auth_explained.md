# `complete_resource_token_auth` Explained

`complete_resource_token_auth` is the single call that associates a Google OAuth
token with a specific authenticated user inside AgentCore Identity.

---

## The Two Parameters

### `session_uri`

Comes from the `session_id` query parameter when AgentCore redirects the browser
to `localhost:9090/oauth2/callback?session_id=...`

It is a pointer to the **pending OAuth session** sitting inside AgentCore Identity.
When the agent called `GetResourceOauth2Token` to start the 3LO flow, AgentCore
created a session internally — holding the in-progress authorization request, the
scopes requested, and the provider details. The `session_uri` is the handle to
that specific session.

Passing it to `CompleteResourceTokenAuth` tells AgentCore: *"finalise this specific
pending OAuth session — the user has consented, go fetch and store the token."*

Without it AgentCore would not know which of potentially many in-flight OAuth
sessions across all users to complete.

### `user_identifier`

The **Supabase JWT** stored earlier via `store_token_in_oauth2_callback_server(bearer_token)`.

It tells AgentCore: *"the person who just consented on Google is the same person
identified by this JWT."*

AgentCore uses it to:

1. Verify the JWT is valid (signature, expiry, audience)
2. Extract the user's identity (`sub` claim — the Supabase user UUID)
3. Store the Google access token in the vault **scoped to that specific user**

This is the session binding security check. If the JWT belongs to user A, the
Google token is stored under user A. When user A's agent later calls
`GetResourceOauth2Token`, it gets user A's token — never user B's.

### Why Both Are Needed Together

```
session_uri        → which OAuth session to complete  (identifies the transaction)
user_identifier    → who owns it                       (identifies the person)
```

Neither alone is sufficient. `session_uri` without `user_identifier` would let
anyone complete any session. `user_identifier` without `session_uri` gives no
context about which pending authorization to act on. Together they form the
binding: *this transaction belongs to this user*.

---

## What AgentCore Does Internally

```
CompleteResourceTokenAuth(session_uri, user_identifier)
         │
         ├── 1. Looks up the pending session by session_uri
         │        → finds the authorization code Google sent back
         │
         ├── 2. Validates the user_identifier JWT
         │        → checks signature via Supabase JWKS
         │        → extracts sub claim (e.g. "f264b5d6-6656-48c1-8d21-992751419eef")
         │
         ├── 3. Exchanges the authorization code for a Google access token
         │        → POST to Google's token endpoint with client_id + client_secret
         │
         └── 4. Stores the Google token in the vault
                  → keyed by: provider ("google-cal-provider") + user sub
                  → backed by AWS Secrets Manager
```

---

## Before and After

**Before** `complete_resource_token_auth`: AgentCore has an authorization code
sitting in a pending session, but no idea who it belongs to.

**After**: the Google token is locked to a specific user identity and retrievable
only in the context of that user's session.

Once stored, whenever the agent calls `GetResourceOauth2Token` on behalf of the
same Supabase user (matched by `sub`), AgentCore looks up the vault by
provider + user sub and returns the cached Google token — without triggering
another consent flow.
