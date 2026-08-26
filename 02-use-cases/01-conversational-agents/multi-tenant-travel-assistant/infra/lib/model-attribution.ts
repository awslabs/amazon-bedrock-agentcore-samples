import { CfnOutput, Stack } from 'aws-cdk-lib';
import * as bedrock from 'aws-cdk-lib/aws-bedrock';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

/**
 * The model id the agent uses.
 *
 * **Must match `MODEL_ID` in `agent/.../model/load.py`.** They cross a repo boundary — this builds the
 * profile, that one falls back to the raw id — so the value is stated in both places and a mismatch
 * shows up as spend attributed to the wrong profile rather than as an error.
 *
 * `global.` rather than `us.`: a **global** cross-region profile, which routes wherever capacity is.
 * Verified as a valid `copyFrom` source (it is `SYSTEM_DEFINED` with a real ARN), which is not obvious
 * — the docs describe copying from a *model* ARN or a regional profile.
 */
const MODEL_ID = 'global.anthropic.claude-sonnet-4-5-20250929-v1:0';

/** Bare model id behind the profile, for the IAM grant. */
const FOUNDATION_MODEL = 'anthropic.claude-sonnet-4-5-20250929-v1:0';

/** Where the agent reads the profile ARN. Must match `model/load.py`. */
export const MODEL_PROFILE_PARAM = '/multi-tenant-travel/model/inference-profile-arn';

/**
 * Model spend, attributable.
 *
 * **The gap this closes.** On-demand Bedrock invocations carry no tags: call a raw model id and every
 * request in the account collapses into one undifferentiated line item per model. So the infrastructure
 * could be tagged down to the component while the *expensive half* of the bill — tokens — remained
 * anonymous. An application inference profile is the only tag carrier Bedrock offers: a resource you
 * own, that you invoke instead of the model, and that can be tagged.
 *
 * **One profile per deployment, not per tenant**, and that is a scaling decision rather than
 * simplicity. Profiles are account-scoped resources under a service quota, so a profile-per-customer
 * design reintroduces exactly the silo problem pooled tenancy exists to avoid — and at a few thousand
 * customers it stops being possible at all. The split that does scale:
 *
 * - **this profile** answers "what did the agent's model usage cost?" in Cost Explorer, natively;
 * - **the application ledger** answers "which tenant drove it?", from `tenant_id` and the four token
 *   counters it already records per turn.
 *
 * Neither half answers the question alone, which is the same shape as every other cost dimension here
 * here: AWS attributes cost to a *resource*, never to a request.
 *
 * **Deliberately not a tenant dimension**, therefore. A profile per tier or environment is the useful
 * granularity; per-tenant belongs in the ledger.
 */
export class ModelAttribution extends Construct {
  public readonly profile: bedrock.CfnApplicationInferenceProfile;
  /** ARN the agent invokes in place of the model id. */
  public readonly profileArn: string;
  /** Foundation-model ARN the runtime role must also be granted. */
  public readonly foundationModelArn: string;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    const stack = Stack.of(this);

    this.profile = new bedrock.CfnApplicationInferenceProfile(this, 'AgentModel', {
      inferenceProfileName: `${stack.stackName.toLowerCase()}-agent`,
      modelSource: {
        // The system-defined global profile, by ARN. A bare model id is rejected here.
        copyFrom: `arn:aws:bedrock:${stack.region}:${stack.account}:inference-profile/${MODEL_ID}`,
      },
      // `component: agent` matches the tag the runtime itself carries, so model spend and compute
      // spend land in the same Cost Explorer group. That is the point of one vocabulary across both
      // stacks — the vocabulary itself is in `multi-tenant-travel-stack.ts`.
      tags: [
        { key: 'project', value: 'multi-tenant-travel' },
        { key: 'component', value: 'agent' },
        // Must match `bin/infra.ts`: this profile is tagged directly rather than by the app-level
        // aspect, so a divergence here silently splits model spend from the rest of the sample's.
        { key: 'sample', value: 'multi-tenant-travel-assistant' },
      ],
    });

    this.profileArn = this.profile.attrInferenceProfileArn;
    this.foundationModelArn = `arn:aws:bedrock:${stack.region}::foundation-model/${FOUNDATION_MODEL}`;

    /**
     * Published rather than passed, because the agent lives in the AgentCore CLI's own CDK app and
     * cannot reference this construct. Same reason the guardrail id travels this way — and the same
     * benefit: the agent resolves it at runtime, so a hand-copied ARN cannot go stale.
     */
    new ssm.StringParameter(this, 'ProfileArnParam', {
      parameterName: MODEL_PROFILE_PARAM,
      stringValue: this.profileArn,
      description: 'Application inference profile the agent invokes — carries the cost tags',
    });

    new CfnOutput(this, 'InferenceProfileArn', {
      value: this.profileArn,
      description: 'Invoke this instead of the model id, so model spend is attributable',
    });
  }
}
