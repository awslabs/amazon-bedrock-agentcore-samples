import { CfnOutput, Duration, RemovalPolicy, Stack } from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';
import { piiMaskingPolicy } from './log-masking';
import * as path from 'path';

/** Repo root, independent of whether this runs from source or `dist/`. */
const REPO_ROOT = path.resolve(__dirname, __dirname.includes('dist') ? '../../..' : '../..');

export interface RequestInterceptorProps {
  readonly userPoolId: string;
  /** Client ids whose tokens this gateway accepts. */
  readonly allowedClientIds: string[];
}

/**
 * The Gateway request interceptor — the verifier for the whole tool layer.
 *
 * **Only the Lambda lives here.** Attaching it to the gateway is not in the CLI's
 * `agentcore.json` schema, so that step runs through `bedrock-agentcore-control` after
 * `agentcore deploy` (see `scripts/configure-gateway.py`). Splitting it this way keeps
 * the function under CDK — where its code, permissions and log retention belong —
 * without hand-editing CLI-generated CDK, which `AGENTS.md` forbids.
 *
 * It sits on the hot path of every tool call, so it carries no dependencies and caches
 * the JWKS across invocations.
 */
export class RequestInterceptor extends Construct {
  public readonly fn: lambda.Function;

  constructor(scope: Construct, id: string, props: RequestInterceptorProps) {
    super(scope, id);

    const stack = Stack.of(this);

    this.fn = new lambda.Function(this, 'Fn', {
      functionName: `${stack.stackName}-gateway-interceptor`,
      // Node for cold-start latency on the conversational path, and because
      // `node:crypto` verifies RS256 natively — no `jose`, no `aws-jwt-verify`.
      runtime: lambda.Runtime.NODEJS_24_X,
      architecture: lambda.Architecture.ARM_64,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(REPO_ROOT, 'infra/lambda/interceptor')),
      // Every tool call waits on this, so the budget is tight. The only network call is
      // a JWKS fetch, and only on a cold start or key rotation.
      timeout: Duration.seconds(10),
      memorySize: 512,
      environment: {
        USER_POOL_ID: props.userPoolId,
        COGNITO_REGION: stack.region,
        ALLOWED_CLIENT_IDS: props.allowedClientIds.join(','),
      },
      // These lines are a diagnostic authorization trail — CloudTrail is the authoritative
      // record — so they outlive a debugging session. `logGroup` rather than the
      // deprecated `logRetention`, which adds a custom-resource Lambda per function.
      logGroup: new logs.LogGroup(this, 'LogGroup', {
        logGroupName: `/aws/lambda/${stack.stackName}-gateway-interceptor`,
        retention: logs.RetentionDays.ONE_MONTH,
        removalPolicy: RemovalPolicy.DESTROY,
        // This function reads a JWT, so it is the one place a claim could reach a log line by
        // accident. It logs ids and scopes only — never the token, never a name — and this masks
        // what a future edit might add.
        dataProtectionPolicy: piiMaskingPolicy(),
      }),
    });

    // Invocable only by the gateway service. Narrowed to this account so another
    // account's gateway cannot drive our verifier.
    this.fn.addPermission('InvokeFromGateway', {
      principal: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
      action: 'lambda:InvokeFunction',
      sourceAccount: stack.account,
    });

    // Read by the post-deploy configuration script, so the ARN is never pasted by hand.
    new ssm.StringParameter(this, 'ArnParam', {
      parameterName: '/multi-tenant-travel/gateway/interceptor-arn',
      stringValue: this.fn.functionArn,
      description: 'Request interceptor Lambda — attached to the gateway post-deploy',
    });

    new CfnOutput(this, 'InterceptorArn', {
      value: this.fn.functionArn,
      description: 'Attach to the gateway with scripts/configure-gateway.py',
    });
  }
}
