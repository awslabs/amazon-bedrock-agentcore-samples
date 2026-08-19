import { defineBackend } from '@aws-amplify/backend';
import { auth } from './auth/resource';
import { data } from './data/resource';
import { Effect, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { CfnOutput } from 'aws-cdk-lib';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

// ES module equivalent of __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load deployment config for unique export names
const configPath = path.join(__dirname, '..', 'deployment-config.json');
const deploymentConfig = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
const deploymentId = deploymentConfig.deploymentId;

const backend = defineBackend({
  auth,
  data,
});

// Grant authenticated users access to send emails via SES
backend.auth.resources.authenticatedUserIamRole.addToPrincipalPolicy(
  new PolicyStatement({
    effect: Effect.ALLOW,
    actions: [
      'ses:SendEmail',
      'ses:SendRawEmail'
    ],
    resources: ['*'] // You can restrict this to specific SES identities
  })
);

// Create resource server for machine-to-machine authentication
import { UserPoolResourceServer, ResourceServerScope, UserPoolClient, OAuthScope } from 'aws-cdk-lib/aws-cognito';

const resourceServer = new UserPoolResourceServer(backend.stack, 'GatewayResourceServer', {
  userPool: backend.auth.resources.userPool,
  identifier: 'concierge-gateway',
  userPoolResourceServerName: 'concierge-gateway-resource-server',
  scopes: [
    new ResourceServerScope({
      scopeName: 'invoke',
      scopeDescription: 'Invoke gateway and targets',
    }),
  ],
});

// Create machine client for gateway OAuth authentication
const machineClient = new UserPoolClient(backend.stack, 'GatewayMachineClient', {
  userPool: backend.auth.resources.userPool,
  userPoolClientName: 'concierge-gateway-machine-client',
  generateSecret: true,
  oAuth: {
    flows: {
      clientCredentials: true,
    },
    scopes: [
      OAuthScope.resourceServer(
        resourceServer,
        new ResourceServerScope({
          scopeName: 'invoke',
          scopeDescription: 'Invoke gateway and targets',
        })
      ),
    ],
  },
});
machineClient.node.addDependency(resourceServer);

// Add Cognito domain for OAuth token endpoint
import { UserPoolDomain } from 'aws-cdk-lib/aws-cognito';

const userPoolDomain = new UserPoolDomain(backend.stack, 'CognitoDomain', {
  userPool: backend.auth.resources.userPool,
  cognitoDomain: {
    domainPrefix: `concierge-${deploymentId}-${backend.stack.account}`,  // Must be globally unique - includes account ID
  },
});

// Export Cognito configuration for Agent CDK stack to import
new CfnOutput(backend.stack, 'UserPoolIdExport', {
  value: backend.auth.resources.userPool.userPoolId,
  exportName: `ConciergeAgent-${deploymentId}-Auth-UserPoolId`,
  description: 'Cognito User Pool ID (unique per deployment)'
});

new CfnOutput(backend.stack, 'ClientIdExport', {
  value: backend.auth.resources.userPoolClient.userPoolClientId,
  exportName: `ConciergeAgent-${deploymentId}-Auth-ClientId`,
  description: 'Cognito User Pool Client ID (unique per deployment)'
});

new CfnOutput(backend.stack, 'RegionExport', {
  value: backend.stack.region,
  exportName: `ConciergeAgent-${deploymentId}-Auth-Region`,
  description: 'AWS Region (unique per deployment)'
});

new CfnOutput(backend.stack, 'MachineClientIdExport', {
  value: machineClient.userPoolClientId,
  exportName: `ConciergeAgent-${deploymentId}-Auth-MachineClientId`,
  description: 'Machine client ID for gateway OAuth and MCP authentication'
});

// Table exports with deployment ID
new CfnOutput(backend.stack, 'UserProfileTableNameExport', {
  value: backend.data.resources.tables['UserProfile'].tableName,
  exportName: `ConciergeAgent-${deploymentId}-Data-UserProfileTableName`,
  description: 'DynamoDB UserProfile table name (unique per deployment)'
});

new CfnOutput(backend.stack, 'WishlistTableNameExport', {
  value: backend.data.resources.tables['Wishlist'].tableName,
  exportName: `ConciergeAgent-${deploymentId}-Data-WishlistTableName`,
  description: 'DynamoDB Wishlist table name (unique per deployment)'
});

new CfnOutput(backend.stack, 'ItineraryTableNameExport', {
  value: backend.data.resources.tables['Itinerary'].tableName,
  exportName: `ConciergeAgent-${deploymentId}-Data-ItineraryTableName`,
  description: 'DynamoDB Itinerary table name (unique per deployment)'
});

new CfnOutput(backend.stack, 'FeedbackTableNameExport', {
  value: backend.data.resources.tables['Feedback'].tableName,
  exportName: `ConciergeAgent-${deploymentId}-Data-FeedbackTableName`,
  description: 'DynamoDB Feedback table name (unique per deployment)'
});
