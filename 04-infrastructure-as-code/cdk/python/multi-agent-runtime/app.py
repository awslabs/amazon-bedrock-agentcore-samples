#!/usr/bin/env python3
import aws_cdk as cdk
from multi_agent_stack import MultiAgentStack

app = cdk.App()
MultiAgentStack(app, "MultiAgentDemo")

app.synth()
