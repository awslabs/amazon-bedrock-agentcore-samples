# 0008 — View-limited share links enforced by a conditional write, not client trust

## Status
Accepted.

## Context

The optional web layer lets a reviewer upload a Scope of Work, run it against the live
agent, and hand a link to someone else — a customer contact, a manager — so they can see
the one result without an account. That link is, by construction, unauthenticated: anyone
who has it can open it. Two properties were wanted regardless: it should stop working
after a small number of views, and it should stop working after a bounded time, so a link
posted somewhere public or forwarded indefinitely doesn't turn into a standing, silent
disclosure.

S3 has no concept of "this object may be read N times." A naive implementation — check a
counter, then read the object — has a race: two near-simultaneous requests can both read
the counter before either writes it back, and both succeed when only one should.

## Decision

`/share/*.json` is served by the Lambda, not directly by S3. On each request it performs a
single DynamoDB `UpdateItem` with `ConditionExpression: attribute_exists(share_id) AND
view_count < :max` (`:max = 3`) and `UpdateExpression: ADD view_count :incr`. Only if that
conditional write succeeds does the Lambda then read the result from S3 and return it. The
DynamoDB item's `ttl` attribute is set to 30 days out at write time and DynamoDB's native
TTL sweep removes it; the S3 object is independently expired by a bucket lifecycle rule,
filtered on an `AutoExpire=true` object tag rather than the `share/` prefix alone, because
the prefix also holds the static, never-expiring page shell.

The bucket policy grants `s3:GetObject` only to CloudFront's Origin Access Control
principal, scoped to this one distribution. A client cannot fetch the S3 object directly
to bypass the counter — the only path to the data goes through the Lambda's conditional
write.

## Rationale

A conditional write is the correct primitive for "at most N," full stop — it is what
DynamoDB's compare-and-swap semantics exist for, and it is genuinely atomic under
concurrent requests, which a read-then-write counter in application code is not.

Splitting *content* expiry (S3 lifecycle) from *view-count* expiry (DynamoDB TTL) rather
than inventing one mechanism to do both was deliberate: they are different failure modes
(a link that's technically still within its 30 days but has been viewed out, vs. a link
that's under its view cap but aged out) and conflating them would have made the Lambda
responsible for reimplementing what each service already does correctly and cheaply.

Routing the JSON read through the Lambda (rather than a cheaper direct-to-S3 fetch with
the counter as a side effect) was the one deliberate cost/purity tradeoff here — it adds
one Lambda invocation to every share view. At sample-project volumes this is immaterial;
at scale it is the kind of thing you'd revisit with a DynamoDB Streams-triggered async
counter instead, accepting eventual rather than immediate enforcement.

## Consequences

CloudFront's cache behavior order matters and is easy to get subtly wrong: `/share/*.json`
must be registered *before* the broader `/share/*` behavior (which serves the static
`share/view.html` shell straight from S3), or CloudFront's first-match routing would let
`.json` requests fall through to the uncounted path and the cap would do nothing. This is
called out explicitly in `web/cdk/lib/web-stack.ts` and in `web/cdk/README.md`.

The Lambda's IAM role needs `s3:GetObject`/`s3:PutObject`/`s3:PutObjectTagging` scoped to
`share/*` and `dynamodb:PutItem`/`UpdateItem`/`GetItem` scoped to the one table — nothing
broader. `web/cdk/lib/web-stack.ts` states these explicitly with `iam.PolicyStatement`
rather than the CDK L2 `grant*()` convenience methods, which default to a wider action set
than this Lambda ever calls.
