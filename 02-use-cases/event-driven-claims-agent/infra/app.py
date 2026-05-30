#!/usr/bin/env python3
import os
import aws_cdk as cdk
from claims_infra_stack import ClaimsInfraStack

app = cdk.App()
ClaimsInfraStack(app, "ClaimsInfraStack", env=cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT", "570688688682"),
    region=os.environ.get("CDK_DEFAULT_REGION", "us-west-2"),
))
app.synth()
