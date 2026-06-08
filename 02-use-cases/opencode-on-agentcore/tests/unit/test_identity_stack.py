# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for Identity stack (stacks/identity_stack.py).

Feature: 24-cmk-encrypt-all-log-groups

Validates: Requirements 1.2, 1.4, 4.2
"""

from __future__ import annotations

import json
from pathlib import Path

import aws_cdk as cdk
from aws_cdk import assertions
from aws_cdk import aws_kms as kms

from stacks.identity_stack import IdentityStack

# ---------------------------------------------------------------------------
# Fixed stub inputs
# ---------------------------------------------------------------------------

_REGION = "us-east-1"
_ACCOUNT = "123456789012"

_CDK_JSON_PATH = Path(__file__).resolve().parents[2] / "cdk.json"


def _load_cdk_context() -> dict:
    with open(_CDK_JSON_PATH) as f:
        return json.load(f)["context"]


# ---------------------------------------------------------------------------
# Stack factory
# ---------------------------------------------------------------------------


def _build_identity_stack() -> tuple[cdk.App, IdentityStack]:
    ctx = _load_cdk_context()
    app = cdk.App(context=ctx)
    env = cdk.Environment(account=_ACCOUNT, region=_REGION)

    cmk_stack = cdk.Stack(app, "StubCmkStack", env=env)
    stub_cmk = kms.Key(cmk_stack, "StubCmk")

    identity_stack = IdentityStack(
        app,
        "OpenCodeIdentity",
        cmk=stub_cmk,
        callback_url="https://test.execute-api.us-east-1.amazonaws.com/callback",
        env=env,
    )
    return app, identity_stack


# ---------------------------------------------------------------------------
# H7 -- All log groups encrypted with CMK
# ---------------------------------------------------------------------------


class TestLogGroupsEncryptedWithCmk:
    """Verify every AWS::Logs::LogGroup in IdentityStack has a KmsKeyId."""

    def test_all_log_groups_have_kms_key_id(self) -> None:
        _app, identity_stack = _build_identity_stack()
        template = assertions.Template.from_stack(identity_stack)
        tpl = template.to_json()

        log_groups = {
            lid: res
            for lid, res in tpl.get("Resources", {}).items()
            if res.get("Type") == "AWS::Logs::LogGroup"
        }
        assert len(log_groups) >= 2, (
            f"Expected at least 2 LogGroup resources, found {len(log_groups)}"
        )

        for lid, res in log_groups.items():
            props = res.get("Properties", {})
            assert "KmsKeyId" in props, (
                f"LogGroup {lid} is missing KmsKeyId property"
            )
