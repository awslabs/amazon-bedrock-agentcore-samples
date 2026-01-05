import boto3

from cx_agent_backend.domain.ports.secret_reader import SecretReader
from cx_agent_backend.infrastructure.config.settings import settings


class AWSSecretsReader(SecretReader):
    def read_secret(self, name: str) -> str:
        client = boto3.client("secretsmanager", region_name=settings.aws_region)
        try:
            print(f"Reading secret: {name} in region: {settings.aws_region}")
            response = client.get_secret_value(SecretId=name)
            return response["SecretString"]
        except client.exceptions.ResourceNotFoundException:
            print(f"Secret not found: {name} in region: {settings.aws_region}")
            raise ValueError(f"Missing secret value for {name}")
        except Exception as e:
            print(f"Error reading secret {name}: {str(e)}")
            raise
