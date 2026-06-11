import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import * as path from 'path';

export class InfrastructureStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;
  public readonly database: rds.DatabaseInstance;
  public readonly dbSecret: secretsmanager.Secret;
  public readonly receiptsBucket: s3.Bucket;
  public readonly apiLambda?: lambda.Function;
  public readonly api?: apigateway.RestApi;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Create VPC with public and private subnets
    this.vpc = new ec2.Vpc(this, 'RtpOverlayVpc', {
      maxAzs: 2,
      natGateways: 1,
      enableDnsHostnames: true,  // ✅ Enable DNS hostnames
      enableDnsSupport: true,    // ✅ Enable DNS resolution
      subnetConfiguration: [
        {
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
          cidrMask: 24,
        },
        {
          name: 'Private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
          cidrMask: 24,
        },
        {
          name: 'Database',
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
          cidrMask: 24,
        },
      ],
    });

    // Create VPC Endpoint for Bedrock AgentCore with Private DNS enabled
    this.vpc.addInterfaceEndpoint('BedrockAgentCoreEndpoint', {
      service: new ec2.InterfaceVpcEndpointService('com.amazonaws.us-east-1.bedrock-agentcore'),
      privateDnsEnabled: true,  // ✅ CRITICAL: Enable private DNS
      subnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
    });

    // Create database credentials secret
    this.dbSecret = new secretsmanager.Secret(this, 'DbSecret', {
      secretName: 'rtp-overlay-db-credentials',
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ username: 'rtpadmin' }),
        generateStringKey: 'password',
        excludePunctuation: true,
        includeSpace: false,
        passwordLength: 32,
      },
    });

    // Create security group for RDS
    const dbSecurityGroup = new ec2.SecurityGroup(this, 'DbSecurityGroup', {
      vpc: this.vpc,
      description: 'Security group for RTP Overlay RDS instance',
      allowAllOutbound: true,
    });

    // Allow connections from within VPC
    dbSecurityGroup.addIngressRule(
      ec2.Peer.ipv4(this.vpc.vpcCidrBlock),
      ec2.Port.tcp(5432),
      'Allow PostgreSQL access from VPC'
    );

    // Create security group for Lambda functions
    const lambdaSecurityGroup = new ec2.SecurityGroup(this, 'LambdaSecurityGroup', {
      vpc: this.vpc,
      description: 'Security group for Lambda functions',
      allowAllOutbound: true,
    });

    // Allow Lambda to connect to RDS
    dbSecurityGroup.addIngressRule(
      lambdaSecurityGroup,
      ec2.Port.tcp(5432),
      'Allow Lambda access to RDS'
    );

    // Create RDS PostgreSQL instance
    this.database = new rds.DatabaseInstance(this, 'RtpOverlayDatabase', {
      engine: rds.DatabaseInstanceEngine.postgres({
        version: rds.PostgresEngineVersion.VER_15,
      }),
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
      vpc: this.vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
      },
      securityGroups: [dbSecurityGroup],
      credentials: rds.Credentials.fromSecret(this.dbSecret),
      databaseName: 'rtpoverlay',
      allocatedStorage: 20,
      maxAllocatedStorage: 100,
      storageEncrypted: true,
      backupRetention: cdk.Duration.days(7),
      deleteAutomatedBackups: true,
      removalPolicy: cdk.RemovalPolicy.SNAPSHOT,
      deletionProtection: false,
      publiclyAccessible: false,
    });

    // Create S3 bucket for receipt documents
    this.receiptsBucket = new s3.Bucket(this, 'ReceiptsBucket', {
      bucketName: `rtp-overlay-receipts-${this.account}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN, // Keep bucket on stack deletion
      autoDeleteObjects: false, // Don't auto-delete objects
      lifecycleRules: [
        {
          id: 'DeleteOldVersions',
          noncurrentVersionExpiration: cdk.Duration.days(90),
        },
      ],
      cors: [
        {
          allowedMethods: [s3.HttpMethods.GET, s3.HttpMethods.PUT, s3.HttpMethods.POST],
          allowedOrigins: ['*'], // Update with your frontend domain in production
          allowedHeaders: ['*'],
          maxAge: 3000,
        },
      ],
    });

    // Outputs
    new cdk.CfnOutput(this, 'VpcId', {
      value: this.vpc.vpcId,
      description: 'VPC ID',
      exportName: 'RtpOverlayVpcId',
    });

    new cdk.CfnOutput(this, 'DatabaseEndpoint', {
      value: this.database.dbInstanceEndpointAddress,
      description: 'RDS Database Endpoint',
      exportName: 'RtpOverlayDbEndpoint',
    });

    new cdk.CfnOutput(this, 'DatabasePort', {
      value: this.database.dbInstanceEndpointPort,
      description: 'RDS Database Port',
      exportName: 'RtpOverlayDbPort',
    });

    new cdk.CfnOutput(this, 'DatabaseSecretArn', {
      value: this.dbSecret.secretArn,
      description: 'Database credentials secret ARN',
      exportName: 'RtpOverlayDbSecretArn',
    });

    new cdk.CfnOutput(this, 'ReceiptsBucketName', {
      value: this.receiptsBucket.bucketName,
      description: 'S3 bucket for receipt documents',
      exportName: 'RtpOverlayReceiptsBucket',
    });

    new cdk.CfnOutput(this, 'ReceiptsBucketArn', {
      value: this.receiptsBucket.bucketArn,
      description: 'S3 bucket ARN',
      exportName: 'RtpOverlayReceiptsBucketArn',
    });

    // Export VPC configuration for Lambda deployments
    new cdk.CfnOutput(this, 'PrivateSubnetIds', {
      value: this.vpc.privateSubnets.map(subnet => subnet.subnetId).join(','),
      description: 'Private subnet IDs for Lambda functions',
      exportName: 'RtpOverlayPrivateSubnetIds',
    });

    new cdk.CfnOutput(this, 'LambdaSecurityGroupId', {
      value: lambdaSecurityGroup.securityGroupId,
      description: 'Security group ID for Lambda functions',
      exportName: 'RtpOverlayLambdaSecurityGroupId',
    });

    // Note: Lambda function will be added in a separate deployment
    // after the backend code is built and ready
    new cdk.CfnOutput(this, 'NextSteps', {
      value: 'Infrastructure deployed! Next: Deploy Lambda function with backend code',
      description: 'Next deployment steps',
    });
  }
}
