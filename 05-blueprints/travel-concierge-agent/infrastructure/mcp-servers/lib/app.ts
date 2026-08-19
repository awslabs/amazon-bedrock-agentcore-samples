#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import * as fs from 'fs';
import { TravelStack } from './travel-stack';
import { CartStack } from './cart-stack';
import { ItineraryStack } from './itinerary-stack';

// Load deployment config
const deploymentConfig = JSON.parse(fs.readFileSync('../../deployment-config.json', 'utf-8'));
const DEPLOYMENT_ID = deploymentConfig.deploymentId;

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || 'us-east-1'
};

new TravelStack(app, `TravelStack-${DEPLOYMENT_ID}`, {
  env,
  description: `Travel MCP Server - Travel search tools (${DEPLOYMENT_ID})`
});

new CartStack(app, `CartStack-${DEPLOYMENT_ID}`, {
  env,
  description: `Cart MCP Server - Shopping cart tools (${DEPLOYMENT_ID})`
});

new ItineraryStack(app, `ItineraryStack-${DEPLOYMENT_ID}`, {
  env,
  description: `Itinerary MCP Server - Itinerary management tools (${DEPLOYMENT_ID})`
});

app.synth();
