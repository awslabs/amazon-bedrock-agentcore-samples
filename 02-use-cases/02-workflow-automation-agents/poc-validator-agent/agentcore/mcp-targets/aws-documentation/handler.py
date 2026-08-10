"""Bedrock AgentCore Gateway Lambda target: real AWS documentation, not a mock.

Wraps AWS Labs' own official ``awslabs.aws-documentation-mcp-server`` (a stdio
MCP server) using AWS Labs' own ``run-mcp-servers-with-aws-lambda`` adapter, so
the Gateway target this sample ships actually answers instead of pointing at
the placeholder endpoint the original build left behind.
"""

import sys

from mcp.client.stdio import StdioServerParameters
from mcp_lambda import BedrockAgentCoreGatewayTargetHandler, StdioServerAdapterRequestHandler

server_params = StdioServerParameters(
    command=sys.executable,
    args=["-m", "awslabs.aws_documentation_mcp_server.server"],
)

event_handler = BedrockAgentCoreGatewayTargetHandler(StdioServerAdapterRequestHandler(server_params))


def handler(event, context):
    return event_handler.handle(event, context)
