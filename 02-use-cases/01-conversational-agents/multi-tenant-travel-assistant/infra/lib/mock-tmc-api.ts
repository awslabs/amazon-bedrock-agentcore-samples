import { CfnOutput, Duration, RemovalPolicy, Stack } from 'aws-cdk-lib';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';
import { piiMaskingPolicy } from './log-masking';
import * as path from 'path';

/** Repo root, independent of whether this runs from source or `dist/`. */
const REPO_ROOT = path.resolve(__dirname, __dirname.includes('dist') ? '../../..' : '../..');

export interface MockTmcApiProps {
  readonly tables: Record<string, dynamodb.Table>;
  readonly tablePrefix: string;
  readonly policyDocsBucket: s3.Bucket;

  /**
   * The private network to run in, and the endpoint that may reach the API.
   *
   * Optional so this construct still synthesises without a VPC — a reader who wants the public
   * arrangement (or is debugging without paying for endpoints) omits it and gets the public shape
   * back. Supplying it makes both the function and the API private together, which has to be atomic:
   * a private API with a non-VPC Lambda would still work, but a VPC Lambda calling a public API
   * would have no route to it.
   */
  readonly network?: {
    readonly vpc: ec2.IVpc;
    readonly subnets: ec2.SubnetSelection;
    readonly securityGroup: ec2.ISecurityGroup;
    readonly executeApiEndpoint: ec2.IInterfaceVpcEndpoint;
  };
}

/**
 * The mock TMC API: FastAPI on Lambda behind API Gateway.
 *
 * **Private when a `network` is supplied, public otherwise.** Tools were built and proven against a
 * reachable endpoint first, because debugging VPC networking and tool logic simultaneously is how a
 * build stalls. That ordering paid off exactly as intended: going private changed this construct and
 * nothing above it — no tool's `BACKEND_API_URL` changes, because a private REST API keeps its
 * hostname and the `execute-api` endpoint's wildcard DNS resolves it inside the VPC.
 *
 * **The API is converted in place rather than replaced.** `endpointTypes` is a mutable property on a
 * REST API (edge-optimized → private is a supported transition), so the api id survives — which
 * matters because that id appears in every tool's environment and in
 * `/multi-tenant-travel/backend/api-url`. Recreating it would have been a coordinated redeploy of ten functions.
 *
 * This is the stack a reader deletes. It stands in for the travel platform a
 * TMC already runs, so nothing in the agent or tool layers imports from it —
 * they call it over HTTP, exactly as they would call a real one.
 */
export class MockTmcApi extends Construct {
  /**
   * The stage name, exposed because an endpoint policy has to name it in the ARN it scopes to.
   *
   * A `static` constant rather than a hardcoded `'v1'` in two files: the stage appears in the API's
   * URL and in the resource ARN of anything restricting access to it, and those two drifting apart
   * produces an endpoint that refuses the traffic it exists to carry.
   */
  public static readonly STAGE = 'v1';

  public readonly api: apigw.RestApi;
  /** Exposed so the tenant-scoped data role can name it as the only allowed assumer. */
  public readonly handler: lambda.Function;

  constructor(scope: Construct, id: string, props: MockTmcApiProps) {
    super(scope, id);

    const stackName = Stack.of(this).stackName;

    this.handler = new lambda.Function(this, 'MockTmcApi', {
      functionName: `${stackName}-mock-tmc`,
      runtime: lambda.Runtime.PYTHON_3_14,
      // Must match the bundling image's architecture. The Docker image builds
      // aarch64 wheels, and a function left on the x86_64 default fails at
      // `import pydantic_core._pydantic_core` — a native-extension mismatch that
      // only surfaces at runtime, never at synth or deploy. ARM is also cheaper
      // per millisecond, so it is the right default anyway.
      architecture: lambda.Architecture.ARM_64,
      handler: 'lambda_handler.handler',
      // Resolved from the repo root, not `__dirname`: compiled output lives in
      // `dist/lib/`, so a relative walk from there points at the wrong place.
      code: lambda.Code.fromAsset(path.join(REPO_ROOT, 'backend'), {
        // Dependencies must be installed *into* the bundle — `fromAsset` alone
        // copies source and would ship a package that fails at `import fastapi`.
        //
        // `--platform manylinux2014_aarch64 --only-binary :all:` is not optional:
        // pydantic-core ships a compiled wheel, and a macOS build silently
        // produces a package that raises on import inside Lambda.
        bundling: {
          image: lambda.Runtime.PYTHON_3_14.bundlingImage,
          command: [
            'bash',
            '-c',
            [
              'pip install --no-cache-dir -r requirements-lambda.txt -t /asset-output',
              'cp -r app generator seed lambda_handler.py /asset-output/',
              'find /asset-output -name "__pycache__" -type d -exec rm -rf {} + || true',
            ].join(' && '),
          ],
        },
        exclude: [
          'tests',
          '.venv',
          '__pycache__',
          '**/__pycache__',
          '*.pyc',
          '.pytest_cache',
          '.ruff_cache',
          'README.md',
        ],
      }),
      // Deterministic generation is CPU-bound, not IO-bound: more memory buys
      // proportionally more CPU, and 512MB keeps a search comfortably inside the
      // latency a conversation tolerates.
      memorySize: 512,
      timeout: Duration.seconds(29), // API Gateway caps at 29s
      environment: {
        POWERTOOLS_SERVICE_NAME: 'mock-tmc',
        TABLE_PREFIX: props.tablePrefix,
        POLICY_DOCS_BUCKET: props.policyDocsBucket.bucketName,
      },
      // Attaching a Lambda to a VPC is two properties and one consequence: an ENI per concurrent
      // execution, drawn from these subnets. The subnets are `PRIVATE_ISOLATED`, so this function
      // has no route to the internet — every AWS call it makes goes through an endpoint or fails.
      // `sts` and the two gateway endpoints are what keep it working.
      vpc: props.network?.vpc,
      vpcSubnets: props.network?.subnets,
      securityGroups: props.network ? [props.network.securityGroup] : undefined,
    });

    // **PII masking on the backend's log group — the one that matters most.**
    //
    // This is the system of record: it legitimately returns passport numbers, loyalty numbers and
    // card digits, because curating them is the *tool* layer's job, not the backend's. So it is
    // the one component where PII could plausibly reach a log line, and where an ingestion-time
    // mask guards a real path rather than an empty one.
    //
    // Applied to the group **CDK already created for this function** rather than declaring a new
    // one. A fresh `LogGroup` with the same name fails validation ("already exists") while
    // orphaning the original — the logical id is what CloudFormation matches on, not the name.
    // Reaching through to the L1 attaches the policy with no id change and no replacement.
    const mockTmcLogGroup = this.handler.logGroup.node.defaultChild as logs.CfnLogGroup | undefined;
    if (mockTmcLogGroup) {
      mockTmcLogGroup.dataProtectionPolicy = piiMaskingPolicy()._bind(this);
    }

    // Least privilege per table, not a wildcard — but deliberately still broad *across
    // tenants*, and that is the point worth understanding.
    //
    // The request path does not use this grant: the backend assumes
    // `TenantIsolation`'s role per request with a tenant session tag, whose
    // `dynamodb:LeadingKeys` condition pins access to that tenant's partitions. What remains
    // here serves the seed script and local runs where `TENANT_DATA_ROLE_ARN` is unset.
    //
    // It also *has* to stay cross-tenant: the backend serves every tenant, so its own role must
    // be able to reach every partition, and narrowing per request is what bounds the blast
    // radius of a bug. That residual trust in a pooled service is the standard multi-tenant SaaS
    // boundary rather than anything agent-specific — see `lib/tenant-isolation.ts`.
    for (const table of Object.values(props.tables)) {
      table.grantReadWriteData(this.handler);
    }
    props.policyDocsBucket.grantRead(this.handler);

    this.api = new apigw.LambdaRestApi(this, 'MockTmcRestApi', {
      restApiName: `${stackName}-api`,
      description: 'Mock TMC API — replace with your real travel platform',
      handler: this.handler,
      proxy: true,
      /**
       * **`AWS_IAM`, because without it every control in this sample is bypassable.**
       *
       * This API trusts `X-Tenant-Id` — it has to, because the gateway interceptor is what
       * establishes tenant identity by overwriting that header from a verified token. Left
       * unauthenticated and public, anyone could send the header themselves: `curl` with no headers
       * was `401`, and `curl -H "X-Tenant-Id: globex"` was `200` with full profile PII. Cedar, the
       * interceptor, session-tagged STS and `dynamodb:LeadingKeys` all sit *in front of* this API, so
       * reaching it directly walks around the entire thing.
       *
       * **What this does and does not change.** It does not make the header trustworthy. It makes the
       * *caller* trustworthy, which turns the header from attacker-controlled input into an internal
       * contract between components we control. The layering to hold in your head: **the interceptor
       * decides which tenant; IAM decides who is allowed to assert one.**
       *
       * Applied to every method including `/health`, rather than carving out an unauthenticated
       * resource for it. A `{proxy+}` catch-all is one method, so an exemption means a second
       * resource and a second thing to keep correct — and "is the backend up?" is a question for
       * something holding credentials anyway.
       */
      defaultMethodOptions: { authorizationType: apigw.AuthorizationType.IAM },
      deployOptions: {
        stageName: MockTmcApi.STAGE,
        // Tracing and metrics because the cost story needs the request-level picture, not just
        // aggregate latency.
        tracingEnabled: true,
        metricsEnabled: true,
        /**
         * **Access logs and execution logs, which an earlier comment here claimed were already on and
         * were not.** `cdk-nag` caught the discrepancy (`AwsSolutions-APIG1`/`APIG6`) — a reminder
         * that a comment asserting a property is not the same as the property.
         *
         * `INFO` rather than `ERROR` for execution logging: this API is a stand-in for a travel
         * platform, and the interesting failures are 4xx refusals that `ERROR` would not record.
         * `dataTraceEnabled` is deliberately **off** — it logs full request and response bodies, and
         * this API legitimately returns passport numbers and card digits.
         */
        accessLogDestination: new apigw.LogGroupLogDestination(
          new logs.LogGroup(this, 'MockTmcAccessLogs', {
            logGroupName: `/aws/apigateway/${stackName}-api`,
            retention: logs.RetentionDays.TWO_WEEKS,
            removalPolicy: RemovalPolicy.DESTROY,
          }),
        ),
        accessLogFormat: apigw.AccessLogFormat.clf(),
        loggingLevel: apigw.MethodLoggingLevel.INFO,
        dataTraceEnabled: false,
      },
      ...(props.network
        ? {
            endpointConfiguration: {
              types: [apigw.EndpointType.PRIVATE],
              vpcEndpoints: [props.network.executeApiEndpoint],
            },
            /**
             * **A private API without a resource policy is unreachable, not merely private.**
             *
             * This is the one part of going private that is not a flag. A `PRIVATE` endpoint type
             * removes the public route; it does not grant anyone the private one. With no policy the
             * API denies everything — including the endpoint it is attached to — and the symptom is
             * a `403` with `"User: anonymous is not authorized"`, which reads like an auth
             * misconfiguration rather than a missing policy.
             *
             * The condition is what does the work: `aws:SourceVpce` pins access to *our* endpoint,
             * so `Principal: '*'` is not the wildcard it appears to be. Anyone in another account
             * with their own endpoint is still refused. Naming the endpoint rather than the VPC is
             * the tighter of the two forms and costs nothing extra.
             */
            policy: new iam.PolicyDocument({
              statements: [
                new iam.PolicyStatement({
                  principals: [new iam.AnyPrincipal()],
                  actions: ['execute-api:Invoke'],
                  resources: ['execute-api:/*'],
                  conditions: {
                    StringEquals: {
                      'aws:SourceVpce': props.network.executeApiEndpoint.vpcEndpointId,
                    },
                  },
                }),
              ],
            }),
          }
        : {}),
    });

    new CfnOutput(this, 'MockTmcApiUrl', {
      value: this.api.url,
      description: 'Base URL of the mock TMC API',
    });
  }
}
