# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for Observability stack.

Requirements: 9.4, 9.5, 12.3
"""

import aws_cdk as cdk
from aws_cdk import assertions, aws_kms as kms
import pytest

from stacks.observability_stack import ObservabilityStack


@pytest.fixture
def template():
    app = cdk.App(context={"cloudwatch_log_retention_days": 90})
    cmk_stack = cdk.Stack(app, "CmkStack")
    cmk = kms.Key(cmk_stack, "Cmk")
    stack = ObservabilityStack(app, "TestObs", cmk=cmk)
    return assertions.Template.from_stack(stack)


class TestObservabilityStack:
    def test_log_groups_created(self, template):
        template.resource_count_is("AWS::Logs::LogGroup", 2)

    def test_log_group_retention(self, template):
        template.has_resource_properties("AWS::Logs::LogGroup", {"RetentionInDays": 90})

    def test_no_alarms(self, template):
        """All alarms removed in V2 — AgentCore built-in monitoring replaces them."""
        template.resource_count_is("AWS::CloudWatch::Alarm", 0)

    def test_no_queue_depth_alarm(self, template):
        """Queue depth alarm removed — no SQS queue in the current architecture."""
        with pytest.raises(Exception):
            template.has_resource_properties("AWS::CloudWatch::Alarm", {
                "AlarmName": "opencode-queue-depth",
            })

    def test_cost_alarm_removed(self, template):
        """Daily cost alarm was removed — naive cost calculation dropped."""
        with pytest.raises(Exception):
            template.has_resource_properties("AWS::CloudWatch::Alarm", {
                "AlarmName": "opencode-daily-cost",
            })

    def test_no_dashboard_in_stack(self, template):
        """Dashboard removed — replaced by CloudWatch GenAI Observability dashboard."""
        template.resource_count_is("AWS::CloudWatch::Dashboard", 0)
