import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';

export interface AgentCoreLambdaLayerProps {
  layerName?: string;
  description?: string;
  compatibleRuntimes?: lambda.Runtime[];
  sourcePath: string;
}

export class AgentCoreLambdaLayer extends Construct {
  public readonly layer: lambda.LayerVersion;

  constructor(scope: Construct, id: string, props: AgentCoreLambdaLayerProps) {
    super(scope, id);

    this.layer = new lambda.LayerVersion(this, 'Layer', {
      layerVersionName: props.layerName,
      description: props.description || 'Bedrock Agent Lambda Layer',
      compatibleRuntimes: props.compatibleRuntimes || [lambda.Runtime.NODEJS_18_X],
      code: lambda.Code.fromAsset(props.sourcePath),
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
  }
}
