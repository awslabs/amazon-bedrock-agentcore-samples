# poc-validator web layer — CDK

Infrastructure as code for the web layer in front of the poc-validator-agent
AgentCore Runtime: a static page (S3 + CloudFront), a Lambda proxy that runs
the agent and serves view-limited shared results, and the DynamoDB table
backing the 3-view / 30-day share cap.

The AgentCore Runtime/Memory/Gateway/Policy stack itself is separate — that's
managed by `agentcore/cdk/` via the `agentcore` CLI. This stack only covers
what sits in front of it.

## What's here

Every resource in `lib/web-stack.ts` was first built by hand, one verified
step at a time, directly against the account (Lambda → IAM role → CloudFront
origin/behavior → CloudFront Function → DynamoDB table → S3 lifecycle rule),
each step curl-tested before moving to the next. This stack started as the
IaC write-up of that same design, and has since fully replaced the hand-built
version: the original resources were torn down and this stack deployed fresh
in their place, then re-verified end to end (a real upload → run → share-link
round trip against the CDK-deployed stack, not just `cdk synth`).

That teardown-and-rebuild is also how the one real bug in this stack got
found: CDK's `FunctionUrlOrigin.withOriginAccessControl()` grants CloudFront
only `lambda:InvokeFunctionUrl` on the Lambda's resource policy. Lambda's
newer "Dual Auth" requirement for Function URLs also needs plain
`lambda:InvokeFunction` on the same principal/condition — without it, every
request through the OAC-signed origin 403s with Lambda's generic
"Forbidden... Function URL authorization" error, which gives no hint that
the missing piece is a second IAM statement rather than anything about the
signature itself. Fixed with an explicit `webInvokeFn.addPermission(...)`
call right after the distribution is created (see the comment in
`lib/web-stack.ts` and [aws-cdk#35872](https://github.com/aws/aws-cdk/issues/35872),
open at the time of writing).

### A note on the pinned resource names

The Lambda `functionName`, DynamoDB `tableName`, and S3 `bucketName` are
pinned rather than auto-generated (matching what this sample's other docs
reference by name). That means `cdk deploy` will fail with "already exists"
rather than silently creating a duplicate if resources with these exact
names already exist in the target account and aren't already owned by this
stack — most likely to come up if you're adapting this stack for your own
use rather than deploying it as-is. Either rename them in `lib/web-stack.ts`
first, or, if the existing resources really are meant to be this stack's
(e.g. you're recovering a stack after deleting it from CloudFormation state
without deleting the underlying resources), adopt them with `cdk import`
instead of `cdk deploy` — CloudFront distributions and CloudFront Functions
have more limited `cdk import` support than Lambda/DynamoDB/S3/IAM as of
this writing, so check its resource-type support list first.

## Deploying fresh (e.g. into a new account/region)

```bash
npm install
npm run build
npx cdk deploy \
  --context agentRuntimeArn="arn:aws:bedrock-agentcore:<region>:<account>:runtime/<name>" \
  --context demoKey="$(openssl rand -hex 24)" \
  --context basicAuthCredentialBase64="$(printf 'user:pass' | base64)"
```

`publicBaseUrl` is intentionally omitted on the first deploy — the
distribution's domain name isn't known until after it exists, and wiring it
as a same-stack reference would create a circular CloudFormation dependency
(the Distribution needs the Lambda's Function URL as an origin; the Lambda
would need the Distribution's domain name). Read the `DistributionDomainName`
output from the first deploy, then redeploy passing it:

```bash
npx cdk deploy --context ... --context publicBaseUrl="https://<output-domain>"
```

## Notable design choices carried over from the hand-built version

- **CloudFront Function does Basic Auth**, not a Lambda@Edge — cheaper, lower
  latency, sufficient for gating a small internal/demo tool. It also strips
  the client's `Authorization` header after validating it, because the
  `/api/invoke` and `/share/*.json` routes are OAC-signed by CloudFront
  itself, and a leftover client `Authorization` header collides with that
  SigV4 signature (this was a real bug hit during manual build-out).
- **The Lambda serves two routes**, not two Lambdas: `POST /api/invoke`
  (gated by a shared-secret header, since a browser can't SigV4-sign) and
  `GET /share/*.json` (publicly reachable, but rate-limited to 3 views via a
  DynamoDB conditional `UpdateItem`). One function, one IAM role, less to
  keep in sync.
- **`/share/*.json` must be an earlier CloudFront behavior than `/share/*`**
  — CloudFront matches path patterns in list order, and the view-counted
  Lambda route has to win before the raw-S3-fetch route ever gets a chance,
  or the view cap would be trivially bypassable.
- **The S3 lifecycle rule filters on a tag (`AutoExpire=true`), not just the
  `share/` prefix** — the static `share/view.html` shell also lives under
  `share/` and must never expire; only the per-run result JSON objects the
  Lambda writes are tagged.
- **DynamoDB, not just S3, for view-counting** — S3 has no atomic counter;
  enforcing "viewed at most 3 times" correctly under concurrent requests
  needs a real conditional write, which is what `ConditionExpression:
  "attribute_exists(share_id) AND view_count < :max"` on `UpdateItem` gives.
