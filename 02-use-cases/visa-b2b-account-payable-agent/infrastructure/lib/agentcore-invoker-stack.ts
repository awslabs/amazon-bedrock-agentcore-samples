import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';
import * as path from 'path';

export class AgentCoreInvokerStack extends cdk.Stack {
  public readonly agentCoreInvokerLambda: lambda.Function;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Create AgentCore Invoker Lambda (Python)
    // No VPC needed - only calls AWS APIs (bedrock-agentcore)
    // RUNTIME_ARN will be set via deployment script from SSM Parameter Store
    this.agentCoreInvokerLambda = new lambda.Function(this, 'AgentCoreInvokerLambda', {
      functionName: 'rtp-overlay-agentcore-invoker',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'agentcore_invoker.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../lambda/agentcore-invoker'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash',
            '-c',
            [
              'pip install --platform manylinux2014_x86_64 --only-binary=:all: -r requirements.txt -t /asset-output',
              'cp agentcore_invoker.py /asset-output/',
            ].join(' && '),
          ],
        },
      }),
      timeout: cdk.Duration.seconds(300),
      memorySize: 512,
      environment: {
        // Placeholder - will be updated by deployment script
        RUNTIME_ARN: 'PLACEHOLDER',
      },
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // Grant AgentCore Invoker Lambda permissions to invoke AgentCore Runtime
    this.agentCoreInvokerLambda.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          'bedrock-agentcore:InvokeAgentRuntime',
          'bedrock-agentcore:GetAgentRuntime',
        ],
        resources: [`arn:aws:bedrock-agentcore:us-east-1:${this.account}:runtime/*`],
      })
    );

    // Outputs
    new cdk.CfnOutput(this, 'AgentCoreInvokerLambdaName', {
      value: this.agentCoreInvokerLambda.functionName,
      description: 'AgentCore Invoker Lambda function name',
      exportName: 'AgentCoreInvokerLambdaName',
    });

    new cdk.CfnOutput(this, 'AgentCoreInvokerLambdaArn', {
      value: this.agentCoreInvokerLambda.functionArn,
      description: 'AgentCore Invoker Lambda ARN',
      exportName: 'AgentCoreInvokerLambdaArn',
    });
  }
}
