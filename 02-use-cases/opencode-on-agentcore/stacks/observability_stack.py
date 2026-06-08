# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""OpenCode Observability stack — CloudWatch log groups.

Custom dashboard and alarms are not deployed — AgentCore's built-in GenAI
observability dashboard provides token usage, cost visibility, and monitoring.
ADOT collector runs as a sidecar managed by the AgentCore platform.

Requirements: 3.3, 3.4
"""

import aws_cdk as cdk
from aws_cdk import (
    aws_kms as kms,
    aws_logs as logs,
    RemovalPolicy,
)
import cdk_nag
from constructs import Construct

from stacks import retention_days


class ObservabilityStack(cdk.Stack):
    """CloudWatch log groups for container and system logs."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        cmk: kms.IKey,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        log_retention_days = self.node.try_get_context("cloudwatch_log_retention_days") or 90
        ret = retention_days(log_retention_days)

        # -----------------------------------------------------------------
        # Log Groups
        # -----------------------------------------------------------------
        self.container_log_group = logs.LogGroup(
            self, "ContainerLogGroup",
            log_group_name="/opencode/container",
            retention=ret,
            encryption_key=cmk,
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.system_log_group = logs.LogGroup(
            self, "SystemLogGroup",
            log_group_name="/opencode/system",
            retention=ret,
            encryption_key=cmk,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # -----------------------------------------------------------------
        # No custom alarms or dashboards — AgentCore built-in GenAI
        # observability provides monitoring. ADOT collector runs as a
        # sidecar managed by the AgentCore platform.
        # -----------------------------------------------------------------
