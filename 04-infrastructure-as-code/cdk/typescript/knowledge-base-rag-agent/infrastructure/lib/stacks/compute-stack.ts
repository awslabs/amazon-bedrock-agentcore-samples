import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as bedrock from 'aws-cdk-lib/aws-bedrock';
import * as path from 'path';

export interface ComputeStackProps extends cdk.StackProps {
  vpc: ec2.Vpc;
  userPool: cognito.UserPool;
  userPoolClient: cognito.UserPoolClient;
  tables: {
    [key: string]: dynamodb.Table;
  };
  bucket: s3.Bucket;
  bedrockAgent?: bedrock.CfnAgent | cdk.CustomResource;
}

export class ComputeStack extends cdk.Stack {
  public readonly chatFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: ComputeStackProps) {
    super(scope, id, props);

    // Set parameter prefix for SSM parameters
    const paramPrefix = '/AgentCoreTemplate';

    // Import the common layer from the shared resources stack
    const commonLayerArn = ssm.StringParameter.valueForStringParameter(
      this,
      `${paramPrefix}/CommonLayerArn`
    );
    const commonLayer = lambda.LayerVersion.fromLayerVersionArn(
      this,
      'CommonLayer',
      commonLayerArn
    );

    // Create single Lambda function for chat with Bedrock agent
    this.chatFunction = new lambda.Function(this, 'ChatFunction', {
      runtime: lambda.Runtime.NODEJS_20_X,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../src/functions/chat/dist')),
      layers: [commonLayer],
      timeout: cdk.Duration.minutes(5),
      memorySize: 1024,
      // T-3 DoS Protection: Set reserved concurrency to prevent resource exhaustion
      reservedConcurrentExecutions: 50, // Limit concurrent executions to prevent resource exhaustion
      environment: {
        SESSIONS_TABLE: props.tables.sessions?.tableName || 'AgentCoreSessions',
        DATA_BUCKET_NAME: props.bucket.bucketName,
        AGENT_ID: ssm.StringParameter.valueForStringParameter(
          this,
          `${paramPrefix}/AgentCoreId`
        ),
        AGENT_ALIAS_ID: ssm.StringParameter.valueForStringParameter(
          this,
          `${paramPrefix}/AgentCoreAliasId`
        ),
      },
    });

    // Grant permissions to chat function
    if (props.tables.chatHistory) {
      props.tables.chatHistory.grantReadWriteData(this.chatFunction);
    }
    if (props.tables.sessions) {
      props.tables.sessions.grantReadWriteData(this.chatFunction);
    }
    props.bucket.grantReadWrite(this.chatFunction);

    // Grant KMS permissions for S3 encryption/decryption
    this.chatFunction.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'kms:Decrypt',
          'kms:DescribeKey',
          'kms:Encrypt',
          'kms:GenerateDataKey',
          'kms:GenerateDataKeyWithoutPlaintext',
          'kms:ReEncrypt*',
        ],
        resources: [
          // Allow access to the S3 encryption key
          `arn:aws:kms:${this.region}:${this.account}:key/*`,
        ],
        conditions: {
          StringEquals: {
            'kms:ViaService': [`s3.${this.region}.amazonaws.com`],
          },
        },
      })
    );

    // Import shared policies from the shared resources stack
    const bedrockAccessPolicyArn = ssm.StringParameter.valueForStringParameter(
      this,
      `${paramPrefix}/Policies/BedrockAccessPolicyArn`
    );
    const ssmParameterAccessPolicyArn = ssm.StringParameter.valueForStringParameter(
      this,
      `${paramPrefix}/Policies/SSMParameterAccessPolicyArn`
    );

    // Attach shared policies to the chat function
    this.chatFunction.role?.addManagedPolicy(
      iam.ManagedPolicy.fromManagedPolicyArn(this, 'BedrockAccessPolicy', bedrockAccessPolicyArn)
    );
    this.chatFunction.role?.addManagedPolicy(
      iam.ManagedPolicy.fromManagedPolicyArn(this, 'SSMParameterAccessPolicy', ssmParameterAccessPolicyArn)
    );

    // Outputs
    new cdk.CfnOutput(this, 'ChatFunctionArn', {
      value: this.chatFunction.functionArn,
      description: 'Chat function ARN',
      exportName: `${this.stackName}-ChatFunctionArn`,
    });
  }
}
