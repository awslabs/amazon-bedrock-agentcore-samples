import * as cdk from "aws-cdk-lib";
import { Match, Template } from "aws-cdk-lib/assertions";
// Imported from the compiled output (`npm run build` must run first, same as
// `npm run cdk`/`agentcore deploy` do) rather than the TypeScript source.
// web-stack.ts resolves its Lambda asset directory relative to __dirname,
// matching the compiled dist/lib/ location it runs from in a real deploy —
// importing the .ts source directly under ts-jest resolves __dirname one
// level shallower (lib/ instead of dist/lib/) and points at a directory
// that doesn't exist, which is a test-environment artifact, not a bug in
// the deployed stack.
// eslint-disable-next-line @typescript-eslint/no-var-requires
const { PocValidatorWebStack } = require("../dist/lib/web-stack");

const RUNTIME_ARN =
  "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/TestRuntime-abc123";

function synth(props?: Partial<{ publicBaseUrl: string }>) {
  const app = new cdk.App();
  const stack = new PocValidatorWebStack(app, "TestWebStack", {
    agentRuntimeArn: RUNTIME_ARN,
    basicAuthCredentialBase64: "dGVzdDp0ZXN0", // "test:test"
    demoKey: "test-demo-key",
    publicBaseUrl: props?.publicBaseUrl,
  });
  return Template.fromStack(stack);
}

describe("PocValidatorWebStack", () => {
  test("synthesizes cleanly with and without publicBaseUrl", () => {
    expect(() => synth()).not.toThrow();
    expect(() => synth({ publicBaseUrl: "https://example.cloudfront.net" })).not.toThrow();
  });

  test("the results bucket blocks all public access and retains its 30-day share lifecycle rule", () => {
    const template = synth();
    template.hasResourceProperties("AWS::S3::Bucket", {
      PublicAccessBlockConfiguration: {
        BlockPublicAcls: true,
        BlockPublicPolicy: true,
        IgnorePublicAcls: true,
        RestrictPublicBuckets: true,
      },
      LifecycleConfiguration: {
        Rules: Match.arrayWith([
          Match.objectLike({
            ExpirationInDays: 30,
            Prefix: "share/",
            Status: "Enabled",
            TagFilters: [{ Key: "AutoExpire", Value: "true" }],
          }),
        ]),
      },
    });
  });

  test("the view-count table uses on-demand billing and a TTL attribute (not RCU/WCU provisioning)", () => {
    const template = synth();
    template.hasResourceProperties("AWS::DynamoDB::Table", {
      BillingMode: "PAY_PER_REQUEST",
      TimeToLiveSpecification: { AttributeName: "ttl", Enabled: true },
      KeySchema: [{ AttributeName: "share_id", KeyType: "HASH" }],
    });
  });

  test("the Lambda's IAM policy is scoped to specific actions and resources, never a wildcard", () => {
    const template = synth();
    const policies = template.findResources("AWS::IAM::Policy");
    const statements = Object.values(policies).flatMap(
      (p: any) => p.Properties.PolicyDocument.Statement,
    );

    // Every statement this stack authored must name its actions explicitly and
    // must not grant Resource: "*" — this is the property the CDK dual-auth
    // gap and the L2 grant*() convenience methods were both deliberately
    // avoided to preserve (see the comment above addToRolePolicy in
    // web-stack.ts).
    for (const statement of statements) {
      expect(statement.Action).not.toBe("*");
      if (Array.isArray(statement.Action)) {
        expect(statement.Action).not.toContain("*");
      }
      expect(statement.Resource).not.toBe("*");
    }

    expect(statements).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          Action: "bedrock-agentcore:InvokeAgentRuntime",
          Resource: [RUNTIME_ARN, `${RUNTIME_ARN}/runtime-endpoint/*`],
        }),
      ]),
    );
  });

  test("CloudFront grants the Lambda plain lambda:InvokeFunction, not just InvokeFunctionUrl (the dual-auth fix)", () => {
    // Regression test for the CDK dual-auth gap documented in web-stack.ts
    // and https://github.com/aws/aws-cdk/issues/35872 — FunctionUrlOrigin
    // .withOriginAccessControl() alone only grants lambda:InvokeFunctionUrl,
    // which 403s every request under Lambda's Function URL "Dual Auth"
    // requirement without this explicit permission alongside it.
    const template = synth();
    template.hasResourceProperties("AWS::Lambda::Permission", {
      Action: "lambda:InvokeFunction",
      Principal: "cloudfront.amazonaws.com",
    });
  });

  test("CloudFront routes /share/*.json ahead of /share/* so view-counted reads never fall through to raw S3", () => {
    const template = synth();
    const distributions = template.findResources("AWS::CloudFront::Distribution");
    const [, distribution] = Object.entries(distributions)[0];
    const behaviors: any[] = (distribution as any).Properties.DistributionConfig
      .CacheBehaviors;

    const patterns = behaviors.map((b) => b.PathPattern);
    const jsonIndex = patterns.indexOf("/share/*.json");
    const shareIndex = patterns.indexOf("/share/*");

    expect(jsonIndex).toBeGreaterThanOrEqual(0);
    expect(shareIndex).toBeGreaterThanOrEqual(0);
    expect(jsonIndex).toBeLessThan(shareIndex);
  });

  test("the Basic Auth CloudFront Function is attached to the default behavior and /api/invoke, not to /share/*", () => {
    // /share/* must stay reachable without login — that's the whole point of
    // a shareable, view-limited link (ADR 0008).
    const template = synth();
    const distributions = template.findResources("AWS::CloudFront::Distribution");
    const [, distribution] = Object.entries(distributions)[0];
    const config = (distribution as any).Properties.DistributionConfig;

    expect(config.DefaultCacheBehavior.FunctionAssociations).toEqual(
      expect.arrayContaining([expect.objectContaining({ EventType: "viewer-request" })]),
    );

    const apiInvoke = config.CacheBehaviors.find(
      (b: any) => b.PathPattern === "/api/invoke",
    );
    expect(apiInvoke.FunctionAssociations).toEqual(
      expect.arrayContaining([expect.objectContaining({ EventType: "viewer-request" })]),
    );

    const shareStatic = config.CacheBehaviors.find(
      (b: any) => b.PathPattern === "/share/*",
    );
    expect(shareStatic.FunctionAssociations ?? []).toHaveLength(0);
  });

  test("ALLOWED_ORIGIN and PUBLIC_BASE_URL fall back to safe defaults when publicBaseUrl is not yet known (first deploy)", () => {
    const template = synth();
    template.hasResourceProperties("AWS::Lambda::Function", {
      Environment: {
        Variables: Match.objectLike({
          ALLOWED_ORIGIN: "*",
          PUBLIC_BASE_URL: "",
        }),
      },
    });
  });

  test("ALLOWED_ORIGIN and PUBLIC_BASE_URL are set once publicBaseUrl is known (second deploy)", () => {
    const template = synth({ publicBaseUrl: "https://d123.cloudfront.net" });
    template.hasResourceProperties("AWS::Lambda::Function", {
      Environment: {
        Variables: Match.objectLike({
          ALLOWED_ORIGIN: "https://d123.cloudfront.net",
          PUBLIC_BASE_URL: "https://d123.cloudfront.net",
        }),
      },
    });
  });
});
