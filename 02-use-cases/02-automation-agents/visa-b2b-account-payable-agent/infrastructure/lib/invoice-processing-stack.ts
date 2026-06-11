import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3n from 'aws-cdk-lib/aws-s3-notifications';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import * as path from 'path';

interface InvoiceProcessingStackProps extends cdk.StackProps {
  rtpApiUrl: string;
}

export class InvoiceProcessingStack extends cdk.Stack {
  public readonly invoiceProcessingLambda: lambda.Function;
  public readonly inputBucket: s3.Bucket;
  public readonly outputBucket: s3.Bucket;
  public readonly apiKeySecret: secretsmanager.Secret;

  constructor(scope: Construct, id: string, props: InvoiceProcessingStackProps) {
    super(scope, id, props);

    // Create API key secret for Lambda → API authentication
    this.apiKeySecret = new secretsmanager.Secret(this, 'RtpApiKeySecret', {
      secretName: 'rtp-overlay/api-key',
      description: 'API key for Lambda to authenticate with RTP Overlay API',
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ apiKey: '' }),
        generateStringKey: 'apiKey',
        excludePunctuation: true,
        passwordLength: 32,
      },
    });

    // Create S3 input bucket for invoice uploads
    this.inputBucket = new s3.Bucket(this, 'InvoiceInputBucket', {
      bucketName: `rtp-overlay-invoices-input-${this.account}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      lifecycleRules: [
        {
          id: 'DeleteOldVersions',
          noncurrentVersionExpiration: cdk.Duration.days(90),
        },
      ],
    });

    // Create S3 output bucket for ISO20022 XML files
    this.outputBucket = new s3.Bucket(this, 'Iso20022OutputBucket', {
      bucketName: `rtp-overlay-iso20022-${this.account}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      lifecycleRules: [
        {
          id: 'DeleteOldVersions',
          noncurrentVersionExpiration: cdk.Duration.days(90),
        },
      ],
    });

    // Create Lambda function for invoice processing
    this.invoiceProcessingLambda = new lambda.Function(this, 'InvoiceProcessingLambda', {
      functionName: 'rtp-overlay-invoice-processor',
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'lambda_iso20022.lambda_handler',
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
      timeout: cdk.Duration.minutes(2),
      memorySize: 1024,
      environment: {
        INPUT_BUCKET: this.inputBucket.bucketName,
        OUTPUT_BUCKET: this.outputBucket.bucketName,
        RTP_API_URL: props.rtpApiUrl,
        API_KEY_SECRET_NAME: this.apiKeySecret.secretName,
        // AWS_REGION is automatically available in Lambda runtime
      },
      logRetention: logs.RetentionDays.ONE_MONTH,
    });

    // Grant Lambda permissions
    // S3 read from input bucket
    this.inputBucket.grantRead(this.invoiceProcessingLambda);

    // S3 write to output bucket for ISO20022 files
    this.outputBucket.grantWrite(this.invoiceProcessingLambda);

    // Bedrock invoke permissions
    this.invoiceProcessingLambda.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['bedrock:InvokeModel'],
        resources: [
          `arn:aws:bedrock:*::foundation-model/*`,
          `arn:aws:bedrock:${this.region}:${this.account}:inference-profile/*`,
        ],
      })
    );

    // Secrets Manager read permission
    this.apiKeySecret.grantRead(this.invoiceProcessingLambda);

    // Grant Payment Agent (AgentCore Runtime) permission to invoke this Lambda
    // Note: This permission will be added automatically when the Payment Agent is deployed
    // The AgentCore Runtime role is auto-created by AWS during Payment Agent deployment
    // If you need to add this manually later, run:
    // aws lambda add-permission --function-name rtp-overlay-invoice-processor \
    //   --statement-id AllowAgentCoreInvoke \
    //   --action lambda:InvokeFunction \
    //   --principal arn:aws:iam::<account>:role/AmazonBedrockAgentCoreSDKRuntime-us-east-1-<id>

    // Note: S3 event notifications must be configured manually after deployment.
    // After deployment, run:
    // cd infrastructure && ./configure-s3-notifications.sh
    // See DEPLOYMENT-QUICK-START.md for details

    // Outputs
    new cdk.CfnOutput(this, 'InputBucketName', {
      value: this.inputBucket.bucketName,
      description: 'S3 bucket for invoice uploads',
      exportName: 'RtpOverlayInvoiceInputBucket',
    });

    new cdk.CfnOutput(this, 'InputBucketArn', {
      value: this.inputBucket.bucketArn,
      description: 'Invoice input bucket ARN',
      exportName: 'RtpOverlayInvoiceInputBucketArn',
    });

    new cdk.CfnOutput(this, 'OutputBucketName', {
      value: this.outputBucket.bucketName,
      description: 'S3 bucket for ISO20022 XML files',
      exportName: 'RtpOverlayIso20022OutputBucket',
    });

    new cdk.CfnOutput(this, 'OutputBucketArn', {
      value: this.outputBucket.bucketArn,
      description: 'ISO20022 output bucket ARN',
      exportName: 'RtpOverlayIso20022OutputBucketArn',
    });

    new cdk.CfnOutput(this, 'LambdaFunctionName', {
      value: this.invoiceProcessingLambda.functionName,
      description: 'Invoice processing Lambda function name',
      exportName: 'RtpOverlayInvoiceProcessorName',
    });

    new cdk.CfnOutput(this, 'ApiKeySecretArn', {
      value: this.apiKeySecret.secretArn,
      description: 'ARN of the API key secret',
      exportName: 'RtpOverlayApiKeySecretArn',
    });

    new cdk.CfnOutput(this, 'ApiKeySecretName', {
      value: this.apiKeySecret.secretName,
      description: 'Name of the API key secret',
    });
  }
}
