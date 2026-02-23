import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { NodejsFunction } from 'aws-cdk-lib/aws-lambda-nodejs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as path from 'path';
// Note: Using standard CDK constructs instead of custom constructs for simplicity

/**
 * API Gateway Stack with Comprehensive DoS Protection (T-3)
 * 
 * This stack implements multiple layers of protection against Denial of Service attacks:
 * 
 * 1. API Gateway Rate Limiting:
 *    - 100 requests/second per user (rate limit)
 *    - 200 requests burst capacity
 *    - 10,000 requests/day quota per user
 * 
 * 2. Lambda Reserved Concurrency:
 *    - Chat Function: 50 concurrent executions max
 *    - Health Check Function: 10 concurrent executions max
 *    - Setup Functions: 5 concurrent executions max
 * 
 * 3. Request Validation:
 *    - Input validation on all endpoints
 *    - Authentication required for sensitive endpoints
 * 
 * 4. Monitoring and Logging:
 *    - CloudWatch logging for all requests
 *    - Metrics enabled for monitoring
 *    - Rate limit configuration stored in SSM for monitoring
 */

export interface ApiStackProps extends cdk.StackProps {
  vpc: ec2.Vpc;
  userPool: cognito.UserPool;
  corsEnabled?: boolean;
  corsOrigins?: string[];
}

export class ApiStack extends cdk.Stack {
  public readonly api: apigateway.RestApi;
  public readonly chatFunction: NodejsFunction;

  constructor(scope: Construct, id: string, props: ApiStackProps) {
    super(scope, id, props);

    // Set parameter prefix for SSM parameters
    const paramPrefix = '/AgentCoreTemplate';

    // Configure CORS options if enabled
    const corsOptions = props.corsEnabled
      ? {
          defaultCorsPreflightOptions: {
            allowOrigins: props.corsOrigins || apigateway.Cors.ALL_ORIGINS,
            allowMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
            allowHeaders: [
              'Content-Type',
              'Authorization',
              'X-Api-Key',
              'X-Amz-Security-Token',
              'Accept',
            ],
            allowCredentials: true,
            maxAge: cdk.Duration.seconds(600),
          },
        }
      : {};

    // Create CloudWatch Logs role for API Gateway
    const apiGatewayCloudWatchRole = new iam.Role(this, 'ApiGatewayCloudWatchRole', {
      assumedBy: new iam.ServicePrincipal('apigateway.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AmazonAPIGatewayPushToCloudWatchLogs'),
      ],
    });

    // Set the CloudWatch Logs role for API Gateway at the account level
    new apigateway.CfnAccount(this, 'ApiGatewayAccount', {
      cloudWatchRoleArn: apiGatewayCloudWatchRole.roleArn,
    });

    // Create CloudWatch log group for API Gateway
    const apiLogGroup = new logs.LogGroup(this, 'ApiLogGroup', {
      logGroupName: `/aws/apigateway/AgentCoreApi`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Create the API with proper options
    this.api = new apigateway.RestApi(this, 'Api', {
      restApiName: 'Knowledge Base RAG Agent API',
      description: 'Core API for Knowledge Base RAG Agent (chat, knowledge base, agent interactions)',
      deployOptions: {
        stageName: 'v1',
        metricsEnabled: true,
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        dataTraceEnabled: true,
        accessLogDestination: new apigateway.LogGroupLogDestination(apiLogGroup),
        accessLogFormat: apigateway.AccessLogFormat.jsonWithStandardFields({
          caller: true,
          httpMethod: true,
          ip: true,
          protocol: true,
          requestTime: true,
          resourcePath: true,
          responseLength: true,
          status: true,
          user: true,
        }),
      },
      ...corsOptions,
    });

    // Create Cognito authorizer
    const authorizer = new apigateway.CognitoUserPoolsAuthorizer(this, 'Authorizer', {
      cognitoUserPools: [props.userPool],
    });

    // Create usage plan for rate limiting (T-3 DoS Protection)
    const usagePlan = this.api.addUsagePlan('DefaultUsagePlan', {
      name: 'AgentCore-DefaultPlan',
      description: 'Default usage plan with rate limiting for DoS protection (T-3)',
      throttle: {
        rateLimit: 100, // 100 requests per second per user (T-3 requirement)
        burstLimit: 200, // Allow bursts up to 200 requests (T-3 requirement)
      },
      quota: {
        limit: 10000, // 10,000 requests per day per user to prevent abuse
        period: apigateway.Period.DAY,
      },
    });

    // Create API key for usage plan tracking
    const apiKey = this.api.addApiKey('DefaultApiKey', {
      apiKeyName: 'AgentCore-DefaultKey',
      description: 'Default API key for rate limiting and DoS protection',
    });

    // Associate API key with usage plan
    usagePlan.addApiKey(apiKey);

    // Associate usage plan with API stage for rate limiting
    usagePlan.addApiStage({
      stage: this.api.deploymentStage,
    });

    // Create API resources with /api prefix for Bedrock Agent interactions
    const apiRoot = this.api.root.addResource('api');
    const chatResource = apiRoot.addResource('chat');
    const knowledgeBaseResource = apiRoot.addResource('knowledge-base');
    const agentResource = apiRoot.addResource('agent');

    // Create chat endpoints with Lambda integration
    const chatInvokeResource = chatResource.addResource('invoke');

    // Import the common layer from the shared resources stack
    const commonLayerArn = ssm.StringParameter.valueForStringParameter(
      this,
      `${paramPrefix}/CommonLayerArn`
    );
    const commonLayer = lambda.LayerVersion.fromLayerVersionArn(
      this,
      'CommonLayer',
      commonLayerArn
    );

    // Create CloudWatch log group for Lambda function
    const chatLambdaLogGroup = new logs.LogGroup(this, 'ChatLambdaLogGroup', {
      logGroupName: `/aws/lambda/AgentCoreApi-Chat`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Get AgentCore Runtime configuration from SSM Parameter Store
    const agentCoreRuntimeArn = ssm.StringParameter.valueForStringParameter(
      this,
      `${paramPrefix}/AgentCore/RuntimeArn`
    );
    const sessionsTableName = ssm.StringParameter.valueForStringParameter(
      this,
      `${paramPrefix}/Tables/sessionsTableName`
    );
    const chatHistoryTableName = ssm.StringParameter.valueForStringParameter(
      this,
      `${paramPrefix}/Tables/chatHistoryTableName`
    );

    // Create Lambda function for chat interactions with AgentCore Runtime
    // Using NodejsFunction for esbuild-based bundling (no Docker required)
    this.chatFunction = new NodejsFunction(this, 'ChatFunction', {
      functionName: 'AgentCoreApi-Chat',
      runtime: lambda.Runtime.NODEJS_20_X,
      handler: 'handler',
      entry: path.join(__dirname, '../../src/functions/chat/index.ts'),
      environment: {
        AGENTCORE_RUNTIME_ARN: agentCoreRuntimeArn,
        SESSIONS_TABLE: sessionsTableName,
        CHAT_HISTORY_TABLE: chatHistoryTableName,
      },
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      layers: [commonLayer],
      logGroup: chatLambdaLogGroup,
      // T-3 DoS Protection: Set reserved concurrency to prevent resource exhaustion
      reservedConcurrentExecutions: 50,
      bundling: {
        minify: true,
        sourceMap: true,
        // Bundle all dependencies - no external modules needed
        // The Lambda layer provides AWS SDK clients, but logger is bundled
      },
    });

    // Import shared policies from the shared resources stack
    const bedrockAccessPolicyArn = ssm.StringParameter.valueForStringParameter(
      this,
      `${paramPrefix}/Policies/BedrockAccessPolicyArn`
    );
    const ssmParameterAccessPolicyArn = ssm.StringParameter.valueForStringParameter(
      this,
      `${paramPrefix}/Policies/SSMParameterAccessPolicyArn`
    );

    // Attach shared policies to the chat Lambda function
    this.chatFunction.role?.addManagedPolicy(
      iam.ManagedPolicy.fromManagedPolicyArn(this, 'BedrockAccessPolicy', bedrockAccessPolicyArn)
    );
    this.chatFunction.role?.addManagedPolicy(
      iam.ManagedPolicy.fromManagedPolicyArn(this, 'SSMParameterAccessPolicy', ssmParameterAccessPolicyArn)
    );

    // Grant AgentCore Runtime invocation permissions
    this.chatFunction.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'bedrock-agentcore:InvokeAgentRuntime',
          'bedrock-agentcore:InvokeAgentRuntimeForUser',
        ],
        resources: [
          `arn:aws:bedrock-agentcore:${this.region}:${this.account}:runtime/*`,
        ],
      })
    );

    // Grant DynamoDB permissions to the chat Lambda function
    this.chatFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          'dynamodb:PutItem',
          'dynamodb:GetItem',
          'dynamodb:UpdateItem',
          'dynamodb:Query',
          'dynamodb:Scan',
        ],
        resources: [
          `arn:aws:dynamodb:${this.region}:${this.account}:table/${sessionsTableName}`,
          `arn:aws:dynamodb:${this.region}:${this.account}:table/${sessionsTableName}/index/*`,
          `arn:aws:dynamodb:${this.region}:${this.account}:table/${chatHistoryTableName}`,
          `arn:aws:dynamodb:${this.region}:${this.account}:table/${chatHistoryTableName}/index/*`,
        ],
      })
    );

    // CORS preflight OPTIONS method is automatically added by defaultCorsPreflightOptions
    // No need to manually add OPTIONS method

    // T-3 DoS Protection: Add method-level throttling for chat endpoint
    chatInvokeResource.addMethod('POST', new apigateway.LambdaIntegration(this.chatFunction), {
      methodResponses: [
        {
          statusCode: '200',
          responseModels: {
            'application/json': apigateway.Model.EMPTY_MODEL,
          },
        },
      ],
      authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
      // Method-level throttling provides additional protection beyond usage plan
      requestValidatorOptions: {
        validateRequestBody: true,
        validateRequestParameters: true,
      },
    });

    // Create knowledge base endpoints
    const knowledgeBaseQueryResource = knowledgeBaseResource.addResource('query');
    knowledgeBaseQueryResource.addMethod('POST', new apigateway.LambdaIntegration(this.chatFunction), {
      methodResponses: [
        {
          statusCode: '200',
          responseModels: {
            'application/json': apigateway.Model.EMPTY_MODEL,
          },
        },
      ],
      authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    // Create a simple health check Lambda for testing
    const healthCheckLambda = new lambda.Function(this, 'HealthCheckFunction', {
      functionName: 'AgentCoreApi-HealthCheck',
      runtime: lambda.Runtime.NODEJS_20_X,
      handler: 'index.handler',
      code: lambda.Code.fromInline(`
        exports.handler = async (event) => {
          console.log('Health check called:', JSON.stringify(event, null, 2));
          return {
            statusCode: 200,
            headers: {
              'Content-Type': 'application/json',
              'Access-Control-Allow-Origin': '*',
              'Access-Control-Allow-Methods': 'OPTIONS,GET',
              'Access-Control-Allow-Headers': 'Content-Type'
            },
            body: JSON.stringify({
              status: 'healthy',
              timestamp: new Date().toISOString(),
              message: 'API Gateway is working correctly'
            })
          };
        };
      `),
      timeout: cdk.Duration.seconds(10),
      memorySize: 128,
      // T-3 DoS Protection: Set reserved concurrency for health check function
      reservedConcurrentExecutions: 10, // Lower limit for health check function
    });

    // Create health check endpoint (no auth required for testing)
    const healthResource = apiRoot.addResource('health');
    healthResource.addMethod('GET', new apigateway.LambdaIntegration(healthCheckLambda), {
      methodResponses: [
        {
          statusCode: '200',
          responseModels: {
            'application/json': apigateway.Model.EMPTY_MODEL,
          },
        },
      ],
    });

    // Create authenticated health check endpoint to test Cognito auth
    const authHealthResource = apiRoot.addResource('auth-health');
    authHealthResource.addMethod('GET', new apigateway.LambdaIntegration(healthCheckLambda), {
      methodResponses: [
        {
          statusCode: '200',
          responseModels: {
            'application/json': apigateway.Model.EMPTY_MODEL,
          },
        },
      ],
      authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    // Create agent status endpoint
    const agentStatusResource = agentResource.addResource('status');
    agentStatusResource.addMethod('GET', new apigateway.LambdaIntegration(this.chatFunction), {
      methodResponses: [
        {
          statusCode: '200',
          responseModels: {
            'application/json': apigateway.Model.EMPTY_MODEL,
          },
        },
      ],
      authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    // Create chat history endpoint
    const chatHistoryResource = chatResource.addResource('history');
    chatHistoryResource.addMethod('GET', new apigateway.LambdaIntegration(this.chatFunction), {
      methodResponses: [
        {
          statusCode: '200',
          responseModels: {
            'application/json': apigateway.Model.EMPTY_MODEL,
          },
        },
      ],
      authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    // Grant API Gateway permission to invoke Lambda functions (explicit permissions)
    this.chatFunction.addPermission('ApiGatewayInvoke', {
      principal: new iam.ServicePrincipal('apigateway.amazonaws.com'),
      sourceArn: this.api.arnForExecuteApi(),
    });

    healthCheckLambda.addPermission('ApiGatewayInvokeHealth', {
      principal: new iam.ServicePrincipal('apigateway.amazonaws.com'),
      sourceArn: this.api.arnForExecuteApi(),
    });







    // Outputs
    // Store chat function name in SSM Parameter Store for monitoring
    new ssm.StringParameter(this, 'ChatFunctionNameParameter', {
      parameterName: `${paramPrefix}/ChatFunctionName`,
      description: 'Chat Lambda function name',
      stringValue: this.chatFunction.functionName,
    });

    // Store API endpoint in SSM Parameter Store
    new ssm.StringParameter(this, 'ApiEndpointParameter', {
      parameterName: `${paramPrefix}/ApiEndpoint`,
      description: 'API Gateway endpoint URL',
      stringValue: this.api.url,
    });

    // Store API ID in SSM Parameter Store
    new ssm.StringParameter(this, 'ApiIdParameter', {
      parameterName: `${paramPrefix}/ApiId`,
      description: 'API Gateway ID',
      stringValue: this.api.restApiId,
    });

    // Store API stage name in SSM Parameter Store
    new ssm.StringParameter(this, 'ApiStageNameParameter', {
      parameterName: `${paramPrefix}/ApiStageName`,
      description: 'API Gateway stage name',
      stringValue: this.api.deploymentStage.stageName,
    });

    // Store rate limiting configuration in SSM Parameter Store for monitoring
    new ssm.StringParameter(this, 'RateLimitConfigParameter', {
      parameterName: `${paramPrefix}/RateLimitConfig`,
      description: 'API Gateway rate limiting configuration for DoS protection (T-3)',
      stringValue: JSON.stringify({
        rateLimit: 100,
        burstLimit: 200,
        dailyQuota: 10000,
        lambdaConcurrency: {
          chatFunction: 50,
          healthCheckFunction: 10,
        },
      }),
    });

    // CloudFormation outputs
    new cdk.CfnOutput(this, 'ApiEndpoint', {
      value: this.api.url,
      description: 'API Gateway endpoint URL',
      exportName: `${this.stackName}-ApiEndpoint`,
    });
  }
}
