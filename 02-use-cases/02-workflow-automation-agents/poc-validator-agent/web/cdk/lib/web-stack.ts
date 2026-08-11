import * as path from 'path';
import { CfnOutput, Duration, RemovalPolicy, Stack, StackProps, Tags } from 'aws-cdk-lib';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

export interface PocValidatorWebStackProps extends StackProps {
  /** ARN of the already-deployed AgentCore Runtime (managed by agentcore/cdk, not this stack). */
  readonly agentRuntimeArn: string;
  /** Basic-Auth credential the CloudFront Function checks against, as "user:pass" base64. */
  readonly basicAuthCredentialBase64: string;
  /** Shared secret the browser sends on POST /api/invoke; validated inside the Lambda. */
  readonly demoKey: string;
  /**
   * The distribution's own public URL (e.g. "https://d1234.cloudfront.net"),
   * needed by the Lambda for CORS and for building share_url links back to
   * itself. Unknowable on a true first deploy — leave undefined, deploy once,
   * read the DistributionDomainName output, then redeploy passing it. This
   * two-phase dance is inherent to any CloudFront-fronts-its-own-Lambda
   * setup; trying to wire it as a same-stack reference creates a circular
   * CloudFormation dependency (Distribution needs the Function URL as an
   * origin; Lambda would need the Distribution's domain name).
   */
  readonly publicBaseUrl?: string;
}

/**
 * The web layer in front of the poc-validator-agent AgentCore Runtime:
 * a static page (S3 + CloudFront), a Lambda proxy for running the agent and
 * serving view-limited shared results, and the DynamoDB table backing the
 * 3-view / 30-day share cap.
 *
 * This stack defines every resource as CDK would create it fresh. The
 * equivalent resources already exist by hand in the account (built
 * incrementally, verified at each step) — see web/cdk/README.md for the
 * `cdk import` path to adopt them instead of standing up duplicates.
 */
export class PocValidatorWebStack extends Stack {
  constructor(scope: Construct, id: string, props: PocValidatorWebStackProps) {
    super(scope, id, props);

    // ---- Storage: the static page/share-shell bucket ----------------------
    const siteBucket = new s3.Bucket(this, 'SiteBucket', {
      bucketName: `poc-validator-agentcore-demo-${this.account}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: RemovalPolicy.RETAIN,
      lifecycleRules: [
        {
          id: 'expire-shared-results-30d',
          enabled: true,
          prefix: 'share/',
          tagFilters: { AutoExpire: 'true' },
          expiration: Duration.days(30),
        },
      ],
    });

    // ---- View-count table for the 3-view share cap -------------------------
    const viewsTable = new dynamodb.Table(this, 'ShareViewsTable', {
      tableName: 'poc-validator-share-views',
      partitionKey: { name: 'share_id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      timeToLiveAttribute: 'ttl',
      removalPolicy: RemovalPolicy.RETAIN,
    });

    // ---- Lambda: invokes the agent, serves view-limited share reads -------
    const webInvokeFn = new lambda.Function(this, 'WebInvokeFunction', {
      functionName: 'poc-validator-web-invoke',
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'handler.handler',
      // Ships its own boto3/botocore rather than relying on the runtime's
      // bundled version, which may predate the bedrock-agentcore service.
      code: lambda.Code.fromAsset(path.join(__dirname, '..', '..', '..', 'lambda'), {
        bundling: {
          // Prefer a plain host `pip install` (same command used to build the
          // real, deployed package by hand) over Docker-based bundling — the
          // Docker image pull for lambda.Runtime bundlingImage has been a
          // real source of friction/hangs on this machine. Docker bundling
          // is kept as the fallback for a CI/fresh-machine deploy where the
          // host may not have a matching Python available.
          image: lambda.Runtime.PYTHON_3_13.bundlingImage,
          command: ['bash', '-c', 'pip install -r requirements.txt -t /asset-output && cp handler.py /asset-output/'],
          local: {
            tryBundle(outputDir: string): boolean {
              const { execFileSync } = require('child_process');
              const src = path.join(__dirname, '..', '..', '..', 'lambda');
              try {
                execFileSync('pip3', ['install', '--quiet', '-r', path.join(src, 'requirements.txt'), '-t', outputDir]);
                execFileSync('cp', [path.join(src, 'handler.py'), outputDir]);
                return true;
              } catch {
                return false; // falls back to Docker bundling above
              }
            },
          },
        },
      }),
      timeout: Duration.minutes(5),
      memorySize: 512,
      environment: {
        AGENT_RUNTIME_ARN: props.agentRuntimeArn,
        DEMO_KEY: props.demoKey,
        RESULTS_BUCKET: siteBucket.bucketName,
        VIEWS_TABLE: viewsTable.tableName,
        // See publicBaseUrl doc comment: unknowable on a first deploy without
        // creating a circular dependency on the Distribution below.
        ALLOWED_ORIGIN: props.publicBaseUrl ?? '*',
        PUBLIC_BASE_URL: props.publicBaseUrl ?? '',
      },
    });

    // Deliberately explicit rather than the L2 grant*() convenience methods:
    // those grant broader action sets (List*, DeleteItem, Scan, Query, ...)
    // than this Lambda ever calls. This lists exactly the actions verified
    // against the live, hand-built role — matching the real security
    // posture is worth more here than the convenience.
    webInvokeFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['bedrock-agentcore:InvokeAgentRuntime'],
        resources: [props.agentRuntimeArn, `${props.agentRuntimeArn}/runtime-endpoint/*`],
      })
    );
    webInvokeFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['s3:PutObject', 's3:PutObjectTagging', 's3:GetObject'],
        resources: [siteBucket.arnForObjects('share/*')],
      })
    );
    webInvokeFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['dynamodb:PutItem', 'dynamodb:UpdateItem', 'dynamodb:GetItem'],
        resources: [viewsTable.tableArn],
      })
    );

    const webInvokeFnUrl = webInvokeFn.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.AWS_IAM,
      cors: {
        allowedOrigins: ['*'], // effectively same-origin once behind CloudFront; not the real gate
        allowedMethods: [lambda.HttpMethod.GET, lambda.HttpMethod.POST],
        allowedHeaders: ['content-type', 'x-demo-key'],
      },
    });

    // ---- Basic Auth at the edge --------------------------------------------
    const basicAuthFn = new cloudfront.Function(this, 'BasicAuthFunction', {
      functionName: 'poc-validator-basic-auth',
      runtime: cloudfront.FunctionRuntime.JS_2_0,
      code: cloudfront.FunctionCode.fromInline(`
function handler(event) {
    var request = event.request;
    var headers = request.headers;
    var expected = "Basic ${props.basicAuthCredentialBase64}";
    if (!headers.authorization || headers.authorization.value !== expected) {
        return {
            statusCode: 401,
            statusDescription: "Unauthorized",
            headers: { "www-authenticate": { value: 'Basic realm="POC Validator demo"' } },
        };
    }
    delete headers.authorization;
    return request;
}
`),
    });

    // ---- CloudFront: one distribution, two origins, three ordered routes --
    const s3Origin = origins.S3BucketOrigin.withOriginAccessControl(siteBucket);
    const lambdaOrigin = origins.FunctionUrlOrigin.withOriginAccessControl(webInvokeFnUrl);

    const distribution = new cloudfront.Distribution(this, 'Distribution', {
      comment: 'poc-validator-agentcore-demo HTTPS front',
      defaultBehavior: {
        origin: s3Origin,
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        functionAssociations: [{ function: basicAuthFn, eventType: cloudfront.FunctionEventType.VIEWER_REQUEST }],
      },
      defaultRootObject: 'index.html',
      additionalBehaviors: {
        // Order matters within this object only insofar as CDK preserves
        // insertion order in the synthesized template's CacheBehaviors list;
        // /share/*.json must precede /share/* so view-counted reads never
        // fall through to a raw, uncounted S3 fetch.
        '/share/*.json': {
          origin: lambdaOrigin,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
        },
        '/api/invoke': {
          origin: lambdaOrigin,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
          functionAssociations: [{ function: basicAuthFn, eventType: cloudfront.FunctionEventType.VIEWER_REQUEST }],
        },
        '/share/*': {
          origin: s3Origin,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        },
      },
    });

    // CDK's FunctionUrlOrigin.withOriginAccessControl() grants only
    // lambda:InvokeFunctionUrl. As of the "Dual Auth" requirement Lambda
    // rolled out for Function URLs, CloudFront also needs plain
    // lambda:InvokeFunction on the same principal/condition, or every
    // request 403s with the generic "Forbidden" Function-URL-auth error —
    // hit this for real on this stack's first deploy. See
    // https://github.com/aws/aws-cdk/issues/35872 (still open as of writing).
    webInvokeFn.addPermission('AllowCloudFrontInvokeFunction', {
      principal: new iam.ServicePrincipal('cloudfront.amazonaws.com'),
      action: 'lambda:InvokeFunction',
      sourceArn: `arn:aws:cloudfront::${this.account}:distribution/${distribution.distributionId}`,
    });

    new CfnOutput(this, 'DistributionDomainName', {
      value: distribution.distributionDomainName,
      description:
        'Redeploy this stack passing this value (as https://<this>) via publicBaseUrl ' +
        "if it doesn't already match what the Lambda has for ALLOWED_ORIGIN/PUBLIC_BASE_URL.",
    });

    Tags.of(this).add('project', 'poc-validator-agent');
    Tags.of(this).add('layer', 'web');
  }
}
