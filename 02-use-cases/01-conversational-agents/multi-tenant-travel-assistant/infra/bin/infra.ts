#!/usr/bin/env node
/**
 * Infrastructure — everything the AgentCore CLI does not own.
 *
 * The CLI generates and drives its own CDK app for the runtime, memory,
 * gateways, evaluators and policy engines (`agentcore.json` is marked
 * `managedBy: CDK`). This app covers the rest: the mock TMC's storage and API,
 * and later the VPC, Cognito, knowledge base and CloudTrail.
 *
 * Two CDK *apps* is unavoidable — the CLI regenerates its own, and hand-editing
 * generated CDK is out of bounds. Two *stacks* inside this app was not: see
 * `MultiTenantTravelStack`.
 */
import { App, Aspects, Tags } from 'aws-cdk-lib';
import { AwsSolutionsChecks } from 'cdk-nag';
import { MultiTenantTravelStack } from '../lib/multi-tenant-travel-stack';

const app = new App();

/**
 * **Deliberately not `CDK_DEFAULT_REGION`.** That derives from the ambient
 * `AWS_REGION`, which a reader may well have set for an unrelated project in the
 * same account — and the failure mode is silent rather than loud: instead of
 * updating the existing stack, CDK creates a *second parallel one* in the other
 * region, leaving two Cognito pools, two sets of tables, and an agent wired to
 * whichever it resolved first. Nothing errors. The demo just stops making sense.
 *
 * So the region is an explicit opt-in with one documented default. Ambient
 * credentials still pick the *account*, because deploying to the wrong account
 * fails loudly on permissions instead of quietly succeeding.
 */
const region = process.env.TRAVEL_REGION ?? 'us-east-1';

/**
 * **`us-east-1` is a hard requirement, not a default with a fallback — so it fails here rather than
 * twenty minutes into a deploy.**
 *
 * The README used to show `TRAVEL_REGION=eu-west-1 ./deploy.sh` as a working example. It never
 * worked, and the way it failed was the problem: the Lambda Web Adapter layer ARN in
 * `conversation-api.ts` is regional and pinned
 * (`arn:aws:lambda:us-east-1:753240598075:layer:LambdaAdapterLayerArm64:28`), so a function in
 * another region cannot attach it. That file's own comment records what happens next — a layer that
 * does not run surfaces as an **init timeout**, not as an architecture error. Twenty minutes of
 * CloudFormation, then a timeout that names nothing.
 *
 * Two pins, and only one is a defect worth fixing:
 *
 *   * The layer ARN **is** a defect. Fixing it means a region-to-ARN map, or resolving the layer at
 *     synth. Deliberately not done: nobody has asked for another region, and it is real surgery to
 *     support a claim we can simply stop making.
 *   * The `CLOUDFRONT`-scoped web ACL is **not** a defect. That scope must live in `us-east-1`, which
 *     `edge-protection.ts` states. It now only applies with `--waf`, so it is no longer an
 *     unconditional pin — which is why the check below names it separately.
 *
 * Refusing loudly is the honest resolution of a documented promise the code cannot keep.
 */
if (region !== 'us-east-1') {
  const reasons = [
    'the Lambda Web Adapter layer ARN in lib/conversation-api.ts is pinned to us-east-1, and a ' +
      'mismatched layer fails as a Lambda init timeout rather than as an architecture error',
  ];
  if (process.env.TRAVEL_WAF === 'true') {
    reasons.push(
      'a CLOUDFRONT-scoped WAF web ACL can only exist in us-east-1 (AWS constraint, not a ' +
        'preference) — it would need its own us-east-1 stack with crossRegionReferences',
    );
  }
  throw new Error(
    `TRAVEL_REGION=${region} is not supported. This sample deploys to us-east-1 only:\n` +
      reasons.map((reason) => `  - ${reason}`).join('\n') +
      '\nUnset TRAVEL_REGION, or set it to us-east-1.',
  );
}

new MultiTenantTravelStack(app, 'multi-tenant-travel', {
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region },
  description: 'Mock TMC storage and API (the platform a TMC already runs)',
  /**
   * **`TRAVEL_RUNTIME_ARN` and `TRAVEL_MEMORY_ID` are gone, and their removal is the fix.**
   *
   * They used to be read here and passed down to the conversation API. Because the agent's stack
   * deploys after this one, a redeploy from a shell without them exported wrote an **empty string
   * over a working value** — successfully, with a clean log, surfacing days later as a `404` from
   * AgentCore on a traveller's next message.
   *
   * The conversation API resolves both from Parameter Store at cold start, published by
   * `scripts/publish_agent_refs.py` from the agent stack's outputs. A value that cannot be passed in
   * cannot be passed in wrong — which is a better guarantee than a documented reminder to export it.
   */
  /** Where the SPA is served from. Defaults to the Vite dev server. */
  frontendOrigin: process.env.TRAVEL_FRONTEND_ORIGIN,
  /**
   * Run the capability and data layers in a private VPC — **off by default, because it is the
   * larger of the two switches here that cost money while idle.**
   *
   * Eleven interface endpoints across two AZs is ~$161/month standing, whether or not anyone
   * speaks to the agent. Defaulting this on would mean a reader who cloned the repo to look around
   * found that out from an invoice, which is not an acceptable way to learn it.
   * `TRAVEL_PRIVATE=true` opts in; the Cost section of `README.md` shows the working and the
   * rejected alternatives.
   */
  private: process.env.TRAVEL_PRIVATE === 'true',
  /**
   * Put a WAF web ACL in front of the distribution — **off by default, on the reasoning already
   * written down for `private` above.**
   *
   * The web ACL and its five rules were ~$10/month standing and, until this switch existed, the
   * *only* standing cost in a default deploy. So the argument made for the VPC applied here and was
   * not being followed: a reader cloning a sample to read it paid a monthly fee for a control they
   * had not asked for. With this off, an idle default deployment costs approximately nothing.
   *
   * **Safe to default off because the ACL is not the tenancy boundary**, which
   * `edge-protection.ts` states at length: it is volumetric and known-bad-signature protection, and
   * authorisation is Cognito's verified claims, the interceptor, Cedar and `dynamodb:LeadingKeys`.
   * Turning it off removes rate limiting and managed rule sets — which a shared public URL wants
   * and a private dev deploy does not. API Gateway throttling stays on as the free abuse ceiling.
   *
   * `TRAVEL_WAF=true` opts in. Recommended before publishing the demo URL broadly.
   */
  waf: process.env.TRAVEL_WAF === 'true',
});

/**
 * Cost attribution starts at the tag, and **a tag with one value answers nothing.**
 *
 * An earlier version stopped here, applying `project` and `sample` to everything. An audit found 58
 * of 65 resources tagged and the tagging useless: every resource carried an identical pair, so
 * "what does retrieval cost versus the tool Lambdas?" had no answer. Coverage is not attribution —
 * a dimension needs to *vary*.
 *
 * These two stay as the rollup ("everything belonging to this sample"). What makes cost answerable
 * is `component`, applied per construct in `MultiTenantTravelStack` — which is also where the reason
 * `tenant` is deliberately **not** a resource tag is written down.
 *
 * **Tagging alone still bills nothing to anyone.** Each key must be activated under Billing → Cost
 * allocation tags, it takes ~24h to appear, and it is **not retroactive** — spend before activation
 * is permanently unattributable. That asymmetry is why tags go on early rather than when the cost
 * work starts.
 */
Tags.of(app).add('project', 'multi-tenant-travel');
/**
 * **Names *this* sample, so its spend stays separable from anything else in the account.**
 *
 * `project` and `sample` are both rollups and neither varies within this stack, so the only work this
 * key does is distinguish this deployment from its neighbours. That matters because an account used
 * for evaluation usually holds several samples at once, and two of them asserting the same value
 * merges their costs into one line item that answers nothing — the same "coverage is not attribution"
 * trap described below, one level up.
 *
 * Two mechanics worth knowing before changing it: a tag *value* needs no activation (only keys do), and
 * a change is **not retroactive** — spend already recorded keeps the old value.
 */
Tags.of(app).add('sample', 'multi-tenant-travel-assistant');

/**
 * `dev` unless told otherwise. Named explicitly rather than inferred from the region or account,
 * because a mis-attributed environment is worse than an absent one: it silently moves spend between
 * budgets that different people answer for.
 */
Tags.of(app).add('environment', process.env.TRAVEL_ENVIRONMENT ?? 'dev');

/**
 * **cdk-nag: every synth is a security review.**
 *
 * `AwsSolutionsChecks` is the broadest of the bundled packs. Registered as an Aspect
 * here rather than run as a separate command on purpose — a check you have to remember to run is a
 * check that stops being run. Findings surface at synth, so a regression cannot reach a deploy.
 *
 * **Pinned to cdk-nag v2, deliberately, after trying v3.** v3 rewrites the engine from an `IAspect`
 * to an `IPolicyValidationPlugin` and replaces `NagSuppressions` with
 * `Validations.of().acknowledge()`. That API could not express three of this stack's findings: the
 * `AwsSolutions-IAM4` finding ids embed a managed-policy ARN
 * (`Policy::arn:<AWS::Partition>:iam::aws:policy/…`), and CDK rejects any id containing more than one
 * `::` because it reserves that as the annotation-prefix delimiter. Bare, prefixed, `[Policy]`, `[*]`
 * and resource-level forms were all tried; none both parse and match.
 *
 * v2 solves it with a different shape entirely: **`appliesTo` as its own field**, rather than a
 * finding encoded into the id. That is also the better form — the list in `lib/nag-suppressions.ts`
 * keeps each suppression narrow, so a *new* managed policy or wildcard still fails the check instead
 * of being silently covered.
 *
 * `verbose` because the default output names the rule and not the reason, and the reasons in
 * `lib/nag-suppressions.ts` are the artifact a reviewer actually reads.
 */
Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));

app.synth();
