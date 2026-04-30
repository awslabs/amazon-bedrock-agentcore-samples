<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Troubleshooting

Common problems seen during deploy, redeploy, and cleanup, and how to get past them.

## "Resource already exists" errors after a previous deployment

Several resources use `RETAIN` removal policy (DynamoDB table, S3 bucket, ECR repository, CloudWatch log groups) to prevent accidental data loss. After `cdk destroy`, these resources remain and can cause "already exists" errors on the next `cdk deploy`. Run the cleanup script before redeploying:

```bash
export AWS_REGION=us-east-1   # match your target region
./scripts/cleanup-retained-resources.sh
```

The script removes: the `opencode-jobs` DynamoDB table, the `opencode-artifacts-*` S3 bucket, the `opencode-agentcore` ECR repository, the `/opencode/*` CloudWatch log groups, and any orphaned security groups, subnets, and VPCs tagged with `Project=OpenCode`.

AgentCore-managed ENIs attached to security groups may take 5-10 minutes to release after runtime deletion. If the script reports "ENIs may still be releasing", wait a few minutes and run it again. The SGs and VPC are orphaned but won't block a fresh deploy - CDK creates new ones.

## IAM role already exists during deployment

If deploying to a second region in the same account, IAM roles (which are global) may conflict. The role names include the region suffix (e.g., `opencode-agentcore-execution-role-us-east-1`) to prevent this. If you see this error from an older deployment, delete the orphaned role manually.

## Security group deletion fails during `cdk destroy`

AgentCore runtimes create ENIs in your VPC subnets that are managed by the service. After the runtime is deleted, these ENIs take several minutes to release. `cdk destroy` will fail with `resource has a dependent object` on the security group. Wait a few minutes and run `cdk destroy` again, or use `./scripts/cleanup-retained-resources.sh` to clean up.

## CDK bootstrap required

Run `cdk bootstrap aws://<account>/<region>` before the first deployment to a new region.

## GitHub OAuth App not working

Verify the callback URL in your GitHub OAuth App matches the provider-specific URL from AgentCore Identity. Run `./scripts/setup-oauth-app.sh` — it displays the correct callback URL after registering the provider. The URL format is `https://bedrock-agentcore.<region>.amazonaws.com/identities/oauth2/callback/<provider-uuid>`, where the UUID is assigned when the credential provider is created.

## Gateway targets not working

The Gateway MCP Server target (`opencode`) is created natively in CDK via `Gateway.add_mcp_server_target()` and uses `GATEWAY_IAM_ROLE` for Gateway to Runtime authentication (SigV4). Tools are discovered dynamically via implicit sync. If the target is missing or misconfigured, re-run `cdk deploy OpenCodeGateway` to recreate it from the CloudFormation template.

## Regional deployment failures

If deployment fails with an unrecognized `AWS::BedrockAgentCore::*` resource type, the target region does not yet support Bedrock AgentCore. Deploy to a supported region (us-east-1 or eu-central-1 are confirmed working) or see the tested regions note in [HARDENING.md](HARDENING.md#tested-regions).
