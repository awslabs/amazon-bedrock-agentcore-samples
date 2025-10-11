#!/usr/bin/env python3
from bedrock_agentcore.identity.auth import requires_access_token
from boto3.session import Session
import argparse
import boto3
import json
import logging
import requests
import sys
import traceback
import urllib.parse
import uuid

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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


def main():
    parser = argparse.ArgumentParser(description="Agent Runtime CLI Tool")
    parser.add_argument("--prompt", required=True, help="Prompt to send to the agent")
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

    print("🚀 Agent Runtime CLI Tool")
    print("=" * 30)

    # Get AWS info
    account_id, region = get_aws_info()
    print(f"📋 AWS Account ID: {account_id}")
    print(f"🌍 AWS Region: {region}")

    # Get the nested AgentServerStack name from the parent stack
    print(f"📦 Parent Stack Name: {args.stack_name}")
    agent_stack_name = get_nested_stack_name(args.stack_name, "AgentServerStack", region)
    print(f"📦 Agent Stack Name: {agent_stack_name}")

    # Get runtime ID and provider name from the nested stack outputs
    runtime_id = get_stack_output(agent_stack_name, "AgentRuntimeId", region)
    provider_name = get_stack_output(agent_stack_name, "AgentProviderName", region)
    print(f"🤖 Agent Runtime ID: {runtime_id}")
    print(f"🔐 OAuth2 Provider: {provider_name}")

    # Create and run the agent client
    try:

        @requires_access_token(
            provider_name=provider_name,
            scopes=[],
            auth_flow="M2M",
            into="bearer_token",
            force_authentication=True,
        )
        def invoke_endpoint(
            runtime_id, session_id, payload, stream=False, bearer_token=""
        ):
            """Invoke agent runtime with given parameters"""

            print(f"🔑 Bearer token received: {bearer_token[:20]}...")
            agent_arn = (
                f"arn:aws:bedrock-agentcore:{region}:{account_id}:runtime/{runtime_id}"
            )

            print(agent_arn)
            escaped_arn = urllib.parse.quote(agent_arn, safe="")
            url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_arn}/invocations"

            headers = {
                "authorization": f"Bearer {bearer_token}",
                "Content-Type": "application/json",
                "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
            }

            try:
                body = json.loads(payload) if isinstance(payload, str) else payload
            except json.JSONDecodeError:
                body = {"payload": payload}

            try:
                response = requests.post(
                    url,
                    params={"qualifier": "DEFAULT"},
                    headers=headers,
                    json=body,
                    timeout=100,
                    stream=stream,
                )
                if stream:
                    last_data = False
                    for line in response.iter_lines(chunk_size=1):
                        if line:
                            line = line.decode("utf-8")
                            if line.startswith("data: "):
                                last_data = True
                                line = line[6:]
                                line = line.replace('"', "")
                                print(line)
                            elif line:
                                line = line.replace('"', "")
                                if last_data:
                                    print("\n" + line)
                                last_data = False
                else:
                    return response

            except requests.exceptions.RequestException as e:
                print("Failed to invoke agent endpoint: %s", str(e))
                raise

        print(
            invoke_endpoint(
                runtime_id,
                str(uuid.uuid4()),
                payload={
                    "prompt": args.prompt
                },
            ).content
        )

    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")
        logger.error(f"Main traceback: {traceback.format_exc()}")
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
