import * as cdk from 'aws-cdk-lib';
import * as agentcore from '@aws-cdk/aws-bedrock-agentcore-alpha';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import * as path from 'path';
import * as fs from 'fs';

// Sanitize names for AgentCore resources (alphanumeric + underscores only)
const sanitizeName = (name: string) =>
  name.toLowerCase().replace(/[^a-z0-9]/g, '_').replace(/_+/g, '_');

// Load deployment config
const deploymentConfig = JSON.parse(fs.readFileSync('../../deployment-config.json', 'utf-8'));
const DEPLOYMENT_ID = deploymentConfig.deploymentId;

export interface BaseMcpStackProps extends cdk.StackProps {
  mcpName: string;
  agentCodePath: string;
  environmentVariables?: { [key: string]: string };
  additionalPolicies?: iam.PolicyStatement[];
  ssmParameters?: string[];
}

export abstract class BaseMcpStack extends cdk.Stack {
  public readonly runtime: agentcore.Runtime;
  public readonly role: iam.Role;

  constructor(scope: Construct, id: string, props: BaseMcpStackProps) {
    super(scope, id, props);

    // Add deployment info
    cdk.Tags.of(this).add('DeploymentId', DEPLOYMENT_ID);
    cdk.Tags.of(this).add('DeploymentName', deploymentConfig.deploymentName || DEPLOYMENT_ID);

    // Import Cognito configuration from Amplify stack
    const userPoolId = cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Auth-UserPoolId`);
    const cognitoRegion = cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Auth-Region`);
    const machineClientId = cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Auth-MachineClientId`);
    const cognitoDiscoveryUrl = `https://cognito-idp.${cognitoRegion}.amazonaws.com/${userPoolId}/.well-known/openid-configuration`;

    // Create execution role
    this.role = new iam.Role(this, 'Role', {
      assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
      description: `Execution role for ${props.mcpName} MCP server`
    });

    // Add base CloudWatch Logs permissions
    this.role.addToPolicy(new iam.PolicyStatement({
      sid: 'CloudWatchLogs',
      effect: iam.Effect.ALLOW,
      actions: [
        'logs:CreateLogGroup',
        'logs:CreateLogStream',
        'logs:PutLogEvents'
      ],
      resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:/aws/bedrock-agentcore/*`]
    }));

    // Add Bedrock model invocation permissions (including cross-region inference)
    this.role.addToPolicy(new iam.PolicyStatement({
      sid: 'BedrockModelInvoke',
      effect: iam.Effect.ALLOW,
      actions: [
        'bedrock:InvokeModel',
        'bedrock:InvokeModelWithResponseStream'
      ],
      resources: [
        `arn:aws:bedrock:*::foundation-model/*`,
        `arn:aws:bedrock:*:${this.account}:inference-profile/*`
      ]
    }));

    // Add additional policies if provided
    if (props.additionalPolicies) {
      props.additionalPolicies.forEach(policy => this.role.addToPolicy(policy));
    }

    // Add SSM parameter read access if provided
    if (props.ssmParameters && props.ssmParameters.length > 0) {
      this.role.addToPolicy(new iam.PolicyStatement({
        sid: 'SSMParameterAccess',
        effect: iam.Effect.ALLOW,
        actions: ['ssm:GetParameter', 'ssm:GetParameters'],
        resources: props.ssmParameters.map(param =>
          `arn:aws:ssm:${this.region}:${this.account}:parameter${param}`
        )
      }));

      // Add KMS decrypt permission for SecureString parameters
      this.role.addToPolicy(new iam.PolicyStatement({
        sid: 'KMSDecrypt',
        effect: iam.Effect.ALLOW,
        actions: ['kms:Decrypt'],
        resources: [`arn:aws:kms:${this.region}:${this.account}:key/*`],
        conditions: {
          StringEquals: {
            'kms:ViaService': `ssm.${this.region}.amazonaws.com`
          }
        }
      }));
    }

    // Build environment variables
    const envVars = {
      AWS_REGION: this.region,
      ...props.environmentVariables
    };

    // Create MCP Runtime with OAuth authentication
    this.runtime = new agentcore.Runtime(this, 'Runtime', {
      runtimeName: sanitizeName(`${props.mcpName}_mcp_${this.stackName}`),
      agentRuntimeArtifact: agentcore.AgentRuntimeArtifact.fromAsset(
        path.join(__dirname, '../../..', props.agentCodePath) // nosemgrep
      ),
      executionRole: this.role,
      protocolConfiguration: agentcore.ProtocolType.MCP,
      networkConfiguration: agentcore.RuntimeNetworkConfiguration.usingPublicNetwork(),
      authorizerConfiguration: agentcore.RuntimeAuthorizerConfiguration.usingOAuth(
        cognitoDiscoveryUrl,
        machineClientId
      ),
      environmentVariables: envVars,
      description: `MCP Server: ${props.mcpName} (OAuth enabled)`
    });

    // Outputs
    new cdk.CfnOutput(this, 'RuntimeArn', {
      value: this.runtime.agentRuntimeArn,
      description: `${props.mcpName} MCP Runtime ARN`,
      exportName: `${this.stackName}-RuntimeArn`
    });

    new cdk.CfnOutput(this, 'RuntimeId', {
      value: this.runtime.agentRuntimeId,
      description: `${props.mcpName} MCP Runtime ID`,
      exportName: `${this.stackName}-RuntimeId`
    });
  }
}
