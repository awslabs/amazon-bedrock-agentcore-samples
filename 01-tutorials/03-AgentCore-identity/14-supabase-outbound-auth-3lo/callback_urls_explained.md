# Callback URLs Explained

Two different callback URLs appear in this tutorial. They serve different purposes
at different stages of the OAuth2 3-Legged Auth (3LO) flow.

---

## Cell 13 — AgentCore's Callback URL

```
https://bedrock-agentcore.us-west-2.amazonaws.com/identities/oauth2/callback/<uuid>
```

**Direction: Google → AgentCore**

When the user clicks the authorization URL and grants consent on Google's consent
screen, Google needs somewhere to redirect the browser back to. That destination
is this URL. You register it in Google Console under **Authorised Redirect URIs**
so Google trusts it.

What happens at this URL:

1. Google redirects the user's browser here with an authorization code
2. AgentCore exchanges that code for a Google access token
3. AgentCore stores the token in its internal token vault (backed by Secrets Manager)
4. AgentCore then redirects the browser again — this time to the local callback URL

AgentCore acts as the intermediary between Google and your application. It handles
the token exchange so your agent code never touches the raw authorization code.

---

## Cell 16 — Local Callback URL

```
http://localhost:9090/oauth2/callback
```

**Direction: AgentCore → your machine**

After AgentCore stores the Google token, it redirects the browser to this local
URL with a `session_id` parameter. The `oauth2_callback_server.py` running on
port 9090 receives that redirect and does one critical thing — it calls
`CompleteResourceTokenAuth` with:

- the `session_id` from the URL parameter
- the Supabase JWT stored earlier via `store_token_in_oauth2_callback_server()`

This is the **session binding** step. It tells AgentCore: *"the person who just
consented on Google is the same person identified by this Supabase JWT"*. Only
after this call does AgentCore release the stored Google token to the agent.

You register this URL on the workload identity (`allowedResourceOauth2ReturnUrls`)
so AgentCore will only redirect to pre-approved destinations — preventing a
different user from intercepting another user's OAuth session.

---

## The Full Redirect Chain

```
User browser
    │
    │  1. Agent prints authorization URL → user clicks it
    ▼
Google consent screen
    │
    │  2. User grants consent → Google redirects to AgentCore callback URL (cell 13)
    ▼
AgentCore (bedrock-agentcore.amazonaws.com/identities/oauth2/callback/...)
    │  exchanges auth code for Google access token
    │  stores token in vault
    │  3. Redirects browser to local callback URL (cell 16) with ?session_id=...
    ▼
oauth2_callback_server.py (localhost:9090/oauth2/callback)
    │  calls CompleteResourceTokenAuth(session_id, supabase_jwt)
    │  4. Binds the Google token to this specific Supabase user
    ▼
Agent can now call GetResourceOauth2Token and receive the Google access token
```

---

## Summary

| | Cell 13 — AgentCore callback | Cell 16 — Local callback |
|---|---|---|
| Direction | Google → AgentCore | AgentCore → your machine |
| Registered with | Google Console (Authorised Redirect URIs) | AgentCore workload identity (`allowedResourceOauth2ReturnUrls`) |
| Hosted by | AWS (AgentCore Identity service) | `oauth2_callback_server.py` on port 9090 |
| Purpose | Receive auth code from Google, exchange for access token | Bind the OAuth session to the authenticated Supabase user |
| Handled by | AgentCore automatically | `CompleteResourceTokenAuth` call in `oauth2_callback_server.py` |
