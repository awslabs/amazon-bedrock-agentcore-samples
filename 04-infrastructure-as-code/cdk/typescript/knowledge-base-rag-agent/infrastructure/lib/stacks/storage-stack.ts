import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as kms from 'aws-cdk-lib/aws-kms';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ssm from 'aws-cdk-lib/aws-ssm';

export class StorageStack extends cdk.Stack {
  public readonly dataBucket: s3.Bucket;
  public readonly encryptionKey: kms.Key;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Parameter prefix for SSM parameters
    const paramPrefix = '/AgentCoreTemplate';

    // Create KMS key for S3 encryption
    this.encryptionKey = new kms.Key(this, 'EncryptionKey', {
      enableKeyRotation: true,
      description: 'KMS key for Knowledge Base RAG Agent S3 buckets',
      alias: 'alias/knowledge-base-rag-agent-s3',
      policy: new iam.PolicyDocument({
        statements: [
          // Allow root account full access (required for key management)
          new iam.PolicyStatement({
            sid: 'Enable IAM User Permissions',
            effect: iam.Effect.ALLOW,
            principals: [new iam.AccountRootPrincipal()],
            actions: ['kms:*'],
            resources: ['*'],
          }),
          // Allow S3 service to use the key for server-side encryption
          new iam.PolicyStatement({
            sid: 'Allow S3 Service',
            effect: iam.Effect.ALLOW,
            principals: [new iam.ServicePrincipal('s3.amazonaws.com')],
            actions: [
              'kms:Decrypt',
              'kms:DescribeKey',
              'kms:Encrypt',
              'kms:GenerateDataKey',
              'kms:ReEncrypt*',
            ],
            resources: ['*'],
          }),
          // Allow CloudFront OAC to decrypt objects for distribution
          new iam.PolicyStatement({
            sid: 'Allow CloudFront OAC',
            effect: iam.Effect.ALLOW,
            principals: [new iam.ServicePrincipal('cloudfront.amazonaws.com')],
            actions: [
              'kms:Decrypt',
              'kms:DescribeKey',
            ],
            resources: ['*'],
            conditions: {
              StringEquals: {
                'kms:ViaService': [`s3.${this.region}.amazonaws.com`],
              },
            },
          }),
        ],
      }),
    });

    // Create S3 bucket for data storage
    this.dataBucket = new s3.Bucket(this, 'DataBucket', {
      bucketName: cdk.PhysicalName.GENERATE_IF_NEEDED, // Let CloudFormation generate a unique name
      encryption: s3.BucketEncryption.KMS,
      encryptionKey: this.encryptionKey,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      versioned: true,
      enforceSSL: true, // Require SSL/TLS for all requests
      lifecycleRules: [
        {
          id: 'archive-after-90-days',
          transitions: [
            {
              storageClass: s3.StorageClass.INFREQUENT_ACCESS,
              transitionAfter: cdk.Duration.days(30),
            },
            {
              storageClass: s3.StorageClass.GLACIER,
              transitionAfter: cdk.Duration.days(90),
            },
          ],
        },
      ],
    });



    // Store KMS key ARN in SSM Parameter Store for other stacks to use
    new ssm.StringParameter(this, 'EncryptionKeyArnParameter', {
      parameterName: `${paramPrefix}/EncryptionKeyArn`,
      description: 'KMS key ARN for S3 encryption',
      stringValue: this.encryptionKey.keyArn,
    });

    // Store bucket names in SSM Parameter Store
    new ssm.StringParameter(this, 'DataBucketNameParameter', {
      parameterName: `${paramPrefix}/DataBucketName`,
      description: 'Data bucket name',
      stringValue: this.dataBucket.bucketName,
    });



    // Outputs
    new cdk.CfnOutput(this, 'DataBucketName', {
      value: this.dataBucket.bucketName,
      description: 'Data bucket name',
      exportName: `${this.stackName}-DataBucketName`,
    });


  }
}
