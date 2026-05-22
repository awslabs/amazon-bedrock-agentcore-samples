import * as cdk from "aws-cdk-lib";
import * as agentcore from "aws-cdk-lib/aws-bedrockagentcore";
import * as iam from "aws-cdk-lib/aws-iam";
import * as cr from "aws-cdk-lib/custom-resources";
import { Construct } from "constructs";
import * as fs from "fs";
import * as path from "path";

/**
 * Amazon Bedrock AgentCore Policy Stack for Lakehouse Agent
 *
 * Prerequisites:
 *   Before deploying, remove Interceptors from the Gateway.
 *   (Interceptor + Policy Engine の共存時にポリシー作成が内部エラーになる問題の回避)
 *
 * Deploy flow:
 *   1. CfnPolicyEngine — Policy Engine 作成
 *   2. CfnPolicy x N — Cedar ポリシー作成 (permit_all を最初に、forbid をその後に)
 *   3. IAM Policy — Gateway ロールに Policy 評価権限を追加
 *   4. UpdateGateway (AwsCustomResource) — Policy Engine + Interceptor を同時アタッチ
 */
export class PolicyStack extends cdk.Stack {
	constructor(scope: Construct, id: string, props?: cdk.StackProps) {
		super(scope, id, props);

		// --- Context values ---
		const gatewayId = this.node.tryGetContext("gatewayId") as string;
		const gatewayName = this.node.tryGetContext("gatewayName") as string;
		const gatewayArn = this.node.tryGetContext("gatewayArn") as string;
		const gatewayRoleArn = this.node.tryGetContext("gatewayRoleArn") as string;
		const discoveryUrl = this.node.tryGetContext("discoveryUrl") as string;
		const allowedClientId = this.node.tryGetContext(
			"allowedClientId",
		) as string;
		const requestInterceptorArn = this.node.tryGetContext(
			"requestInterceptorArn",
		) as string;
		const responseInterceptorArn = this.node.tryGetContext(
			"responseInterceptorArn",
		) as string;

		// --- Step 1: Policy Engine (CloudFormation native) ---
		const policyEngine = new agentcore.CfnPolicyEngine(this, "PolicyEngine", {
			name: "LakehousePolicyEngine",
			description: "Cedar policies for lakehouse-agent: Design 1 + Design 3",
		});

		// --- Step 2: Cedar policies (CfnPolicy, chained sequentially) ---
		// permit_all must be created FIRST (IGNORE_ALL_FINDINGS for Overly Permissive warning).
		// forbid policies are created after permit_all exists (avoids Overly Restrictive error).
		const policiesDir = path.join(__dirname, "..", "policies");
		const policyFiles = fs
			.readdirSync(policiesDir)
			.filter((f) => f.endsWith(".cedar"))
			.sort();

		// Reorder: permit_all first, then forbids
		const permitFirst = [
			...policyFiles.filter((f) => f.startsWith("permit")),
			...policyFiles.filter((f) => !f.startsWith("permit")),
		];

		let permitAllPolicy: agentcore.CfnPolicy | undefined;
		const allPolicies: agentcore.CfnPolicy[] = [];

		for (const policyFile of permitFirst) {
			const policyName = policyFile.replace(".cedar", "").replace(/-/g, "_");
			let cedarStatement = fs.readFileSync(
				path.join(policiesDir, policyFile),
				"utf-8",
			);
			cedarStatement = cedarStatement.replace(/\{gateway_arn\}/g, gatewayArn);

			const isPermitAll = policyName === "permit_all";

			const policy = new agentcore.CfnPolicy(this, `Policy_${policyName}`, {
				policyEngineId: policyEngine.attrPolicyEngineId,
				name: policyName,
				definition: { cedar: { statement: cedarStatement } },
				validationMode: isPermitAll
					? "IGNORE_ALL_FINDINGS"
					: "FAIL_ON_ANY_FINDINGS",
			});

			if (isPermitAll) {
				// permit_all depends on engine
				policy.addDependency(policyEngine);
				permitAllPolicy = policy;
			} else {
				// forbid policies depend on permit_all (avoids Overly Restrictive)
				// but are parallel to each other
				policy.addDependency(permitAllPolicy!);
			}
			allPolicies.push(policy);
		}

		// --- Step 3: IAM permissions for Gateway role ---
		const gatewayRole = iam.Role.fromRoleArn(
			this,
			"ExistingGatewayRole",
			gatewayRoleArn,
			{ mutable: true },
		);
		const policyEvalPolicy = new iam.Policy(this, "PolicyEvalPermissions", {
			policyName: "LakehousePolicyEval",
			statements: [
				new iam.PolicyStatement({
					actions: [
						"bedrock-agentcore:AuthorizeAction",
						"bedrock-agentcore:PartiallyAuthorizeActions",
						"bedrock-agentcore:GetPolicyEngine",
						"bedrock-agentcore:CheckAuthorizePermissions",
					],
					resources: [policyEngine.attrPolicyEngineArn],
				}),
			],
		});
		gatewayRole.attachInlinePolicy(policyEvalPolicy);

		// --- Step 4: UpdateGateway — attach Policy Engine + Interceptors ---
		const updateGateway = new cr.AwsCustomResource(this, "UpdateGateway", {
			installLatestAwsSdk: true,
			onCreate: {
				service: "bedrock-agentcore-control",
				action: "UpdateGateway",
				parameters: {
					gatewayIdentifier: gatewayId,
					name: gatewayName,
					roleArn: gatewayRoleArn,
					protocolType: "MCP",
					authorizerType: "CUSTOM_JWT",
					authorizerConfiguration: {
						customJWTAuthorizer: {
							discoveryUrl,
							allowedClients: [allowedClientId],
						},
					},
					interceptorConfigurations: [
						{
							interceptor: {
								lambda: { arn: requestInterceptorArn },
							},
							interceptionPoints: ["REQUEST"],
							inputConfiguration: { passRequestHeaders: true },
						},
						{
							interceptor: {
								lambda: { arn: responseInterceptorArn },
							},
							interceptionPoints: ["RESPONSE"],
							inputConfiguration: { passRequestHeaders: true },
						},
					],
					policyEngineConfiguration: {
						arn: policyEngine.attrPolicyEngineArn,
						mode: "ENFORCE",
					},
				},
				physicalResourceId: cr.PhysicalResourceId.of(
					`update-gw-${gatewayId}-${Date.now()}`,
				),
			},
			onUpdate: {
				service: "bedrock-agentcore-control",
				action: "UpdateGateway",
				parameters: {
					gatewayIdentifier: gatewayId,
					name: gatewayName,
					roleArn: gatewayRoleArn,
					protocolType: "MCP",
					authorizerType: "CUSTOM_JWT",
					authorizerConfiguration: {
						customJWTAuthorizer: {
							discoveryUrl,
							allowedClients: [allowedClientId],
						},
					},
					interceptorConfigurations: [
						{
							interceptor: {
								lambda: { arn: requestInterceptorArn },
							},
							interceptionPoints: ["REQUEST"],
							inputConfiguration: { passRequestHeaders: true },
						},
						{
							interceptor: {
								lambda: { arn: responseInterceptorArn },
							},
							interceptionPoints: ["RESPONSE"],
							inputConfiguration: { passRequestHeaders: true },
						},
					],
					policyEngineConfiguration: {
						arn: policyEngine.attrPolicyEngineArn,
						mode: "ENFORCE",
					},
				},
				physicalResourceId: cr.PhysicalResourceId.of(
					`update-gw-${gatewayId}-${Date.now()}`,
				),
			},
			policy: cr.AwsCustomResourcePolicy.fromStatements([
				new iam.PolicyStatement({
					actions: [
						"bedrock-agentcore:UpdateGateway",
						"bedrock-agentcore:GetGateway",
					],
					resources: [gatewayArn],
				}),
				new iam.PolicyStatement({
					actions: ["iam:PassRole"],
					resources: [gatewayRoleArn],
				}),
			]),
			timeout: cdk.Duration.minutes(5),
		});

		updateGateway.node.addDependency(policyEvalPolicy);
		for (const p of allPolicies) {
			updateGateway.node.addDependency(p);
		}

		// --- Outputs ---
		new cdk.CfnOutput(this, "PolicyEngineId", {
			value: policyEngine.attrPolicyEngineId,
		});
		new cdk.CfnOutput(this, "PolicyEngineArn", {
			value: policyEngine.attrPolicyEngineArn,
		});
		new cdk.CfnOutput(this, "GatewayId", { value: gatewayId });
	}
}
