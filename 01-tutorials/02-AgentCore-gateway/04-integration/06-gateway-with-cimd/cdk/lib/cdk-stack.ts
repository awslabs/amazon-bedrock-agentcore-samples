import * as cdk from "aws-cdk-lib";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as apigateway from "aws-cdk-lib/aws-apigatewayv2";
import * as authorizers from "aws-cdk-lib/aws-apigatewayv2-authorizers";
import * as integrations from "aws-cdk-lib/aws-apigatewayv2-integrations";
import * as iam from "aws-cdk-lib/aws-iam";
import { Construct } from "constructs";
import * as path from "path";
import * as agentcore from "@aws-cdk/aws-bedrock-agentcore-alpha";

export class CdkStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // =============================================================================
    // COGNITO USER POOL
    // =============================================================================

    // Create Cognito User Pool
    const userPool = new cognito.UserPool(this, "AgentCoreConfluencePool", {
      selfSignUpEnabled: false,
      signInAliases: {
        email: true,
      },
      autoVerify: {
        email: true,
      },
      standardAttributes: {
        email: {
          required: true,
          mutable: true,
        },
      },
      passwordPolicy: {
        minLength: 8,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: true,
      },
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // Create Cognito Domain
    const cognitoDomainPrefix = `agentcore-cimd`;
    const cognitoDomain = userPool.addDomain("CognitoDomain", {
      cognitoDomain: {
        domainPrefix: cognitoDomainPrefix,
      },
    });

    const readScope = new cognito.ResourceServerScope({
      scopeName: "mcp.read",
      scopeDescription: "Read MCP",
    });
    const writeScope = new cognito.ResourceServerScope({
      scopeName: "mcp.write",
      scopeDescription: "Write MCP",
    });
    // Create Resource Server
    const resourceServer = userPool.addResourceServer(
      "AgentCoreResourceServer",
      {
        identifier: "agentcore-gateway",
        userPoolResourceServerName: "AgentCore Gateway",
        scopes: [readScope, writeScope],
      },
    );

    const mcpScopes = [
      cognito.OAuthScope.resourceServer(resourceServer, readScope),
      cognito.OAuthScope.resourceServer(resourceServer, writeScope),
    ];

    // M2M Client for testing
    const m2mClient = userPool.addClient("M2MClient", {
      userPoolClientName: `agentcore-m2m`,
      generateSecret: true,
      oAuth: {
        flows: {
          clientCredentials: true,
        },
        scopes: mcpScopes,
      },
    });

    // =============================================================================
    // LAMBDA FUNCTIONS
    // =============================================================================

    // Create Lambda execution role
    const lambdaRole = new iam.Role(this, "McpProxyLambdaRole", {
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaBasicExecutionRole",
        ),
        iam.ManagedPolicy.fromAwsManagedPolicyName("AmazonBedrockFullAccess"),
      ],
    });

    // Add inline policy for AgentCore Identity and Secrets Manager
    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "bedrock-agentcore:CompleteResourceTokenAuth",
          "bedrock-agentcore:GetResourceOauth2Token",
        ],
        resources: ["*"],
      }),
    );

    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["bedrock-agentcore:*"],
        resources: ["*"],
      }),
    );

    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["iam:PassRole"],
        resources: ["*"],
      }),
    );

    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["secretsmanager:GetSecretValue"],
        resources: ["*"],
      }),
    );

    // Scope down these
    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["cognito-idp:*"],
        resources: ["*"],
      }),
    );

    // MCP Proxy Lambda
    const proxyLambda = new lambda.Function(this, "McpProxyLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "lambda_function.lambda_handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "../../lambda"), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            "bash",
            "-c",
            [
              "pip install --target /asset-output boto3 botocore requests --upgrade",
              "cp mcp_proxy_lambda.py /asset-output/lambda_function.py",
            ].join(" && "),
          ],
        },
      }),
      role: lambdaRole,
      timeout: cdk.Duration.seconds(60),
      memorySize: 256,
      environment: {
        GATEWAY_URL: "", // Will be updated after gateway creation
        COGNITO_DOMAIN: `https://${cognitoDomain.domainName}.auth.${this.region}.amazoncognito.com`,
        CLIENT_ID: "", // Will be updated after VS Code client creation
        // CLIENT_SECRET: "",
        CALLBACK_LAMBDA_URL: "", // Will be updated after API Gateway creation
      },
    });

    // Callback Lambda (with bundled boto3 for AgentCore APIs)
    const callbackLambda = new lambda.Function(this, "McpCallbackLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "lambda_function.lambda_handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "../../lambda"), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            "bash",
            "-c",
            [
              "pip install --target /asset-output boto3 botocore requests --upgrade",
              "cp callback_lambda.py /asset-output/lambda_function.py",
            ].join(" && "),
          ],
        },
      }),
      role: lambdaRole,
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });

    // =============================================================================
    // API GATEWAY
    // =============================================================================

    // Create HTTP API
    const httpApi = new apigateway.HttpApi(this, "McpOAuthProxyApi", {
      corsPreflight: {
        allowOrigins: ["*"],
        allowMethods: [
          apigateway.CorsHttpMethod.GET,
          apigateway.CorsHttpMethod.POST,
          apigateway.CorsHttpMethod.OPTIONS,
        ],
        allowHeaders: ["*"],
      },
    });

    // Create Lambda integrations
    const proxyIntegration = new integrations.HttpLambdaIntegration(
      "ProxyIntegration",
      proxyLambda,
    );

    const callbackIntegration = new integrations.HttpLambdaIntegration(
      "CallbackIntegration",
      callbackLambda,
    );

    // Add routes
    httpApi.addRoutes({
      path: "/.well-known/oauth-authorization-server",
      methods: [apigateway.HttpMethod.GET],
      integration: proxyIntegration,
    });

    httpApi.addRoutes({
      path: "/.well-known/oauth-protected-resource",
      methods: [apigateway.HttpMethod.GET],
      integration: proxyIntegration,
    });

    httpApi.addRoutes({
      path: "/authorize",
      methods: [apigateway.HttpMethod.GET],
      integration: proxyIntegration,
    });

    httpApi.addRoutes({
      path: "/callback",
      methods: [apigateway.HttpMethod.GET],
      integration: proxyIntegration,
    });

    httpApi.addRoutes({
      path: "/token",
      methods: [apigateway.HttpMethod.POST],
      integration: proxyIntegration,
    });

    httpApi.addRoutes({
      path: "/register",
      methods: [apigateway.HttpMethod.POST],
      integration: proxyIntegration,
    });

    httpApi.addRoutes({
      path: "/ping",
      methods: [apigateway.HttpMethod.GET],
      integration: callbackIntegration,
    });

    httpApi.addRoutes({
      path: "/userIdentifier/token",
      methods: [apigateway.HttpMethod.POST],
      integration: callbackIntegration,
    });

    // Default route for MCP proxy
    httpApi.addRoutes({
      path: "/{proxy+}",
      methods: [apigateway.HttpMethod.ANY],
      integration: proxyIntegration,
    });

    // Get API endpoint
    const apiEndpoint =
      httpApi.url ||
      `https://${httpApi.httpApiId}.execute-api.${this.region}.amazonaws.com`;

    httpApi.addRoutes({
      path: "/oauth2/callback",
      methods: [apigateway.HttpMethod.GET],
      integration: callbackIntegration,
    });

    proxyLambda.addEnvironment(
      "CALLBACK_LAMBDA_URL",
      apiEndpoint.replace(/\/$/, ""),
    );

    proxyLambda.addEnvironment("USER_POOL_ID", userPool.userPoolId);

    const gatewayRole = new iam.Role(this, "GatewayRole", {
      assumedBy: iam.ServicePrincipal.fromStaticServicePrincipleName(
        "bedrock-agentcore.amazonaws.com",
      ),
      inlinePolicies: {
        getAccessToken: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: [
                "bedrock-agentcore:GetWorkloadAccess*",
                "bedrock-agentcore:GetResourceOauth2Token",
                "secretsmanager:GetSecretValue",
              ],
              resources: ["*"],
              effect: iam.Effect.ALLOW,
            }),
          ],
        }),
      },
    });

    const gateway = new agentcore.Gateway(this, "AgentCoreMcpGateway", {
      gatewayName: `agentcore-mcp-gateway-cimd`,
      description: "AgentCore Gateway for VS Code IDE integration",
      protocolConfiguration: agentcore.GatewayProtocol.mcp({
        searchType: agentcore.McpGatewaySearchType.SEMANTIC,
        supportedVersions: [
          agentcore.MCPProtocolVersion.MCP_2025_03_26,
          agentcore.MCPProtocolVersion.MCP_2025_06_18,
          "2025-11-25" as agentcore.MCPProtocolVersion,
        ],
      }),
      role: gatewayRole,
      exceptionLevel: agentcore.GatewayExceptionLevel.DEBUG,
      authorizerConfiguration: agentcore.GatewayAuthorizer.usingCognito({
        userPool: userPool,
        allowedClients: [m2mClient],
      }),
      // This is not supported for now for 3LO outbound auth
      // authorizerConfiguration: agentcore.GatewayAuthorizer.usingAwsIam(),
    });

    proxyLambda.addEnvironment("GATEWAY_URL", gateway.gatewayUrl ?? "");

    // =============================================================================
    // OUTPUTS
    // =============================================================================

    new cdk.CfnOutput(this, "UserPoolId", {
      value: userPool.userPoolId,
      description: "Cognito User Pool ID",
    });

    new cdk.CfnOutput(this, "UserPoolArn", {
      value: userPool.userPoolArn,
      description: "Cognito User Pool ARN",
    });

    new cdk.CfnOutput(this, "CognitoDomain", {
      value: cognitoDomain.domainName,
      description: "Cognito Domain",
    });

    new cdk.CfnOutput(this, "CognitoDomainUrl", {
      value: `https://${cognitoDomain.domainName}.auth.${this.region}.amazoncognito.com`,
      description: "Cognito Domain URL",
    });

    new cdk.CfnOutput(this, "DiscoveryUrl", {
      value: `https://cognito-idp.${this.region}.amazonaws.com/${userPool.userPoolId}/.well-known/openid-configuration`,
      description: "OIDC Discovery URL",
    });

    new cdk.CfnOutput(this, "M2MClientId", {
      value: m2mClient.userPoolClientId,
      description: "M2M Client ID (for testing)",
    });

    // new cdk.CfnOutput(this, "VSCodeClientId", {
    //   value: vscodeClient.userPoolClientId,
    //   description: "VS Code Client ID",
    // });

    new cdk.CfnOutput(this, "ApiEndpoint", {
      value: apiEndpoint,
      description: "API Gateway Endpoint",
    });

    new cdk.CfnOutput(this, "ProxyLambdaName", {
      value: proxyLambda.functionName,
      description: "MCP Proxy Lambda Function Name",
    });

    new cdk.CfnOutput(this, "CallbackLambdaName", {
      value: callbackLambda.functionName,
      description: "Callback Lambda Function Name",
    });

    new cdk.CfnOutput(this, "VSCodeMcpConfig", {
      value: JSON.stringify(
        {
          servers: {
            [`agentcore-confluence`]: {
              type: "http",
              url: apiEndpoint.replace(/\/$/, "") + "/mcp",
              headers: {
                "MCP-Protocol-Version": "2025-11-25",
              },
            },
          },
        },
        null,
        2,
      ),
      description: "VS Code MCP Configuration (add to .vscode/mcp.json)",
    });

    new cdk.CfnOutput(this, "Gateway", {
      value: gateway.gatewayId,
      description: "Gateway ID",
    });
  }
}
