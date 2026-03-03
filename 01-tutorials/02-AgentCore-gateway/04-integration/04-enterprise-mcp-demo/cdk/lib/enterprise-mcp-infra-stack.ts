import * as cdk from "aws-cdk-lib";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as iam from "aws-cdk-lib/aws-iam";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as targets from "aws-cdk-lib/aws-elasticloadbalancingv2-targets";
import * as apigatewayv2 from "aws-cdk-lib/aws-apigatewayv2";
import * as apigatewayv2integrations from "aws-cdk-lib/aws-apigatewayv2-integrations";
import * as certificatemanager from "aws-cdk-lib/aws-certificatemanager";
import * as route53 from "aws-cdk-lib/aws-route53";
import * as route53targets from "aws-cdk-lib/aws-route53-targets";
import { Construct } from "constructs";
import * as path from "path";
import * as agentcore from "@aws-cdk/aws-bedrock-agentcore-alpha";
import * as bedrockl1 from 'aws-cdk-lib/aws-bedrock';
import { AgentCorePolicyEngine } from "./agentcore-policy-engine";

export class EnterpriseMcpInfraStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // =============================================================================
    // CONFIGURATION FROM CONTEXT
    // =============================================================================

    // Deployment type is determined by CDK context variable
    // Use: cdk deploy -c deploymentType=API_GATEWAY
    // Or set in cdk.context.json
    const deploymentType = this.node.tryGetContext("deploymentType") || "ALB";

    if (!["ALB", "API_GATEWAY"].includes(deploymentType)) {
      throw new Error(`Invalid deployment type: ${deploymentType}. Must be ALB or API_GATEWAY`);
    }

    const isAlbDeployment = deploymentType === "ALB";
    const isApiGatewayDeployment = deploymentType === "API_GATEWAY";

    // Domain and infrastructure configuration from context
    const domainName = this.node.tryGetContext("domainName") || "";
    const hostedZoneName = this.node.tryGetContext("hostedZoneName") || "";
    const hostedZoneId = this.node.tryGetContext("hostedZoneId") || "";
    const certificateArn = this.node.tryGetContext("certificateArn") || "";

    // =============================================================================
    // PRE-TOKEN GENERATION LAMBDA
    // =============================================================================

    // Create Lambda execution role for pre-token generation
    const preTokenLambdaRole = new iam.Role(this, "PreTokenLambdaRole", {
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaBasicExecutionRole"
        ),
      ],
    });

    // Pre-Token Generation Lambda
    const preTokenGenerationLambda = new lambda.Function(
      this,
      "PreTokenGenerationLambda",
      {
        runtime: lambda.Runtime.PYTHON_3_12,
        handler: "lambda_function.lambda_handler",
        code: lambda.Code.fromAsset(path.join(__dirname, "../lambda"), {
          bundling: {
            image: lambda.Runtime.PYTHON_3_12.bundlingImage,
            command: [
              "bash",
              "-c",
              [
                "cp pre_token_generation_lambda.py /asset-output/lambda_function.py",
              ].join(" && "),
            ],
          },
        }),
        role: preTokenLambdaRole,
        timeout: cdk.Duration.seconds(60),
        memorySize: 128,
        description: "Lambda to add custom claims to Cognito tokens based on user email",
      }
    );

    // =============================================================================
    // COGNITO USER POOL
    // =============================================================================

    // Create Cognito User Pool
    const userPool = new cognito.UserPool(this, "AgentCoreEnterprisePool", {
      userPoolName: `agentcore-enterprise-pool`,
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

    // Grant Cognito permission to invoke the pre-token generation Lambda
    preTokenGenerationLambda.addPermission("CognitoInvokePermission", {
      principal: new iam.ServicePrincipal("cognito-idp.amazonaws.com"),
      sourceArn: userPool.userPoolArn,

    });

    userPool.addTrigger(cognito.UserPoolOperation.PRE_TOKEN_GENERATION_CONFIG, preTokenGenerationLambda, cognito.LambdaVersion.V3_0);


    // Create Cognito Domain
    const cognitoDomainPrefix = `agentcore-vscode-domain-${this.account}`;
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
      }
    );

    const mcpScopes = [
      cognito.OAuthScope.resourceServer(resourceServer, readScope),
      cognito.OAuthScope.resourceServer(resourceServer, writeScope),
    ];

    // =============================================================================
    // BEDROCK GUARDRAILS
    // =============================================================================

    const guardrails = new bedrockl1.CfnGuardrail(this, "AgentCoreGuardrail", {
      name: "AgentCore-Enterprise-Guardrail",
      description: "Guardrail for AgentCore Enterprise MCP Gateway",
      blockedInputMessaging: "Your request contains content that violates our policies and cannot be processed.",
      blockedOutputsMessaging: "The response contains content that violates our policies and cannot be displayed.",
      sensitiveInformationPolicyConfig:{
        // setting up some example PII entity types to anonymize in responses. This can be customized based on specific requirements.
        piiEntitiesConfig:[
          {
            type: 'ADDRESS',
            action: 'ANONYMIZE',
            inputEnabled: true,
            inputAction: 'ANONYMIZE'
          },
          {
            type: 'NAME',
            action: 'ANONYMIZE',
            inputEnabled: true,
            inputAction: 'ANONYMIZE'
          },
          {
            type: 'EMAIL',
            action: 'ANONYMIZE',
            inputEnabled: true,
            inputAction: 'ANONYMIZE'
          },
          {
            type: 'CREDIT_DEBIT_CARD_NUMBER',
            action: 'BLOCK',
            inputEnabled: true,
            inputAction: 'BLOCK'
          }
        ]
      }
    }
    );

    // =============================================================================
    // LAMBDA FUNCTIONS
    // =============================================================================

    // Create Lambda execution role
    const lambdaRole = new iam.Role(this, "McpProxyLambdaRole", {
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaBasicExecutionRole"
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
      })
    );

    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "bedrock:ApplyGuardrail"
        ],
        resources:[guardrails.attrGuardrailArn]
      }));

    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["bedrock-agentcore:InvokeGateway"],
        resources: ["*"],
      })
    );

    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["secretsmanager:GetSecretValue"],
        resources: ["*"],
      })
    );

    // MCP Proxy Lambda (with increased timeout for ALB)
    const proxyLambda = new lambda.Function(this, "McpProxyLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "lambda_function.lambda_handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "../lambda"), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            "bash",
            "-c",
            ["cp mcp_proxy_lambda.py /asset-output/lambda_function.py"].join(
              " && "
            ),
          ],
        },
      }),
      role: lambdaRole,
      timeout: cdk.Duration.seconds(300), // 5 minutes for ALB
      memorySize: 256,
      environment: {
        GATEWAY_URL: "", // Will be updated after gateway creation
        COGNITO_DOMAIN: `https://${cognitoDomain.domainName}.auth.${this.region}.amazoncognito.com`,
        CLIENT_ID: "", // Will be updated after VS Code client creation
        // CLIENT_SECRET: "",
        CALLBACK_LAMBDA_URL: "", // Will be updated after ALB creation
      },
    });

    // Weather Lambda
    const weatherLambda = new lambda.Function(this, "WeatherLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "lambda_function.lambda_handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "../lambda/mcp-servers/weather"), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            "bash",
            "-c",
            ["cp weather_lambda.py /asset-output/lambda_function.py"].join(
              " && "
            ),
          ],
        },
      }),
      role: lambdaRole,
      timeout: cdk.Duration.seconds(300), // 5 minutes for ALB
      memorySize: 256,
    });

    // Inventory Lambda
    const inventoryLambda = new lambda.Function(this, "InventoryLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "lambda_function.lambda_handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "../lambda/mcp-servers/inventory"), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            "bash",
            "-c",
            ["cp inventory_lambda.py /asset-output/lambda_function.py"].join(
              " && "
            ),
          ],
        },
      }),
      role: lambdaRole,
      timeout: cdk.Duration.seconds(300), // 5 minutes for ALB
      memorySize: 256,
    });

    // User Details Lambda
    const userDetailsLambda = new lambda.Function(this, "UserDetailsLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "lambda_function.lambda_handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "../lambda/mcp-servers/user_details"), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            "bash",
            "-c",
            ["cp user_details_lambda.py /asset-output/lambda_function.py"].join(
              " && "
            ),
          ],
        },
      }),
      role: lambdaRole,
      timeout: cdk.Duration.seconds(300), // 5 minutes for ALB
      memorySize: 256,
    });


    // Interceptor Lambda
    const interceptorLambda = new lambda.Function(this, "McpInterceptorLambda", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "lambda_function.lambda_handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "../lambda/interceptor"), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            "bash",
            "-c",
            ["cp interceptor.py /asset-output/lambda_function.py"].join(
              " && "
            ),
          ],
        },
      }),
      role: lambdaRole,
      timeout: cdk.Duration.seconds(300), // 5 minutes for ALB
      memorySize: 256,
      environment: {
        "GUARDRAIL_ID": guardrails.attrGuardrailId,
        "GUARDRAIL_VERSION": guardrails.attrVersion
      },
    });

    // =============================================================================
    // CONDITIONAL DEPLOYMENT: ALB OR API GATEWAY
    // =============================================================================

    let endpointUrl: string;
    let vpc: ec2.Vpc | undefined;
    let alb: elbv2.ApplicationLoadBalancer | undefined;
    let httpApi: apigatewayv2.HttpApi | undefined;

    if (isAlbDeployment) {
      // =============================================================================
      // VPC AND APPLICATION LOAD BALANCER
      // =============================================================================

      // Create a new VPC with public subnets and internet gateway
      vpc = new ec2.Vpc(this, "McpVpc", {
        maxAzs: 2,
        natGateways: 0,
        subnetConfiguration: [
          {
            name: "Public",
            subnetType: ec2.SubnetType.PUBLIC,
            cidrMask: 24,
          },
        ],
      });

      // Create Application Load Balancer
      alb = new elbv2.ApplicationLoadBalancer(this, "McpOAuthProxyALB", {
        vpc,
        internetFacing: true,
        loadBalancerName: "mcp-oauth-proxy-alb",
      });

      // Import the certificate
      const certificate = certificatemanager.Certificate.fromCertificateArn(
        this,
        "AlbCertificate",
        certificateArn
      );

      // Create HTTPS Listener
      const mainListener = alb.addListener("HttpsListener", {
        port: 443,
        protocol: elbv2.ApplicationProtocol.HTTPS,
        certificates: [certificate],
        defaultAction: elbv2.ListenerAction.fixedResponse(404, {
          contentType: "text/plain",
          messageBody: "Not Found",
        }),
      });

      // Add HTTP listener that redirects to HTTPS
      alb.addListener("HttpListener", {
        port: 80,
        protocol: elbv2.ApplicationProtocol.HTTP,
        defaultAction: elbv2.ListenerAction.redirect({
          protocol: "HTTPS",
          port: "443",
          permanent: true,
        }),
      });

      // Import the hosted zone
      const hostedZone = route53.HostedZone.fromHostedZoneAttributes(
        this,
        "HostedZone",
        {
          hostedZoneId: hostedZoneId,
          zoneName: hostedZoneName,
        }
      );

      // Create DNS record pointing to the ALB
      new route53.ARecord(this, "AlbAliasRecord", {
        zone: hostedZone,
        recordName: domainName,
        target: route53.RecordTarget.fromAlias(
          new route53targets.LoadBalancerTarget(alb)
        ),
      });

      // Create Lambda Target Group
      const proxyTargetGroup = new elbv2.ApplicationTargetGroup(
        this,
        "ProxyTargetGroup",
        {
          vpc,
          targetType: elbv2.TargetType.LAMBDA,
          targets: [new targets.LambdaTarget(proxyLambda)],
          healthCheck: {
            enabled: true,
            path: "/ping",
            interval: cdk.Duration.seconds(300),
          },
        }
      );

      // Grant ALB permission to invoke Lambda
      proxyLambda.grantInvoke(
        new iam.ServicePrincipal("elasticloadbalancing.amazonaws.com")
      );

      // Proxy Lambda routes - specific paths
      mainListener.addTargetGroups("ProxyWellKnownAuthRule", {
        priority: 40,
        conditions: [
          elbv2.ListenerCondition.pathPatterns([
            "/.well-known/oauth-authorization-server",
          ]),
        ],
        targetGroups: [proxyTargetGroup],
      });

      mainListener.addTargetGroups("ProxyWellKnownResourceRule", {
        priority: 50,
        conditions: [
          elbv2.ListenerCondition.pathPatterns([
            "/.well-known/oauth-protected-resource",
          ]),
        ],
        targetGroups: [proxyTargetGroup],
      });

      mainListener.addTargetGroups("ProxyAuthorizeRule", {
        priority: 60,
        conditions: [elbv2.ListenerCondition.pathPatterns(["/authorize"])],
        targetGroups: [proxyTargetGroup],
      });

      mainListener.addTargetGroups("ProxyCallbackRule", {
        priority: 70,
        conditions: [elbv2.ListenerCondition.pathPatterns(["/callback"])],
        targetGroups: [proxyTargetGroup],
      });

      mainListener.addTargetGroups("ProxyTokenRule", {
        priority: 80,
        conditions: [elbv2.ListenerCondition.pathPatterns(["/token"])],
        targetGroups: [proxyTargetGroup],
      });

      mainListener.addTargetGroups("ProxyRegisterRule", {
        priority: 90,
        conditions: [elbv2.ListenerCondition.pathPatterns(["/register"])],
        targetGroups: [proxyTargetGroup],
      });

      // Default catch-all rule for Proxy Lambda
      mainListener.addTargetGroups("ProxyDefaultRule", {
        priority: 100,
        conditions: [elbv2.ListenerCondition.pathPatterns(["/*"])],
        targetGroups: [proxyTargetGroup],
      });

      // Use custom domain as endpoint
      endpointUrl = `https://${domainName}.${hostedZoneName}`;

      // Outputs for ALB
      new cdk.CfnOutput(this, "AlbEndpoint", {
        value: endpointUrl,
        description: "ALB Endpoint (HTTPS with Custom Domain)",
      });

      new cdk.CfnOutput(this, "CustomDomain", {
        value: domainName,
        description: "Custom Domain Name",
      });

      new cdk.CfnOutput(this, "AlbDnsName", {
        value: alb.loadBalancerDnsName,
        description: "ALB DNS Name",
      });
    } else {
      // =============================================================================
      // API GATEWAY HTTP API
      // =============================================================================

      // Create HTTP API
      httpApi = new apigatewayv2.HttpApi(this, "McpHttpApi", {
        apiName: "mcp-oauth-proxy-api",
        description: "MCP OAuth Proxy HTTP API",
        corsPreflight: {
          allowOrigins: ["*"],
          allowMethods: [
            apigatewayv2.CorsHttpMethod.GET,
            apigatewayv2.CorsHttpMethod.POST,
            apigatewayv2.CorsHttpMethod.OPTIONS,
          ],
          allowHeaders: ["*"],
        },
      });

      // Create Lambda integrations
      const proxyIntegration =
        new apigatewayv2integrations.HttpLambdaIntegration(
          "ProxyIntegration",
          proxyLambda
        );

      // Add OAuth and well-known routes
      httpApi.addRoutes({
        path: "/.well-known/oauth-authorization-server",
        methods: [apigatewayv2.HttpMethod.GET],
        integration: proxyIntegration,
      });

      httpApi.addRoutes({
        path: "/.well-known/oauth-protected-resource",
        methods: [apigatewayv2.HttpMethod.GET],
        integration: proxyIntegration,
      });

      httpApi.addRoutes({
        path: "/authorize",
        methods: [apigatewayv2.HttpMethod.GET],
        integration: proxyIntegration,
      });

      httpApi.addRoutes({
        path: "/callback",
        methods: [apigatewayv2.HttpMethod.GET],
        integration: proxyIntegration,
      });

      httpApi.addRoutes({
        path: "/token",
        methods: [apigatewayv2.HttpMethod.POST],
        integration: proxyIntegration,
      });

      httpApi.addRoutes({
        path: "/register",
        methods: [apigatewayv2.HttpMethod.POST],
        integration: proxyIntegration,
      });

      // Default route for MCP proxy (catch-all)
      httpApi.addRoutes({
        path: "/{proxy+}",
        methods: [apigatewayv2.HttpMethod.ANY],
        integration: proxyIntegration,
      });

      // Check if custom domain is provided
      if (domainName && domainName.trim() !== "") {
        // Custom domain setup for API Gateway
        const certificate = certificatemanager.Certificate.fromCertificateArn(
          this,
          "ApiGatewayCertificate",
          certificateArn
        );

        const domainNameResource = new apigatewayv2.DomainName(
          this,
          "ApiGatewayDomain",
          {
            domainName: domainName,
            certificate: certificate,
          }
        );

        new apigatewayv2.ApiMapping(this, "ApiMapping", {
          api: httpApi,
          domainName: domainNameResource,
        });

        // Create DNS record
        const hostedZone = route53.HostedZone.fromHostedZoneAttributes(
          this,
          "HostedZone",
          {
            hostedZoneId: hostedZoneId,
            zoneName: hostedZoneName,
          }
        );

        new route53.ARecord(this, "ApiGatewayAliasRecord", {
          zone: hostedZone,
          recordName: domainName,
          target: route53.RecordTarget.fromAlias(
            new route53targets.ApiGatewayv2DomainProperties(
              domainNameResource.regionalDomainName,
              domainNameResource.regionalHostedZoneId
            )
          ),
        });

        endpointUrl = `https://${domainName}`;

        new cdk.CfnOutput(this, "CustomDomain", {
          value: domainName,
          description: "Custom Domain Name",
        });
      } else {
        // Use default API Gateway URL
        endpointUrl = httpApi.apiEndpoint;
      }

      // Outputs for API Gateway
      new cdk.CfnOutput(this, "ApiGatewayEndpoint", {
        value: endpointUrl,
        description: "API Gateway Endpoint URL",
      });

      new cdk.CfnOutput(this, "ApiGatewayId", {
        value: httpApi.apiId,
        description: "API Gateway ID",
      });

      new cdk.CfnOutput(this, "ApiGatewayDefaultUrl", {
        value: httpApi.apiEndpoint,
        description: "API Gateway Default URL",
      });
    }

    // =============================================================================
    // VS CODE COGNITO CLIENT (with callback URLs)
    // =============================================================================

    const callbackUrls = [
      "http://127.0.0.1:33418",
      "http://127.0.0.1:33418/",
      "http://localhost:33418",
      "http://localhost:33418/",
      `${endpointUrl}/callback`,
      `${endpointUrl}/callback/`,
      "https://vscode.dev/redirect",
      "https://insiders.vscode.dev/redirect",
    ];

    const vscodeClient = userPool.addClient("VSCodeClient", {
      userPoolClientName: `agentcore-vscode`,
      generateSecret: false,
      oAuth: {
        flows: {
          authorizationCodeGrant: true,
        },
        scopes: [
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.PROFILE,
          cognito.OAuthScope.EMAIL,
          cognito.OAuthScope.PHONE,
          ...mcpScopes,
        ],
        callbackUrls: callbackUrls,
      },
      authFlows: {
        userSrp: true,
      },
      supportedIdentityProviders: [
        cognito.UserPoolClientIdentityProvider.COGNITO,
      ],
    });

    // Update Lambda environment variables with VS Code client ID and endpoint
    proxyLambda.addEnvironment("CLIENT_ID", vscodeClient.userPoolClientId);
    proxyLambda.addEnvironment("CALLBACK_LAMBDA_URL", endpointUrl);

    const gatewayRole = new iam.Role(this, "GatewayRole", {
      assumedBy: iam.ServicePrincipal.fromStaticServicePrincipleName(
        "bedrock-agentcore.amazonaws.com"
      ),
      inlinePolicies: {
        getAccessToken: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: [
                "bedrock-agentcore:GetWorkloadAccess*",
                "bedrock-agentcore:GetResourceOauth2Token",
                "bedrock-agentcore:GetPolicyEngine",
                "secretsmanager:GetSecretValue",
                "bedrock-agentcore:AuthorizeAction",
                "bedrock-agentcore:PartiallyAuthorizeActions"
              ],
              resources: ["*"],
              effect: iam.Effect.ALLOW,
            }),
          ],
        }),
      },
    });

    const gateway = new agentcore.Gateway(this, "AgentCoreMcpGateway", {
      gatewayName: `agentcore-mcp-gateway-${this.account}`,
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
        allowedClients: [vscodeClient],
      }),
      interceptorConfigurations: [
        agentcore.LambdaInterceptor.forRequest(interceptorLambda, { passRequestHeaders: true }),
        agentcore.LambdaInterceptor.forResponse(interceptorLambda, { passRequestHeaders: true })
      ],
    });

    const toolSchema = agentcore.ToolSchema.fromInline([
			{
				name: 'get_weather',
				description: "Get weather for a location",
				inputSchema: {
					type: agentcore.SchemaDefinitionType.OBJECT,
					properties: {
						timezone: {
							type: agentcore.SchemaDefinitionType.STRING,
							description: "the location e.g. seattle, wa"
						}
					}
				}
			}
		]);

    gateway.addLambdaTarget("WeatherLambdaTarget", {
      lambdaFunction: weatherLambda,
      gatewayTargetName: "weather-tool",
      toolSchema: toolSchema,
      credentialProviderConfigurations:[agentcore.GatewayCredentialProvider.fromIamRole()]
    });

    const inventoryToolSchema = agentcore.ToolSchema.fromInline([
			{
				name: 'get_inventory',
				description: "Get inventory for a product",
				inputSchema: {
					type: agentcore.SchemaDefinitionType.OBJECT,
					properties: {
						productId: {
							type: agentcore.SchemaDefinitionType.STRING,
							description: "the product ID to check inventory for"
						}
					}
				}
			}
		]);

    const userDetailsToolSchema = agentcore.ToolSchema.fromInline([
      {
        name: 'get_user_email',
        description: "Get user email for a user",
        inputSchema: {
          type: agentcore.SchemaDefinitionType.OBJECT,
          properties: {
            userId: {
              type: agentcore.SchemaDefinitionType.STRING,
              description: "the user ID to get email for"
            }
          }
        }
      },
      {
        name: 'get_user_cc_number',
        description: "Get user credit card number for a user",
        inputSchema: {
          type: agentcore.SchemaDefinitionType.OBJECT,
          properties: {
            userId: {
              type: agentcore.SchemaDefinitionType.STRING,
              description: "the user ID to get credit card number for"
            }
          }
        }
      }
    ]);

    gateway.addLambdaTarget("InventoryLambdaTarget", {
      lambdaFunction: inventoryLambda,
      gatewayTargetName: "inventory-tool",
      toolSchema: inventoryToolSchema,
      credentialProviderConfigurations:[agentcore.GatewayCredentialProvider.fromIamRole()]
    });

    gateway.addLambdaTarget("UserDetailsLambdaTarget", {
      lambdaFunction: userDetailsLambda,
      gatewayTargetName: "user-details-tool",
      toolSchema: userDetailsToolSchema,
      credentialProviderConfigurations:[agentcore.GatewayCredentialProvider.fromIamRole()]
    });

    proxyLambda.addEnvironment("GATEWAY_URL", gateway.gatewayUrl ?? "");

    // Create policy engine
    const agentCorePolicyEngine = new AgentCorePolicyEngine(this, "AgentCorePolicyEngine", {
      policyEngineName: `enterprise_mcp_policy_engine`,
      description: "Policy engine for AgentCore Enterprise MCP Gateway",
      region: this.region,
      gatewayRole: gatewayRole,
    });

    // Add policies to the engine FIRST
    const policyEngineStatementInventoryTool = `permit (principal is AgentCore::OAuthUser, action in [AgentCore::Action::"inventory-tool", AgentCore::Action::"weather-tool"],resource == AgentCore::Gateway::"${gateway.gatewayArn}") when {principal.hasTag("user_tag") && principal.getTag("user_tag") == "admin_user"};`;
    const policyEngineStatementWeatherTool = `permit (principal is AgentCore::OAuthUser,action in [AgentCore::Action::"weather-tool"],resource == AgentCore::Gateway::"${gateway.gatewayArn}") when {principal.hasTag("user_tag") && principal.getTag("user_tag") == "regular_user"};`;
    const policyEngineStatementUserDetailsTool = `permit (principal is AgentCore::OAuthUser,action in [AgentCore::Action::"user-details-tool"],resource == AgentCore::Gateway::"${gateway.gatewayArn}") when {principal.hasTag("user_tag")};`;

    // Add admin user policy (inventory and weather tools)
    const adminUserPolicy = agentCorePolicyEngine.addPolicy(
      "admin_user_policy",
      "Policy for admin users to access inventory and weather tools",
      policyEngineStatementInventoryTool
    );

    // Add regular user policy (weather tool only)
    const regularUserPolicy = agentCorePolicyEngine.addPolicy(
      "regular_user_policy",
      "Policy for regular users to access weather tool only",
      policyEngineStatementWeatherTool
    );

    // Add user details tool policy (only users with user_tag can access)
    const userDetailsToolPolicy = agentCorePolicyEngine.addPolicy(
      "user_details_policy",
      "Policy for users to access user details tool only if they have user_tag defined",
      policyEngineStatementUserDetailsTool
    );

    // Associate with gateway AFTER all policies are added
    agentCorePolicyEngine.associateWithGateway(gateway.gatewayId, 'ENFORCE');
    agentCorePolicyEngine.node.addDependency(interceptorLambda); // Ensure interceptor Lambda is created before policy engine association

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

    new cdk.CfnOutput(this, "VSCodeClientId", {
      value: vscodeClient.userPoolClientId,
      description: "VS Code Client ID",
    });

    new cdk.CfnOutput(this, "DeploymentTypeOutput", {
      value: deploymentType,
      description: "Deployment Type (ALB or API_GATEWAY)",
    });

    new cdk.CfnOutput(this, "EndpointUrl", {
      value: endpointUrl,
      description: "Service Endpoint URL",
    });

    new cdk.CfnOutput(this, "ProxyLambdaName", {
      value: proxyLambda.functionName,
      description: "MCP Proxy Lambda Function Name",
    });

    new cdk.CfnOutput(this, "VSCodeMcpConfig", {
      value: JSON.stringify(
        {
          servers: {
            [`enterprise-mcp-server`]: {
              type: "http",
              url: endpointUrl + "/mcp",
            },
          },
        },
        null,
        2
      ),
      description: "VS Code MCP Configuration (add to .vscode/mcp.json)",
    });

    new cdk.CfnOutput(this, "Gateway", {
      value: gateway.gatewayId,
      description: "Gateway ID",
    });

    new cdk.CfnOutput(this, "PreTokenGenerationLambdaName", {
      value: preTokenGenerationLambda.functionName,
      description: "Pre-Token Generation Lambda Function Name",
    });

    new cdk.CfnOutput(this, "PreTokenGenerationLambdaArn", {
      value: preTokenGenerationLambda.functionArn,
      description: "Pre-Token Generation Lambda Function ARN",
    });
  }
}
