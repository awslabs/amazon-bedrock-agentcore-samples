# Why require IMDSv2, and why does IAM matter as much as network controls?

**IMDSv2 (Instance Metadata Service Version 2):** EC2's original metadata
service (IMDSv1) is reachable via a simple, unauthenticated HTTP GET from
anything running on the instance — including, notoriously, a
server-side-request-forgery (SSRF) vulnerability in application code, which
an attacker can use to fetch the instance's IAM credentials without any
other foothold. IMDSv2 requires a session token obtained via a PUT request
first, which SSRF payloads (typically GET-only) cannot easily replicate.
Enforcing it (`HttpTokens: required` in the instance's metadata options, not
just "available") closes a real, repeatedly-exploited class of credential
theft.

**Why IAM policy design matters as much as network design:** a reviewer
focused only on VPCs, subnets, and security groups can still miss the
biggest actual risk — an EC2 instance role, Lambda execution role, or ECS
task role with `Action: "*"` or an overly broad service wildcard
(`s3:*` on `Resource: "*"` when the workload only needs to read one bucket).
Network controls limit *how* something can be reached; IAM controls limit
*what* it can do once reached. A tightly-networked resource with an
over-permissioned role still represents a large blast radius if that
resource is ever compromised through any vector (a dependency
vulnerability, a leaked credential, a misconfigured public endpoint
elsewhere).

**What to check for:** `MetadataOptions.HttpTokens` not set to `required`
on EC2 launch configurations, and any IAM role/policy attached to a
compute resource with a wildcard action or wildcard resource where a scoped
equivalent (specific actions, specific ARNs) would satisfy the same
functional requirement.
