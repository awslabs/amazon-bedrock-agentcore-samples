import * as cdk from 'aws-cdk-lib';
import * as agentcore from '@aws-cdk/aws-bedrock-agentcore-alpha';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as customResources from 'aws-cdk-lib/custom-resources';
import { Construct } from 'constructs';
import { GatewayConstruct } from './constructs/gateway-construct';
import * as path from 'path';
import * as fs from 'fs';

// Sanitize names for AgentCore resources (alphanumeric + underscores)
const sanitizeName = (name: string) =>
  name.toLowerCase().replace(/[^a-z0-9]/g, '_').replace(/_+/g, '_');

// Load deployment config
const deploymentConfig = JSON.parse(fs.readFileSync('../../deployment-config.json', 'utf-8'));
const DEPLOYMENT_ID = deploymentConfig.deploymentId;

export class AgentStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Add deployment info
    cdk.Tags.of(this).add('DeploymentId', DEPLOYMENT_ID);
    cdk.Tags.of(this).add('DeploymentName', deploymentConfig.deploymentName || DEPLOYMENT_ID);

    // Import Cognito from Amplify
    const userPoolId = cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Auth-UserPoolId`);
    const clientId = cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Auth-ClientId`);
    const cognitoRegion = cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Auth-Region`);
    const discoveryUrl = `https://cognito-idp.${cognitoRegion}.amazonaws.com/${userPoolId}/.well-known/openid-configuration`;

    // Import machine client ID from Amplify (created there for proper deployment order)
    const machineClientId = cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Auth-MachineClientId`);

    // Import the user pool for OAuth provider secret retrieval
    const userPool = cognito.UserPool.fromUserPoolId(this, 'ImportedUserPool', userPoolId);

    // Import DynamoDB tables
    const userProfileTableName = cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Data-UserProfileTableName`);
    const wishlistTableName = cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Data-WishlistTableName`);
    const itineraryTableName = cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Data-ItineraryTableName`);
    const feedbackTableName = cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Data-FeedbackTableName`);

    // Import MCP runtime ARNs (using deployment ID in stack names)
    const travelRuntimeArn = cdk.Fn.importValue(`TravelStack-${DEPLOYMENT_ID}-RuntimeArn`);
    const cartRuntimeArn = cdk.Fn.importValue(`CartStack-${DEPLOYMENT_ID}-RuntimeArn`);
    const itineraryRuntimeArn = cdk.Fn.importValue(`ItineraryStack-${DEPLOYMENT_ID}-RuntimeArn`);

    // 1. Create Custom Resource Lambda for OAuth Provider
    const oauthProviderRole = new iam.Role(this, 'OAuthProviderLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: 'Execution role for OAuth Provider Custom Resource Lambda',
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ],
      inlinePolicies: {
        OAuthProviderPolicy: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock-agentcore:CreateOAuth2CredentialProvider',
                'bedrock-agentcore:DeleteOAuth2CredentialProvider',
                'bedrock-agentcore:ListOAuth2CredentialProviders',
                'bedrock-agentcore:GetOAuth2CredentialProvider',
                'bedrock-agentcore:CreateTokenVault',  // Required for OAuth provider creation
                'bedrock-agentcore:DeleteTokenVault',
                'bedrock-agentcore:GetTokenVault',
                'secretsmanager:CreateSecret',  // Required to store OAuth client secret
                'secretsmanager:DeleteSecret',
                'secretsmanager:GetSecretValue',
                'secretsmanager:PutSecretValue',
                'cognito-idp:DescribeUserPoolClient'  // Required to fetch client secret
              ],
              resources: ['*']
            })
          ]
        })
      }
    });

    const oauthProviderLambda = new lambda.Function(this, 'OAuthProviderLambda', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'lambdas', 'oauth-provider')),
      timeout: cdk.Duration.minutes(5),
      role: oauthProviderRole,
      description: 'Custom Resource for OAuth2 Credential Provider management'
    });

    const oauthProvider = new customResources.Provider(this, 'OAuthProvider', {
      onEventHandler: oauthProviderLambda
    });

    // 2. Create OAuth Provider via Custom Resource
    const oauthCredentialProvider = new cdk.CustomResource(this, 'OAuthCredentialProvider', {
      serviceToken: oauthProvider.serviceToken,
      properties: {
        ProviderName: sanitizeName(`oauth_provider_${this.stackName}`),
        UserPoolId: userPoolId,
        ClientId: machineClientId,
        DiscoveryUrl: discoveryUrl,
        Version: '2' // Increment to force update
      }
    });

    const oauthProviderArn = oauthCredentialProvider.getAttString('ProviderArn');

    // 1. Create Memory using L2 construct
    const memory = new agentcore.Memory(this, 'Memory', {
      memoryName: sanitizeName(`memory_${this.stackName}`),
      description: 'Short-term memory for Concierge Agent',
    });

    // 2. Create execution role for main agent
    const agentRole = new iam.Role(this, 'AgentRole', {
      assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
      description: 'Execution role for Concierge Agent'
    });

    // Grant DynamoDB permissions
    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: ['dynamodb:GetItem', 'dynamodb:Scan', 'dynamodb:UpdateItem', 'dynamodb:Query', 'dynamodb:PutItem', 'dynamodb:DeleteItem', 'dynamodb:BatchWriteItem'],
      resources: [
        `arn:aws:dynamodb:${this.region}:${this.account}:table/${userProfileTableName}`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/${userProfileTableName}/index/*`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/${wishlistTableName}`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/${wishlistTableName}/index/*`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/${itineraryTableName}`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/${itineraryTableName}/index/*`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/${feedbackTableName}`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/${feedbackTableName}/index/*`
      ]
    }));

    // Grant CloudWatch Logs permissions
    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: ['logs:CreateLogGroup', 'logs:CreateLogStream', 'logs:PutLogEvents', 'logs:DescribeLogGroups', 'logs:DescribeLogStreams', 'logs:GetLogEvents', 'logs:FilterLogEvents'],
      resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:*`]
    }));

    // Grant Memory access
    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        'bedrock-agentcore:GetMemory',
        'bedrock-agentcore:ListMemories',
        'bedrock-agentcore:CreateEvent',
        'bedrock-agentcore:GetEvent',
        'bedrock-agentcore:ListEvents',
        'bedrock-agentcore:RetrieveMemoryRecords'
      ],
      resources: [memory.memoryArn]
    }));

    // Grant Bedrock model access
    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
      resources: [
        `arn:aws:bedrock:*::foundation-model/*`,
        `arn:aws:bedrock:*:${this.account}:inference-profile/*`
      ]
    }));

    // Grant Gateway invoke permissions (for runtime to call gateway)
    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: ['bedrock-agentcore:InvokeGateway'],
      resources: ['*']  // Will be restricted to specific gateway after creation
    }));

    // Grant ECR permissions (required for runtime to pull container image)
    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        'ecr:GetAuthorizationToken',
        'ecr:BatchCheckLayerAvailability',
        'ecr:GetDownloadUrlForLayer',
        'ecr:BatchGetImage'
      ],
      resources: ['*']
    }));

    // Grant Cognito permissions (required for runtime to fetch machine client secret and domain)
    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        'cognito-idp:DescribeUserPoolClient',
        'cognito-idp:DescribeUserPool'
      ],
      resources: [`arn:aws:cognito-idp:${this.region}:${this.account}:userpool/${userPoolId}`]
    }));

    // 3. Create main agent runtime using L2 construct
    const baseEnvVars = {
      MEMORY_ID: memory.memoryId,
      USER_PROFILE_TABLE_NAME: userProfileTableName,
      WISHLIST_TABLE_NAME: wishlistTableName,
      ITINERARY_TABLE_NAME: itineraryTableName,
      FEEDBACK_TABLE_NAME: feedbackTableName,
      DEPLOYMENT_ID: DEPLOYMENT_ID,
      // Gateway M2M authentication credentials (for runtime to call gateway)
      GATEWAY_CLIENT_ID: machineClientId,
      GATEWAY_USER_POOL_ID: userPoolId,
      GATEWAY_SCOPE: 'concierge-gateway/invoke',
    };

    // Create runtime first (without GATEWAY_URL since gateway doesn't exist yet)
    const runtime = new agentcore.Runtime(this, 'Runtime', {
      runtimeName: sanitizeName(`agent_${this.stackName}`),
      agentRuntimeArtifact: agentcore.AgentRuntimeArtifact.fromAsset(
        path.join(__dirname, '../../..', 'concierge_agent', 'supervisor_agent')
      ),
      executionRole: agentRole,
      protocolConfiguration: agentcore.ProtocolType.HTTP,
      networkConfiguration: agentcore.RuntimeNetworkConfiguration.usingPublicNetwork(),
      authorizerConfiguration: agentcore.RuntimeAuthorizerConfiguration.usingJWT(
        discoveryUrl,
        [clientId, machineClientId]  // Accept user tokens (frontend) AND M2M tokens (gateway)
      ),
      environmentVariables: baseEnvVars,
      description: 'Concierge Agent Runtime'
    });

    // 6. Create Gateway with JWT inbound and OAuth outbound
    // IMPORTANT: Gateway must use SAME M2M client as runtime and OAuth provider
    // Inbound: Frontend authenticates to gateway using M2M JWT token
    // Outbound: Gateway authenticates to targets using OAuth (same M2M client)
    const gateway = new GatewayConstruct(this, 'Gateway', {
      gatewayName: sanitizeName(`gateway_${this.stackName}`).replace(/_/g, '-'),
      mcpRuntimeArns: [
        { name: 'CartTools', arn: cartRuntimeArn },
        { name: 'ItineraryTools', arn: itineraryRuntimeArn },
        { name: 'TravelTools', arn: travelRuntimeArn }
      ],
      cognitoClientId: machineClientId,  // Use M2M client (same as runtime and OAuth)
      cognitoDiscoveryUrl: discoveryUrl,
      oauthProviderArn: oauthProviderArn,
      oauthScope: 'concierge-gateway/invoke'
    });

    // Store gateway URL in SSM Parameter Store for runtime to access
    const gatewayUrlParameter = new cdk.aws_ssm.StringParameter(this, 'GatewayUrlParameter', {
      parameterName: `/concierge-agent/${DEPLOYMENT_ID}/gateway-url`,
      stringValue: gateway.gatewayUrl,
      description: 'AgentCore Gateway URL for supervisor agent',
      tier: cdk.aws_ssm.ParameterTier.STANDARD,
    });

    // Grant runtime permission to read SSM parameter
    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: ['ssm:GetParameter'],
      resources: [gatewayUrlParameter.parameterArn]
    }));

    // Outputs
    new cdk.CfnOutput(this, 'MainRuntimeArn', {
      value: runtime.agentRuntimeArn,
      exportName: `${this.stackName}-MainRuntimeArn`
    });

    new cdk.CfnOutput(this, 'MainRuntimeId', {
      value: runtime.agentRuntimeId,
      exportName: `${this.stackName}-MainRuntimeId`
    });

    new cdk.CfnOutput(this, 'MemoryId', {
      value: memory.memoryId,
      exportName: `${this.stackName}-MemoryId`
    });

    new cdk.CfnOutput(this, 'GatewayUrl', {
      value: gateway.gatewayUrl,
      exportName: `${this.stackName}-GatewayUrl`,
      description: 'Gateway URL for MCP client connections (IAM auth)'
    });

    new cdk.CfnOutput(this, 'GatewayId', {
      value: gateway.gatewayId,
      exportName: `${this.stackName}-GatewayId`,
      description: 'Gateway ID'
    });

    new cdk.CfnOutput(this, 'GatewayArn', {
      value: gateway.gatewayArn,
      exportName: `${this.stackName}-GatewayArn`,
      description: 'Gateway ARN'
    });

    new cdk.CfnOutput(this, 'GatewayTargetCount', {
      value: gateway.targets.length.toString(),
      description: 'Number of gateway targets configured'
    });

    new cdk.CfnOutput(this, 'MachineClientId', {
      value: machineClientId,
      description: 'Machine client ID for gateway OAuth and MCP authentication (imported from Amplify)'
    });

    new cdk.CfnOutput(this, 'OAuthProviderArn', {
      value: oauthProviderArn,
      exportName: `${this.stackName}-OAuthProviderArn`,
      description: 'OAuth provider ARN for gateway targets'
    });
  }
}
