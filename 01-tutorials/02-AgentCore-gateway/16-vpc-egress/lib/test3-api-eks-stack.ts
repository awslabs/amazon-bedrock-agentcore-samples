import * as cdk from 'aws-cdk-lib/core';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as eks from 'aws-cdk-lib/aws-eks';
import * as route53 from 'aws-cdk-lib/aws-route53';
import { KubectlV31Layer } from '@aws-cdk/lambda-layer-kubectl-v31';
import { NagSuppressions } from 'cdk-nag';
import { Construct } from 'constructs';

export interface ApiEksStackProps extends cdk.StackProps {
  clusterName: string;
  kubectlRoleArn: string;
  kubectlSecurityGroupId: string;
  kubectlPrivateSubnetIds: string[];
  vpc: ec2.IVpc;
  certificateArn: string;
  parentDomain: string;
  privateSubdomain: string;
}

export class ApiEksStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ApiEksStackProps) {
    super(scope, id, props);

    const fullDomain = `${props.privateSubdomain}.${props.parentDomain}`;

    const cluster = eks.Cluster.fromClusterAttributes(this, 'ImportedCluster', {
      clusterName: props.clusterName,
      kubectlRoleArn: props.kubectlRoleArn,
      kubectlSecurityGroupId: props.kubectlSecurityGroupId,
      kubectlPrivateSubnetIds: props.kubectlPrivateSubnetIds,
      vpc: props.vpc,
      kubectlLayer: new KubectlV31Layer(this, 'KubectlLayer'),
    });

    // --- Kubernetes resources ---
    const namespace = cluster.addManifest('ApiNamespace', {
      apiVersion: 'v1',
      kind: 'Namespace',
      metadata: { name: 'rest-api' },
    });

    const deployment = cluster.addManifest('ApiDeployment', {
      apiVersion: 'apps/v1',
      kind: 'Deployment',
      metadata: {
        name: 'rest-api',
        namespace: 'rest-api',
      },
      spec: {
        replicas: 1,
        selector: { matchLabels: { app: 'rest-api' } },
        template: {
          metadata: { labels: { app: 'rest-api' } },
          spec: {
            containers: [{
              name: 'rest-api',
              image: 'python:3.12-slim',
              command: ['sh', '-c',
                'pip install fastapi uvicorn && python -c "\n'
                + 'from fastapi import FastAPI\n'
                + 'app = FastAPI()\n'
                + 'items = []\n'
                + '@app.get(\'/health\')\n'
                + 'def health():\n'
                + '    return {\'status\': \'ok\'}\n'
                + '@app.get(\'/items\')\n'
                + 'def list_items():\n'
                + '    return items\n'
                + '@app.post(\'/items\')\n'
                + 'def create_item(item: dict):\n'
                + '    items.append(item)\n'
                + '    return item\n'
                + 'import uvicorn\n'
                + 'uvicorn.run(app, host=\'0.0.0.0\', port=8080)\n'
                + '"',
              ],
              ports: [{ containerPort: 8080 }],
            }],
          },
        },
      },
    });
    deployment.node.addDependency(namespace);

    // NLB created via Kubernetes Service type LoadBalancer with AWS annotations
    const privateSubnetIds = props.kubectlPrivateSubnetIds.join(',');
    const nlbService = cluster.addManifest('ApiNlbService', {
      apiVersion: 'v1',
      kind: 'Service',
      metadata: {
        name: 'rest-api-nlb',
        namespace: 'rest-api',
        annotations: {
          'service.beta.kubernetes.io/aws-load-balancer-type': 'nlb',
          'service.beta.kubernetes.io/aws-load-balancer-scheme': 'internal',
          'service.beta.kubernetes.io/aws-load-balancer-nlb-target-type': 'ip',
          'service.beta.kubernetes.io/aws-load-balancer-ssl-cert': props.certificateArn,
          'service.beta.kubernetes.io/aws-load-balancer-ssl-ports': '443',
          'service.beta.kubernetes.io/aws-load-balancer-subnets': privateSubnetIds,
        },
      },
      spec: {
        type: 'LoadBalancer',
        selector: { app: 'rest-api' },
        ports: [
          {
            name: 'https',
            port: 443,
            targetPort: 8080,
            protocol: 'TCP',
          },
        ],
      },
    });
    nlbService.node.addDependency(deployment);

    // --- Private hosted zone ---
    const privateZone = new route53.PrivateHostedZone(this, 'ApiPrivateZone', {
      zoneName: props.parentDomain,
      vpc: props.vpc,
    });

    // --- Outputs ---
    new cdk.CfnOutput(this, 'PrivateDomain', {
      value: fullDomain,
      description: 'Private DNS name (resolves only inside VPC)',
    });

    new cdk.CfnOutput(this, 'PrivateHostedZoneId', {
      value: privateZone.hostedZoneId,
    });


    NagSuppressions.addStackSuppressions(this, [
      { id: 'AwsSolutions-IAM4', reason: 'EKS kubectl provider uses CDK-managed policies' },
      { id: 'AwsSolutions-IAM5', reason: 'EKS kubectl provider uses CDK-managed wildcard permissions' },
      { id: 'AwsSolutions-L1', reason: 'Lambda runtime is managed by CDK EKS construct' },
    ], true);
  }
}
