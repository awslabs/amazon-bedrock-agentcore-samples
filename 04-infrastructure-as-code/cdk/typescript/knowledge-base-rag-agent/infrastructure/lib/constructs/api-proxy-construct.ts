import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export interface ApiProxyConstructProps {
  /**
   * The API endpoint to proxy requests to
   */
  apiEndpoint: string;

  /**
   * The allowed origins for CORS
   */
  allowedOrigins: string[];

  /**
   * The name of the API Gateway
   */
  apiName?: string;
}

/**
 * A construct that creates a serverless proxy for API requests
 */
export class ApiProxyConstruct extends Construct {
  /**
   * The API Gateway instance
   */
  public readonly api: apigateway.RestApi;

  /**
   * The Lambda function that handles the proxy requests
   */
  public readonly proxyFunction: lambda.Function;

  /**
   * The URL of the API Gateway
   */
  public readonly apiUrl: string;

  constructor(scope: Construct, id: string, props: ApiProxyConstructProps) {
    super(scope, id);

    // Create the Lambda function for the proxy
    this.proxyFunction = new lambda.Function(this, 'ProxyFunction', {
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.handler',
      code: lambda.Code.fromInline(`
const https = require('https');
const url = require('url');

exports.handler = async (event) => {
  console.log('Event:', JSON.stringify(event));
  
  try {
    // Get the target API endpoint from environment variable
    const targetApiEndpoint = process.env.TARGET_API_ENDPOINT;
    if (!targetApiEndpoint) {
      return {
        statusCode: 500,
        headers: getCorsHeaders(event),
        body: JSON.stringify({ error: 'Target API endpoint not configured' })
      };
    }
    
    // Parse the target URL
    const targetUrl = new url.URL(targetApiEndpoint);
    
    // Get the path and query parameters from the event
    const path = event.path || '';
    const queryParams = event.queryStringParameters || {};
    
    // Build the target path
    let targetPath = path;
    if (event.pathParameters && event.pathParameters.proxy) {
      targetPath = event.pathParameters.proxy;
    }
    
    // Remove leading slash if present
    if (targetPath.startsWith('/')) {
      targetPath = targetPath.substring(1);
    }
    
    // Build the full URL
    const fullUrl = \`\${targetApiEndpoint}/\${targetPath}\`;
    console.log('Proxying request to:', fullUrl);
    
    // Get the HTTP method
    const method = event.httpMethod || 'GET';
    
    // Get the request body
    const body = event.body ? (event.isBase64Encoded ? Buffer.from(event.body, 'base64').toString() : event.body) : null;
    
    // Get the headers
    const headers = event.headers || {};
    
    // Remove host header as it will be set by the https module
    delete headers.host;
    
    // Forward the request
    const response = await makeRequest(fullUrl, method, headers, body);
    
    // Return the response
    return {
      statusCode: response.statusCode,
      headers: {
        ...response.headers,
        ...getCorsHeaders(event)
      },
      body: response.body
    };
  } catch (error) {
    console.error('Error:', error);
    
    return {
      statusCode: 500,
      headers: getCorsHeaders(event),
      body: JSON.stringify({ 
        error: 'Internal server error',
        message: error.message,
        stack: process.env.NODE_ENV === 'development' ? error.stack : undefined
      })
    };
  }
};

function getCorsHeaders(event) {
  const origin = event.headers && (event.headers.Origin || event.headers.origin);
  const allowedOrigins = process.env.ALLOWED_ORIGINS ? process.env.ALLOWED_ORIGINS.split(',') : [];
  
  // Check if the origin is allowed
  const allowOrigin = origin && (allowedOrigins.includes('*') || allowedOrigins.includes(origin)) 
    ? origin 
    : allowedOrigins[0] || '*';
  
  return {
    'Access-Control-Allow-Origin': allowOrigin,
    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,Access-Control-Allow-Origin,Access-Control-Allow-Headers,Access-Control-Allow-Methods,Origin,Accept',
    'Access-Control-Allow-Methods': 'OPTIONS,GET,PUT,POST,DELETE,PATCH,HEAD',
    'Access-Control-Allow-Credentials': 'true',
    'Access-Control-Max-Age': '600'
  };
}

function makeRequest(url, method, headers, body) {
  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(url);
    
    const options = {
      hostname: parsedUrl.hostname,
      port: parsedUrl.port || 443,
      path: \`\${parsedUrl.pathname}\${parsedUrl.search}\`,
      method: method,
      headers: headers
    };
    
    const req = https.request(options, (res) => {
      let responseBody = '';
      
      res.on('data', (chunk) => {
        responseBody += chunk;
      });
      
      res.on('end', () => {
        resolve({
          statusCode: res.statusCode,
          headers: res.headers,
          body: responseBody
        });
      });
    });
    
    req.on('error', (error) => {
      reject(error);
    });
    
    if (body) {
      req.write(body);
    }
    
    req.end();
  });
}
      `),
      environment: {
        TARGET_API_ENDPOINT: props.apiEndpoint,
        ALLOWED_ORIGINS: props.allowedOrigins.join(','),
        NODE_ENV: 'production',
      },
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });

    // Create a policy to allow the Lambda function to make HTTP requests
    const policy = new iam.PolicyStatement({
      actions: ['logs:CreateLogGroup', 'logs:CreateLogStream', 'logs:PutLogEvents'],
      resources: ['*'],
    });

    this.proxyFunction.addToRolePolicy(policy);

    // Create a role for API Gateway CloudWatch logging
    const apiGatewayLoggingRole = new iam.Role(this, 'ApiGatewayLoggingRole', {
      assumedBy: new iam.ServicePrincipal('apigateway.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          'service-role/AmazonAPIGatewayPushToCloudWatchLogs'
        ),
      ],
    });

    // Create the API Gateway
    this.api = new apigateway.RestApi(this, 'ProxyApi', {
      restApiName: props.apiName || 'API Proxy',
      description: 'Proxy API for Bedrock Agent Assistant',
      cloudWatchRole: true,
      defaultCorsPreflightOptions: {
        allowOrigins: props.allowedOrigins,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: [
          'Content-Type',
          'X-Amz-Date',
          'Authorization',
          'X-Api-Key',
          'X-Amz-Security-Token',
          'Access-Control-Allow-Origin',
          'Access-Control-Allow-Headers',
          'Access-Control-Allow-Methods',
          'Origin',
          'Accept',
        ],
        allowCredentials: true,
        maxAge: cdk.Duration.seconds(600),
      },
      deployOptions: {
        stageName: 'prod',
        metricsEnabled: true,
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        dataTraceEnabled: true,
      },
    });

    // Add a proxy resource to the API Gateway
    const proxyResource = this.api.root.addResource('{proxy+}');

    // Add a method to the proxy resource
    proxyResource.addMethod('ANY', new apigateway.LambdaIntegration(this.proxyFunction));

    // Add a method to the root resource
    this.api.root.addMethod('ANY', new apigateway.LambdaIntegration(this.proxyFunction));

    // Set the API URL
    this.apiUrl = `${this.api.url}`;

    // Output the API URL
    new cdk.CfnOutput(this, 'ApiProxyUrl', {
      value: this.apiUrl,
      description: 'The URL of the API Proxy',
    });
  }
}
