#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { PocValidatorWebStack } from "../lib/web-stack";

const app = new cdk.App();

const account = process.env.CDK_DEFAULT_ACCOUNT;
const region = process.env.CDK_DEFAULT_REGION ?? "us-east-1";

new PocValidatorWebStack(app, "PocValidatorWebStack", {
  env: { account, region },
  agentRuntimeArn: app.node.tryGetContext("agentRuntimeArn"),
  demoKey: app.node.tryGetContext("demoKey"),
  basicAuthCredentialBase64: app.node.tryGetContext("basicAuthCredentialBase64"),
  publicBaseUrl: app.node.tryGetContext("publicBaseUrl"),
});
