import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import * as path from 'path';

interface GRProcessingStackProps extends cdk.StackProps {
  rtpApiUrl: string;
  inputBucketName?: string;
}

export class GRProcessingStack extends cdk.Stack {
  public readonly grProcessingLambda: lambda.Function;
  public readonly inputBucket: s3.Bucket;

  constructor(scope: Construct, id: string, props: GRProcessingStackProps) {
    super(scope, id, props);

    // Create S3 input bucket for GR uploads
    const inputBucketName = props.inputBucketName || `rtp-overlay-receipts-input-${this.account}`;
    this.inputBucket = new s3.Bucket(this, 'GRInputBucket', {
      bucketName: inputBucketName,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: false,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // Create Lambda execution role
    const lambdaRole = new iam.Role(this, 'GRLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Grant Bedrock permissions
    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ['bedrock:InvokeModel'],
        resources: [
          `arn:aws:bedrock:*::foundation-model/*`,
          `arn:aws:bedrock:${this.region}:${this.account}:inference-profile/*`,
        ],
      })
    );

    // Create Lambda function for GR processing
    this.grProcessingLambda = new lambda.Function(this, 'GRProcessingLambda', {
      functionName: 'rtp-overlay-gr-processor',
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'lambda_goods_receipt.lambda_handler',
      role: lambdaRole,
      code: lambda.Code.fromAsset(path.join(__dirname, '../../python'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_11.bundlingImage,
          command: [
            'bash',
            '-c',
            'pip install -r requirements.txt -t /asset-output && cp -au . /asset-output',
          ],
        },
      }),
      timeout: cdk.Duration.minutes(5),
      memorySize: 1024,
      environment: {
        RTP_API_URL: props.rtpApiUrl,
        BEDROCK_MODEL_ID: 'us.anthropic.claude-sonnet-4-20250514-v1:0',
      },
      logRetention: logs.RetentionDays.ONE_MONTH,
    });

    // Grant S3 read permissions
    this.inputBucket.grantRead(this.grProcessingLambda);

    // Note: S3 event notifications must be configured manually after deployment.
    // After deployment, run:
    // cd infrastructure && ./configure-s3-notifications-gr.sh
    // See DEPLOYMENT-QUICK-START.md for details

    // Outputs
    new cdk.CfnOutput(this, 'LambdaFunctionName', {
      value: this.grProcessingLambda.functionName,
      description: 'GR processing Lambda function name',
    });

    new cdk.CfnOutput(this, 'InputBucketName', {
      value: this.inputBucket.bucketName,
      description: 'S3 bucket for GR uploads',
    });
  }
}
