#!/usr/bin/env python3
import aws_cdk as cdk
from mcp_server_stack import MCPServerStack

app = cdk.App()
MCPServerStack(app, "MCPServerDemo")

app.synth()
