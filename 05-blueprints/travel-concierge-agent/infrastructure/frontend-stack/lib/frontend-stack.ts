import * as cdk from 'aws-cdk-lib';
import * as amplify from '@aws-cdk/aws-amplify-alpha';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import * as fs from 'fs';

// Load deployment config
const deploymentConfig = JSON.parse(fs.readFileSync('../../deployment-config.json', 'utf-8'));
const DEPLOYMENT_ID = deploymentConfig.deploymentId;

export class FrontendStack extends cdk.Stack {
  public readonly amplifyApp: amplify.App;
  public readonly amplifyUrl: string;
  public readonly stagingBucket: s3.Bucket;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Add deployment info
    cdk.Tags.of(this).add('DeploymentId', DEPLOYMENT_ID);
    cdk.Tags.of(this).add('DeploymentName', deploymentConfig.deploymentName || DEPLOYMENT_ID);

    // Create staging bucket for Amplify deployments
    this.stagingBucket = new s3.Bucket(this, 'StagingBucket', {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      versioned: true,
      publicReadAccess: false,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      lifecycleRules: [
        {
          id: 'DeleteOldDeployments',
          enabled: true,
          expiration: cdk.Duration.days(30),
        },
      ],
    });

    // Add bucket policy for Amplify access
    this.stagingBucket.addToResourcePolicy(
      new iam.PolicyStatement({
        sid: 'AmplifyAccess',
        effect: iam.Effect.ALLOW,
        principals: [new iam.ServicePrincipal('amplify.amazonaws.com')],
        actions: ['s3:GetObject', 's3:GetObjectVersion'],
        resources: [this.stagingBucket.arnForObjects('*')],
      })
    );

    // Create Amplify app
    this.amplifyApp = new amplify.App(this, 'AmplifyApp', {
      appName: 'concierge-agent-frontend',
      description: 'Concierge Agent - React/Vite Frontend',
      platform: amplify.Platform.WEB,
    });

    // Create main branch
    this.amplifyApp.addBranch('main', {
      stage: 'PRODUCTION',
      branchName: 'main',
    });

    // Predictable domain format
    this.amplifyUrl = `https://main.${this.amplifyApp.appId}.amplifyapp.com`;

    // Outputs
    new cdk.CfnOutput(this, 'AmplifyAppId', {
      value: this.amplifyApp.appId,
      description: 'Amplify App ID',
      exportName: `${this.stackName}-AmplifyAppId`
    });

    new cdk.CfnOutput(this, 'AmplifyUrl', {
      value: this.amplifyUrl,
      description: 'Amplify App URL'
    });

    new cdk.CfnOutput(this, 'StagingBucketName', {
      value: this.stagingBucket.bucketName,
      description: 'S3 Staging Bucket Name',
      exportName: `${this.stackName}-StagingBucketName`
    });
  }
}
