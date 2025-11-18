"""DynamoDB client for inserting JSON documents."""

import boto3
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class DynamoClient:
    def __init__(self, table_name: str, region: str = "us-east-1"):
        self.table_name = table_name
        self.region = region
        self.client = boto3.client("dynamodb", region_name=region)

    def insert_item(self, item: Dict[str, Any]) -> bool:
        """Insert a JSON document into DynamoDB table."""
        try:
            logger.info(f"Inserting item into DynamoDB table: {self.table_name}")
            
            # Convert Python dict to DynamoDB format
            dynamodb_item = self._convert_to_dynamodb_format(item)
            
            self.client.put_item(
                TableName=self.table_name,
                Item=dynamodb_item
            )
            
            logger.info("Successfully inserted item into DynamoDB")
            return True
            
        except Exception as e:
            logger.error(f"Error inserting item into DynamoDB: {str(e)}")
            raise

    def _convert_to_dynamodb_format(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Python dict to DynamoDB attribute format."""
        dynamodb_item = {}
        
        for key, value in item.items():
            if isinstance(value, str):
                dynamodb_item[key] = {"S": value}
            elif isinstance(value, (int, float)):
                dynamodb_item[key] = {"N": str(value)}
            elif isinstance(value, bool):
                dynamodb_item[key] = {"BOOL": value}
            elif isinstance(value, dict):
                dynamodb_item[key] = {"S": json.dumps(value)}
            elif isinstance(value, list):
                dynamodb_item[key] = {"S": json.dumps(value)}
            else:
                dynamodb_item[key] = {"S": str(value)}
                
        return dynamodb_item


_dynamo_client: DynamoClient = None


def initialize_dynamo_client(table_name: str, region: str = "us-east-1"):
    """
    Initialize the global DynamoDB client.

    Args:
        table_name: DynamoDB table name
        region: AWS region
    """
    global _dynamo_client
    _dynamo_client = DynamoClient(table_name=table_name, region=region)
    logger.info(f"DynamoDB client initialized (table: {table_name})")


def insert_item(item: Dict[str, Any]) -> bool:
    """
    Insert a JSON document using the global DynamoDB client.

    Args:
        item: Dictionary/JSON document to insert

    Returns:
        True if successful

    Raises:
        RuntimeError: If DynamoDB client not initialized
    """
    if _dynamo_client is None:
        raise RuntimeError(
            "DynamoDB client not initialized. Call initialize_dynamo_client() first."
        )
    return _dynamo_client.insert_item(item)
