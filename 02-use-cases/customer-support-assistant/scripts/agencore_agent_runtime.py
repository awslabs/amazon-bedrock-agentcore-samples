import boto3
from utils import get_aws_region

agentcore_control_client = boto3.client(
    "bedrock-agentcore-control", region_name=get_aws_region()
)

# print(agentcore_control_client.list_agent_runtimes())

runtime_delete_response = agentcore_control_client.delete_agent_runtime()
