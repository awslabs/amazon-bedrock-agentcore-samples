import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

/**
 * Lambda@Edge function to rewrite request paths for API Gateway integration
 */
export class OriginRequestFunction extends Construct {
  public readonly function: lambda.Function;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    // Create the Lambda@Edge function
    this.function = new lambda.Function(this, 'Function', {
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.handler',
      code: lambda.Code.fromInline(`
        exports.handler = async (event) => {
          const request = event.Records[0].cf.request;
          
          // Log the original request for debugging
          console.log('Original request:', JSON.stringify(request));
          
          // Check if this is an API request
          if (request.uri.startsWith('/api/')) {
            // Store the original URI for logging
            const originalUri = request.uri;
            
            // Remove the /api prefix and add /v1 prefix
            request.uri = request.uri.replace('/api/', '/v1/');
            
            // Log the modified request for debugging
            console.log('Modified request URI from', originalUri, 'to', request.uri);
            
            // Ensure the host header is set correctly
            if (request.headers && request.headers.host && request.headers.host.length > 0) {
              console.log('Original host header:', request.headers.host[0].value);
              
              // Extract the origin domain from the request
              const originDomain = request.origin.custom.domainName;
              request.headers.host = [{ key: 'Host', value: originDomain }];
              
              console.log('Modified host header to:', originDomain);
            }
            
            // Log all headers for debugging
            console.log('Request headers:', JSON.stringify(request.headers));
            
            // Ensure authorization headers are preserved
            if (request.headers && request.headers.authorization) {
              console.log('Authorization header present:', request.headers.authorization[0].value.substring(0, 20) + '...');
            } else {
              console.log('No authorization header present');
            }
          }
          
          // Log the final request for debugging
          console.log('Final request:', JSON.stringify(request));
          
          return request;
        };
      `),
      description: 'Lambda@Edge function to rewrite API request paths',
    });

    // Add permissions for Lambda@Edge
    const edgeServicePrincipal = new iam.ServicePrincipal('edgelambda.amazonaws.com');
    this.function.grantInvoke(edgeServicePrincipal);

    // Add CloudWatch Logs permissions
    this.function.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['logs:CreateLogGroup', 'logs:CreateLogStream', 'logs:PutLogEvents'],
        resources: ['*'],
      })
    );
  }
}
