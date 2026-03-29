import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as path from 'path';

/**
 * Properties for the Shared Resources Stack
 */
export interface SharedResourcesStackProps extends cdk.StackProps {
  // No specific props needed for now, but keeping interface for future extensibility
}

/**
 * AWS CDK Stack for Shared Resources
 *
 * This stack creates common resources that are used by multiple other stacks:
 * - Lambda layers for shared dependencies
 * - Common utilities and configurations
 * - Shared IAM policies and roles
 * 
 * This stack is deployed first to avoid circular dependencies between other stacks.
 */
export class SharedResourcesStack extends cdk.Stack {
  /** Common Lambda layer for shared dependencies */
  public readonly commonLayer: lambda.LayerVersion;
  /** Common IAM policy for Bedrock access */
  public readonly bedrockAccessPolicy: iam.ManagedPolicy;
  /** Common IAM policy for SSM parameter access */
  public readonly ssmParameterAccessPolicy: iam.ManagedPolicy;

  constructor(scope: Construct, id: string, props?: SharedResourcesStackProps) {
    super(scope, id, props);

    // Parameter prefix for SSM parameters
    const paramPrefix = '/AgentCoreTemplate';

    // Create a common Lambda Layer for shared dependencies
    // This layer contains common Node.js packages used across multiple Lambda functions
    this.commonLayer = new lambda.LayerVersion(this, 'CommonLayer', {
      layerVersionName: 'AgentCoreTemplate-CommonLayer',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../src/functions/layers/common')),
      compatibleRuntimes: [lambda.Runtime.NODEJS_20_X, lambda.Runtime.NODEJS_18_X],
      description: 'Common dependencies for Knowledge Base RAG Agent Lambda functions',
    });

    // Store the common layer ARN in SSM Parameter Store for other stacks to reference
    new ssm.StringParameter(this, 'CommonLayerArnParameter', {
      parameterName: `${paramPrefix}/CommonLayerArn`,
      stringValue: this.commonLayer.layerVersionArn,
      description: 'Common Lambda Layer ARN for shared dependencies',
    });

    // Store the parameter prefix for consistency across stacks
    new ssm.StringParameter(this, 'ParameterPrefixParameter', {
      parameterName: `${paramPrefix}/ParameterPrefix`,
      stringValue: paramPrefix,
      description: 'Common parameter prefix for all SSM parameters',
    });

    // Create common IAM policies for reuse across stacks
    
    // Common Bedrock access policy for Lambda functions
    this.bedrockAccessPolicy = new iam.ManagedPolicy(this, 'BedrockAccessPolicy', {
      managedPolicyName: 'AgentCoreTemplate-BedrockAccess',
      description: 'Common policy for Bedrock access across Lambda functions',
      statements: [
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: [
            'bedrock:InvokeAgent',
            'bedrock:InvokeModel',
            'bedrock:InvokeModelWithResponseStream',
            'bedrock:GetAgent',
            'bedrock:ListAgents',
            'bedrock:GetAgentAlias',
            'bedrock:GetKnowledgeBase',
            'bedrock:Retrieve',
            'bedrock:RetrieveAndGenerate',
          ],
          resources: ['*'], // Bedrock resources don't support resource-specific ARNs
        }),
      ],
    });

    // Common SSM parameter access policy
    this.ssmParameterAccessPolicy = new iam.ManagedPolicy(this, 'SSMParameterAccessPolicy', {
      managedPolicyName: 'AgentCoreTemplate-SSMParameterAccess',
      description: 'Common policy for SSM parameter access',
      statements: [
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ['ssm:GetParameter', 'ssm:GetParameters'],
          resources: [`arn:aws:ssm:${this.region}:${this.account}:parameter${paramPrefix}/*`],
        }),
      ],
    });

    // Store policy ARNs in SSM for other stacks to reference
    new ssm.StringParameter(this, 'BedrockAccessPolicyArnParameter', {
      parameterName: `${paramPrefix}/Policies/BedrockAccessPolicyArn`,
      stringValue: this.bedrockAccessPolicy.managedPolicyArn,
      description: 'Common Bedrock access policy ARN',
    });

    new ssm.StringParameter(this, 'SSMParameterAccessPolicyArnParameter', {
      parameterName: `${paramPrefix}/Policies/SSMParameterAccessPolicyArn`,
      stringValue: this.ssmParameterAccessPolicy.managedPolicyArn,
      description: 'Common SSM parameter access policy ARN',
    });

    // CloudFormation outputs for easy reference
    new cdk.CfnOutput(this, 'CommonLayerArn', {
      value: this.commonLayer.layerVersionArn,
      description: 'Common Lambda Layer ARN',
      exportName: `${this.stackName}-CommonLayerArn`,
    });

    new cdk.CfnOutput(this, 'ParameterPrefix', {
      value: paramPrefix,
      description: 'Common parameter prefix',
      exportName: `${this.stackName}-ParameterPrefix`,
    });

    new cdk.CfnOutput(this, 'BedrockAccessPolicyArn', {
      value: this.bedrockAccessPolicy.managedPolicyArn,
      description: 'Common Bedrock access policy ARN',
      exportName: `${this.stackName}-BedrockAccessPolicyArn`,
    });

    new cdk.CfnOutput(this, 'SSMParameterAccessPolicyArn', {
      value: this.ssmParameterAccessPolicy.managedPolicyArn,
      description: 'Common SSM parameter access policy ARN',
      exportName: `${this.stackName}-SSMParameterAccessPolicyArn`,
    });

    // Tag all resources for organization and cost tracking
    cdk.Tags.of(this).add('Project', 'AgentCoreTemplate');
    cdk.Tags.of(this).add('Component', 'SharedResources');
  }
}