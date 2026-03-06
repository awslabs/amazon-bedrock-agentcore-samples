import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as path from 'path';
import { CorsCloudFrontConfig } from '../constructs/cors-cloudfront-config';

export interface WebConsoleStackProps extends cdk.StackProps {
  userPoolId: string;
  userPoolClientId: string;
  identityPoolId: string;
  apiGatewayId: string;
}

export class WebConsoleStack extends cdk.Stack {
  public readonly distributionUrl: string;

  constructor(scope: Construct, id: string, props: WebConsoleStackProps) {
    super(scope, id, props);

    const { userPoolId, userPoolClientId, identityPoolId, apiGatewayId } = props;

    // Parameter prefix for SSM parameters
    const paramPrefix = '/AgentCoreTemplate';

    // Import KMS key from storage stack for consistent encryption
    const encryptionKeyArn = ssm.StringParameter.valueForStringParameter(
      this,
      `${paramPrefix}/EncryptionKeyArn`
    );
    const encryptionKey = kms.Key.fromKeyArn(this, 'ImportedEncryptionKey', encryptionKeyArn);

    // S3 bucket for static website hosting with SSE-KMS encryption
    const websiteBucket = new s3.Bucket(this, 'WebsiteBucket', {
      encryption: s3.BucketEncryption.KMS,
      encryptionKey: encryptionKey,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      enforceSSL: true, // Require SSL/TLS for all requests
    });

    // Origin Access Control for CloudFront
    const originAccessControl = new cloudfront.S3OriginAccessControl(this, 'OAC', {
      description: 'OAC for Bedrock Agent web console',
    });

    // S3 Origin for static content using modern S3BucketOrigin
    const webBucketOrigin = origins.S3BucketOrigin.withOriginAccessControl(websiteBucket, {
      originAccessControl: originAccessControl,
    });

    // Import API Gateway by ID to avoid hard dependency
    const apiGateway = apigateway.RestApi.fromRestApiId(this, 'ImportedApi', apiGatewayId);

    // Use the CORS CloudFront construct
    const corsCloudFront = new CorsCloudFrontConfig(this, 'CorsCloudFront', {
      apiGateway: apiGateway,
      bedrockApiGateway: apiGateway,
      webBucketOrigin: webBucketOrigin,
      apiStageName: 'v1',
    });

    const distribution = corsCloudFront.distribution;

    // Create configuration file for the web app
    const webConfig = {
      apiUrl: `/api`, // Use CloudFront path instead of direct API Gateway URL
      userPoolId,
      userPoolClientId,
      identityPoolId,
      region: this.region,
      // Environment variables for Next.js
      NEXT_PUBLIC_API_ENDPOINT: `/api`,
      NEXT_PUBLIC_BEDROCK_AGENT_API_URL: `/api`,
      NEXT_PUBLIC_COGNITO_REGION: this.region,
      NEXT_PUBLIC_COGNITO_USER_POOL_ID: userPoolId,
      NEXT_PUBLIC_COGNITO_USER_POOL_WEB_CLIENT_ID: userPoolClientId,
      NEXT_PUBLIC_COGNITO_IDENTITY_POOL_ID: identityPoolId,
      NEXT_PUBLIC_ENVIRONMENT: 'production',
      NEXT_PUBLIC_REGION: this.region,
    };

    // Deploy all static website files in a single deployment
    // S3 automatically detects content types based on file extensions
    const websiteDeployment = new s3deploy.BucketDeployment(this, 'WebsiteDeployment', {
      sources: [s3deploy.Source.asset(path.join(__dirname, '../../../web-console/build'))],
      destinationBucket: websiteBucket,
      memoryLimit: 512,
      ephemeralStorageSize: cdk.Size.mebibytes(1024),
    });

    // Deploy config.json separately to ensure it has the correct content type
    const configDeployment = new s3deploy.BucketDeployment(this, 'ConfigDeployment', {
      sources: [s3deploy.Source.jsonData('config.json', webConfig)],
      destinationBucket: websiteBucket,
      prune: false, // Don't delete other files
      contentType: 'application/json',
      cacheControl: [
        s3deploy.CacheControl.setPublic(),
        s3deploy.CacheControl.maxAge(cdk.Duration.hours(1)),
      ],
      memoryLimit: 512,
      ephemeralStorageSize: cdk.Size.mebibytes(1024),
      // Force redeploy by adding a comment
    });

    // Ensure config is deployed after website files
    configDeployment.node.addDependency(websiteDeployment);

    // Grant KMS permissions to BucketDeployment Lambda functions
    encryptionKey.grantEncryptDecrypt(websiteDeployment.handlerRole);
    encryptionKey.grantEncryptDecrypt(configDeployment.handlerRole);

    this.distributionUrl = `https://${distribution.distributionDomainName}`;

    // Outputs
    new cdk.CfnOutput(this, 'WebsiteUrl', {
      value: this.distributionUrl,
      description: 'CloudFront distribution URL for web console',
    });

    new cdk.CfnOutput(this, 'DistributionId', {
      value: distribution.distributionId,
      description: 'CloudFront distribution ID for cache invalidation',
    });

    new cdk.CfnOutput(this, 'WebsiteBucketName', {
      value: websiteBucket.bucketName,
      description: 'S3 bucket for web console static files',
    });
  }
}
