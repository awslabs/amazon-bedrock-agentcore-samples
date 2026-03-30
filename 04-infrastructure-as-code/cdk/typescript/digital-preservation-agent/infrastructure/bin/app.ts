#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { Aspects } from 'aws-cdk-lib';
import { AwsSolutionsChecks } from 'cdk-nag';
import { DigitalPreservationStack } from '../lib/stacks/digital-preservation-stack';

const app = new cdk.App();

Aspects.of(app).add(new AwsSolutionsChecks());

new DigitalPreservationStack(app, 'DigitalPreservationAgentStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
  description:
    'Digital preservation agent with Apache Tika, Siegfried, DROID, and MediaInfo on ECS Fargate, AgentCore Gateway, and AgentCore Runtime',
});

app.synth();
