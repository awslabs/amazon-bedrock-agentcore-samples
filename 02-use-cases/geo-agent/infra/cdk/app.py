#!/usr/bin/env python3
"""CDK app entry point for GEO Edge Serving infrastructure."""

import aws_cdk as cdk
from geo_stack import GeoEdgeServingStack

app = cdk.App()

GeoEdgeServingStack(
    app,
    "GeoEdgeServing",
    env=cdk.Environment(
        region=app.node.try_get_context("region") or "us-east-1",
    ),
)

app.synth()
