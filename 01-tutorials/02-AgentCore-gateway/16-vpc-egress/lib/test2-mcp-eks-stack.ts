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

    // ClusterIP Service — NGINX Ingress routes traffic here via path-based rules
    const mcpService = cluster.addManifest("McpService", {
      apiVersion: "v1",
      kind: "Service",
      metadata: {
        name: "mcp-server",
        namespace: "mcp-server",
      },
      spec: {
        type: "ClusterIP",
        selector: { app: "mcp-server" },
        ports: [
          {
            name: "http",
            port: 8000,
            targetPort: 8000,
            protocol: "TCP",
          },
        ],
      },
    });
    mcpService.node.addDependency(deployment);

    // --- Stock MCP Server (second MCP server, routed via NGINX Ingress) ---
    const stockDeployment = cluster.addManifest("StockMcpDeployment", {
      apiVersion: "apps/v1",
      kind: "Deployment",
      metadata: {
        name: "stock-mcp-server",
        namespace: "mcp-server",
      },
      spec: {
        replicas: 1,
        selector: { matchLabels: { app: "stock-mcp-server" } },
        template: {
          metadata: { labels: { app: "stock-mcp-server" } },
          spec: {
            containers: [
              {
                name: "stock-mcp-server",
                image: "python:3.12-slim",
                command: [
                  "sh",
                  "-c",
                  'pip install "fastmcp>=2.0" && python -c "\n' +
                    "import random\n" +
                    "from fastmcp import FastMCP\n" +
                    "mcp = FastMCP('Stock Price MCP Server')\n" +
                    "STOCKS = {'AAPL': {'name': 'Apple Inc.', 'base_price': 195.50}, 'GOOGL': {'name': 'Alphabet Inc.', 'base_price': 141.80}, 'AMZN': {'name': 'Amazon.com Inc.', 'base_price': 185.60}, 'MSFT': {'name': 'Microsoft Corp.', 'base_price': 420.30}, 'TSLA': {'name': 'Tesla Inc.', 'base_price': 245.20}}\n" +
                    "@mcp.tool()\n" +
                    "def get_stock_price(symbol: str) -> dict:\n" +
                    "    symbol = symbol.upper()\n" +
                    "    if symbol not in STOCKS:\n" +
                    "        return {'error': f'Unknown symbol: {symbol}', 'available': list(STOCKS.keys())}\n" +
                    "    stock = STOCKS[symbol]\n" +
                    "    price = round(stock['base_price'] * (1 + random.uniform(-0.05, 0.05)), 2)\n" +
                    "    change = round(price - stock['base_price'], 2)\n" +
                    "    return {'symbol': symbol, 'name': stock['name'], 'price': price, 'change': change, 'volume': random.randint(1000000, 50000000)}\n" +
                    "@mcp.tool()\n" +
                    "def get_market_summary() -> dict:\n" +
                    "    return {'indices': [{'name': 'S&P 500', 'value': round(5200 + random.uniform(-50, 50), 2)}, {'name': 'NASDAQ', 'value': round(16400 + random.uniform(-150, 150), 2)}, {'name': 'DOW', 'value': round(39200 + random.uniform(-200, 200), 2)}]}\n" +
                    "mcp.run(transport='streamable-http', host='0.0.0.0', port=8001, stateless_http=True)\n" +
                    '"',
                ],
                ports: [{ containerPort: 8001 }],
              },
            ],
          },
        },
      },
    });
    stockDeployment.node.addDependency(namespace);

    const stockMcpService = cluster.addManifest("StockMcpService", {
      apiVersion: "v1",
      kind: "Service",
      metadata: {
        name: "stock-mcp-server",
        namespace: "mcp-server",
      },
      spec: {
        type: "ClusterIP",
        selector: { app: "stock-mcp-server" },
        ports: [
          {
            name: "http",
            port: 8001,
            targetPort: 8001,
            protocol: "TCP",
          },
        ],
      },
    });
    stockMcpService.node.addDependency(stockDeployment);

    // --- NGINX Ingress resource ---
    // Path-based routing: /mcp-server/* → mcp-server:8000, /stock-mcp/* → stock-mcp-server:8001
    // The rewrite-target annotation strips the prefix so backends see /mcp (what FastMCP expects)
    const ingress = cluster.addManifest("McpIngress", {
      apiVersion: "networking.k8s.io/v1",
      kind: "Ingress",
      metadata: {
        name: "mcp-ingress",
        namespace: "mcp-server",
        annotations: {
          "kubernetes.io/ingress.class": "nginx",
          "nginx.ingress.kubernetes.io/rewrite-target": "/$2",
          "nginx.ingress.kubernetes.io/proxy-buffering": "off",
          "nginx.ingress.kubernetes.io/proxy-read-timeout": "3600",
          "nginx.ingress.kubernetes.io/proxy-send-timeout": "3600",
        },
      },
      spec: {
        ingressClassName: "nginx",
        rules: [
          {
            http: {
              paths: [
                {
                  path: "/mcp-server(/|$)(.*)",
                  pathType: "ImplementationSpecific",
                  backend: {
                    service: {
                      name: "mcp-server",
                      port: { number: 8000 },
                    },
                  },
                },
                {
                  path: "/stock-mcp(/|$)(.*)",
                  pathType: "ImplementationSpecific",
                  backend: {
                    service: {
                      name: "stock-mcp-server",
                      port: { number: 8001 },
                    },
                  },
                },
              ],
            },
          },
        ],
      },
    });
    ingress.node.addDependency(mcpService);
    ingress.node.addDependency(stockMcpService);

    // --- NLB for NGINX Ingress Controller ---
    // Created here (not in the Helm chart) to use numeric targetPort,
    // avoiding named-port resolution issues with the AWS LB Controller.
    const privateSubnetIds = props.kubectlPrivateSubnetIds.join(",");
    const nlbService = cluster.addManifest("NginxNlbService", {
      apiVersion: "v1",
      kind: "Service",
      metadata: {
        name: "nginx-ingress-nlb",
        namespace: "ingress-nginx",
        annotations: {
          "service.beta.kubernetes.io/aws-load-balancer-type": "nlb",
          "service.beta.kubernetes.io/aws-load-balancer-scheme": "internal",
          "service.beta.kubernetes.io/aws-load-balancer-nlb-target-type": "ip",
          "service.beta.kubernetes.io/aws-load-balancer-ssl-cert":
            props.certificateArn,
          "service.beta.kubernetes.io/aws-load-balancer-ssl-ports": "443",
          "service.beta.kubernetes.io/aws-load-balancer-subnets":
            privateSubnetIds,
        },
      },
      spec: {
        type: "LoadBalancer",
        selector: {
          "app.kubernetes.io/name": "ingress-nginx",
          "app.kubernetes.io/component": "controller",
        },
        ports: [
          {
            name: "https",
            port: 443,
            targetPort: 80,
            protocol: "TCP",
          },
        ],
      },
    });
    nlbService.node.addDependency(ingress);

    // Retain K8s manifests on stack deletion to avoid kubectl Lambda timeout.
    // These resources are cleaned up when the EKS cluster is destroyed.
    for (const manifest of [
      namespace,
      deployment,
      mcpService,
      stockDeployment,
      stockMcpService,
      ingress,
      nlbService,
    ]) {
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
