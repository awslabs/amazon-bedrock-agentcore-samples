#!/usr/bin/env python3
import asyncio
import argparse
import json
import sys
import boto3
import logging
import traceback
from boto3.session import Session
from datetime import timedelta

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import urllib.parse
from bedrock_agentcore.identity.auth import requires_access_token

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_aws_info():
    """Get AWS account ID and region from boto3 session"""
    try:
        boto_session = Session()

        # Get region
        region = boto_session.region_name
        if not region:
            # Try to get from default session
            region = (
                boto3.DEFAULT_SESSION.region_name if boto3.DEFAULT_SESSION else None
            )
            if not region:
                raise ValueError(
                    "AWS region not configured. Please set AWS_DEFAULT_REGION or configure AWS CLI."
                )

        # Get account ID using STS
        sts = boto_session.client("sts")
        account_id = sts.get_caller_identity()["Account"]

        return account_id, region

    except Exception as e:
        print(f"❌ Error getting AWS info: {e}")
        print(
            "Please ensure AWS credentials are configured (aws configure or environment variables)"
        )
        sys.exit(1)


def get_nested_stack_name(parent_stack_name, logical_resource_id, region):
    """Get the physical resource ID (stack name) of a nested stack"""
    try:
        cfn = boto3.client('cloudformation', region_name=region)
        response = cfn.describe_stack_resource(
            StackName=parent_stack_name,
            LogicalResourceId=logical_resource_id
        )

        physical_resource_id = response['StackResourceDetail']['PhysicalResourceId']
        # Physical resource ID for nested stacks is the full stack ARN
        # Extract just the stack name from the ARN
        # Format: arn:aws:cloudformation:region:account:stack/stack-name/guid
        stack_name = physical_resource_id.split('/')[-2]
        return stack_name

    except Exception as e:
        print(f"❌ Error getting nested stack name: {e}")
        sys.exit(1)


def get_stack_output(stack_name, output_key, region):
    """Get CloudFormation stack output value"""
    try:
        cfn = boto3.client('cloudformation', region_name=region)
        response = cfn.describe_stacks(StackName=stack_name)

        if not response['Stacks']:
            raise ValueError(f"Stack '{stack_name}' not found")

        stack = response['Stacks'][0]
        outputs = stack.get('Outputs', [])

        for output in outputs:
            if output['OutputKey'] == output_key:
                return output['OutputValue']

        raise ValueError(f"Output '{output_key}' not found in stack '{stack_name}'")

    except Exception as e:
        print(f"❌ Error getting stack output: {e}")
        sys.exit(1)


def create_mcp_client(provider_name, runtime_id):
    """Create MCP client with given parameters"""

    # Get AWS info from boto3
    account_id, region = get_aws_info()

    print(f"📋 AWS Account ID: {account_id}")
    print(f"🌍 AWS Region: {region}")

    @requires_access_token(
        provider_name=provider_name,
        scopes=[],
        auth_flow="M2M",
        into="bearer_token",
        force_authentication=True,
    )
    async def connect(bearer_token):
        print(f"Bearer token received: {bearer_token}")
        agent_arn = (
            f"arn:aws:bedrock-agentcore:{region}:{account_id}:runtime/{runtime_id}"
        )

        print(agent_arn)
        escaped_arn = urllib.parse.quote(agent_arn, safe="")
        mcp_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_arn}/invocations?qualifier=DEFAULT"

        headers = {
            "authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
        }

        print(f"🔗 Connecting to: {mcp_url}")
        logger.info(f"Agent ARN: {agent_arn}")
        logger.info(f"Headers: {dict(headers)}")

        try:
            logger.info("Creating streamable HTTP client...")
            async with streamablehttp_client(
                mcp_url,
                headers,
                timeout=timedelta(seconds=120),
                terminate_on_close=False,
            ) as (read_stream, write_stream, _):
                logger.info("HTTP client created successfully")
                logger.info("Creating MCP client session...")

                try:
                    async with ClientSession(read_stream, write_stream) as session:
                        print("🔄 Initializing MCP session...")
                        logger.info("Calling session.initialize()...")
                        await session.initialize()
                        logger.info("Session initialized successfully")
                        print("✅ MCP session initialized")

                        # List available tools
                        print("\n🔄 Listing available tools...")
                        logger.info("Calling session.list_tools()...")
                        tool_result = await session.list_tools()
                        logger.info(f"Got {len(tool_result.tools)} tools")

                        print("\n📋 Available MCP Tools:")
                        print("=" * 50)
                        for tool in tool_result.tools:
                            print(f"🔧 {tool.name}")
                            print(f"   Description: {tool.description}")
                            if hasattr(tool, "inputSchema") and tool.inputSchema:
                                properties = tool.inputSchema.get("properties", {})
                                if properties:
                                    print(f"   Parameters: {list(properties.keys())}")
                            print()

                        print(f"✅ Found {len(tool_result.tools)} tools available.")

                        # Test some tools
                        print("\n🧪 Testing MCP Tools:")
                        print("=" * 50)

                        test_cases = [
                            ("get_reviews", {"review_id": "1"}),
                            ("get_products", {"product_id": 1}),
                        ]

                        for tool_name, args in test_cases:
                            try:
                                print(f"\n➕ Testing {tool_name}({args})...")
                                logger.info(
                                    f"Calling tool {tool_name} with args {args}"
                                )
                                result = await session.call_tool(
                                    name=tool_name, arguments=args
                                )
                                logger.info(f"Tool {tool_name} returned: {result}")
                                if result.content:
                                    print(f"   Result: {result.content[0].text}")
                                else:
                                    print("   No content returned")
                            except Exception as e:
                                logger.error(f"Error calling tool {tool_name}: {e}")
                                logger.error(f"Traceback: {traceback.format_exc()}")
                                print(f"   Error: {e}")

                except Exception as session_e:
                    logger.error(f"Error in MCP session: {session_e}")
                    logger.error(f"Session traceback: {traceback.format_exc()}")
                    raise session_e

        except Exception as e:
            logger.error(f"Error in streamable HTTP client: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            print(f"❌ Error connecting to MCP server: {e}")

            # Print any nested exception details
            if hasattr(e, "__cause__") and e.__cause__:
                logger.error(f"Caused by: {e.__cause__}")
                logger.error(
                    f"Cause traceback: {traceback.format_exception(type(e.__cause__), e.__cause__, e.__cause__.__traceback__)}"
                )

            if hasattr(e, "__context__") and e.__context__:
                logger.error(f"Context: {e.__context__}")

            sys.exit(1)

    return connect


def main():
    parser = argparse.ArgumentParser(description="MCP DynamoDB CLI Tool")
    parser.add_argument(
        "--stack-name",
        default="customer-support-vpc",
        help="CloudFormation stack name (default: customer-support-vpc)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Set logging level based on arguments
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    else:
        logging.getLogger().setLevel(logging.WARNING)

    print("🚀 MCP DynamoDB CLI Tool")
    print("=" * 30)

    # Get AWS info
    account_id, region = get_aws_info()
    print(f"📋 AWS Account ID: {account_id}")
    print(f"🌍 AWS Region: {region}")

    # Get the nested MCPServerStack name from the parent stack
    print(f"📦 Parent Stack Name: {args.stack_name}")
    mcp_stack_name = get_nested_stack_name(args.stack_name, "MCPServerStack", region)
    print(f"📦 MCP Stack Name: {mcp_stack_name}")

    # Get runtime ID and provider name from the nested stack outputs
    runtime_id = get_stack_output(mcp_stack_name, "MCPDynamoDBRuntimeId", region)
    provider_name = get_stack_output(mcp_stack_name, "MCPProviderName", region)
    print(f"🤖 MCP Runtime ID: {runtime_id}")
    print(f"🔐 OAuth2 Provider: {provider_name}")

    # Create and run the MCP client
    try:
        client = create_mcp_client(provider_name, runtime_id)
        asyncio.run(client())
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
        logger.error(f"Main traceback: {traceback.format_exc()}")
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
