import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export class VisaLambdaStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const deploymentId = this.node.tryGetContext('deploymentId') || 'default';

    // Lambda function for Visa proxy - using standard Python runtime with ZIP deployment
    const visaLambda = new lambda.Function(this, 'VisaProxyLambda', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'handler.handler',
      code: lambda.Code.fromAsset('../../concierge_agent/local-visa-server', {
        bundling: {
          image: lambda.Runtime.PYTHON_3_11.bundlingImage,
          command: [
            'bash', '-c',
            [
              // Install dependencies with correct platform binaries
              'pip install -r requirements.txt --platform manylinux2014_x86_64 --only-binary=:all: --target /asset-output',
              // Copy Python source files (exclude __pycache__)
              'cp *.py /asset-output/',
              // Copy visa module (exclude __pycache__)
              'rsync -av --exclude="__pycache__" --exclude="*.pyc" --exclude="*.pyo" visa/ /asset-output/visa/',
              // Copy config directory
              'cp -r config /asset-output/',
            ].join(' && ')
          ],
        },
      }),
      timeout: cdk.Duration.seconds(30),
      memorySize: 512,
      environment: {
        CLIENT_APP_ID: 'VICTestAccountTR',
        // AWS_REGION is automatically set by Lambda runtime
      },
      description: 'Visa Payment API Proxy Lambda',
    });

    // Grant Secrets Manager access for Visa credentials
    visaLambda.addToRolePolicy(new iam.PolicyStatement({
      actions: ['secretsmanager:GetSecretValue'],
      resources: [
        // Allow access to visa/* secrets (where actual Visa credentials are stored)
        `arn:aws:secretsmanager:${this.region}:${this.account}:secret:visa/*`,
        // Also allow access to deployment-specific secrets if they exist
        `arn:aws:secretsmanager:${this.region}:${this.account}:secret:concierge-agent/${deploymentId}/visa/*`,
      ],
    }));

    // API Gateway REST API
    const api = new apigateway.RestApi(this, 'VisaProxyApi', {
      restApiName: 'Visa Proxy API',
      description: 'Proxy for Visa Payment API calls',
      deployOptions: {
        stageName: 'prod',
        tracingEnabled: true,
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        metricsEnabled: true,
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS, // Allow all origins for simplicity
        allowMethods: ['GET', 'POST', 'OPTIONS'],
        allowHeaders: ['Content-Type', 'Authorization', 'X-Amz-Date', 'X-Api-Key'],
        allowCredentials: false,
      },
    });

    // Add /api/visa/* proxy resource
    const apiResource = api.root.addResource('api');
    const visaResource = apiResource.addResource('visa');

    // Add proxy+ to catch all paths under /api/visa/
    visaResource.addProxy({
      defaultIntegration: new apigateway.LambdaIntegration(visaLambda, {
        timeout: cdk.Duration.seconds(29),
        proxy: true,
      }),
      anyMethod: true,
    });

    // Add CORS headers to Gateway error responses (4XX, 5XX)
    // This ensures CORS headers are present even when Lambda returns errors
    const corsHeaders = {
      'Access-Control-Allow-Origin': "'*'",
      'Access-Control-Allow-Headers': "'Content-Type,Authorization'",
      'Access-Control-Allow-Methods': "'GET,POST,OPTIONS'",
    };

    // Add CORS to all error response types
    api.addGatewayResponse('Default4xx', {
      type: apigateway.ResponseType.DEFAULT_4XX,
      responseHeaders: corsHeaders,
    });

    api.addGatewayResponse('Default5xx', {
      type: apigateway.ResponseType.DEFAULT_5XX,
      responseHeaders: corsHeaders,
    });

    // CloudFormation Outputs
    new cdk.CfnOutput(this, 'VisaProxyApiUrl', {
      value: api.url,
      description: 'Visa Proxy API Gateway URL (use this in frontend VITE_VISA_PROXY_URL)',
      exportName: `VisaProxyApiUrl-${deploymentId}`,
    });

    new cdk.CfnOutput(this, 'VisaLambdaFunctionName', {
      value: visaLambda.functionName,
      description: 'Visa Lambda Function Name',
      exportName: `VisaLambdaFunctionName-${deploymentId}`,
    });

    new cdk.CfnOutput(this, 'VisaLambdaArn', {
      value: visaLambda.functionArn,
      description: 'Visa Lambda Function ARN',
      exportName: `VisaLambdaArn-${deploymentId}`,
    });
  }
}
