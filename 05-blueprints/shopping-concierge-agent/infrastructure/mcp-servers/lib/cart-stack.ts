import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import { BaseMcpStack } from './base-mcp-stack';
import * as fs from 'fs';

// Load deployment config
const deploymentConfig = JSON.parse(fs.readFileSync('../../deployment-config.json', 'utf-8'));
const DEPLOYMENT_ID = deploymentConfig.deploymentId;

export class CartStack extends BaseMcpStack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, {
      ...props,
      mcpName: 'cart',
      agentCodePath: 'concierge_agent/mcp_cart_tools',
      ssmParameters: [],
      environmentVariables: {
        USER_PROFILE_TABLE_NAME: cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Data-UserProfileTableName`),
        WISHLIST_TABLE_NAME: cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Data-WishlistTableName`)
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

    // Add Visa secrets policy after super() so we can use 'this'
    this.runtime.addToRolePolicy(
      new iam.PolicyStatement({
        sid: 'VisaSecretsAccess',
        effect: iam.Effect.ALLOW,
        actions: [
          'secretsmanager:GetSecretValue'
        ],
        resources: [
          `arn:aws:secretsmanager:${this.region}:${this.account}:secret:visa/*`
        ]
      })
    );
  }
}
