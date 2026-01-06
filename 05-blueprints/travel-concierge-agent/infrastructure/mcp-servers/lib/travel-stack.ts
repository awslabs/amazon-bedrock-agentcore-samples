import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { BaseMcpStack } from './base-mcp-stack';

export class TravelStack extends BaseMcpStack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, {
      ...props,
      mcpName: 'travel',
      agentCodePath: 'concierge_agent/mcp_travel_tools',
      ssmParameters: [
        '/concierge-agent/travel/openweather-api-key',
        '/concierge-agent/travel/tavily-api-key',
        '/concierge-agent/travel/serp-api-key',
        '/concierge-agent/travel/google-maps-key',
        '/concierge-agent/travel/amadeus-public',
        '/concierge-agent/travel/amadeus-secret'
      ]
    });
  }
}
