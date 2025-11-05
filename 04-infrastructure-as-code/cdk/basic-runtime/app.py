#!/usr/bin/env python3
import aws_cdk as cdk
from basic_runtime_stack import BasicRuntimeStack

app = cdk.App()
BasicRuntimeStack(app, "BasicAgentDemo")

app.synth()
