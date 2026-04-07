import * as cdk from "aws-cdk-lib/core";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as eks from "aws-cdk-lib/aws-eks";
import { KubectlV31Layer } from "@aws-cdk/lambda-layer-kubectl-v31";
import { NagSuppressions } from "cdk-nag";
import { Construct } from "constructs";

export interface McpEksStackProps extends cdk.StackProps {
  clusterName: string;
  kubectlRoleArn: string;
  kubectlSecurityGroupId: string;
  kubectlPrivateSubnetIds: string[];
  vpc: ec2.IVpc;
  certificateArn: string;
}

export class McpEksStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: McpEksStackProps) {
    super(scope, id, props);

    const cluster = eks.Cluster.fromClusterAttributes(this, "ImportedCluster", {
      clusterName: props.clusterName,
      kubectlRoleArn: props.kubectlRoleArn,
      kubectlSecurityGroupId: props.kubectlSecurityGroupId,
      kubectlPrivateSubnetIds: props.kubectlPrivateSubnetIds,
      vpc: props.vpc,
      kubectlLayer: new KubectlV31Layer(this, "KubectlLayer"),
    });

    // --- Kubernetes resources ---
    const namespace = cluster.addManifest("McpNamespace", {
      apiVersion: "v1",
      kind: "Namespace",
      metadata: { name: "mcp-server" },
    });

    const deployment = cluster.addManifest("McpDeployment", {
      apiVersion: "apps/v1",
      kind: "Deployment",
      metadata: {
        name: "mcp-server",
        namespace: "mcp-server",
      },
      spec: {
        replicas: 1,
        selector: { matchLabels: { app: "mcp-server" } },
        template: {
          metadata: { labels: { app: "mcp-server" } },
          spec: {
            containers: [
              {
                name: "mcp-server",
                image: "python:3.12-slim",
                command: [
                  "sh",
                  "-c",
                  'pip install "fastmcp>=2.0" && python -c "\n' +
                    "from fastmcp import FastMCP\n" +
                    "from datetime import datetime\n" +
                    "mcp = FastMCP('Mock MCP Server')\n" +
                    "@mcp.tool()\n" +
                    "def echo(message: str) -> str:\n" +
                    "    return message\n" +
                    "@mcp.tool()\n" +
                    "def add(a: float, b: float) -> float:\n" +
                    "    return a + b\n" +
                    "@mcp.tool()\n" +
                    "def get_time() -> str:\n" +
                    "    return datetime.now().isoformat()\n" +
                    "mcp.run(transport='streamable-http', host='0.0.0.0', port=8000, stateless_http=True)\n" +
                    '"',
                ],
                ports: [{ containerPort: 8000 }],
              },
            ],
          },
        },
      },
    });
    deployment.node.addDependency(namespace);

    // NLB created via Kubernetes Service type LoadBalancer with AWS annotations
    // This ensures pods are automatically registered as IP targets
    const privateSubnetIds = props.kubectlPrivateSubnetIds.join(",");
    const nlbService = cluster.addManifest("McpNlbService", {
      apiVersion: "v1",
      kind: "Service",
      metadata: {
        name: "mcp-server-nlb",
        namespace: "mcp-server",
        annotations: {
          // Use NLB instead of Classic LB
          "service.beta.kubernetes.io/aws-load-balancer-type": "nlb",
          // Internal (not internet-facing)
          "service.beta.kubernetes.io/aws-load-balancer-scheme": "internal",
          // Use IP targets (pods directly, not NodePort)
          "service.beta.kubernetes.io/aws-load-balancer-nlb-target-type": "ip",
          // TLS termination with ACM cert
          "service.beta.kubernetes.io/aws-load-balancer-ssl-cert":
            props.certificateArn,
          "service.beta.kubernetes.io/aws-load-balancer-ssl-ports": "443",
          // Place NLB in private subnets
          "service.beta.kubernetes.io/aws-load-balancer-subnets":
            privateSubnetIds,
        },
      },
      spec: {
        type: "LoadBalancer",
        selector: { app: "mcp-server" },
        ports: [
          {
            name: "https",
            port: 443,
            targetPort: 8000,
            protocol: "TCP",
          },
        ],
      },
    });
    nlbService.node.addDependency(deployment);

    // Retain K8s manifests on stack deletion to avoid kubectl Lambda timeout.
    // The NLB deprovisioning can exceed Lambda's 15-min limit, causing cdk destroy to hang.
    // These resources are cleaned up when the EKS cluster is destroyed.
    for (const manifest of [namespace, deployment, nlbService]) {
      manifest.node.findAll().forEach((child) => {
        if (child instanceof cdk.CfnResource) {
          child.applyRemovalPolicy(cdk.RemovalPolicy.RETAIN);
        }
      });
    }

    NagSuppressions.addStackSuppressions(
      this,
      [
        {
          id: "AwsSolutions-IAM4",
          reason: "EKS kubectl provider uses CDK-managed policies",
        },
        {
          id: "AwsSolutions-IAM5",
          reason: "EKS kubectl provider uses CDK-managed wildcard permissions",
        },
        {
          id: "AwsSolutions-L1",
          reason: "Lambda runtime is managed by CDK EKS construct",
        },
      ],
      true,
    );
  }
}
