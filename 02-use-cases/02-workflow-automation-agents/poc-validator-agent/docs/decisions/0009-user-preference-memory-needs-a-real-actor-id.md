# 0009 — USER_PREFERENCE memory is only as real as the actor_id behind it

## Status
Accepted.

## Context

AgentCore Memory ships a third built-in strategy alongside SEMANTIC and
SUMMARIZATION: `USER_PREFERENCE`, which accumulates durable, per-actor
preferences across sessions (region, segment, and industry a given reviewer
tends to submit, for instance) so a repeat reviewer doesn't re-state context
that was already implicit in their last three reviews.

Adding the strategy to `agentcore.json` is one config entry. Making it mean
anything is a different problem: every AgentCore Memory namespace in this
sample is keyed by `{actorId}`, and the CLI path and the web layer had two
different answers for where that comes from.

The CLI path was already correct — `main.py` derives `actor_id` from
`partner_id` or `user_id` in the invoke payload, so a real caller passing a
consistent identifier gets a consistent actor across calls.

The web layer was not. `web/lambda/handler.py` hardcoded `"user_id": "web-demo"`
on every single request, because the web layer has no login system (see the
README's Known Limitations on the Basic Auth gate being a shared-credential
mechanism, not real multi-user auth). Every visitor to the demo shared one
identity. Adding USER_PREFERENCE on top of that wouldn't have added a broken
feature — it would have added a feature that appears to work while silently
blending every visitor's inferred preferences into one meaningless composite,
which is worse than not having it.

## Decision

Give the web layer a per-browser pseudo-identity instead of a per-account one.
The page generates a random 128-bit id client-side on first visit
(`crypto.getRandomValues`), stores it in `localStorage`, and sends it as
`browser_id` on every `/api/invoke` call. The Lambda validates it strictly
(`^[a-f0-9]{32}$`, since it becomes part of a Memory namespace string) and
falls back to `"anonymous"` if it's missing, malformed, or `localStorage` is
unavailable (private browsing, storage blocked). The resulting `user_id` sent
to the Runtime is `web-{browser_id}` — never `"web-demo"`.

## Rationale

This is deliberately *not* a login system, and doesn't pretend to be one. It's
the minimum needed for USER_PREFERENCE to attach to something real: a
returning browser, not a returning *person*. Clear the browser's storage, get
a new identity, lose the accumulated preferences — that's an honest, disclosed
tradeoff for a demo tool with no account system, not a security gap, since no
access control depends on this id (Basic Auth already gates the page itself;
the demo-key header already gates the invoke call).

The alternative — leaving `"web-demo"` in place and only wiring USER_PREFERENCE
correctly for the CLI path — was considered and rejected. It would have meant
shipping a feature that behaves correctly in the code path fewer people will
actually try and silently does the wrong thing in the one most people will.

## Consequences

`getBrowserId()` in the page's JS is the only place this id is generated; the
Lambda never invents one on the server side, so a validation failure
degrades to `"anonymous"` rather than minting a new identity per request
(which would silently defeat the point — every anonymous request sharing one
bucket is a known, disclosed simplification, not a bug, since it degrades to
exactly the old shared-identity behavior rather than something worse).
