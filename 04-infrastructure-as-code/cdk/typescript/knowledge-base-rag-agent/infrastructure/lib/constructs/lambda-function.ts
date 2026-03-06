import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';

export interface AgentCoreLambdaProps {
  functionName: string;
  handler: string;
  sourcePath: string;
  environment?: { [key: string]: string };
  timeout?: cdk.Duration;
  memorySize?: number;
  layers?: lambda.ILayerVersion[];
  tracing?: lambda.Tracing;
  logRetention?: cdk.aws_logs.RetentionDays;
}

export class AgentCoreLambda extends Construct {
  public readonly function: lambda.Function;

  constructor(scope: Construct, id: string, props: AgentCoreLambdaProps) {
    super(scope, id);

    this.function = new lambda.Function(this, 'Function', {
      functionName: props.functionName,
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: props.handler,
      code: lambda.Code.fromAsset(props.sourcePath),
      environment: props.environment,
      timeout: props.timeout || cdk.Duration.seconds(30),
      memorySize: props.memorySize || 128,
      layers: props.layers,
      tracing: props.tracing || lambda.Tracing.ACTIVE,
      logRetention: props.logRetention || cdk.aws_logs.RetentionDays.ONE_WEEK,
    });
  }
}
