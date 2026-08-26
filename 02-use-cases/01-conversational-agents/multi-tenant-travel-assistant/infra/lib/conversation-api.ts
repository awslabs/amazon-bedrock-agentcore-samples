import { CfnOutput, Duration, RemovalPolicy, Stack } from 'aws-cdk-lib';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';
import * as path from 'path';
import { lockedRequirement } from './locked-requirement';
import { piiMaskingPolicy } from './log-masking';

/** Repo root, independent of whether this runs from source or `dist/`. */
const REPO_ROOT = path.resolve(__dirname, __dirname.includes('dist') ? '../../..' : '../..');

/** Stage name, needed to compose the callback URL before the stage itself exists. */
const STAGE = 'v1';

/**
 * Lambda Web Adapter, `us-east-1`.
 *
 * **ARM64, and the architecture must match the function's.** The published examples almost all use
 * `LambdaAdapterLayerX86`; pasting that ARN onto an ARM function produces a layer that does not
 * run, and the failure surfaces as an init timeout rather than as an architecture error.
 *
 * Pinned by version because a layer ARN *is* a version — there is no "latest" to float to, which is
 * the right property for something on the request path.
 */
const LWA_LAYER_ARN = 'arn:aws:lambda:us-east-1:753240598075:layer:LambdaAdapterLayerArm64:28';

export interface ConversationApiProps {
  /** Web client — no secret, PKCE. The BFF drives the code exchange server-side. */
  readonly webClientId: string;
  /** Hosted UI base URL, e.g. `https://multi-tenant-travel-<account>.auth.us-east-1.amazoncognito.com`. */
  readonly hostedUiDomain: string;
  /** Policy documents, presigned on click after the tenant re-check. */
  readonly policyDocsBucket: s3.Bucket;

  /**
   * **The runtime ARN and memory id are deliberately *not* props.**
   *
   * Both belong to the AgentCore CLI's own stack, which deploys after this one — so they can be
   * neither CloudFormation references nor synth-time constants. They used to be threaded through
   * here from `TRAVEL_RUNTIME_ARN` / `TRAVEL_MEMORY_ID`, which meant a redeploy from a shell
   * missing those variables wrote an **empty string over a working configuration**, with no deploy
   * error and a `404` from AgentCore on the next turn.
   *
   * The function resolves both from Parameter Store instead (`app/agent_refs.py`), written by
   * `scripts/publish_agent_refs.py` from the agent stack's outputs. Removing the props is the fix:
   * a value that cannot be passed in cannot be passed in wrong.
   */
}

/**
 * The conversation API — the browser's only entrance.
 *
 * **A BFF rather than a browser talking to AgentCore directly**, because the alternative puts a
 * Cognito token somewhere JavaScript can read it. Here the browser holds an opaque session id in an
 * httpOnly cookie and the tokens live in DynamoDB, so an XSS bug in the SPA finds nothing to steal.
 *
 * **Two streaming hops, and one alone fails silently.** `responseTransferMode: STREAM` on the
 * integration and `AWS_LWA_INVOKE_MODE=response_stream` on the function. With only one configured
 * the response still arrives — as a single flush, with no error logged anywhere. Which is why the
 * verification asserts chunk-arrival *spread* rather than that a response came back.
 *
 * **API Gateway rather than a Function URL.** Both are streaming front doors and you need exactly
 * one; API Gateway brings throttling, WAF and a custom domain later. Most Lambda Web Adapter
 * examples use a Function URL because it is the shortest demo path, which is why
 * `responseTransferMode` is easy to miss — it is the API Gateway equivalent of
 * `InvokeMode: RESPONSE_STREAM`.
 */
export class ConversationApi extends Construct {
  public readonly api: apigw.RestApi;
  public readonly handler: lambda.Function;
  public readonly sessionTable: dynamodb.Table;
  /** Seals the OAuth tokens in the session row — see the construction site for why. */
  public readonly sessionKey: kms.Key;
  /**
   * The Cognito callback URL, set by `allowOrigins`.
   *
   * Not known at construction: it lives on the *site's* origin, which is the CloudFront distribution
   * built after this. See `allowOrigins` for why it cannot be the API Gateway host.
   */
  public oauthRedirectUri = '';
  /** Hostname of the API Gateway stage — what the CloudFront behaviour forwards to. */
  public readonly domainName: string;
  /** Stage name, which is also the path prefix CloudFront routes here. */
  public static readonly STAGE = STAGE;

  constructor(scope: Construct, id: string, props: ConversationApiProps) {
    super(scope, id);

    const stack = Stack.of(this);
    const stackName = stack.stackName;

    /**
     * Seals the session's OAuth tokens before they are written.
     *
     * The table's default at-rest encryption is transparent to callers — anyone with
     * `dynamodb:GetItem` reads plaintext. Sealing means a reader needs `kms:Decrypt` on this key as
     * well, and every decrypt is a CloudTrail event. One over-broad IAM grant then leaks ciphertext
     * rather than live credentials for every signed-in traveller.
     */
    this.sessionKey = new kms.Key(this, 'SessionKey', {
      description: 'Seals OAuth tokens stored in the conversation API session table',
      enableKeyRotation: true,
      // Minimum window AWS allows. Destroying the key makes live sessions undecryptable — a
      // re-login for fixture users, data loss for anything real.
      removalPolicy: RemovalPolicy.DESTROY,
      pendingWindow: Duration.days(7),
    });

    // Sessions and pending logins share one table, distinguished by a `pending#` key prefix. Two
    // tables would mean two TTL configurations and two grants for one lifecycle — a login in
    // progress *is* a session that has not completed.
    this.sessionTable = new dynamodb.Table(this, 'Sessions', {
      tableName: `${stackName}-sessions`,
      partitionKey: { name: 'session_id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      // **TTL is the expiry mechanism, not a cleanup job.** An abandoned session disappears with
      // nothing scheduled. The application still treats a past-TTL row as absent, because
      // DynamoDB's deletion is eventual and a security check must not be.
      timeToLiveAttribute: 'expires_at',
      removalPolicy: RemovalPolicy.DESTROY,
    });

    // **Created before the function, and its *id* is what composes the callback URL.**
    // `api.url` resolves through the stage, which depends on the methods, which depend on the
    // function — so putting `api.url` in the function's environment is a CloudFormation cycle.
    // `restApiId` refers to the API resource alone, which nothing here depends on, so composing
    // the URL by hand is not a shortcut but the only acyclic form.
    this.api = new apigw.RestApi(this, 'ConversationRestApi', {
      restApiName: `${stackName}-conversation`,
      description: 'Conversation API — browser sessions and the SSE relay',
      deployOptions: {
        stageName: STAGE,
        tracingEnabled: true,
        metricsEnabled: true,
        /**
         * **The abuse ceiling that is always on, because the WAF is not.**
         *
         * The web ACL is opt-in (`--waf`) so a default deploy has no standing cost — which also means
         * a default deploy has no rate limiting, and this is the public surface: CloudFront forwards
         * `/v1/*` here. Free, unlike WAF, and it bounds the thing that actually hurts, which is not
         * request volume but *model spend*: every turn that reaches the agent costs tokens, so an
         * open loop against this endpoint is a bill rather than a slowdown.
         *
         * Generous on purpose. A turn is one POST that streams for ten to thirty seconds, so a demo
         * with a handful of people never approaches 20/s — and the eval suite, which is the heaviest
         * legitimate caller at 57 turns, runs them one at a time. The account default is 10,000/s;
         * this is three orders of magnitude below it, which is the point.
         *
         * **Not applied to the mock TMC**, deliberately. It is `AWS_IAM`-authorized and reachable
         * only by the tool roles, so who may call it is already bounded — and a turn legitimately
         * makes many parallel tool calls (15 in one step, measured), so a low ceiling there would
         * throttle correct behaviour rather than abuse.
         */
        throttlingRateLimit: 20,
        throttlingBurstLimit: 40,
        // Access and execution logging. **`dataTraceEnabled` stays off**, and on this API that is not
        // a preference: request bodies are traveller-authored prose and responses are the agent's
        // stream, so full-payload logging would put conversation content in CloudWatch — the one
        // thing `log-masking.ts` exists to keep out.
        accessLogDestination: new apigw.LogGroupLogDestination(
          new logs.LogGroup(this, 'ConversationAccessLogs', {
            logGroupName: `/aws/apigateway/${stackName}-conversation`,
            retention: logs.RetentionDays.TWO_WEEKS,
            removalPolicy: RemovalPolicy.DESTROY,
          }),
        ),
        accessLogFormat: apigw.AccessLogFormat.clf(),
        loggingLevel: apigw.MethodLoggingLevel.INFO,
        dataTraceEnabled: false,
      },
      // **CORS is answered by the application, not by `defaultCorsPreflightOptions`.** A MOCK
      // preflight integration cannot express what a credentialed request needs (a concrete origin
      // plus `Allow-Credentials: true`), and two places answering OPTIONS is how they come to
      // disagree.
    });

    // Composed from `restApiId` rather than read off `api.url`, which resolves through the *stage* —
    // a token that depends on the methods, which depend on the function. Using that here would be a
    // CloudFormation cycle rather than a convenience.
    this.domainName = `${this.api.restApiId}.execute-api.${stack.region}.${stack.urlSuffix}`;

    this.handler = new lambda.Function(this, 'ConversationApi', {
      functionName: `${stackName}-conversation-api`,
      runtime: lambda.Runtime.PYTHON_3_14,
      architecture: lambda.Architecture.ARM_64,
      // **The handler is a shell script**, which is how the Lambda Web Adapter works: the layer's
      // bootstrap wrapper runs it, and it starts an ordinary HTTP server the adapter proxies to.
      handler: 'run.sh',
      layers: [lambda.LayerVersion.fromLayerVersionArn(this, 'LwaLayer', LWA_LAYER_ARN)],
      code: lambda.Code.fromAsset(REPO_ROOT, {
        bundling: {
          image: lambda.Runtime.PYTHON_3_14.bundlingImage,
          command: [
            'bash',
            '-c',
            [
              // uvicorn and h11 only — both pure Python. **No FastAPI here on purpose**: its
              // pydantic-core dependency ships a compiled wheel, and this is a zip-packaged
              // function. boto3 comes from the Lambda runtime rather than the bundle.
              //
              // **Pinned from `conversation-api/uv.lock`**, which is the lock the local smoke test
              // (`app.test_local`, run by `./test.sh`) resolves against — so the server this Lambda
              // runs is the server the suite exercised. It was a bare `uvicorn`: whatever pip found
              // at bundling time, which means a reader cloning this months from now deploys a
              // version nobody tested, and `h11` comes along at whatever that resolves to. uvicorn
              // reads request bytes and drives the SSE relay, so a behaviour change there shows up
              // as a streaming bug with nothing in this repo having changed.
              `pip install --no-cache-dir ${lockedRequirement('conversation-api/uv.lock', 'uvicorn')} -t /asset-output`,
              'cp conversation-api/app/*.py /asset-output/',
              // `-p` preserves the exec bit. A non-executable handler script fails at init with
              // nothing in the error pointing at the file mode.
              'cp -p conversation-api/app/run.sh /asset-output/',
              // The card contract, for the closed action registry. Imported from the same file the
              // tools construct cards from, so a click this API accepts is a click a card could
              // actually have offered.
              'cp -r shared /asset-output/',
              'find /asset-output -name "__pycache__" -type d -exec rm -rf {} + || true',
              'find /asset-output -name "test_*.py" -delete || true',
            ].join(' && '),
          ],
        },
        exclude: [
          'backend',
          'agent',
          'infra',
          'frontend',
          'tools',
          'evaluation',
          '.docs',
          '.git',
          'node_modules',
          '**/.venv',
          '**/__pycache__',
          '**/cdk.out',
        ],
      }),
      // Generous, because what bounds this function is the *agent's* turn length: it stays alive
      // for as long as the stream it relays. The API Gateway 29-second limit does not apply once
      // streaming has begun — it bounds time-to-first-byte — so the function timeout is the real
      // cap on how long an answer may take.
      timeout: Duration.minutes(5),
      // Relaying bytes, not computing. Memory here buys the CPU that starts uvicorn quickly.
      memorySize: 512,
      environment: {
        // **Both of these activate the adapter, and both are required.** Without the wrapper the
        // handler never runs; without `response_stream` the adapter buffers, and the whole
        // streaming configuration silently does nothing.
        AWS_LAMBDA_EXEC_WRAPPER: '/opt/bootstrap',
        AWS_LWA_INVOKE_MODE: 'response_stream',
        PORT: '8000',
        SESSION_TABLE: this.sessionTable.tableName,
        SESSION_KMS_KEY_ID: this.sessionKey.keyId,
        COGNITO_CLIENT_ID: props.webClientId,
        COGNITO_DOMAIN: props.hostedUiDomain,
        POLICY_DOCS_BUCKET: props.policyDocsBucket.bucketName,
        // **No `RUNTIME_ARN` or `MEMORY_ID` here, deliberately.** Both belong to the AgentCore CLI's
        // stack, which deploys after this one, so they used to arrive as environment variables of the
        // `cdk deploy` command — and a redeploy from a shell that had not exported them wrote an
        // **empty string over a working value**. Nothing failed at deploy time; the next traveller
        // got a `404 <UnknownOperationException/>` from AgentCore, an error naming neither the ARN
        // nor this deployment.
        //
        // The function now resolves both from Parameter Store at cold start (`app/agent_refs.py`),
        // which no deploy can erase, and which is where every other cross-stack value in this sample
        // already lives. `scripts/publish_agent_refs.py` writes them from the agent stack's outputs.
        // An env var still overrides, for a local run against a specific runtime.
      },
      logGroup: new logs.LogGroup(this, 'ConversationApiLogGroup', {
        logGroupName: `/aws/lambda/${stackName}-conversation-api`,
        retention: logs.RetentionDays.TWO_WEEKS,
        removalPolicy: RemovalPolicy.DESTROY,
        // A backstop on the one log group whose traffic includes traveller-authored prose. This
        // function logs decisions and ids, never message content — so in normal operation there is
        // nothing here to mask, which is the point: it covers the mistake, not the designed path.
        dataProtectionPolicy: piiMaskingPolicy(),
      }),
    });

    this.sessionTable.grantReadWriteData(this.handler);
    // Not `grantEncryptDecrypt`, which adds `GenerateDataKey*` the function never calls.
    this.sessionKey.grant(this.handler, 'kms:Encrypt', 'kms:Decrypt');
    props.policyDocsBucket.grantRead(this.handler);

    /**
     * Read a past conversation's messages from AgentCore Memory.
     *
     * **`ListEvents` only — no write, and no long-term memory access.** The BFF reads transcripts to
     * render history; it never writes events (the agent owns that) and never touches the
     * `USER_PREFERENCE` records, which are the model's context rather than anything a browser should
     * see. Granting `RetrieveMemoryRecords` here would put a traveller's inferred preferences one
     * route away from being displayed, which is a product decision nobody has made.
     *
     * Per-traveller scoping is *not* IAM's job here and cannot be: `ListEvents` takes the actor as a
     * parameter, so any actor is reachable with this permission. The boundary is the ownership check
     * against the BFF's own conversation index, from verified session ids — see
     * `conversations.owns`.
     */
    /**
     * **Scoped to this account's memories rather than to one id, and that is now a deliberate
     * trade rather than a first-deploy placeholder.**
     *
     * The memory id is resolved at runtime from Parameter Store, so it is not knowable at synth time
     * — there is no specific ARN to name. What replaces it is the two controls that were doing the
     * real work anyway: the id comes from a parameter only a deploy can write, and per-traveller
     * scoping was never IAM's job here (`ListEvents` takes the actor as a parameter, so any actor is
     * reachable with this permission regardless of how the resource is scoped — the boundary is
     * `conversations.owns`).
     *
     * The alternative — keeping a synth-time id to narrow this — is what allowed a deploy to
     * overwrite a working configuration with an empty string. A slightly broader resource scope on a
     * read-only action is the cheaper of the two risks.
     */
    this.handler.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['bedrock-agentcore:ListEvents'],
        resources: [`arn:aws:bedrock-agentcore:${stack.region}:${stack.account}:memory/*`],
      }),
    );

    // The two parameters carrying the agent's identity across the stack boundary. Read-only, and
    // scoped to this sample's prefix rather than to the account's parameters.
    this.handler.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['ssm:GetParameter'],
        resources: [
          `arn:aws:ssm:${stack.region}:${stack.account}:parameter/multi-tenant-travel/agent/*`,
        ],
      }),
    );

    // **The runtime call is bearer-authorized and still needs this.** The token authorises the
    // *caller* to AgentCore; the SDK independently SigV4-signs the HTTP request, so this role needs
    // the data-plane action or the request never leaves. Both ARNs, because the endpoint qualifier
    // arrives as a suffix.
    //
    // Cognito's `GetUser` — the fail-closed check before each invoke — needs no IAM permission:
    // the access token is itself the credential.
    // Same reasoning as `ListEvents` above: the runtime ARN is resolved from Parameter Store at cold
    // start, so this is scoped to the account's own runtimes. A caller still cannot invoke one
    // without a traveller's bearer token, which the Runtime's own `CUSTOM_JWT` authorizer verifies —
    // this permission alone reaches nothing.
    this.handler.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['bedrock-agentcore:InvokeAgentRuntime'],
        resources: [
          `arn:aws:bedrock-agentcore:${stack.region}:${stack.account}:runtime/*`,
          `arn:aws:bedrock-agentcore:${stack.region}:${stack.account}:runtime/*/*`,
        ],
      }),
    );

    /**
     * **One streaming integration for every method, because the adapter's invoke mode is
     * function-wide.**
     *
     * `AWS_LWA_INVOKE_MODE=response_stream` is an environment variable, so it cannot vary per
     * method: the adapter emits a **streaming payload for every invocation** — a JSON metadata
     * prelude, eight NUL bytes, then the body. Verified by invoking the function directly:
     *
     *     {"statusCode":401,"headers":{…},"cookies":[]}\0\0\0\0\0\0\0\0{"error": "no session"}
     *
     * A BUFFERED integration expects plain proxy-response JSON and cannot parse that. So mixing the
     * modes against one function is not available; separating them would mean two *functions*
     * identical but for that variable — double the cold starts, two log groups, two bundles for one
     * service. Streaming a short JSON body costs nothing measurable, so every method rides the
     * streaming integration and the mode is consistent end to end.
     *
     * The reference material only ever puts `OPTIONS` on a buffered path, where a 204 with no body
     * hides the mismatch — which is why this is a step past what that documents.
     *
     * `LambdaIntegration` selects the streaming invocation URI
     * (`2021-11-15/…/response-streaming-invocations`) automatically from the transfer mode — but see
     * the permission below, because it does *not* select the matching IAM action.
     */
    const streaming = new apigw.LambdaIntegration(this.handler, {
      proxy: true,
      responseTransferMode: apigw.ResponseTransferMode.STREAM,
      // Well above the 29-second default. For a streaming integration that ceiling applies to
      // time-to-first-byte, so this bounds how long the agent may take to say its first word —
      // not how long the answer may be.
      timeout: Duration.minutes(5),
    });

    const conversation = this.api.root.addResource('conversation').addResource('{id}');
    for (const leaf of ['messages', 'actions']) {
      const resource = conversation.addResource(leaf);
      resource.addMethod('POST', streaming);
      // The credentialed preflight, answered by the application rather than by a MOCK integration:
      // a MOCK cannot express what a cookie-bearing request needs (a concrete origin plus
      // `Allow-Credentials: true`), and two places answering OPTIONS is how they come to disagree.
      resource.addMethod('OPTIONS', streaming);
    }

    const auth = this.api.root.addResource('auth');
    auth.addResource('login').addMethod('GET', streaming);
    auth.addResource('callback').addMethod('GET', streaming);
    auth.addResource('logout').addMethod('POST', streaming);
    auth.addResource('session').addMethod('GET', streaming);

    this.api.root.addResource('documents').addResource('{doc_id}').addMethod('GET', streaming);

    // The history sidebar: the traveller's past conversations, and one conversation's messages.
    //
    // **Plural `conversations`, distinct from the singular `conversation/{id}` above**, and the
    // difference is not cosmetic: that one *starts* a turn, this one *reads* what happened. Sharing a
    // path would mean one resource whose method mix decides whether a request spends a runtime
    // invoke, which is exactly the kind of thing to keep visibly separate.
    const history = this.api.root.addResource('conversations');
    history.addMethod('GET', streaming);
    history.addResource('{conversation_id}').addMethod('GET', streaming);

    // Not for the browser: the Lambda Web Adapter probes `GET /` before routing traffic, and a
    // stage with no root method answers 403 — which the adapter reads as a failed start.
    this.api.root.addMethod('GET', streaming);

    /**
     * **Force a new stage deployment whenever the transfer-mode assignment changes.**
     *
     * A REST stage serves a *deployment* — an immutable snapshot of the methods and integrations.
     * CDK decides whether one is needed from each integration's `deploymentToken`, and
     * `LambdaIntegration` computes that as `JSON.stringify({ functionName })` (see
     * `aws-apigateway/lib/integrations/lambda.js`). **`responseTransferMode` is not in it**, so
     * moving a method between STREAM and BUFFERED can update the integration without producing a
     * new deployment — a green `cdk deploy` that changes nothing at the stage.
     *
     * Salting the deployment's logical id with the assignment makes the snapshot move with it.
     * Update the value below when a method's mode changes.
     *
     * **Expect a minute or two of 502s after any such change even so.** API Gateway fronts REST
     * stages with CloudFront, which serves the previous mapping — including cached *error*
     * responses — while the change propagates. During this build that looked exactly like a broken
     * integration and sent the diagnosis down two wrong paths. Re-test after a pause before
     * concluding anything, and check `x-cache` on the response: `Error from cloudfront` on a route
     * whose Lambda log shows the correct status is propagation, not configuration.
     */
    this.api.latestDeployment?.addToLogicalId({
      transferModes: { STREAM: 'all methods' },
      routes: ['conversations', 'conversations/{conversation_id}'],
    });

    // **`LambdaIntegration` grants `lambda:InvokeFunction` and nothing else.** A streaming
    // integration needs `lambda:InvokeFunctionWithResponseStream`, and without it the symptom is a
    // 5xx with no useful message anywhere — indistinguishable from the invoke-mode mismatch
    // described above, which is why both are worth knowing about. Granted explicitly, scoped to
    // this API.
    this.handler.addPermission('ApiGatewayInvokeWithResponseStream', {
      principal: new iam.ServicePrincipal('apigateway.amazonaws.com'),
      action: 'lambda:InvokeFunctionWithResponseStream',
      sourceArn: this.api.arnForExecuteApi(),
    });

    // Published so the SPA build and the verification script read one value rather than each
    // hardcoding a stage URL that moves whenever the API is replaced.
    new ssm.StringParameter(this, 'ConversationApiUrlParam', {
      parameterName: '/multi-tenant-travel/conversation-api/url',
      stringValue: this.api.url,
      description: 'Base URL of the conversation API — read by the SPA build and by tests',
    });

    new CfnOutput(this, 'ConversationApiUrl', {
      value: this.api.url,
      description: "Conversation API base URL (the browser's only entrance)",
    });
  }

  /**
   * Name the origins the SPA is served from, and derive the OAuth callback from the first.
   *
   * **Called after the CloudFront distribution exists**, because that is the origin — and it has to
   * be, for a reason only a browser reveals. The session cookie is `SameSite=Strict`, so a cookie set
   * on `execute-api.amazonaws.com` is never sent on a request from the CloudFront origin: different
   * sites. The login completes, the cookie is stored, and every request afterwards is
   * unauthenticated. `curl` cannot reproduce it, having no same-site policy, so the whole flow passed
   * its scripted checks before a headless browser ran it.
   *
   * The callback therefore points at the *site*, on this API's stage path, which the distribution
   * forwards here unmodified — so the code is still exchanged server-side and the `Set-Cookie` that
   * establishes the session is same-site with the SPA.
   *
   * A setter rather than a prop because the distribution needs this API's hostname while this API
   * needs the distribution's domain. Passing strings in one direction and calling this in the other
   * keeps CloudFormation from seeing a cycle.
   */
  public allowOrigins(origins: string): void {
    const site = origins.split(',')[0].replace(/\/$/, '');
    this.oauthRedirectUri = `${site}/${STAGE}/auth/callback`;
    this.handler.addEnvironment('FRONTEND_ORIGIN', origins);
    this.handler.addEnvironment('OAUTH_REDIRECT_URI', this.oauthRedirectUri);

    new CfnOutput(this, 'OAuthRedirectUri', {
      value: this.oauthRedirectUri,
      description: 'Registered as a Cognito callback URL — the code is exchanged server-side',
    });
  }
}
