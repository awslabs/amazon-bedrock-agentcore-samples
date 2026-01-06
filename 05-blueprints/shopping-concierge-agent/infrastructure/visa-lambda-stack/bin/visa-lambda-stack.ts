#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { VisaLambdaStack } from '../lib/visa-lambda-stack';

const app = new cdk.App();

const deploymentId = app.node.tryGetContext('deploymentId') || 'default';

new VisaLambdaStack(app, `VisaLambdaStack-${deploymentId}`, {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
  },
  description: `Visa Payment API Proxy Lambda Stack for deployment: ${deploymentId}`,
});

app.synth();
