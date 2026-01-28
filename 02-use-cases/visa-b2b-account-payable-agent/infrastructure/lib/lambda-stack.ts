import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import * as path from 'path';

interface LambdaStackProps extends cdk.StackProps {
  vpcId: string;
  dbEndpoint: string;
  dbSecretArn: string;
  s3BucketName: string;
}

export class LambdaStack extends cdk.Stack {
  public readonly apiLambda: lambda.Function;
  public readonly api: apigateway.RestApi;

  constructor(scope: Construct, id: string, props: LambdaStackProps) {
    super(scope, id, props);

    // Import VPC
    const vpc = ec2.Vpc.fromLookup(this, 'ImportedVpc', {
      vpcId: props.vpcId,
    });

    // Create Lambda security group
    const lambdaSg = new ec2.SecurityGroup(this, 'LambdaSecurityGroup', {
      vpc,
      description: 'Security group for RTP Overlay Lambda',
      allowAllOutbound: true,
    });

    // Create Lambda Layer with node_modules
    const dependenciesLayer = new lambda.LayerVersion(this, 'DependenciesLayer', {
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda-layer.zip')),
      compatibleRuntimes: [lambda.Runtime.NODEJS_20_X],
      description: 'Node modules for RTP Overlay application',
    });

    // Create Lambda function
    this.apiLambda = new lambda.Function(this, 'ApiLambda', {
      runtime: lambda.Runtime.NODEJS_20_X,
      handler: 'dist/lambda.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda-code.zip')),
      layers: [dependenciesLayer],
      vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
      securityGroups: [lambdaSg],
      timeout: cdk.Duration.seconds(60),
      memorySize: 512,
      environment: {
        NODE_ENV: 'production',
        DB_HOST: props.dbEndpoint,
        DB_PORT: '5432',
        DB_DATABASE: 'rtpoverlay',
        DB_SSL: 'true', // Enable SSL for RDS connection
        DB_SECRET_ARN: props.dbSecretArn, // For fetching credentials
        AWS_S3_BUCKET: props.s3BucketName,
        S3_INPUT_BUCKET: `rtp-overlay-invoices-input-${this.account}`,
        S3_GR_INPUT_BUCKET: `rtp-overlay-receipts-input-${this.account}`,
        ISO20022_BUCKET_NAME: `rtp-overlay-iso20022-${this.account}`,
        RECEIPTS_BUCKET: props.s3BucketName,
        CORS_ORIGIN: '*', // Update with your frontend domain
        PAYMENT_AGENT_ARN: `arn:aws:bedrock-agentcore:us-east-1:${this.account}:runtime/visa_b2b_payment_agent-pnP6d452ZH`,
        KMS_KEY_ID: 'alias/rtp-overlay-payment-cards', // For card encryption/decryption
        // Import from AgentCore Invoker stack (deployed separately)
        // This will be empty on first deployment, then populated after deploy-agentcore-invoker.sh
        // Run ./deploy-lambda.sh again after deploying AgentCore Invoker to update this value
        AGENTCORE_INVOKER_LAMBDA_NAME: this.node.tryGetContext('agentcoreInvokerExists') === 'true'
          ? cdk.Fn.importValue('AgentCoreInvokerLambdaName')
          : 'rtp-overlay-agentcore-invoker', // Default function name
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // Grant Lambda access to Secrets Manager
    this.apiLambda.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['secretsmanager:GetSecretValue'],
        resources: [props.dbSecretArn],
      })
    );

    // Grant Lambda access to S3 (receipts bucket)
    this.apiLambda.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['s3:GetObject', 's3:PutObject', 's3:DeleteObject'],
        resources: [`arn:aws:s3:::${props.s3BucketName}/*`],
      })
    );
    
    this.apiLambda.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['s3:ListBucket'],
        resources: [`arn:aws:s3:::${props.s3BucketName}`],
      })
    );

    // Grant Lambda access to invoice input bucket
    this.apiLambda.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['s3:PutObject', 's3:GetObject'],
        resources: [`arn:aws:s3:::rtp-overlay-invoices-input-${this.account}/*`],
      })
    );

    // Grant Lambda access to goods receipt input bucket
    this.apiLambda.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['s3:PutObject', 's3:GetObject'],
        resources: [`arn:aws:s3:::rtp-overlay-receipts-input-${this.account}/*`],
      })
    );

    // Grant Lambda access to ISO20022 output bucket
    this.apiLambda.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['s3:GetObject'],
        resources: [`arn:aws:s3:::rtp-overlay-iso20022-${this.account}/*`],
      })
    );

    // Grant Lambda access to invoke AgentCore Runtime
    this.apiLambda.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          'bedrock-agentcore:InvokeRuntime',
          'bedrock-agentcore:GetAgentRuntime',
        ],
        resources: [`arn:aws:bedrock-agentcore:us-east-1:${this.account}:runtime/*`],
      })
    );

    // Create API Gateway
    this.api = new apigateway.RestApi(this, 'RtpOverlayApi', {
      restApiName: 'RTP Overlay API',
      description: 'API for RTP Overlay System',
      binaryMediaTypes: ['multipart/form-data', 'image/*', 'application/pdf'],
      deployOptions: {
        stageName: 'prod',
        throttlingRateLimit: 100,
        throttlingBurstLimit: 200,
        // Logging disabled to avoid CloudWatch Logs role requirement
        // loggingLevel: apigateway.MethodLoggingLevel.INFO,
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS, // Update with your frontend domain
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'Authorization'],
      },
    });

    // Add Lambda integration
    const integration = new apigateway.LambdaIntegration(this.apiLambda);

    // Add proxy resource to handle all paths
    const proxy = this.api.root.addProxy({
      defaultIntegration: integration,
      anyMethod: true,
    });

    // Outputs
    new cdk.CfnOutput(this, 'ApiUrl', {
      value: this.api.url,
      description: 'API Gateway URL',
      exportName: 'RtpOverlayApiUrl',
    });

    new cdk.CfnOutput(this, 'LambdaFunctionName', {
      value: this.apiLambda.functionName,
      description: 'Lambda function name',
      exportName: 'RtpOverlayLambdaName',
    });

    // Create migration Lambda function
    const migrationLambda = new lambda.Function(this, 'MigrationLambda', {
      runtime: lambda.Runtime.NODEJS_20_X,
      handler: 'dist/scripts/migrate-and-seed-lambda.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda-code.zip')),
      layers: [dependenciesLayer],
      vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
      securityGroups: [lambdaSg],
      timeout: cdk.Duration.minutes(5),
      memorySize: 512,
      environment: {
        NODE_ENV: 'production',
        DB_HOST: props.dbEndpoint,
        DB_PORT: '5432',
        DB_DATABASE: 'rtpoverlay',
        DB_SECRET_ARN: props.dbSecretArn,
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // Grant migration Lambda access to Secrets Manager
    migrationLambda.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['secretsmanager:GetSecretValue'],
        resources: [props.dbSecretArn],
      })
    );

    new cdk.CfnOutput(this, 'MigrationLambdaName', {
      value: migrationLambda.functionName,
      description: 'Migration Lambda function name',
    });

    // Grant API Lambda permission to invoke AgentCore Invoker Lambda (deployed separately)
    // The AgentCore Invoker Lambda is deployed via deploy-agentcore-invoker.sh
    this.apiLambda.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['lambda:InvokeFunction'],
        resources: [`arn:aws:lambda:us-east-1:${this.account}:function:rtp-overlay-agentcore-invoker`],
      })
    );

    // Grant Lambda access to KMS for card encryption/decryption
    this.apiLambda.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          'kms:Encrypt',
          'kms:Decrypt',
          'kms:DescribeKey',
        ],
        resources: [`arn:aws:kms:us-east-1:${this.account}:key/*`],
        conditions: {
          'StringEquals': {
            'kms:RequestAlias': 'alias/rtp-overlay-payment-cards',
          },
        },
      })
    );
  }
}
