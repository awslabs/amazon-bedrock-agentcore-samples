#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib/core';
import { AwsSolutionsChecks } from 'cdk-nag';
import { VpcegressStack } from '../lib/vpcegress-stack';
import { McpEcsStack } from '../lib/test1-mcp-ecs-stack';
import { McpEksStack } from '../lib/test2-mcp-eks-stack';
import { ApiEksStack } from '../lib/test3-api-eks-stack';
import { PrivateApigwStack } from '../lib/test4-private-apigw-stack';
import { PrivateApiPublicCertStack } from '../lib/test5-private-api-public-cert-stack';
import { PublicDnsPrivateCertStack } from '../lib/test6-public-dns-private-cert-stack';
import { PrivateDnsPrivateCertStack } from '../lib/test7-private-dns-private-cert-stack';
import { EksClusterStack } from '../lib/shared/eks-cluster-stack';
import { PrivateCaStack } from '../lib/shared/private-ca-stack';
import { AgentCoreGatewayStack } from '../lib/shared/agentcore-gateway-stack';

const app = new cdk.App();
cdk.Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));

const accountA = process.env.ACCOUNT_A_ID || app.node.tryGetContext('accountA');
const accountB = process.env.ACCOUNT_B_ID || app.node.tryGetContext('accountB');
const baseDomain = app.node.tryGetContext('baseDomain') || 'egress-test.example.com';
const publicCertArn = app.node.tryGetContext('publicCertArn') || '';
const hostedZoneId = app.node.tryGetContext('hostedZoneId') || '';
const parentDomain = app.node.tryGetContext('parentDomain') || '';
const privateSubdomain = app.node.tryGetContext('privateSubdomain') || '';

if (!accountA) {
  throw new Error(
    'Account A ID is required. Set ACCOUNT_A_ID env var or pass -c accountA=<id>\n'
    + 'Example: ACCOUNT_A_ID=123456789012 cdk deploy ...\n'
    + 'Or:      cdk deploy -c accountA=123456789012 ...'
  );
}

const envA = { account: accountA, region: 'us-west-2' };

// Existing VPC stacks
const vpcUsWest2 = new VpcegressStack(app, 'VpcegressStack-USWest2', {
  env: envA,
  vpcCidr: '10.0.0.0/16',
});

new VpcegressStack(app, 'VpcegressStack-USEast1', {
  env: { account: accountA, region: 'us-east-1' },
  vpcCidr: '10.1.0.0/16',
});

if (accountB) {
  new VpcegressStack(app, 'VpcegressStack-USWest2-AccountB', {
    env: { account: accountB, region: 'us-west-2' },
    vpcCidr: '10.2.0.0/16',
  });
}

// Test 1: MCP Server on ECS (requires publicCertArn)
if (publicCertArn) {
  new McpEcsStack(app, 'Test1-McpEcs', {
    env: envA,
    vpc: vpcUsWest2.vpc,
    certificateArn: publicCertArn,
  });
}

// Shared EKS Cluster
const eksCluster = new EksClusterStack(app, 'SharedEksCluster', {
  env: envA,
  vpc: vpcUsWest2.vpc,
});

// Test 2: MCP Server on EKS (requires publicCertArn + parentDomain + privateSubdomain)
if (publicCertArn && parentDomain && privateSubdomain) {
  new McpEksStack(app, 'Test2-McpEks', {
    env: envA,
    clusterName: eksCluster.cluster.clusterName,
    kubectlRoleArn: eksCluster.cluster.kubectlRole!.roleArn,
    kubectlSecurityGroupId: eksCluster.cluster.kubectlSecurityGroup!.securityGroupId,
    kubectlPrivateSubnetIds: eksCluster.cluster.kubectlPrivateSubnets!.map(s => s.subnetId),
    vpc: vpcUsWest2.vpc,
    certificateArn: publicCertArn,
    parentDomain,
    privateSubdomain,
  });

  // Test 3: REST API on EKS
  new ApiEksStack(app, 'Test3-ApiEks', {
    env: envA,
    clusterName: eksCluster.cluster.clusterName,
    kubectlRoleArn: eksCluster.cluster.kubectlRole!.roleArn,
    kubectlSecurityGroupId: eksCluster.cluster.kubectlSecurityGroup!.securityGroupId,
    kubectlPrivateSubnetIds: eksCluster.cluster.kubectlPrivateSubnets!.map(s => s.subnetId),
    vpc: vpcUsWest2.vpc,
    certificateArn: publicCertArn,
    parentDomain,
    privateSubdomain,
  });
}

// Private API Gateway
new PrivateApigwStack(app, 'PrivateApigw', {
  env: envA,
  vpc: vpcUsWest2.vpc,
});

// Test 5: Private DNS + Public Certificate
new PrivateApiPublicCertStack(app, 'Test5-PrivateApiPublicCert', {
  env: envA,
  vpc: vpcUsWest2.vpc,
  baseDomain,
  publicCertArn,
});

// Shared Private CA (for Tests 6 and 7)
const privateCa = new PrivateCaStack(app, 'SharedPrivateCa', {
  env: envA,
  baseDomain,
});

// Test 6: Public DNS + Private Certificate
new PublicDnsPrivateCertStack(app, 'Test6-PublicDnsPrivateCert', {
  env: envA,
  vpc: vpcUsWest2.vpc,
  baseDomain,
  certificateAuthorityArn: privateCa.caArn,
  hostedZoneId,
});

// Shared AgentCore Gateway (Cognito M2M auth)
new AgentCoreGatewayStack(app, 'SharedAgentCoreGateway', {
  env: envA,
});

// Test 7: Private DNS + Private Certificate
new PrivateDnsPrivateCertStack(app, 'Test7-PrivateDnsPrivateCert', {
  env: envA,
  vpc: vpcUsWest2.vpc,
  baseDomain,
  certificateAuthorityArn: privateCa.caArn,
});
