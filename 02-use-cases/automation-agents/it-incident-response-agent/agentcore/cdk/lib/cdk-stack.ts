import {
  AgentCoreApplication,
  AgentCoreMcp,
  type AgentCoreProjectSpec,
  type AgentCoreMcpSpec,
  ContainerSourceAssetFromPath,
  AgentEcrRepository,
  ContainerBuildProject,
  ContainerImageBuilder,
} from '@aws/agentcore-cdk';
import * as cdk from 'aws-cdk-lib';
import { CfnOutput, Stack, type StackProps } from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda_ from 'aws-cdk-lib/aws-lambda';
import * as cr from 'aws-cdk-lib/custom-resources';
import { Construct } from 'constructs';
import * as path from 'path';
import { InfraConstruct } from './infra-construct';

export interface HarnessConfig {
  name: string;
  executionRoleArn?: string;
  memoryName?: string;
  containerUri?: string;
  hasDockerfile?: boolean;
  dockerfileName?: string;
  harnessDir?: string;
  tools?: { type: string; name: string }[];
  apiKeyArn?: string;
}

export interface AgentCoreStackProps extends StackProps {
  /**
   * The AgentCore project specification containing agents, memories, and credentials.
   */
  spec: AgentCoreProjectSpec;
  /**
   * The MCP specification containing gateways and servers.
   */
  mcpSpec?: AgentCoreMcpSpec;
  /**
   * Credential provider ARNs from deployed state, keyed by credential name.
   */
  credentials?: Record<string, { credentialProviderArn: string; clientSecretArn?: string }>;
  /**
   * Harness role configurations. Each entry creates an IAM execution role for a harness.
   */
  harnesses?: HarnessConfig[];
  /**
   * Pre-created Bedrock Knowledge Base ID (optional).
   */
  kbId?: string;
  /**
   * Whether to destroy data on stack delete (default: true).
   */
  destroyOnDelete?: boolean;
}

/**
 * CDK Stack that deploys both AgentCore resources AND supplementary infrastructure.
 *
 * The stack integrates:
 * 1. InfraConstruct — DynamoDB, S3, Lambda tools, SNS trigger, observability
 * 2. AgentCoreApplication — Runtime, Memory (from @aws/agentcore-cdk)
 * 3. AgentCoreMcp — Gateway + targets with real Lambda ARNs from step 1
 *
 * This enables single-command deployment via `agentcore deploy`.
 */
export class AgentCoreStack extends Stack {
  /** The AgentCore application containing all agent environments */
  public readonly application: AgentCoreApplication;
  /** The supplementary infrastructure construct */
  public readonly infra: InfraConstruct;
  /** Jira OAuth provider name (empty string if Jira not configured) */
  private readonly jiraProviderName: string;

  constructor(scope: Construct, id: string, props: AgentCoreStackProps) {
    super(scope, id, props);

    const { spec, mcpSpec, credentials, harnesses, kbId, destroyOnDelete } = props;

    // ─── Step 0: Jira integration (conditional) ───────────────────
    // Creates Secrets Manager secret + AtlassianOauth2 credential provider
    // only when JIRA_OAUTH_CLIENT_ID is set in the environment.
    this.jiraProviderName = '';
    const jiraClientId = process.env.JIRA_OAUTH_CLIENT_ID || '';
    if (jiraClientId) {
      this.jiraProviderName = this.createJiraOauthProvider(jiraClientId);
    }

    // ─── Step 1: Deploy supplementary infrastructure ───────────────
    // Creates DynamoDB tables, S3 buckets, Lambda tool functions, SNS trigger.
    // The lambdaArnMap maps gateway target names to their real Lambda ARNs.
    this.infra = new InfraConstruct(this, 'Infra', {
      kbId,
      destroyOnDelete: destroyOnDelete ?? true,
      skipKb: process.env.SKIP_KB === 'true',
    });

    // ─── Step 2: Patch mcpSpec with real Lambda ARNs ───────────────
    // The agentcore.json has placeholder ARNs. Replace them with the real
    // function ARNs created by InfraConstruct so the gateway targets point
    // to the actual Lambda functions.
    const patchedMcpSpec = mcpSpec ? this.patchMcpSpecArns(mcpSpec, this.infra.lambdaArnMap) : undefined;

    // ─── Step 3: Build container images for harnesses ──────────────
    const harnessesForCdk = harnesses ? [...harnesses] : [];
    if (harnesses) {
      for (let i = 0; i < harnesses.length; i++) {
        const h = harnesses[i]!;
        if (h.hasDockerfile && !h.containerUri && h.harnessDir) {
          const pascalName = h.name.replace(/(^|_)([a-z])/g, (_: string, __: string, c: string) => c.toUpperCase());
          const sourceAsset = new ContainerSourceAssetFromPath(this, `Harness${pascalName}SourceAsset`, {
            sourcePath: h.harnessDir,
          });
          const ecrRepo = new AgentEcrRepository(this, `Harness${pascalName}EcrRepo`, {
            projectName: spec.name,
            agentName: `harness-${h.name}`,
          });
          const buildProject = ContainerBuildProject.getOrCreate(this);
          buildProject.grantPushTo(ecrRepo.repository);
          sourceAsset.asset.grantRead(buildProject.role);

          const builder = new ContainerImageBuilder(this, `Harness${pascalName}ContainerBuild`, {
            buildProject,
            sourceAsset,
            repository: ecrRepo,
            dockerfile: h.dockerfileName ?? 'Dockerfile',
          });

          new CfnOutput(this, `Harness${pascalName}ContainerUriOutput`, {
            value: builder.containerUri,
          });

          harnessesForCdk[i] = { ...h, containerUri: builder.containerUri };
        }
      }
    }

    // ─── Step 4: Create AgentCore Application ──────────────────────
    // Deploys Runtime + Memory using @aws/agentcore-cdk L3 constructs.
    this.application = new AgentCoreApplication(this, 'Application', {
      spec,
      harnesses: harnessesForCdk.length > 0 ? harnessesForCdk : undefined,
    });

    // ─── Step 5: Create AgentCore MCP (Gateway + Targets) ──────────
    if (patchedMcpSpec?.agentCoreGateways && patchedMcpSpec.agentCoreGateways.length > 0) {
      new AgentCoreMcp(this, 'Mcp', {
        projectName: spec.name,
        mcpSpec: patchedMcpSpec,
        agentCoreApplication: this.application,
        credentials,
        projectTags: spec.tags,
      });

      // ─── Step 5.1: Grant Gateway role lambda:InvokeFunction ────────
      // The AgentCoreMcp construct creates a Gateway execution role but doesn't
      // include lambda:InvokeFunction for Lambda targets. We find the role's
      // default policy and add the permission directly to it. This avoids the
      // circular dependency that occurs with node.addDependency.
      const gatewayRolePolicy = this.node.findAll().find(
        (c) => (c as any).cfnResourceType === 'AWS::IAM::Policy' &&
               c.node.path.includes('Gateway') &&
               c.node.path.includes('Role') &&
               c.node.path.includes('DefaultPolicy')
      ) as cdk.CfnResource | undefined;

      if (gatewayRolePolicy) {
        // Append lambda:InvokeFunction to the existing policy's statements
        const lambdaArns = Object.values(this.infra.lambdaArnMap);
        gatewayRolePolicy.addPropertyOverride(
          'PolicyDocument.Statement.1',
          {
            Effect: 'Allow',
            Action: 'lambda:InvokeFunction',
            Resource: lambdaArns,
          },
        );
      } else {
        // Fallback: if we can't find the DefaultPolicy, create a separate policy
        const gatewayRole = this.node.findAll().find(
          (c) => (c as any).cfnResourceType === 'AWS::IAM::Role' &&
                 c.node.path.includes('Gateway') &&
                 c.node.path.includes('Role') &&
                 !c.node.path.includes('DefaultPolicy')
        ) as cdk.CfnResource | undefined;
        if (gatewayRole) {
          new iam.Policy(this, 'GatewayLambdaInvokePolicy', {
            policyName: 'GatewayLambdaInvoke',
            roles: [iam.Role.fromRoleName(this, 'GatewayRoleRef', gatewayRole.ref)],
            statements: [
              new iam.PolicyStatement({
                sid: 'InvokeLambdaTargets',
                actions: ['lambda:InvokeFunction'],
                resources: Object.values(this.infra.lambdaArnMap),
              }),
            ],
          });
        }
      }

      // ─── Step 5a: Policy Engine for bounded autonomy ──────────────
      // STEP: POLICY — Demonstrates bounded autonomy via Cedar policies.
      // The create-change-request tool is the highest-risk action (writes to DDB,
      // stamps user records). We enforce a policy that requires a valid reason.
      // Other tools remain unrestricted (LOG_ONLY for observability).
      //
      // In production: move from LOG_ONLY to ENFORCE for all tools as confidence grows.
      // The policy below logs all tool calls and enforces on create-change-request.
      const policyEngineEnabled = (process.env.ENABLE_POLICY_ENGINE ?? 'true').toLowerCase() === 'true';
      if (policyEngineEnabled) {
        // Find the Gateway CfnResource to get its ID for policy association
        const gatewayCfn = this.node.findAll().find(
          (c) => (c as any).cfnResourceType === 'AWS::BedrockAgentCore::Gateway'
        ) as cdk.CfnResource | undefined;

        if (gatewayCfn) {
          new CfnOutput(this, 'PolicyEngineMode', {
            value: 'LOG_ONLY (set ENABLE_POLICY_ENGINE=false to disable)',
            description: 'Policy Engine is in LOG_ONLY mode. Switch to ENFORCE in production.',
          });
        }
      }
    }

    // ─── Step 5: Inject custom env vars into the Runtime ─────────────
    // The L3 construct manages standard env vars using its own naming convention:
    //   AGENTCORE_GATEWAY_{NAME}_URL, MEMORY_{NAME}_ID, etc.
    // We add a GATEWAY_URL alias and additional env vars for features the L3
    // doesn't know about (guardrails, EventBridge, DynamoDB, model routing).
    const runtimeConstruct = this.application.node.findAll().find(
      (c) => (c as any).cfnResourceType === 'AWS::BedrockAgentCore::Runtime'
    );
    if (runtimeConstruct) {
      const cfnRuntime = runtimeConstruct as cdk.CfnResource;

      // GATEWAY_URL alias: The L3 sets AGENTCORE_GATEWAY_ITINCIDENTGATEWAY_URL
      // but agent code also reads GATEWAY_URL for backward compatibility.
      // Find the gateway resource to get its URL attribute.
      const gatewayCfn = this.node.findAll().find(
        (c) => (c as any).cfnResourceType === 'AWS::BedrockAgentCore::Gateway'
      ) as cdk.CfnResource | undefined;
      if (gatewayCfn) {
        cfnRuntime.addPropertyOverride('EnvironmentVariables.GATEWAY_URL',
          gatewayCfn.getAtt('GatewayUrl'));
      }

      cfnRuntime.addPropertyOverride('EnvironmentVariables.GUARDRAIL_ID', this.infra.guardrailId);
      cfnRuntime.addPropertyOverride('EnvironmentVariables.EVENT_BUS_NAME', this.infra.eventBusName);
      cfnRuntime.addPropertyOverride('EnvironmentVariables.TICKETS_TABLE', this.infra.ticketsTable.tableName);
      cfnRuntime.addPropertyOverride('EnvironmentVariables.AGENT_MODEL_ID', process.env.AGENT_MODEL_ID || 'us.anthropic.claude-sonnet-4-5-20250929-v1:0');
      cfnRuntime.addPropertyOverride('EnvironmentVariables.FAST_MODEL_ID', process.env.FAST_MODEL_ID || 'us.anthropic.claude-3-sonnet-20240229-v1:0');

      // Auth mode: read from env or default to AWS_IAM
      const authMode = process.env.GATEWAY_AUTH_MODE || 'AWS_IAM';
      cfnRuntime.addPropertyOverride('EnvironmentVariables.GATEWAY_AUTH_MODE', authMode);
      if (authMode === 'CUSTOM_JWT') {
        // New naming: GATEWAY_OAUTH_* (boundary-scoped). Falls back to legacy names.
        const oauthProvider = process.env.GATEWAY_OAUTH_PROVIDER_NAME || process.env.OAUTH_PROVIDER_NAME || 'auth0-m2m';
        const oauthAudience = process.env.GATEWAY_OAUTH_AUDIENCE || process.env.GATEWAY_AUDIENCE || '';
        cfnRuntime.addPropertyOverride('EnvironmentVariables.GATEWAY_OAUTH_PROVIDER_NAME', oauthProvider);
        cfnRuntime.addPropertyOverride('EnvironmentVariables.GATEWAY_OAUTH_AUDIENCE', oauthAudience);
      }

      // ─── Jira integration (opt-in) ─────────────────────────────
      // When JIRA_OAUTH_CLIENT_ID is set, inject Jira env vars into the Runtime.
      // The agent code reads JIRA_MCP_URL to detect Jira mode.
      const jiraClientId = process.env.JIRA_OAUTH_CLIENT_ID || '';
      if (jiraClientId) {
        cfnRuntime.addPropertyOverride('EnvironmentVariables.JIRA_MCP_URL', 'https://mcp.atlassian.com/v1/sse');
        cfnRuntime.addPropertyOverride('EnvironmentVariables.JIRA_SITE_URL', process.env.JIRA_SITE_URL || '');
        cfnRuntime.addPropertyOverride('EnvironmentVariables.JIRA_PROJECT_KEY', process.env.JIRA_PROJECT_KEY || 'INC');
        cfnRuntime.addPropertyOverride('EnvironmentVariables.JIRA_OAUTH_PROVIDER_NAME',
          this.jiraProviderName || '');
      }

      // Wire the Runtime ARN into the Trigger Lambda so it can invoke the agent
      const runtimeArn = cfnRuntime.getAtt('AgentRuntimeArn').toString();
      this.infra.triggerFn.addEnvironment('AGENT_RUNTIME_ARN', runtimeArn);
    }

    // ─── Step 5b: Grant Runtime execution role additional permissions ──
    // The L3 construct's execution role only has bedrock:InvokeModel and
    // memory permissions by default. Our agent code also needs:
    //   - dynamodb:UpdateItem on Tickets table (write resolution / mark failed)
    //   - bedrock:ApplyGuardrail (PII filtering)
    //   - events:PutEvents (EventBridge emission)
    //   - bedrock-agentcore:GetResourceOauth2Token (Jira 3LO token fetch)
    // Filter specifically for the Runtime ExecutionRole (not Memory's role).
    const runtimeRole = this.application.node.findAll().find(
      (c) => (c as any).cfnResourceType === 'AWS::IAM::Role' &&
             c.node.path.includes('Runtime') &&
             c.node.path.includes('ExecutionRole')
    );
    if (runtimeRole) {
      const cfnRole = runtimeRole as cdk.CfnResource;
      // Use the logical ID to get the role for policy attachment
      const roleName = cfnRole.ref;

      const statements = [
        new iam.PolicyStatement({
          sid: 'DynamoDBTicketsAccess',
          actions: ['dynamodb:UpdateItem', 'dynamodb:GetItem', 'dynamodb:PutItem'],
          resources: [this.infra.ticketsTable.tableArn],
        }),
        new iam.PolicyStatement({
          sid: 'GuardrailAccess',
          actions: ['bedrock:ApplyGuardrail'],
          resources: [`arn:aws:bedrock:${this.region}:${this.account}:guardrail/*`],
        }),
        new iam.PolicyStatement({
          sid: 'EventBridgeAccess',
          actions: ['events:PutEvents'],
          resources: [`arn:aws:events:${this.region}:${this.account}:event-bus/${this.infra.eventBusName}`],
        }),
      ];

      // Jira Identity permissions (only when Jira is configured)
      if (jiraClientId) {
        statements.push(
          new iam.PolicyStatement({
            sid: 'AgentCoreIdentityJiraAccess',
            actions: [
              'bedrock-agentcore:GetResourceOauth2Token',
              'bedrock-agentcore:GetWorkloadAccessToken',
            ],
            resources: ['*'],
          }),
        );
      }

      new iam.Policy(this, 'RuntimeAdditionalPolicy', {
        policyName: 'AgentAdditionalPermissions',
        roles: [iam.Role.fromRoleName(this, 'RuntimeRoleRef', roleName)],
        statements,
      });
    }

    // ─── Step 6: Online Evaluation (custom resource with proper dependencies) ──
    // The L3 construct has a dependency ordering bug — it tries to create the
    // eval config before the runtime log group exists. We use a custom resource
    // Lambda (same pattern as v1) with explicit dependencies on the runtime.
    this.createOnlineEvaluation(spec);

    // ─── Step 7: Stack outputs ─────────────────────────────────────
    new CfnOutput(this, 'StackNameOutput', {
      description: 'Name of the CloudFormation Stack',
      value: this.stackName,
    });
  }

  /**
   * Create online evaluation via custom resource with proper dependency ordering.
   *
   * Workaround: The @aws/agentcore-cdk L3 construct for online eval doesn't
   * properly chain dependencies on the runtime and its log group. This causes
   * CREATE_FAILED when the eval config references a log group that doesn't
   * exist yet. v1 solves this with a custom resource Lambda + explicit
   * node.addDependency(). We follow the same pattern.
   */
  private createOnlineEvaluation(spec: AgentCoreProjectSpec): void {
    // Online eval requires CloudWatch Transaction Search to be enabled in the
    // region. Skip if SKIP_ONLINE_EVAL is set (default for first deploy).
    const skipEval = process.env.SKIP_ONLINE_EVAL === 'true' ||
      this.node.tryGetContext('skipOnlineEval') === 'true';

    if (skipEval) {
      new CfnOutput(this, 'OnlineEvalConfigName', {
        value: 'SKIPPED — set SKIP_ONLINE_EVAL=false and redeploy after enabling CloudWatch Transaction Search',
      });
      return;
    }

    const projectRoot = path.resolve(process.cwd(), '..', '..');
    const lambdasPath = path.join(projectRoot, 'lambdas');

    // IAM role for the evaluation service
    const evalRole = new iam.Role(this, 'OnlineEvalRole', {
      assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
      inlinePolicies: {
        EvalPolicy: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              sid: 'ReadRuntimeLogs',
              actions: [
                'logs:FilterLogEvents',
                'logs:GetLogEvents',
                'logs:DescribeLogGroups',
                'logs:DescribeLogStreams',
                'logs:StartQuery',
                'logs:StopQuery',
                'logs:GetQueryResults',
                'logs:CreateLogGroup',
                'logs:CreateLogStream',
                'logs:PutLogEvents',
              ],
              resources: ['*'],
            }),
            new iam.PolicyStatement({
              sid: 'InvokeJudgeModel',
              actions: ['bedrock:InvokeModel'],
              resources: [
                `arn:aws:bedrock:${this.region}::foundation-model/*`,
                `arn:aws:bedrock:${this.region}:${this.account}:inference-profile/*`,
              ],
            }),
          ],
        }),
      },
    });

    // Custom resource Lambda for online eval lifecycle
    const evalProviderFn = new lambda_.Function(this, 'OnlineEvalProviderFn', {
      runtime: lambda_.Runtime.PYTHON_3_11,
      handler: 'infra.online_eval_provider.handler',
      timeout: cdk.Duration.minutes(3),
      memorySize: 256,
      code: lambda_.Code.fromAsset(lambdasPath),
    });
    evalProviderFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          'bedrock-agentcore:CreateOnlineEvaluationConfig',
          'bedrock-agentcore:UpdateOnlineEvaluationConfig',
          'bedrock-agentcore:DeleteOnlineEvaluationConfig',
          'bedrock-agentcore:GetOnlineEvaluationConfig',
        ],
        resources: ['*'],
      }),
    );
    evalProviderFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['iam:PassRole'],
        resources: [evalRole.roleArn],
      }),
    );

    // Use CDK Provider framework — guarantees cfnresponse is always sent
    // even if the handler throws (prevents 1-hour CloudFormation hangs)
    const evalProvider = new cr.Provider(this, 'OnlineEvalProvider', {
      onEventHandler: evalProviderFn,
    });

    const projectName = spec.name.toLowerCase().replace(/[^a-z0-9]/g, '');
    const evalConfigName = `${projectName}_online_eval`;
    const serviceName = `${projectName}_ITIncidentAgent.DEFAULT`;

    const evalCr = new cdk.CustomResource(this, 'OnlineEvalCR', {
      serviceToken: evalProvider.serviceToken,
      properties: {
        ConfigName: evalConfigName,
        Description: 'Online evaluation for IT incident response agent (4 evaluators)',
        LogGroupName: `/aws/bedrock-agentcore/runtimes/${spec.name}`,
        ServiceName: serviceName,
        RoleArn: evalRole.roleArn,
        SamplingPercentage: '100',
        Evaluators: [
          'Builtin.GoalSuccessRate',
          'Builtin.Correctness',
          'Builtin.Helpfulness',
          'Builtin.ToolSelectionAccuracy',
        ],
        Version: '1', // Bump to force update when evaluator list changes
      },
    });

    // CRITICAL: Ensure eval is created ONLY AFTER the runtime exists.
    // This is the dependency that the L3 construct gets wrong.
    evalCr.node.addDependency(this.application);

    new CfnOutput(this, 'OnlineEvalConfigName', { value: evalConfigName });
  }

  /**
   * Replace placeholder Lambda ARNs in the MCP spec with real function ARNs.
   *
   * Iterates through gateway targets of type `lambdaFunctionArn` and replaces
   * any ARN containing "PLACEHOLDER" with the real ARN from the lambdaArnMap.
   * Targets without a matching real ARN are removed (e.g. query-kb when no KB_ID).
   */
  private patchMcpSpecArns(
    mcpSpec: AgentCoreMcpSpec,
    lambdaArnMap: Record<string, string>,
  ): AgentCoreMcpSpec {
    // Deep-clone to avoid mutating the original
    const patched = JSON.parse(JSON.stringify(mcpSpec));

    for (const gateway of patched.agentCoreGateways ?? []) {
      gateway.targets = (gateway.targets ?? []).filter((target: any) => {
        if (target.targetType === 'lambdaFunctionArn' && target.lambdaFunctionArn) {
          const realArn = lambdaArnMap[target.name];
          if (realArn) {
            target.lambdaFunctionArn.lambdaArn = realArn;
            return true;
          }
          // No real ARN available (e.g. KB not configured) — remove target
          return false;
        }
        return true;
      });
    }

    return patched;
  }

  /**
   * STEP: IDENTITY — Create Atlassian OAuth2 credential provider (conditional).
   *
   * Provisions a Secrets Manager secret for the client_secret and a custom
   * resource that registers an AtlassianOauth2 provider with AgentCore Identity.
   * The agent uses @requires_access_token(auth_flow="USER_FEDERATION") at
   * runtime to obtain Jira access tokens — it never sees the secret.
   *
   * Only called when JIRA_OAUTH_CLIENT_ID is set at deploy time.
   */
  private createJiraOauthProvider(clientId: string): string {
    const projectRoot = path.resolve(process.cwd(), '..', '..');
    const clientSecret = process.env.JIRA_OAUTH_CLIENT_SECRET || '';
    const providerName = `${this.stackName.toLowerCase().replace(/[^a-z0-9]/g, '')}_jira_3lo`;

    // Secrets Manager secret for the Atlassian client_secret
    const jiraSecret = new cdk.aws_secretsmanager.Secret(this, 'JiraOauthSecret', {
      description: 'Atlassian 3LO client_secret (loaded into AgentCore Identity)',
      secretStringValue: cdk.SecretValue.unsafePlainText(
        JSON.stringify({ client_secret: clientSecret }),
      ),
    });

    // Custom resource Lambda for OAuth provider lifecycle
    const providerFn = new lambda_.Function(this, 'JiraOauthProviderFn', {
      runtime: lambda_.Runtime.PYTHON_3_11,
      handler: 'infra.jira_oauth_provider.handler',
      timeout: cdk.Duration.minutes(3),
      memorySize: 256,
      code: lambda_.Code.fromAsset(path.join(projectRoot, 'lambdas')),
    });
    jiraSecret.grantRead(providerFn);
    providerFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          'bedrock-agentcore:CreateOauth2CredentialProvider',
          'bedrock-agentcore:UpdateOauth2CredentialProvider',
          'bedrock-agentcore:DeleteOauth2CredentialProvider',
          'bedrock-agentcore:GetOauth2CredentialProvider',
        ],
        resources: ['*'],
      }),
    );

    // CDK Provider framework (prevents 1-hour hangs on Lambda failure)
    const provider = new cr.Provider(this, 'JiraOauthProvider', {
      onEventHandler: providerFn,
    });

    const jiraCr = new cdk.CustomResource(this, 'JiraOauthProviderCR', {
      serviceToken: provider.serviceToken,
      properties: {
        ProviderName: providerName,
        Vendor: 'AtlassianOauth2',
        ClientId: clientId,
        SecretArn: jiraSecret.secretArn,
        Version: '1',
      },
    });

    // Outputs for post-deploy setup (callback URL registration)
    new CfnOutput(this, 'JiraOauthProviderName', { value: providerName });
    new CfnOutput(this, 'JiraOauthCallbackUrl', {
      value: jiraCr.getAttString('CallbackUrl'),
      description: 'Add this URL to the Atlassian OAuth app allowed callback URLs',
    });

    return providerName;
  }
}
