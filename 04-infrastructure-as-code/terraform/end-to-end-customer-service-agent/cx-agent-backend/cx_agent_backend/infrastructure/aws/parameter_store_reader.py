import boto3

from cx_agent_backend.infrastructure.config.settings import settings


class AWSParameterStoreReader:
    def get_parameter(self, name: str, decrypt: bool = False) -> str:
        client = boto3.client("ssm", region_name=settings.aws_region)
        try:
            response = client.get_parameter(Name=name, WithDecryption=decrypt)
            return response["Parameter"]["Value"]
        except client.exceptions.ParameterNotFound:
            raise ValueError(f"Parameter {name} not found")
