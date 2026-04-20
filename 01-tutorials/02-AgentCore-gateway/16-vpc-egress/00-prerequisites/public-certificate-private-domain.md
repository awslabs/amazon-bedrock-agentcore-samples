<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Public Certificate + Private Domain

> **Note:** The guidance in this document is intended for **workshop and learning purposes only**. For production deployments, please adhere to your organization's security policies, DNS management practices, and certificate lifecycle requirements.

## Overview

| Component | Type | Description |
|-----------|------|-------------|
| **Certificate** | Public (ACM) | Trusted by all clients, including AgentCore Gateway |
| **Domain** | Private (Route 53 private hosted zone) | Resolves only inside the VPC |

## What does this mean?

Your domain (e.g., `internal-mcp.example.com`) only resolves inside VPCs associated with the private hosted zone. It is invisible from the public internet.

The certificate is still publicly trusted because ACM validates domain ownership against the **public parent domain** (`example.com`), not the private hosted zone. The cert doesn't care how DNS resolves at runtime.

```
dig @8.8.8.8 internal-mcp.example.com        → NXDOMAIN (not found)
dig (from inside VPC) internal-mcp.example.com → 10.0.2.52 (load balancer private IP)
```

## How does this work with AgentCore Gateway?

AgentCore Gateway requires a publicly resolvable domain for VPC Lattice routing. Since the domain is private, you use the **`routingDomain`** parameter:

- **`endpoint`**: `https://internal-mcp.example.com/mcp` (private DNS)
- **`routingDomain`**: `internal-xxx.elb.amazonaws.com` (load balancer DNS: publicly resolvable)

VPC Lattice uses `routingDomain` for traffic routing while AgentCore invokes the endpoint domain.

## When to use this

- You don't want the domain visible in public DNS
- You don't want to modify your public hosted zone
- You want the private hosted zone in the same account as the VPC (self-contained)
- You still need a publicly trusted certificate (required by AgentCore Gateway)

## Traffic flow

```
AgentCore Gateway
  → VPC Lattice (routes via routingDomain: *.elb.amazonaws.com)
    → Resource Gateway ENIs
      → Internal Load Balancer (TLS termination with public cert)
        → Your private resource
```

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](../LICENSE.txt) file for details.
