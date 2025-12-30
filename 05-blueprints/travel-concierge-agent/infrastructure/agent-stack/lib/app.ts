#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import * as fs from 'fs';
import { AgentStack } from './agent-stack';

// Load deployment config
const deploymentConfig = JSON.parse(fs.readFileSync('../../deployment-config.json', 'utf-8'));
const DEPLOYMENT_ID = deploymentConfig.deploymentId;

const app = new cdk.App();

new AgentStack(app, `AgentStack-${DEPLOYMENT_ID}`, {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1'
  },
  description: `Concierge Agent with Gateway - Main agent runtime, memory, and gateway with MCP targets (${DEPLOYMENT_ID})`
});

app.synth();
