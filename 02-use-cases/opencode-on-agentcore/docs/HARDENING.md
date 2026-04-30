<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Hardening

This is the production-hardening guide for the sample. It covers Amazon Virtual Private Cloud (Amazon VPC), Amazon Bedrock, Amazon Bedrock AgentCore, and AWS Key Management Service (AWS KMS) configuration choices that differ between a demo deployment and a production one. The defaults in the CDK stacks optimize for cost and simplicity so you can stand up a dev or demo deployment quickly. The notes below describe how to take that deployment closer to production-ready: highly available NAT, enforced Cedar policies, budget alerts, and the known limitations you should design around. Controls are listed from highest to lowest operational impact.

## NAT Gateway High Availability

The default `nat_gateways=1` in [`../stacks/vpc_stack.py`](../stacks/vpc_stack.py) is a **cost optimization for dev and sample workloads**. It routes all outbound traffic from private subnets through a single NAT Gateway in one Availability Zone.

For **production deployments**, set `nat_gateways` to match the number of AZs (default is 2, or the length of your `availability_zones` list). With a single NAT Gateway, an AZ failure takes out **all outbound connectivity** for the entire VPC, meaning the Runtime cannot reach Bedrock, GitHub, DynamoDB, or any other external service until the AZ recovers.

To change this, update the `nat_gateways` value in [`../stacks/vpc_stack.py`](../stacks/vpc_stack.py):

```python
# Production: one NAT Gateway per AZ for high availability
"nat_gateways": 2,  # match your AZ count
```

The tradeoff is cost: each NAT Gateway adds ~$32/month plus data transfer charges. For dev/test environments where brief outages are acceptable, the single NAT Gateway default keeps costs down.

## Cedar Policy Engine

The `OpenCodePolicy` stack deploys a Cedar Policy Engine. Cedar policies are created post-deploy via [`../scripts/create-policies.py`](../scripts/create-policies.py) because the `CfnPolicy` CloudFormation resource handler has stabilization issues. The Gateway associates with the Policy Engine in **LOG_ONLY** mode by default, configured natively in CDK via `AWS::BedrockAgentCore::Gateway.PolicyEngineConfiguration`. In this mode, policy violations are logged but not blocked, so you can validate policy behavior before enforcing.

**Switching from LOG_ONLY to ENFORCE mode:**

Once you've reviewed the CloudWatch logs and confirmed the policies match your intent, update the `PolicyEngineConfiguration.Mode` property in [`../stacks/gateway_stack.py`](../stacks/gateway_stack.py) from `"LOG_ONLY"` to `"ENFORCE"` and redeploy with `cdk deploy`.

**Adding custom policies (e.g., production repo deny):**

Use [`../scripts/create-policies.py`](../scripts/create-policies.py) as a template. Action names follow the `{target}___{tool}` format (e.g., `opencode___run_coding_task`), and the resource must reference the specific gateway ARN. Use `validationMode="IGNORE_ALL_FINDINGS"` for policies referencing tools discovered dynamically.

## Key Management Strategy

The sample provisions a single customer-managed AWS KMS key (CMK) in [`../stacks/security_stack.py`](../stacks/security_stack.py) and threads it through every stack that needs encryption at rest. Summary:

- **Key type:** Symmetric customer-managed CMK, one per deployment.
- **Rotation:** Automatic rotation is enabled (`enable_key_rotation=True`). AWS KMS rotates the key material annually; no action required on your part.
- **Key policy:** The default key policy permits the account root and grants use to the stack-created roles (Runtime execution role, Gateway role, Lambda roles). Review and tighten if you need to constrain which principals can use the key.
- **Alias:** `alias/opencode-cmk-{region}` for easy lookup.
- **Removal policy:** `RETAIN`, so `cdk destroy` does not delete the key. This prevents accidental loss of encrypted data in DynamoDB, CloudWatch Logs, Secrets Manager, or S3. Use [`../scripts/cleanup-retained-resources.sh`](../scripts/cleanup-retained-resources.sh) to remove the CMK alias and schedule key deletion when you're done with the sample.
- **Services using the CMK:** AWS Secrets Manager (OAuth app credentials), Amazon DynamoDB (job records), Amazon CloudWatch Logs (all log groups), Amazon S3 (CloudTrail bucket when enabled). Amazon Bedrock AgentCore managed resources (Gateway, Runtime, Policy Engine, Identity Vault) are encrypted with AWS-owned keys by default; these can be switched to customer-managed keys via the relevant service-level configuration if your threat model requires it.

For a production deployment, consider:

1. Splitting the CMK into per-data-type keys (one for secrets, one for logs, one for DynamoDB) if you need separate key policies or rotation schedules.
2. Adding explicit condition keys (`kms:ViaService`, `kms:CallerAccount`) to the key policy.
3. Enabling AWS CloudTrail data events on the CMK for full key-usage auditing.

## AWS Budgets for Cost Control

The `daily_cost_budget_usd` value in `cdk.json` (default: `50`) is a **reference value only**. It is not enforced by the stack -- there is no AWS Budget, alarm, or throttle created automatically. If Bedrock costs exceed this amount, no default alert fires unless you set up monitoring yourself.

To catch runaway Bedrock costs, create an AWS Budget with daily notifications:

1. Open the [AWS Budgets console](https://console.aws.amazon.com/billing/home#/budgets) or use the CLI
2. Create a **Cost budget** scoped to the `Amazon Bedrock` service
3. Set the budget amount to your `daily_cost_budget_usd` value and the period to **Daily**
4. Add two alert thresholds:
   - **80% of budget** -- early warning that costs are trending high
   - **100% of budget** -- immediate notification that the daily limit has been reached
5. Configure an SNS topic or email as the notification target

Using the CLI:

```bash
aws budgets create-budget \
  --account-id $CDK_DEFAULT_ACCOUNT \
  --budget '{
    "BudgetName": "opencode-daily-bedrock",
    "BudgetLimit": {"Amount": "50", "Unit": "USD"},
    "TimeUnit": "DAILY",
    "BudgetType": "COST",
    "CostFilters": {"Service": ["Amazon Bedrock"]}
  }' \
  --notifications-with-subscribers '[
    {"Notification": {"NotificationType": "ACTUAL", "ComparisonOperator": "GREATER_THAN", "Threshold": 80, "ThresholdType": "PERCENTAGE"}, "Subscribers": [{"SubscriptionType": "EMAIL", "Address": "your-email@example.com"}]},
    {"Notification": {"NotificationType": "ACTUAL", "ComparisonOperator": "GREATER_THAN", "Threshold": 100, "ThresholdType": "PERCENTAGE"}, "Subscribers": [{"SubscriptionType": "EMAIL", "Address": "your-email@example.com"}]}
  ]'
```

For full setup options, see the [AWS Budgets documentation](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html).

## Known Limitations

- **Outbound traffic from the microVM is not FQDN-restricted in v1.** The security group limits egress to port 443; AWS service traffic routes through VPC endpoints. Git clone and push traffic to any HTTPS host on the public internet is unfiltered via the NAT Gateway.
- **GSI1 hot-partition scaling cap.** The admin-monitoring GSI (`status#{status}`) has only 4 partition key values. At high volume this hits the ~3k RCU / 1k WCU per-partition limit. A sharding strategy is documented in [`../stacks/job_store_stack.py`](../stacks/job_store_stack.py) for when scale warrants it.
- **Amazon Cognito MFA is not enforced on the sample user pool.** The user pool is demo-scoped; you are responsible for enabling MFA ([Cognito MFA configuration](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-mfa.html)) and enforcing password policies suitable for your environment before routing real users through it.
- **No prompt-injection or output-content filter is applied to LLM I/O.** The pipeline relies on the upstream Amazon Bedrock model's built-in safety filters, a credential scanner ([`container/tools/scan_and_strip_credentials.py`](../container/tools/scan_and_strip_credentials.py)) that removes common credential patterns from pushed output, Cedar policies scoped to specific `opencode___{tool}` action ARNs, and microVM isolation per session. For stronger guarantees, layer on an [Amazon Bedrock Guardrail](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html) and extend the credential scanner's regex set.

## Third-party dependencies and AI components

This sample uses two third-party components at runtime, both referenced (not vendored) via standard package installers:

- **[OpenCode](https://opencode.ai)** - MIT-licensed AI coding agent, installed at container build time from the upstream installer script ([`../container/Dockerfile`](../container/Dockerfile)). Upstream source: https://github.com/sst/opencode. Pin the version explicitly in the Dockerfile for reproducibility before promoting to production.
- **[FastMCP](https://gofastmcp.com)** - MIT-licensed MCP server framework, installed from PyPI via [`../container/requirements.txt`](../container/requirements.txt).

The LLM itself is Amazon Bedrock-hosted Anthropic Claude, a pre-approved model available through the Amazon Bedrock marketplace. Bedrock enforces its own content filters and safety controls upstream of this sample; customer-side responsibility is limited to model access control via IAM (scoped to specific model ARNs in [`../stacks/agentcore_stack.py`](../stacks/agentcore_stack.py)) and application-level input/output sanitization.

The sample processes user-supplied git repositories as transient input to the LLM. Repositories are cloned into the per-session Firecracker microVM, fed to OpenCode, and discarded when the session ends. They are not logged, persisted to customer-owned storage, or redistributed. The credential scanner runs between LLM output and the git push to reduce the risk of secrets leaking into the PR.

## Deployment Notes

### Tested regions

This sample has been tested and deploys successfully in:

- **us-east-1** (US East - N. Virginia)
- **eu-central-1** (Europe - Frankfurt)

**us-west-2 may have deployment issues.** The `AWS::BedrockAgentCore::GatewayTarget.CredentialProvider` schema in us-west-2 was previously a version behind (missing the `IamCredentialProvider` sub-type). This may have been resolved since last tested. AgentCore Gateway is available in 14 commercial regions as of the latest documentation; check the [AgentCore supported regions page](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html) for the current list. Deploy to us-east-1 or eu-central-1 for confirmed compatibility.

**Other regions - managed session storage.** `FilesystemConfigurations` on `AWS::BedrockAgentCore::Runtime` is documented in the CFN template reference but not yet accepted by the CFN schema validator in every region. [`../stacks/agentcore_stack.py`](../stacks/agentcore_stack.py) only emits the property in `us-east-1` (the only confirmed-deployable region where the Runtime schema also accepts it). In every other deployable region the managed session storage feature is disabled - work directories won't persist across microVM stop/resume, but everything else works. Override via CDK context `-c enable_filesystem_configurations=true` if your region's schema has since caught up.

### Experimental CDK module

[`../stacks/gateway_stack.py`](../stacks/gateway_stack.py) depends on `aws_cdk.aws_bedrock_agentcore_alpha`, an alpha/experimental CDK module. The module is used for:

- `Gateway` - L2 construct for the AgentCore Gateway
- `CustomJwtAuthorizer` - Cognito JWT inbound authorization
- `GatewayExceptionLevel` - debug exception level
- `LambdaInterceptor` - REQUEST interceptor wiring
- `GatewayCredentialProvider.from_iam_role()` - GATEWAY_IAM_ROLE credential provider
- `Gateway.add_mcp_server_target()` - MCP target creation

Alpha APIs may break across minor version bumps. `requirements.txt` pins `aws-cdk.aws-bedrock-agentcore-alpha` with a tight upper bound (currently `>=2.251.0a0,<2.252.0a0`) so minor version bumps of the alpha module require a deliberate synth-and-diff review. Upgrade by bumping both the lower bound and the upper bound together, then running `cdk synth --all` to confirm the template is unchanged.

**Known alpha-module gap - `IamCredentialProvider` sub-object.** `GatewayCredentialProvider.from_iam_role()` emits only `{"CredentialProviderType": "GATEWAY_IAM_ROLE"}` in the synthesized template, omitting the sibling `CredentialProvider.IamCredentialProvider` sub-object that the CFN runtime handler requires. [`../stacks/gateway_stack.py`](../stacks/gateway_stack.py) works around this with an `add_property_override` escape hatch on the underlying `CfnGatewayTarget`. The override injects `{"IamCredentialProvider": {"Service": "bedrock-agentcore"}}` at the correct path. This works in regions whose CFN schema knows about `IamCredentialProvider` (currently us-east-1). us-west-2 is blocked by a separate regional schema lag - see the Tested regions section.

**Known alpha-module gap - Gateway -> DefaultPolicy ordering.** The alpha `Gateway` L2 attaches IAM permissions (including `bedrock-agentcore:GetPolicyEngine`) via `add_to_principal_policy`, which CDK synthesizes into a `DefaultPolicy` resource that is a sibling of the Gateway in the template. When the Gateway resource carries a `PolicyEngineConfiguration` property, the CFN handler validates the policy-engine reference by calling `GetPolicyEngine` using the Gateway's role at creation time - which races the DefaultPolicy attachment and fails with `AccessDenied`. [`../stacks/gateway_stack.py`](../stacks/gateway_stack.py) adds an explicit `cfn_gateway.add_depends_on(cfn_default_policy)` to force the correct ordering.

**Fallback path:** if the alpha L2 drifts, the L1 `aws_cdk.aws_bedrockagentcore.CfnGatewayTarget` with `McpTargetConfigurationProperty` is the documented alternative. The `PolicyEngineConfiguration` is already attached via an `add_property_override` escape hatch on the underlying `CfnGateway`, so it is unaffected by alpha-module drift.

### Why `create-policies.py` is still a script

`AWS::BedrockAgentCore::Policy` (the `CfnPolicy` resource) has a service-side stabilization issue: the CloudFormation resource handler reports `NotStabilized` / `Resource stabilization failed` even when policy creation succeeds, causing stack `CREATE_FAILED` and rollback. [`../scripts/create-policies.py`](../scripts/create-policies.py) bypasses CloudFormation entirely, polls `get_policy` for up to 60 seconds, and cleans up `FAILED` leftovers from previous attempts.

**Unblock criterion:** this script can be migrated into CDK when AWS ships the service-side fix to `CfnPolicy` stabilization (tracked via the AWS "What's New" feed for AgentCore Policy).

**Note:** `AWS::BedrockAgentCore::Gateway.PolicyEngineConfiguration` does **not** share this stabilization bug and is attached natively in CDK via an `add_property_override` escape hatch on the underlying `CfnGateway`.
