<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Managed Amazon VPC Lattice

> This feature is made available to you as a "Beta Service" as defined in the [AWS Service Terms](https://aws.amazon.com/service-terms/). It is subject to your Agreement with AWS and the AWS Service Terms.

Amazon Bedrock AgentCore Gateway creates and manages the VPC Lattice resource gateway and resource configuration on your behalf. You provide your VPC, subnets, and optional security groups — AgentCore handles the rest.

![arch](./images/arch.png)

## How it works

When you call `CreateGatewayTarget` with `privateEndpoint.managedLatticeResource`, AgentCore:

1. **Creates a Resource Gateway** in your VPC — provisions one ENI per subnet you specify. These ENIs are the entry point for AgentCore traffic into your VPC.
2. **Creates a Resource Configuration** scoped to your target endpoint — this defines what AgentCore is allowed to reach through the Resource Gateway.
3. **Associates the Resource Configuration** with the AgentCore service network — this enables end-to-end connectivity.

If a Resource Gateway already exists in your account with the same VPC, subnet, and security group IDs, AgentCore reuses it rather than creating a new one.

AgentCore uses the `AWSServiceRoleForBedrockAgentCoreGatewayNetwork` service-linked role to manage these resources. This role is created automatically the first time you create a gateway target with a managed private endpoint. You do not need VPC Lattice permissions in your own IAM policies.

- Make sure you have correct IAM permissions for [AgentCore Gateway managed Amazon VPC Lattice](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/vpc-egress-private-endpoints.html#lattice-vpc-egress-managed-lattice)
- Learn about Amazon Bedrock AgentCore Gateway - [Service Linked role](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/vpc-egress-private-endpoints.html#lattice-vpc-egress-slr).


## What you need to provide

```json
{
  "privateEndpoint": {
    "managedLatticeResource": {
      "vpcIdentifier": "vpc-0abc123def456",
      "subnetIds": ["subnet-0abc123", "subnet-0def456"],
      "endpointIpAddressType": "IPV4",
      "securityGroupIds": ["sg-0abc123def"],
      "routingDomain": "internal-xxx.elb.amazonaws.com"
    }
  }
}
```

### Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `vpcIdentifier` | Yes | The ID of the VPC that contains your private resource. |
| `subnetIds` | Yes | Subnet IDs where the Resource Gateway ENIs will be placed. |
| `endpointIpAddressType` | Yes | IP address type. Valid values: `IPV4`, `IPV6`. |
| `securityGroupIds` | No | Security groups for the Resource Gateway ENIs. See [Security groups](#security-groups). |
| `routingDomain` | No | Publicly resolvable domain for VPC Lattice routing. See [Routing domain](#routing-domain). |
| `tags` | No | Tags for the managed Resource Gateway. `BedrockAgentCoreGatewayManaged` is reserved. |

## Security groups

The security group controls what **outbound traffic** the Resource Gateway ENIs can send to resources inside your VPC.

**If you do not pass `securityGroupIds`**, AgentCore uses the VPC's default security group. The default SG typically only allows traffic from itself, meaning the ENIs cannot reach your resource — the target creation will fail with a timeout error.

**Always pass a security group** that allows outbound traffic on the port your resource listens on (e.g., port 443 for HTTPS). The simplest approach is to pass the same security group used by your load balancer or VPC endpoint.

Example from the [Getting Started lab](./01-getting-started.ipynb):
```python
"securityGroupIds": [VPCE_SG_ID]  # VPCE SG allows inbound 443 from VPC CIDR
```

## Routing domain

VPC Lattice requires a **publicly resolvable domain** for the resource configuration. If your target endpoint uses a domain that is not publicly resolvable (e.g., a Route 53 private hosted zone), you must set `routingDomain` to an intermediate publicly resolvable domain.

When `routingDomain` is set, AgentCore routes traffic through the routing domain but sends requests with the actual endpoint domain as the TLS SNI hostname, so your resource receives requests addressed to its actual domain.

## Labs

| Notebook | Description |
|----------|-------------|
| [01-getting-started.ipynb](./01-getting-started.ipynb) | Deploy a private API Gateway with mock integrations and connect it to AgentCore Gateway. No domain or certificate needed — uses the API-VPCE DNS format. |
| 02-peering.ipynb (coming soon) | Connect to a private resource in a peered VPC using managed VPC Lattice. |

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](../LICENSE.txt) file for details.
