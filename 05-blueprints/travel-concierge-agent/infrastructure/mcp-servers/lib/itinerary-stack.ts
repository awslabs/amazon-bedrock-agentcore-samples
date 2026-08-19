import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import { BaseMcpStack } from './base-mcp-stack';
import * as fs from 'fs';

// Load deployment config
const deploymentConfig = JSON.parse(fs.readFileSync('../../deployment-config.json', 'utf-8'));
const DEPLOYMENT_ID = deploymentConfig.deploymentId;

export class ItineraryStack extends BaseMcpStack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, {
      ...props,
      mcpName: 'itinerary',
      agentCodePath: 'concierge_agent/mcp_itinerary_tools',
      ssmParameters: [],
      environmentVariables: {
        USER_PROFILE_TABLE_NAME: cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Data-UserProfileTableName`),
        ITINERARY_TABLE_NAME: cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Data-ItineraryTableName`)
      },
      additionalPolicies: [
        new iam.PolicyStatement({
          sid: 'DynamoDBAccess',
          effect: iam.Effect.ALLOW,
          actions: [
            'dynamodb:GetItem',
            'dynamodb:PutItem',
            'dynamodb:UpdateItem',
            'dynamodb:DeleteItem',
            'dynamodb:Query',
            'dynamodb:Scan'
          ],
          resources: [
            `arn:aws:dynamodb:*:*:table/*`
          ]
        })
      ]
    });
  }
}
