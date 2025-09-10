"""
RDS Data API Utilities

This module provides functions to interact with Amazon Aurora Serverless PostgreSQL
databases using the RDS Data API. It handles configuration loading, query execution,
and result formatting.

Configuration is loaded from AWS Systems Manager Parameter Store with the following
required parameters:
- SECRET_ARN: ARN of the AWS Secrets Manager secret containing database credentials
- AURORA_RESOURCE_ARN: ARN of the Aurora Serverless cluster
- DATABASE_NAME: Name of the database to connect to

Optional parameters:
- MAX_RESPONSE_SIZE_BYTES: Maximum size of the response in bytes (default: 25600)
"""

import boto3
import json
from botocore.exceptions import ClientError
from decimal import Decimal
from .ssm_utils import load_config

# Load configuration from SSM parameters
try:
    CONFIG = load_config()
except Exception as e:
    print("\n" + "="*70)
    print("❌ CONFIGURATION LOADING ERROR")
    print("="*70)
    print(f"💥 Error loading configuration from SSM: {e}")
    print("="*70 + "\n")
    CONFIG = {}


def validate_configuration():
    """
    Validates that all required configuration parameters are present.
    
    Raises:
        ValueError: If any required configuration parameters are missing
    """
    required_params = ["SECRET_ARN", "AURORA_RESOURCE_ARN", "DATABASE_NAME", "AWS_REGION"]
    missing_params = [param for param in required_params if param not in CONFIG or not CONFIG[param]]
    
    if missing_params:
        raise ValueError(f"Missing required configuration parameters: {', '.join(missing_params)}")


def get_rds_data_client(region_name: str):
    """
    Creates and returns an RDS Data API client.
    
    Args:
        region_name: AWS region where the Aurora Serverless cluster is located
        
    Returns:
        boto3.client: RDS Data API client
    """
    session = boto3.session.Session()
    return session.client(service_name="rds-data", region_name=region_name)


def execute_statement(sql_query: str, aws_region: str, aurora_resource_arn: str, secret_arn: str, database_name: str):
    """
    Executes a SQL statement using the RDS Data API.
    
    Args:
        sql_query: SQL query string to execute
        aws_region: AWS region where the Aurora Serverless cluster is located
        aurora_resource_arn: ARN of the Aurora Serverless cluster
        secret_arn: ARN of the secret containing database credentials
        database_name: Name of the database to connect to
        
    Returns:
        dict: Response from the RDS Data API
    """
    client = get_rds_data_client(aws_region)
    
    try:
        response = client.execute_statement(
            resourceArn=aurora_resource_arn,
            secretArn=secret_arn,
            database=database_name,
            sql=sql_query,
            includeResultMetadata=True
        )
        print("\n" + "="*70)
        print("✅ SQL STATEMENT EXECUTED SUCCESSFULLY")
        print("="*70)
        print(f"🗄️  Database: {database_name}")
        print(f"📊 Query length: {len(sql_query)} characters")
        print("="*70 + "\n")
        return response
    except ClientError as e:
        print("\n" + "="*70)
        print("❌ SQL EXECUTION ERROR")
        print("="*70)
        print(f"🗄️  Database: {database_name}")
        print(f"💥 Error: {e}")
        print("="*70 + "\n")
        return {"error": str(e)}


def get_size(string: str) -> int:
    """
    Calculates the size of a string in bytes when encoded as UTF-8.
    
    Args:
        string: The string to measure
        
    Returns:
        int: Size of the string in bytes
    """
    return len(string.encode("utf-8"))


def run_sql_query(sql_query: str) -> str:
    """
    Executes a SQL query using the RDS Data API and returns the results as JSON.
    
    The function handles connection to the database, query execution, and formatting
    of results. Special data types (Decimal, date) are properly converted for JSON.
    If the result size exceeds MAX_RESPONSE_SIZE_BYTES, it's truncated.
    
    Args:
        sql_query: SQL query string to execute
        
    Returns:
        str: JSON string containing query results or error information
    """
    print("\n" + "="*70)
    print("🔍 SQL QUERY EXECUTION")
    print("="*70)
    print(f"📝 Query: {sql_query[:100]}{'...' if len(sql_query) > 100 else ''}")
    print("="*70)
    try:
        # Validate configuration parameters before proceeding
        validate_configuration()
        
        response = execute_statement(
            sql_query,
            CONFIG["AWS_REGION"],
            CONFIG["AURORA_RESOURCE_ARN"],
            CONFIG["SECRET_ARN"],
            CONFIG["DATABASE_NAME"]
        )

        if "error" in response:
            return json.dumps({
                "error": f"Something went wrong executing the query: {response['error']}"
            })

        print("\n" + "="*50)
        print("✅ QUERY PROCESSING COMPLETE")
        print("="*50)
        print(f"📊 Records found: {len(response.get('records', []))}")
        print("="*50 + "\n")

        records = []
        records_to_return = []
        message = ""

        # Process the response from RDS Data API
        if "records" in response:
            column_metadata = response.get("columnMetadata", [])
            column_names = [col.get("name") for col in column_metadata]
            
            for row in response["records"]:
                record = {}
                for i, value in enumerate(row):
                    # RDS Data API returns values as dictionaries with type indicators
                    # e.g., {"stringValue": "value"}, {"longValue": 123}, etc.
                    for value_type, actual_value in value.items():
                        if value_type == "numberValue" and isinstance(actual_value, Decimal):
                            record[column_names[i]] = float(actual_value)
                        elif value_type == "stringValue" and column_metadata[i].get("typeName") == "date":
                            record[column_names[i]] = actual_value  # Already a string
                        else:
                            record[column_names[i]] = actual_value
                records.append(record)
                
            max_response_size = CONFIG.get("MAX_RESPONSE_SIZE_BYTES", 25600)
            if get_size(json.dumps(records)) > max_response_size:
                for item in records:
                    if get_size(json.dumps(records_to_return)) <= max_response_size:
                        records_to_return.append(item)
                message = (
                    f"The data is too large, it has been truncated from "
                    f"{len(records)} to {len(records_to_return)} rows."
                )
            else:
                records_to_return = records

        if message != "":
            return json.dumps({"result": records_to_return, "message": message})
        else:
            return json.dumps({"result": records_to_return})
            
    except ValueError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Unexpected error: {str(e)}"})
