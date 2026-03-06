import * as cdk from 'aws-cdk-lib';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import { Construct } from 'constructs';

export interface CorsCloudFrontConfigProps {
  apiGateway: apigateway.IRestApi;
  bedrockApiGateway?: apigateway.IRestApi;
  allowedOrigins?: string[];
  webBucketOrigin: cloudfront.IOrigin;
  apiStageName?: string;
}

export class CorsCloudFrontConfig extends Construct {
  public readonly distribution: cloudfront.Distribution;

  constructor(scope: Construct, id: string, props: CorsCloudFrontConfigProps) {
    super(scope, id);

    // Configuration for CloudFront and CORS

    // Start with the provided origins or an empty array
    let allowedOrigins = props.allowedOrigins || [];

    // Always add localhost for development
    allowedOrigins.push('http://localhost:3000');

    // Remove duplicates
    allowedOrigins = [...new Set(allowedOrigins)];

    const corsHeadersPolicy = new cloudfront.ResponseHeadersPolicy(this, 'CorsHeadersPolicy', {
      corsBehavior: {
        accessControlAllowOrigins: allowedOrigins.length > 0 ? allowedOrigins : ['*'], // Use specific origins if available, otherwise allow all
        accessControlAllowMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
        accessControlAllowHeaders: [
          'Content-Type',
          'Authorization',
          'X-Api-Key',
          'X-Amz-Security-Token',
          'Accept',
          'Origin',
          'Referer',
          'User-Agent',
        ],
        accessControlAllowCredentials: true,
        accessControlMaxAge: cdk.Duration.seconds(600),
        originOverride: true,
      },
    });

    // Create API Gateway origin using HttpOrigin
    const apiDomain = `${props.apiGateway.restApiId}.execute-api.${cdk.Stack.of(this).region}.amazonaws.com`;
    const apiGatewayOrigin = new origins.HttpOrigin(apiDomain, {
      originPath: `/${props.apiStageName || 'v1'}`,
    });

    // Initialize empty behaviors object
    const additionalBehaviors: Record<string, cloudfront.BehaviorOptions> = {};

    // Add Bedrock API behavior if provided
    if (props.bedrockApiGateway) {
      const bedrockApiDomain = `${props.bedrockApiGateway.restApiId}.execute-api.${cdk.Stack.of(this).region}.amazonaws.com`;
      const bedrockApiGatewayOrigin = new origins.HttpOrigin(bedrockApiDomain, {
        originPath: `/${props.apiStageName || 'v1'}`,
      });

      // Add specific paths for chat session API first (more specific patterns)
      additionalBehaviors['/api/session'] = {
        origin: bedrockApiGatewayOrigin,
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
        cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
        cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
        originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
        responseHeadersPolicy: corsHeadersPolicy,
      };

      additionalBehaviors['/api/chat'] = {
        origin: bedrockApiGatewayOrigin,
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
        cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
        cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
        originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
        responseHeadersPolicy: corsHeadersPolicy,
      };

      additionalBehaviors['/api/bedrock-agent/*'] = {
        origin: bedrockApiGatewayOrigin,
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
        cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
        cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
        originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
        responseHeadersPolicy: corsHeadersPolicy,
      };
    }

    // Add root API behavior for exact /api path
    additionalBehaviors['/api'] = {
      origin: apiGatewayOrigin,
      viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
      allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
      cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
      cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
      originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
      responseHeadersPolicy: corsHeadersPolicy,
    };

    // Add general API behavior last (less specific pattern)
    additionalBehaviors['/api/*'] = {
      origin: apiGatewayOrigin,
      viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
      allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
      cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
      cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
      originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
      responseHeadersPolicy: corsHeadersPolicy,
    };

    // Create the CloudFront distribution with S3 origin as default and API Gateway for API paths
    this.distribution = new cloudfront.Distribution(this, 'Distribution', {
      defaultBehavior: {
        origin: props.webBucketOrigin,
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
        cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
        compress: true,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        responseHeadersPolicy: corsHeadersPolicy,
      },
      additionalBehaviors: additionalBehaviors,
      defaultRootObject: 'index.html',
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.seconds(300),
        },
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.seconds(300),
        },
        {
          httpStatus: 500,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.seconds(300),
        },
      ],
    });
  }
}
