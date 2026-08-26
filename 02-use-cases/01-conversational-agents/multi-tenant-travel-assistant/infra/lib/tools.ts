import { CfnOutput, Duration, RemovalPolicy, Stack } from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';
import * as path from 'path';
import { lockedRequirement } from './locked-requirement';
import { piiMaskingPolicy } from './log-masking';

/** Repo root, independent of whether this runs from source or `dist/`. */
const REPO_ROOT = path.resolve(__dirname, __dirname.includes('dist') ? '../../..' : '../..');

export interface ToolsProps {
  /** Base URL of the mock TMC API the tools call over HTTP. */
  readonly backendApiUrl: string;
  /** Knowledge base the retrieval tool queries, with a per-tenant filter. */
  readonly knowledgeBaseId: string;
  readonly knowledgeBaseArn: string;

  /**
   * The private network to run in. Omit for the public arrangement.
   *
   * Every tool family is attached, including the two that never call the backend — `location` needs
   * the geo endpoints and `knowledge` needs `bedrock-agent-runtime`, and leaving either outside
   * would mean two Lambdas on a different network from the other eight for no stated reason.
   */
  readonly network?: {
    readonly vpc: ec2.IVpc;
    readonly subnets: ec2.SubnetSelection;
    readonly securityGroup: ec2.ISecurityGroup;
  };
}

/**
 * Tool Lambdas — the Gateway's targets.
 *
 * **One Lambda per tool family, not per tool.** A family shares a backend client, a
 * response contract and a dispatch loop, so splitting per tool would multiply cold
 * starts and deployment surface for nothing. The Gateway passes the tool name in the
 * Lambda client context, which is how one function serves several tools.
 *
 * **Not containerized, unlike the agent.** A tool fix is a Lambda deploy; an agent fix
 * is an image rebuild. Different blast radius, and worth stating in the README.
 *
 * **Invocable only by the Gateway.** That resource policy is what makes header-injected
 * identity trustworthy: a request that arrives came from the Gateway, and the Gateway
 * forwards only what the interceptor produced. It is also why no KMS-signed assertion
 * is needed — signing would defend against a compromised Gateway, which is outside the
 * threat model and costs a KMS call per request.
 */
export class Tools extends Construct {
  /** Family name → function, so the Gateway construct can reference ARNs. */
  public readonly functions: Record<string, lambda.Function>;

  /** Held rather than threaded through every `toolFamily` call — it is the same for all ten. */
  private readonly network?: ToolsProps['network'];

  constructor(scope: Construct, id: string, props: ToolsProps) {
    super(scope, id);

    this.network = props.network;

    const policy = this.toolFamily('Policy', 'policy', props.backendApiUrl);
    // Profile is where PII curation is demonstrated: the backend returns passport numbers
    // and card digits, and this family is what withholds them from the model.
    const profile = this.toolFamily('Profile', 'profile', props.backendApiUrl);

    // Retrieval is the one family that talks to Bedrock rather than the mock TMC.
    const knowledge = this.toolFamily('Knowledge', 'knowledge', props.backendApiUrl, {
      KNOWLEDGE_BASE_ID: props.knowledgeBaseId,
    });
    knowledge.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['bedrock:Retrieve'],
        resources: [props.knowledgeBaseArn],
      }),
    );

    // The context resolver other tools depend on: its place fields feed the location tools.
    const trips = this.toolFamily('Trips', 'trips', props.backendApiUrl);

    // Search annotates every option against the caller's own policy, server-side.
    const search = this.toolFamily('Search', 'search', props.backendApiUrl);

    // The write path. Same bundle shape as the read tools — the difference that matters is in the
    // handler (two-stage cancellation, tenant booking mode, no auto-booking), not in the infra.
    const booking = this.toolFamily('Booking', 'booking', props.backendApiUrl);

    // Visa rules. Reads the passport country server-side from the profile.
    const entry = this.toolFamily('Entry', 'entry', props.backendApiUrl);

    // **The one family that calls a service other than the mock TMC or Bedrock.** Amazon Location
    // Service's standalone namespaces need no place index or route calculator resource, so this is
    // an IAM grant rather than infrastructure — which is why there is no `geo` construct anywhere.
    const location = this.toolFamily('Location', 'location', props.backendApiUrl);
    location.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          'geo-places:Geocode',
          'geo-places:SearchText',
          'geo-places:SearchNearby',
          'geo-places:Suggest',
          'geo-routes:CalculateRoutes',
        ],
        // These APIs are account-level rather than resource-scoped: there is no ARN to name, so a
        // wildcard is the only expressible form. Stated rather than left looking careless.
        resources: ['*'],
      }),
    );

    // The handoff. Deliberately has no Connect permissions yet: without a configured queue the tool
    // logs its context package and returns a queued card, which keeps the sample deployable by a
    // reader with no Connect instance. Adding `connect:StartTaskContact` here is the one change
    // needed to make the transfer real.
    const escalation = this.toolFamily('Escalation', 'escalation', props.backendApiUrl);

    this.functions = {
      policy,
      profile,
      knowledge,
      trips,
      search,
      booking,
      entry,
      location,
      escalation,
    };

    // The tools read this rather than receiving it as a deploy-time constant, so a
    // backend redeploy that changes the URL does not require rebuilding every tool.
    // SSM rather than a CFN export: exports lock, and removing a reference to an
    // in-use export deadlocks the deploy.
    new ssm.StringParameter(this, 'BackendApiUrlParam', {
      parameterName: '/multi-tenant-travel/backend/api-url',
      stringValue: props.backendApiUrl,
      description: 'Base URL of the mock TMC API — read by tool Lambdas',
    });

    for (const [family, fn] of Object.entries(this.functions)) {
      new CfnOutput(this, `${family}ToolArn`, {
        value: fn.functionArn,
        description: `Gateway target ARN for the ${family} tool family`,
      });
    }
  }

  /**
   * One tool family's Lambda.
   *
   * Packaged from the repo root so `tools.common` resolves as a package the way it does
   * locally — bundling only `tools/<family>/` would break the shared imports that keep
   * the tenant check in one place.
   */
  private toolFamily(
    id: string,
    family: string,
    backendApiUrl: string,
    extraEnvironment: Record<string, string> = {},
  ): lambda.Function {
    const stackName = Stack.of(this).stackName;

    return new lambda.Function(this, id, {
      functionName: `${stackName}-tool-${family}`,
      runtime: lambda.Runtime.PYTHON_3_14,
      // Must match the bundling image's architecture, and ARM is cheaper per
      // millisecond. A mismatch surfaces only at runtime, as an import error.
      architecture: lambda.Architecture.ARM_64,
      handler: `tools.${family}.handler.handler`,
      code: lambda.Code.fromAsset(REPO_ROOT, {
        bundling: {
          image: lambda.Runtime.PYTHON_3_14.bundlingImage,
          command: [
            'bash',
            '-c',
            [
              // Powertools is the only dependency — the backend is reached with
              // `urllib` precisely so this install stays small on a path a user waits on.
              //
              // **Pinned, and pinned from the lockfile rather than from a number typed here.** An
              // unpinned install means the artifact deployed is not the artifact tested, and a
              // breaking upstream release breaks a reader's clone months later with nothing in this
              // repo having changed — which matters more for a sample than for a product, because a
              // sample is cloned long after it is written. Reading `tools/uv.lock` keeps one source
              // of truth: `uv lock` updates flow through, and there is no second place to forget.
              `pip install --no-cache-dir ${lockedRequirement('tools/uv.lock', 'aws-lambda-powertools')} -t /asset-output`,
              'mkdir -p /asset-output/tools',
              'cp -r tools/common /asset-output/tools/',
              `cp -r tools/${family} /asset-output/tools/`,
              // The card contract. Bundled because tools *construct* cards, and the shape must come
              // from the same file the frontend's TypeScript types are generated from — a tool
              // carrying its own copy of a card shape is how a renderer ends up with a tile it
              // cannot draw, silently. Flat `shared/` so the import path matches the repo layout.
              'cp -r shared /asset-output/',
              'touch /asset-output/tools/__init__.py',
              'find /asset-output -name "__pycache__" -type d -exec rm -rf {} + || true',
              'find /asset-output -name "test_*.py" -delete || true',
            ].join(' && '),
          ],
        },
        // **Everything the bundling command does not copy, because the asset hash decides whether
        // nine containers run.** The source has to be the repo root — `tools/` and `shared/` are
        // siblings and both are needed — so anything left in scope contributes to the hash, and a
        // change to it rebundles all nine functions on the next deploy.
        //
        // Measured before this list was completed: adding one file under `scripts/`, which no tool
        // imports, changed all nine hashes. `.ruff_cache` was in scope too, so *running the linter*
        // was enough to invalidate every bundle.
        //
        // Kept as a denylist rather than inverted to `['*', '!tools/**', '!shared/**']`: negation
        // depends on `ignoreMode`, and a silently empty asset is a worse failure than a stale entry
        // here. The two directories that must stay out of it are `tools` and `shared`.
        exclude: [
          'agent',
          'backend',
          'conversation-api',
          'docs',
          'evaluation',
          'frontend',
          'infra',
          'scripts',
          '*.md',
          '*.sh',
          '.docs',
          '.git',
          '.gitignore',
          '.pytest_cache',
          '.ruff_cache',
          '.vscode',
          'node_modules',
          '**/.venv',
          '**/__pycache__',
          '**/cdk.out',
        ],
      }),
      // Small: one HTTP call and some field selection. Memory here buys CPU for JSON
      // parsing, not much else.
      memorySize: 256,
      // Under the Gateway's own patience, so a hung backend surfaces as a tool refusal
      // inside the conversation rather than as a transport error the model cannot explain.
      timeout: Duration.seconds(15),
      environment: {
        POWERTOOLS_SERVICE_NAME: `multi-tenant-travel-tool-${family}`,
        POWERTOOLS_LOG_LEVEL: 'INFO',
        BACKEND_API_URL: backendApiUrl,
        ...extraEnvironment,
      },
      // In the VPC when one is supplied. **The URL above does not change**: a private REST API keeps
      // its hostname, and the `execute-api` endpoint's wildcard private DNS resolves it to the ENI.
      // That is the property that made this migration a two-line change here rather than a redeploy
      // of ten functions with new environment values.
      vpc: this.network?.vpc,
      vpcSubnets: this.network?.subnets,
      securityGroups: this.network ? [this.network.securityGroup] : undefined,
      // `logGroup` rather than the deprecated `logRetention`, which provisions a
      // custom-resource Lambda per function — noise in a sample people read.
      // Tool logs are diagnostic; CloudTrail is the authoritative audit record.
      logGroup: new logs.LogGroup(this, `${id}LogGroup`, {
        logGroupName: `/aws/lambda/${stackName}-tool-${family}`,
        retention: logs.RetentionDays.TWO_WEEKS,
        removalPolicy: RemovalPolicy.DESTROY,
        // Backstop against PII reaching a diagnostic line. These tools deliberately curate PII
        // out of their responses, so in normal operation there is nothing here to mask — which
        // is exactly the point: this covers the mistakes and the third-party output curation
        // cannot reach. Opaque ids stay unmasked, so debuggability survives.
        dataProtectionPolicy: piiMaskingPolicy(),
      }),
    });
  }

  /**
   * Restrict invocation to the Gateway's execution role.
   *
   * Called after the Gateway exists, because the trust anchor is *that* role rather
   * than the service principal alone: `bedrock-agentcore.amazonaws.com` would admit
   * any gateway in any account, and this permission is what the tools' trust in
   * injected identity headers rests on.
   */
  public grantInvokeToGateway(roleArn: string): void {
    for (const fn of Object.values(this.functions)) {
      fn.addPermission('InvokeFromGateway', {
        principal: new iam.ArnPrincipal(roleArn),
        action: 'lambda:InvokeFunction',
      });
    }
  }
}
