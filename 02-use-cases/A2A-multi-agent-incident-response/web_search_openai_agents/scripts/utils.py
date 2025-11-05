import json
import boto3
import requests
from boto3.session import Session
import sys
from typing import Any, Optional
import urllib


def get_ssm_parameter(name: str, with_decryption: bool = True) -> str:
    """Get parameter from AWS Systems Manager Parameter Store."""
    ssm = boto3.client("ssm")
    response = ssm.get_parameter(Name=name, WithDecryption=with_decryption)
    return response["Parameter"]["Value"]


def get_aws_info():
    """Get AWS account ID and region from boto3 session."""
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


def invoke_endpoint(
    agent_arn: str,
    payload,
    session_id: str,
    bearer_token: Optional[str],
    endpoint_name: str = "DEFAULT",
    stream: bool = True,
) -> Any:
    escaped_arn = urllib.parse.quote(agent_arn, safe="")

    _, region = get_aws_info()

    url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_arn}/invocations"

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
    }

    try:
        body = json.loads(payload) if isinstance(payload, str) else payload
    except json.JSONDecodeError:
        body = {"payload": payload}

    response = requests.post(
        url,
        params={"qualifier": endpoint_name},
        headers=headers,
        json=body,
        timeout=100,
        stream=stream,
    )

    if not stream:
        print(
            response.content.decode("utf-8").replace("\\n", "\n").replace('"', ""),
            flush=True,
        )
    else:
        last_data = False

        for line in response.iter_lines(chunk_size=1):
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    last_data = True
                    data_content = line[6:]
                    parsed = json.loads(data_content)

                    # Check for event structure with contentBlockDelta
                    if isinstance(parsed, dict) and "event" in parsed:
                        event = parsed["event"]
                        if isinstance(event, dict) and "contentBlockDelta" in event:
                            delta = event["contentBlockDelta"].get("delta", {})
                            if "text" in delta:
                                text = delta["text"]
                                # Replace literal \n with actual newlines
                                text = text.replace("\\n", "\n")
                                print(text, end="", flush=True)
                elif line:
                    if last_data:
                        parsed = json.loads(line)
                        # Check for event structure with contentBlockDelta
                        if isinstance(parsed, dict) and "event" in parsed:
                            event = parsed["event"]
                            if isinstance(event, dict) and "contentBlockDelta" in event:
                                delta = event["contentBlockDelta"].get("delta", {})
                                if "text" in delta:
                                    text = delta["text"]
                                    # Replace literal \n with actual newlines
                                    text = text.replace("\\n", "\n")
                                    print(text, end="", flush=True)
                    last_data = False
