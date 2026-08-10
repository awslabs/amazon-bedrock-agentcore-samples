# poc-validator web layer — CDK

Infrastructure as code for the web layer in front of the poc-validator-agent
AgentCore Runtime: a static page (S3 + CloudFront), a Lambda proxy that runs
the agent and serves view-limited shared results, and the DynamoDB table
backing the 3-view / 30-day share cap.

The AgentCore Runtime/Memory/Gateway/Policy stack itself is separate — that's
managed by `agentcore/cdk/` via the `agentcore` CLI. This stack only covers
what sits in front of it.

## What's here vs. what's already live

Every resource in `lib/web-stack.ts` was first built by hand, one verified
step at a time, directly against the account (Lambda → IAM role → CloudFront
origin/behavior → CloudFront Function → DynamoDB table → S3 lifecycle rule),
each step curl-tested before moving to the next. This stack is the IaC
write-up of that same design — `cdk synth` produces the CloudFormation a
fresh deployment would create.

**It does not currently manage the live resources.** Deploying this stack as-is
into the same account would try to create a second Lambda, a second
CloudFront distribution, etc. (CDK will fail loudly on the ones with fixed,
already-taken names — the Lambda `functionName` and DynamoDB `tableName` are
both pinned to match the real ones, so a plain `cdk deploy` here will error
with "already exists" rather than silently duplicating them).

### Adopting the existing resources (optional follow-up, not done automatically)

CloudFormation supports importing existing resources into a stack via
`cdk import`. This is the correct path to bring the hand-built resources
under this stack's management, but it's a deliberate, separate action —
not run as part of building this CDK app, because the distribution is
already serving a URL that's been shared and is actively being used, and an
import gone wrong (a field CDK insists on changing vs. the live resource) is
the kind of thing you want to do with nothing time-sensitive riding on it.

To do it when ready:

```bash
npm run build
npx cdk import --context agentRuntimeArn=... --context demoKey=... \
  --context basicAuthCredentialBase64=... --context publicBaseUrl=...
```

`cdk import` will prompt for the physical ID of each resource it can adopt
(Lambda function name, DynamoDB table name, S3 bucket name, IAM role name).
CloudFront distributions and CloudFront Functions have more limited import
support in CDK as of this writing — check `cdk import`'s own resource-type
support list before relying on it for those two; worst case, those two stay
hand-managed and everything else moves under CDK.

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
