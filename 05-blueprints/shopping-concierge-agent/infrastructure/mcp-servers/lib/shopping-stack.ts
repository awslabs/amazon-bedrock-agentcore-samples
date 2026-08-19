import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { BaseMcpStack } from './base-mcp-stack';

export class ShoppingStack extends BaseMcpStack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, {
      ...props,
      mcpName: 'shopping',
      agentCodePath: 'concierge_agent/mcp_shopping_tools',
      ssmParameters: [
        '/concierge-agent/shopping/serp-api-key'
      ]
    });
  }
}
