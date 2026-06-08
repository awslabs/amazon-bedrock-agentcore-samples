# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""OpenCode Policy stack — Cedar Policy Engine for role-based access control.

Creates a CfnPolicyEngine. Cedar policies are created post-deploy via
scripts/create-policies.py using the boto3 API, because the CfnPolicy
CloudFormation resource handler has stabilization issues (NotStabilized).

Requirements: 2.1, 2.2, 2.3, 2.5, 9.1, 9.2, 9.3
"""

import aws_cdk as cdk
from aws_cdk import aws_bedrockagentcore as bedrockagentcore
import cdk_nag
from constructs import Construct


class PolicyStack(cdk.Stack):
    """Cedar Policy Engine — created via CDK; policies added post-deploy."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # -----------------------------------------------------------------
        # Cedar Policy Engine
        # -----------------------------------------------------------------
        self.policy_engine = bedrockagentcore.CfnPolicyEngine(
            self,
            "OpenCodePolicyEngine",
            name="opencode_policy_engine",
            description="Cedar policy engine for OpenCode role-based access control",
        )

        # -----------------------------------------------------------------
        # Outputs
        # -----------------------------------------------------------------
        cdk.CfnOutput(
            self,
            "PolicyEngineId",
            value=self.policy_engine.attr_policy_engine_id,
            description="Cedar Policy Engine ID",
        )

        cdk.CfnOutput(
            self,
            "PolicyEngineArn",
            value=self.policy_engine.attr_policy_engine_arn,
            description="Cedar Policy Engine ARN",
        )

        # -----------------------------------------------------------------
        # cdk-nag suppressions
        # -----------------------------------------------------------------
        cdk_nag.NagSuppressions.add_stack_suppressions(
            self,
            [
                cdk_nag.NagPackSuppression(
                    id="CdkNagValidationFailure",
                    reason="CfnPolicyEngine is an L1 construct not yet covered by cdk-nag rules.",
                ),
            ],
        )
