import {
  AgentCoreApplication,
  AgentCoreMcp,
  type AgentCoreProjectSpec,
  type AgentCoreMcpSpec,
} from '@aws/agentcore-cdk';
import * as cdk from 'aws-cdk-lib';
import { CfnOutput, Stack, type StackProps } from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import { InfraConstruct } from './infra-construct';

export interface AgentCoreStackProps extends StackProps {
  /** The AgentCore project specification containing agents, memories, and credentials. */
  spec: AgentCoreProjectSpec;
  /** The MCP specification containing gateways and servers. */
  mcpSpec?: AgentCoreMcpSpec;
  /** Credential provider ARNs from deployed state, keyed by credential name. */
  credentials?: Record<string, { credentialProviderArn: string; clientSecretArn?: string }>;
}

/**
 * CDK Stack: Event-Driven Claims Agent
 *
 * Integrates:
 * 1. InfraConstruct — DynamoDB, S3, Lambda tools, SNS, EventBridge, Cognito
 * 2. AgentCoreApplication — Runtime, Memory, PolicyEngine, OnlineEval (from agentcore.json)
 * 3. AgentCoreMcp — Gateway + 6 Lambda targets with real ARNs from step 1
 *
 * Deployment: `agentcore deploy --target dev`
 */
export class AgentCoreStack extends Stack {
  public readonly application: AgentCoreApplication;
  public readonly infra: InfraConstruct;

  constructor(scope: Construct, id: string, props: AgentCoreStackProps) {
    super(scope, id, props);

    const { spec, mcpSpec, credentials } = props;

    // ─── Step 1: Supplementary infrastructure ──────────────────────
    // Creates DynamoDB tables, Lambda tool functions, S3, EventBridge, SNS, Cognito.
    // Exposes lambdaArnMap for patching gateway targets.
    this.infra = new InfraConstruct(this, 'Infra', {
      destroyOnDelete: true,
    });

    // ─── Step 2: Patch mcpSpec with real Lambda ARNs + JWT authorizer ──
    const patchedMcpSpec = mcpSpec ? this.patchMcpSpecArns(mcpSpec, this.infra.lambdaArnMap) : undefined;

    // ─── Step 3: AgentCore Application (Runtime + Memory + Eval) ───
    this.application = new AgentCoreApplication(this, 'Application', { spec });

    // ─── Step 4: AgentCore MCP (Gateway + Targets + PolicyEngine) ──
    if (patchedMcpSpec?.agentCoreGateways && patchedMcpSpec.agentCoreGateways.length > 0) {
      new AgentCoreMcp(this, 'Mcp', {
        projectName: spec.name,
        mcpSpec: patchedMcpSpec,
        agentCoreApplication: this.application,
        credentials,
        projectTags: spec.tags,
      });

      // Order GatewayTargets after the gateway role policy so they deploy in a single clean pass
      const gatewayRolePolicy = this.node
        .findAll()
        .find(
          c =>
            (c as cdk.CfnResource).cfnResourceType === 'AWS::IAM::Policy' &&
            c.node.path.includes('Gateway') &&
            c.node.path.includes('Role') &&
            c.node.path.includes('DefaultPolicy')
        ) as cdk.CfnResource | undefined;

      if (gatewayRolePolicy) {
        const gatewayTargets = this.node
          .findAll()
          .filter(
            c => (c as cdk.CfnResource).cfnResourceType === 'AWS::BedrockAgentCore::GatewayTarget'
          ) as cdk.CfnResource[];
        for (const target of gatewayTargets) {
          target.addDependency(gatewayRolePolicy);
        }
      }
    }

    // ─── Step 5: Inject custom env vars into the Runtime ───────────
    const runtimeConstruct = this.application.node
      .findAll()
      .find(c => (c as cdk.CfnResource).cfnResourceType === 'AWS::BedrockAgentCore::Runtime');
    if (runtimeConstruct) {
      const cfnRuntime = runtimeConstruct as cdk.CfnResource;

      // Gateway URL alias (agent code reads AGENTCORE_GATEWAY_URL)
      const gatewayCfn = this.node
        .findAll()
        .find(c => (c as cdk.CfnResource).cfnResourceType === 'AWS::BedrockAgentCore::Gateway') as cdk.CfnResource | undefined;
      if (gatewayCfn) {
        cfnRuntime.addPropertyOverride('EnvironmentVariables.AGENTCORE_GATEWAY_URL', gatewayCfn.getAtt('GatewayUrl'));
      }

      // Cognito token endpoint for M2M auth to Gateway
      cfnRuntime.addPropertyOverride(
        'EnvironmentVariables.AGENTCORE_GATEWAY_TOKEN_ENDPOINT',
        this.infra.cognitoTokenEndpoint
      );
      cfnRuntime.addPropertyOverride(
        'EnvironmentVariables.AGENTCORE_GATEWAY_CLIENT_ID',
        this.infra.cognitoClientId
      );
      // Client secret completes the client_credentials flow for the Gateway CUSTOM_JWT authorizer.
      cfnRuntime.addPropertyOverride(
        'EnvironmentVariables.AGENTCORE_GATEWAY_CLIENT_SECRET',
        this.infra.cognitoClientSecret
      );
      cfnRuntime.addPropertyOverride(
        'EnvironmentVariables.AGENTCORE_GATEWAY_OAUTH_SCOPES',
        'agentcore/invoke'
      );

      // Wire trigger Lambda to Runtime
      const runtimeArn = cfnRuntime.getAtt('AgentRuntimeArn').toString();
      this.infra.triggerFn.addEnvironment('AGENTCORE_RUNTIME_ARN', runtimeArn);
      // Output the Runtime ARN so test scripts (test_invoke.py, test_e2e.py, test_cedar.py)
      // can read it from CloudFormation outputs to invoke the deployed Runtime.
      new CfnOutput(this, 'RuntimeArn', {
        description: 'AgentCore Runtime ARN',
        value: runtimeArn,
      });
      this.infra.triggerFn.addToRolePolicy(
        new iam.PolicyStatement({
          actions: ['bedrock-agentcore:InvokeAgentRuntime'],
          resources: [runtimeArn, `${runtimeArn}/*`],
        })
      );
    }

    // ─── Step 6: Grant Runtime additional permissions ──────────────
    const runtimeRole = this.application.node
      .findAll()
      .find(
        c =>
          (c as cdk.CfnResource).cfnResourceType === 'AWS::IAM::Role' &&
          c.node.path.includes('Runtime') &&
          c.node.path.includes('ExecutionRole')
      );
    if (runtimeRole) {
      const cfnRole = runtimeRole as cdk.CfnResource;
      const roleName = cfnRole.ref;

      new iam.Policy(this, 'RuntimeAdditionalPolicy', {
        policyName: 'ClaimsAgentAdditionalPermissions',
        roles: [iam.Role.fromRoleName(this, 'RuntimeRoleRef', roleName)],
        statements: [
          new iam.PolicyStatement({
            sid: 'BedrockInvokeModel',
            actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
            resources: [
              `arn:aws:bedrock:${this.region}::foundation-model/anthropic.claude-sonnet-4-6`,
              'arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4-6',
              'arn:aws:bedrock:*:*:inference-profile/*',
            ],
          }),
        ],
      });
    }

    // ─── Step 7: Outputs ──────────────────────────────────────────
    new CfnOutput(this, 'StackNameOutput', {
      description: 'CloudFormation Stack Name',
      value: this.stackName,
    });
  }

  /**
   * Replace placeholders in the MCP spec with real CDK-resolved values:
   * - Lambda target ARNs (PLACEHOLDER_* → function ARN from lambdaArnMap)
   * - CUSTOM_JWT authorizer discovery URL + allowed clients (Cognito values from infra)
   */
  private patchMcpSpecArns(mcpSpec: AgentCoreMcpSpec, lambdaArnMap: Record<string, string>): AgentCoreMcpSpec {
    const patched = JSON.parse(JSON.stringify(mcpSpec));
    for (const gateway of patched.agentCoreGateways ?? []) {
      gateway.targets = (gateway.targets ?? []).filter((target: Record<string, unknown>) => {
        if (target.targetType === 'lambdaFunctionArn' && target.lambdaFunctionArn) {
          const realArn = lambdaArnMap[target.name as string];
          if (realArn) {
            (target.lambdaFunctionArn as Record<string, string>).lambdaArn = realArn;
            return true;
          }
          return false;
        }
        return true;
      });

      // Patch CUSTOM_JWT authorizer placeholders with real Cognito values.
      const jwt = gateway.authorizerConfiguration?.customJwtAuthorizer;
      if (jwt) {
        jwt.discoveryUrl = this.infra.cognitoDiscoveryUrl;
        jwt.allowedClients = [this.infra.cognitoClientId];
      }
    }
    return patched;
  }
}
