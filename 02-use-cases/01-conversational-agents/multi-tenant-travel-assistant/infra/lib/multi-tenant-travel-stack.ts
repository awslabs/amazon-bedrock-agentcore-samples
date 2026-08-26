import { Stack, StackProps, Tags } from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import { Audit } from './audit';
import { ConversationApi } from './conversation-api';
import { EdgeProtection } from './edge-protection';
import { FrontendHosting } from './frontend-hosting';
import { Guardrails } from './guardrails';
import { Identity } from './identity';
import { Knowledge } from './knowledge';
import { RequestInterceptor } from './interceptor';
import { ModelAttribution } from './model-attribution';
import { MockTmcApi } from './mock-tmc-api';
import { applyNagSuppressions } from './nag-suppressions';
import { Network } from './network';
import { Storage } from './storage';
import { TenantIsolation } from './tenant-isolation';
import { Tools } from './tools';

export interface MultiTenantTravelStackProps extends StackProps {
  /**
   * **No `runtimeArn` or `memoryId` — removed, because they were a silent-failure mechanism.**
   *
   * Both belong to the AgentCore CLI's stack, which deploys after this one, so they arrived as
   * environment variables of the `cdk deploy` command. A redeploy from a shell that had not exported
   * them replaced a working value with an **empty string**: the stack updated successfully, the
   * deploy log was clean, and the next traveller received a `404 <UnknownOperationException/>` from
   * AgentCore — an error naming neither the ARN nor this deployment. A second deploy in a fresh
   * terminal was enough to break the product.
   *
   * The conversation API resolves both from Parameter Store at cold start instead, which is where
   * every other cross-stack value here already lives, and which no `cdk deploy` can overwrite.
   * `scripts/publish_agent_refs.py` writes them from the agent stack's own outputs, so there is no
   * step for a human to forget.
   */

  /**
   * Origin the SPA is served from — the single allowed CORS origin and the CSRF check's value.
   *
   * Defaults to the Vite dev server, so the API is usable before any hosting exists.
   */
  readonly frontendOrigin?: string;

  /**
   * Whether to run the capability and data layers inside a private VPC.
   *
   * **Opt-in rather than the default, and the reason is money.** Nine interface endpoints across two
   * AZs is ~$161/month standing, whether or not anyone uses the agent — against a default deploy whose
   * only standing charge is a ~$1/month KMS key, everything else being pay-per-request. That is two
   * orders of magnitude, and it accrues idle. A reader cloning this to try it
   * should not discover that by receiving an invoice, so the private topology is a deliberate switch
   * with the cost stated in the README's Cost section, working shown.
   *
   * `TRAVEL_PRIVATE=true` turns it on. Everything works either way — the tools call the backend over
   * HTTP at the same URL in both arrangements.
   */
  readonly private?: boolean;
  /**
   * Whether to put a WAF web ACL in front of the distribution.
   *
   * **Opt-in for the same reason `private` is, and it was inconsistent not to be.** The ACL plus its
   * five rules is ~$10/month standing and was the only standing cost in a default deploy — so the
   * argument written above for the VPC applied here and was not being followed.
   *
   * Safe to default off because the ACL is not the tenancy boundary: it is volumetric and
   * signature-based, and authorisation is Cognito's claims, the interceptor, Cedar and
   * `dynamodb:LeadingKeys`. What is lost is rate limiting and managed rule sets, which matter for a
   * URL shared publicly and not for a dev deploy. API Gateway throttling stays on regardless.
   *
   * `TRAVEL_WAF=true` turns it on, and it is recommended before publishing the demo URL broadly.
   */
  readonly waf?: boolean;
}

/**
 * Everything the AgentCore CLI does not own.
 *
 * **One stack, several constructs.** An earlier split into Data and Backend
 * stacks produced a cross-stack export, and removing a reference to an in-use
 * export deadlocks the deploy: CloudFormation refuses to delete the export while
 * a consumer still imports it, so the consumer must be updated first. Since both
 * halves always deploy and destroy together, the boundary bought nothing and
 * generated that failure mode for free.
 *
 * If a genuine lifecycle difference appears later — tables that should survive a
 * teardown, say — split it then and pass values through SSM parameters rather
 * than CloudFormation exports, which do not lock.
 */
export class MultiTenantTravelStack extends Stack {
  public readonly storage: Storage;
  public readonly api: MockTmcApi;
  public readonly identity: Identity;
  public readonly tools: Tools;
  public readonly tenantIsolation: TenantIsolation;
  public readonly knowledge: Knowledge;
  public readonly guardrails: Guardrails;
  public readonly audit: Audit;
  public readonly interceptor: RequestInterceptor;
  public readonly conversationApi: ConversationApi;
  public readonly frontend: FrontendHosting;
  public readonly modelAttribution: ModelAttribution;
  /** Present only when deployed with `--waf` — see `MultiTenantTravelStackProps.waf`. */
  public readonly edgeProtection?: EdgeProtection;
  /** Present only when deployed private — see `MultiTenantTravelStackProps.private`. */
  public readonly network?: Network;

  constructor(scope: Construct, id: string, props?: MultiTenantTravelStackProps) {
    super(scope, id, props);

    this.storage = new Storage(this, 'Storage');

    /**
     * **First, because everything private depends on it — and absent entirely when public.**
     *
     * Not created-then-unused when `private` is false: an unused VPC is free, but nine unused
     * interface endpoints are ~$161/month, and a construct that provisions expensive resources
     * "just in case the flag flips" is how a sample earns a reputation. The conditional is at the
     * construct boundary so the cost and the code appear or disappear together.
     */
    this.network = props?.private ? new Network(this, 'Network') : undefined;

    this.api = new MockTmcApi(this, 'MockTmc', {
      tables: this.storage.tables,
      tablePrefix: this.storage.tablePrefix,
      policyDocsBucket: this.storage.policyDocsBucket,
      network: this.network && {
        vpc: this.network.vpc,
        subnets: this.network.subnets,
        securityGroup: this.network.securityGroup,
        executeApiEndpoint: this.network.endpoints.executeApi,
      },
    });

    // Independent of the two above: nothing in the mock TMC knows about Cognito,
    // because the backend is a stand-in for a platform that predates the
    // assistant. It trusts a tenant header; establishing *who* the caller is
    // happens above it, at the Runtime and interceptor boundary.
    this.identity = new Identity(this, 'Identity');

    // Row-level isolation for the backend's own data access. Conventional pooled-SaaS
    // practice, wired into an agent stack. See `tenant-isolation.ts` for why this is *not* the
    // prompt-injection defence — Cedar and the interceptor are.
    this.tenantIsolation = new TenantIsolation(this, 'TenantIsolation', {
      tables: this.storage.tables,
      assumedBy: this.api.handler.role!,
    });
    this.api.handler.addEnvironment('TENANT_DATA_ROLE_ARN', this.tenantIsolation.dataRole.roleArn);

    // Policy prose the structured record cannot hold, isolated by a per-tenant metadata
    // filter on every retrieval rather than a knowledge base per tenant.
    this.knowledge = new Knowledge(this, 'Knowledge', {
      documentsBucket: this.storage.policyDocsBucket,
    });

    // The authoritative audit record. Every other component logs its own behaviour, which is
    // diagnostic rather than evidential — an application that is wrong about what it did is wrong
    // in its logs too. CloudTrail is written by AWS, so it answers "what actually happened" for
    // someone who does not take our word for it.
    this.audit = new Audit(this, 'Audit', { logBucket: this.storage.logBucket });

    // The content plane, and independent of everything above it: harmful input, PII masked
    // on output. A backstop rather than a primary control — the tool layer already curates
    // PII away — and deliberately *not* a tenancy control. See the construct for why it is
    // attached to the model rather than to the gateway: only one of those two placements can
    // still see the traveller's own phrasing.
    this.guardrails = new Guardrails(this, 'Guardrails');

    // Makes model spend attributable at all: an on-demand invocation of a raw model id carries no
    // tags, so tokens — the expensive half of the bill — were anonymous while the infrastructure was
    // tagged to the component. See the construct for why this is per deployment, not per tenant.
    this.modelAttribution = new ModelAttribution(this, 'ModelAttribution');

    // The agent-facing capability layer. Calls the mock TMC over HTTP — never imports
    // its code — so `backend/` stays the folder a reader deletes and replaces.
    this.tools = new Tools(this, 'Tools', {
      backendApiUrl: this.api.api.url,
      knowledgeBaseId: this.knowledge.knowledgeBase.attrKnowledgeBaseId,
      knowledgeBaseArn: this.knowledge.knowledgeBase.attrKnowledgeBaseArn,
      network: this.network && {
        vpc: this.network.vpc,
        subnets: this.network.subnets,
        securityGroup: this.network.securityGroup,
      },
    });

    /**
     * **Who is allowed to call the backend at all.** The API is `AWS_IAM`-authorized
     * (`mock-tmc-api.ts`), so a request without a valid SigV4 signature has no principal and is
     * refused before the handler runs. This is the other half: the principals that *may* sign.
     *
     * **Granted here rather than as a resource policy on the API, because the alternative is a
     * cycle.** `MockTmcApi` is constructed before `Tools` — the tool functions need its URL as an
     * environment variable — so the API cannot name roles that do not exist yet. An identity grant
     * points the other way: the role references the API's ARN, which does exist. Same outcome, and
     * it is the standard shape for same-account callers; a resource policy earns its place when the
     * caller is in another account, which is not this.
     *
     * Scoped to `execute-api:Invoke` on this API's paths, not `*`. A tool that should only read
     * policy still gets the whole surface here — the per-tool boundary is Cedar at the gateway and
     * the tenant session tag on the way into DynamoDB, not this grant.
     */
    // **Built by hand rather than with `arnForExecuteApi()`, for a cdk-nag reason worth recording.**
    // The helper formats the ARN through `Stack.formatArn`, which leaves the partition as a token —
    // so the `IAM5` finding reads `arn:<AWS::Partition>:execute-api:...`, and an `appliesTo`
    // suppression cannot match a finding whose partition is unresolved. Every other hand-written
    // wildcard suppression in `nag-suppressions.ts` already spells `arn:aws:` for the same reason.
    const backendInvokeArn = `arn:aws:execute-api:${this.region}:${this.account}:${this.api.api.restApiId}/*/*/*`;
    for (const fn of Object.values(this.tools.functions)) {
      fn.addToRolePolicy(
        new iam.PolicyStatement({
          actions: ['execute-api:Invoke'],
          resources: [backendInvokeArn],
        }),
      );
    }

    // Verifies the traveller's JWT at the edge and injects tenant context. The gateway
    // attachment happens post-deploy (`scripts/configure-gateway.py`) because
    // interceptors are absent from the CLI's schema.
    this.interceptor = new RequestInterceptor(this, 'Interceptor', {
      userPoolId: this.identity.userPool.userPoolId,
      allowedClientIds: [
        this.identity.cliClient.userPoolClientId,
        this.identity.appClient.userPoolClientId,
      ],
    });

    /**
     * **The SPA and the API must share one origin, and arranging that is what this ordering is for.**
     *
     * The distribution serves the bundle *and* forwards `/v1/*` to the API Gateway stage. Necessary
     * rather than neat: the session cookie is `SameSite=Strict`, so a cookie set on
     * `execute-api.amazonaws.com` is never sent from the CloudFront origin — the login appears to
     * succeed and every request after it is unauthenticated. Only a real browser shows this; `curl`
     * has no same-site policy, so the flow passed every scripted check first.
     *
     * The two constructs therefore each need something from the other, which CloudFormation would
     * reject as a cycle. It is broken by passing **strings, not constructs**: the API is built first
     * and exposes a hostname composed from its own id (independent of the stage and the function),
     * and its allowed origin is then set from the distribution's domain. Neither references the
     * other's resources, so there is no cycle to resolve.
     */
    this.conversationApi = new ConversationApi(this, 'ConversationApi', {
      webClientId: this.identity.appClient.userPoolClientId,
      hostedUiDomain: this.identity.domain.baseUrl(),
      policyDocsBucket: this.storage.policyDocsBucket,
    });

    // Rate limiting and managed rules at the edge, when asked for. Built before the distribution
    // because the distribution takes the ACL's ARN; the ACL itself references nothing.
    //
    // **Not created when off, rather than created and unattached.** An unattached ACL still bills
    // per ACL and per rule, so building it either way would keep the cost this switch exists to
    // remove.
    this.edgeProtection = props?.waf ? new EdgeProtection(this, 'EdgeProtection') : undefined;

    this.frontend = new FrontendHosting(this, 'Frontend', {
      apiDomainName: this.conversationApi.domainName,
      apiStage: ConversationApi.STAGE,
      // `undefined` when the WAF is off, which `FrontendHosting` already accepts: the
      // distribution is simply created without an ACL.
      webAclArn: this.edgeProtection?.webAcl.attrArn,
      logBucket: this.storage.logBucket,
    });

    // **The distribution first, then the dev server.** Both are allowed so `npm run dev` works
    // against the deployed API without a second deployment; the order matters because the first
    // entry is where the OAuth callback lands, and that has to be the real site.
    this.conversationApi.allowOrigins(
      props?.frontendOrigin ?? `${this.frontend.origin},http://localhost:5173`,
    );

    this.restrictEndpoints();

    // Cognito must be told about both destinations before it will redirect to either, and neither URL
    // is knowable inside `Identity` — hence the calls rather than props. Both are on the site's
    // origin now: the callback is forwarded to the API by CloudFront, which is what lets the
    // `Set-Cookie` in its response be same-site with the SPA.
    this.identity.addCallbackUrl(this.conversationApi.oauthRedirectUri);
    this.identity.addLogoutUrl(this.frontend.origin);

    /**
     * **`component` is the tag that makes cost answerable**, because it is the one that varies.
     *
     * Applied per construct rather than per resource: a construct is already the unit a reader
     * reasons about ("what does retrieval cost?"), and tagging inside each one would put the
     * vocabulary in eight files instead of this list. `Tags.of(construct)` propagates to every
     * resource beneath it.
     *
     * The values are chosen to answer questions someone actually asks of a bill — *which layer is
     * expensive*, not which AWS service. `knowledge` spans S3 Vectors, a bucket and Bedrock
     * retrieval; `tools` spans nine Lambdas and their log groups. Grouping by service would split
     * both and answer neither.
     *
     * **No `tenant` tag anywhere, and that is the design rather than an omission.** Every resource
     * here is pooled — one table serves all customers, one Lambda answers for all of them — so a
     * tenant tag would be false on the majority of them. Per-tenant cost comes from the application
     * ledger, which records `tenant_id` per turn. Both halves are needed because neither answers the
     * whole question: tags say *what* the money was spent on, the ledger says *who* drove it.
     */
    const components: Array<[Construct, string]> = [
      [this.storage, 'storage'],
      [this.api, 'backend'],
      [this.identity, 'identity'],
      [this.tenantIsolation, 'identity'],
      [this.knowledge, 'knowledge'],
      [this.audit, 'audit'],
      [this.guardrails, 'guardrails'],
      [this.modelAttribution, 'agent'],
      [this.tools, 'tools'],
      [this.interceptor, 'gateway'],
      [this.conversationApi, 'conversation-api'],
      [this.frontend, 'frontend'],
    ];
    // Its own value rather than folding into `frontend`: WAF is billed per ACL, per rule and per
    // million requests, so it is a line item a reader will want to see separately from hosting —
    // when it exists at all.
    if (this.edgeProtection) {
      components.push([this.edgeProtection, 'edge-protection']);
    }
    for (const [construct, component] of components) {
      Tags.of(construct).add('component', component);
    }

    /**
     * cdk-nag suppressions, applied last because several name resource paths built above.
     *
     * In its own file rather than scattered as inline annotations: the suppression list *is* the
     * security-review artifact, and a reviewer should be able to read every accepted finding and its
     * argument in one place instead of hunting through eight constructs. See `nag-suppressions.ts`,
     * which also records which findings were **fixed** rather than accepted — the more useful half.
     */
    applyNagSuppressions(this, this.storage.logBucket);
  }

  /**
   * Narrow each interface endpoint to the calls that legitimately cross it.
   *
   * **The endpoints are worth paying for because of this method, not in spite of it.** An interface
   * endpoint with no policy defaults to `*` on `*` — a private route to the *entire* service. That
   * buys "traffic stays off the internet", which is worth something, and skips the more valuable
   * property: this VPC can reach only these specific things. With a policy, two independent controls
   * must fail before a compromised tool Lambda touches an unrelated resource — its execution role,
   * and the network path itself.
   *
   * Written per service, because a shared "allow the obvious actions" policy applied in a loop would
   * be theatre: the right restriction for `sts` (one role) has nothing in common with the right one
   * for `bedrock-runtime` (one inference profile).
   *
   * Called after the constructs exist, since several statements name ARNs those constructs own.
   *
   * **The three AgentCore endpoints are narrowed by `scripts/restrict_agentcore_endpoints.py`, not
   * here.** Their resources — the runtime, the memory, the gateway — belong to the AgentCore CLI's
   * stack, which deploys *after* this one, so there is no ARN to name at synth time. That is a
   * *sequencing* constraint rather than an impossibility, and the sample already has the tool for it:
   * the same post-deploy pattern `publish_agent_refs.py` uses. Leaving them at the `*`-on-`*` default
   * would have been the one place a control was applied everywhere except three resources.
   */
  private restrictEndpoints(): void {
    const network = this.network;
    if (!network) return;

    /**
     * API Gateway invocations from this account's APIs, and nothing else.
     *
     * **Scoped by account rather than to the backend's specific ARN, because naming it is a
     * CloudFormation cycle.** The private API references this endpoint's id (in
     * `EndpointConfiguration.VpcEndpointIds`), so an endpoint policy naming the API's ARN makes each
     * resource depend on the other. CloudFormation rejects the whole changeset — and it names twenty
     * resources in the error, because the tool Lambdas sit in the middle of the loop, which makes it
     * look like a much bigger problem than it is.
     *
     * The specific fence exists anyway, on the other side: the API's **own** resource policy
     * conditions `execute-api:Invoke` on `aws:SourceVpce` being this endpoint. That is the tighter of
     * the two directions — it is what stops anything outside the VPC reaching the backend. What is
     * given up is only the reverse: this VPC could reach *another* private API in the same account,
     * if one existed and its own policy allowed us. Worth stating plainly rather than implying the
     * restriction is as narrow as the others here.
     */
    network.restrictEndpoint('executeApi', [
      new iam.PolicyStatement({
        principals: [new iam.AnyPrincipal()],
        actions: ['execute-api:Invoke'],
        resources: [`arn:aws:execute-api:${this.region}:${this.account}:*/*`],
      }),
    ]);

    /**
     * `AssumeRole` **and `TagSession`**, on exactly one role.
     *
     * This is the tightest and most valuable of the set. The backend's whole tenant-isolation story
     * is that it assumes a session-tagged role per request; an endpoint that permitted `AssumeRole`
     * on any role would let a bug in that path reach for a wider one. Naming the role means the
     * network refuses what the code should never ask for.
     *
     * **`sts:TagSession` is a separate action from `sts:AssumeRole`, and omitting it was a real
     * outage** — the first thing this deployment got wrong. A tagged `AssumeRole` is authorized
     * against *both*, so an endpoint policy granting only `AssumeRole` denies every call the backend
     * makes. And because tenant isolation runs on **every request**, the whole backend returned 500
     * while the deploy, the endpoints and the routing were all healthy.
     *
     * Worth keeping as the cautionary example for endpoint policies generally: the failure was not
     * "the network is misconfigured", it was "the network is configured to refuse the one call this
     * system is built around", and it surfaced three layers away as a tool saying it couldn't reach
     * the travel system. `Tags`/`TransitiveTagKeys` in a call means `TagSession` in the policy.
     */
    network.restrictEndpoint('sts', [
      new iam.PolicyStatement({
        principals: [new iam.AnyPrincipal()],
        actions: ['sts:AssumeRole', 'sts:TagSession'],
        resources: [this.tenantIsolation.dataRole.roleArn],
      }),
    ]);

    /**
     * Retrieval from our knowledge base only.
     *
     * `bedrock:Retrieve` is the sole action the knowledge tool performs. Notably *not* including
     * `RetrieveAndGenerate`, which would invoke a model — the agent owns model invocation, and a tool
     * quietly generating text would bypass the guardrail and the ledger.
     */
    network.restrictEndpoint('bedrockAgentRuntime', [
      new iam.PolicyStatement({
        principals: [new iam.AnyPrincipal()],
        actions: ['bedrock:Retrieve'],
        resources: [this.knowledge.knowledgeBase.attrKnowledgeBaseArn],
      }),
    ]);

    /**
     * Model inference through the tagged inference profile, plus the foundation models it fronts.
     *
     * **Both ARNs are required and that is not obvious.** Invoking an application inference profile
     * authorizes against the profile *and* the underlying model — so a policy naming only the profile
     * fails with an `AccessDenied` that names the model, which reads like the profile was ignored.
     *
     * **`InvokeModel` is the right action even though Strands calls `Converse`.** Verified rather than
     * assumed: `strands/models/bedrock.py` calls `converse`/`converse_stream`, while the agent's own
     * working IAM policy grants only `InvokeModel`/`InvokeModelWithResponseStream` — so Converse
     * authorizes against those. A policy listing `bedrock:Converse` would deny every turn.
     *
     * **The foundation-model ARN must not pin a region.** The model id is `global.anthropic…`, a
     * cross-region profile whose underlying model ARNs carry *other* regions — so
     * `arn:aws:bedrock:us-east-1::foundation-model/*` would refuse the very model this agent runs on.
     * The account-scoped wildcard is what remains expressible; the meaningful restriction here is the
     * action and the inference-profile ARN, not the model region.
     */
    network.restrictEndpoint('bedrockRuntime', [
      new iam.PolicyStatement({
        principals: [new iam.AnyPrincipal()],
        actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
        resources: [
          this.modelAttribution.profileArn,
          'arn:aws:bedrock:*::foundation-model/*',
          `arn:aws:bedrock:*:${this.account}:inference-profile/*`,
          `arn:aws:bedrock:*:${this.account}:application-inference-profile/*`,
        ],
      }),
      /**
       * **The guardrail crosses this same endpoint, and forgetting it would disable the content
       * control silently.** `ApplyGuardrail` is a `bedrock-runtime` operation, so an endpoint policy
       * covering only the two invoke actions denies it — and the agent treats an unavailable
       * guardrail as non-fatal by design, so the result is a working, *unguarded* agent. Exactly the
       * failure the `ssm` endpoint exists to prevent, arriving by a second route.
       */
      new iam.PolicyStatement({
        principals: [new iam.AnyPrincipal()],
        actions: ['bedrock:ApplyGuardrail'],
        resources: [`arn:aws:bedrock:${this.region}:${this.account}:guardrail/*`],
      }),
    ]);

    /**
     * Amazon Location: the five read operations the location tool calls, and no writes.
     *
     * These APIs are account-level with no resource ARN to name — the same reason the tool's IAM
     * grant uses `*`. So the restriction here is by *action*, which is the only axis available:
     * geocoding and routing yes, anything that could create or track a resource no.
     */
    network.restrictEndpoint('geoPlaces', [
      new iam.PolicyStatement({
        principals: [new iam.AnyPrincipal()],
        actions: [
          'geo-places:Geocode',
          'geo-places:SearchText',
          'geo-places:SearchNearby',
          'geo-places:Suggest',
        ],
        resources: ['*'],
      }),
    ]);
    network.restrictEndpoint('geoRoutes', [
      new iam.PolicyStatement({
        principals: [new iam.AnyPrincipal()],
        actions: ['geo-routes:CalculateRoutes'],
        resources: ['*'],
      }),
    ]);

    /**
     * Read-only, and only under this sample's parameter prefix.
     *
     * `GetParameter`/`GetParameters` but no `PutParameter`: the agent consumes configuration that CDK
     * owns, and a write would mean the runtime could change the guardrail version it then reads. The
     * prefix scope matters in a shared account — an agent that can read `/multi-tenant-travel/*` and nothing else
     * cannot be walked into someone's unrelated database password.
     */
    network.restrictEndpoint('ssm', [
      new iam.PolicyStatement({
        principals: [new iam.AnyPrincipal()],
        actions: ['ssm:GetParameter', 'ssm:GetParameters'],
        resources: [`arn:aws:ssm:${this.region}:${this.account}:parameter/multi-tenant-travel/*`],
      }),
    ]);

    /**
     * Write-only, into this account's log groups.
     *
     * **Added because `verify_network.py` check E caught this endpoint carrying no policy at all.** It
     * was created for the AgentCore Runtime's log delivery — `network.ts` explains why a container in
     * our subnets needs what fifteen VPC Lambdas do not — and then left wide open, which is exactly the
     * gap that check exists to find. The lesson belongs to the check rather than the endpoint: a new
     * endpoint is not finished when traffic starts flowing through it.
     *
     * `PutLogEvents` plus the two `Create*` calls a first write needs, and deliberately no `Describe*`,
     * `FilterLogEvents` or `GetLogEvents`. The runtime's business here is emitting its own logs, not
     * reading anyone's, and that asymmetry is the point — log delivery must not double as a channel for
     * reading back what else in the account has logged.
     *
     * Scoped to this account's log groups rather than the runtime's own, because that group is created
     * by the AgentCore CLI's stack and naming it here is the same cross-stack ordering problem
     * `restrict_agentcore_endpoints.py` exists to solve. So: an account-level fence, not a per-group
     * one, and worth saying rather than implying it is as narrow as the others above.
     */
    network.restrictEndpoint('logs', [
      new iam.PolicyStatement({
        principals: [new iam.AnyPrincipal()],
        actions: ['logs:PutLogEvents', 'logs:CreateLogStream', 'logs:CreateLogGroup'],
        resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:*`],
      }),
    ]);
  }
}
