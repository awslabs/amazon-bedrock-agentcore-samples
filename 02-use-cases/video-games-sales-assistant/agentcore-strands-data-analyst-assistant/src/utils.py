"""
Utility Functions for Video Game Sales Data Analyst Assistant

This module provides utility functions for storing and retrieving video game sales
analysis data from DynamoDB. It handles the formatting and processing of SQL query
results and analysis data for storage and retrieval.

The module uses the following SSM parameters:
- QUESTION_ANSWERS_TABLE: DynamoDB table for storing query results and analysis data
"""

import boto3
import json
from datetime import datetime
from .ssm_utils import load_config

# Load configuration from SSM parameters
try:
    CONFIG = load_config()
except Exception as e:
    print("\n" + "=" * 70)
    print("❌ CONFIGURATION LOADING ERROR")
    print("=" * 70)
    print(f"💥 Error loading configuration from SSM: {e}")
    print("=" * 70 + "\n")
    CONFIG = {}


def save_raw_query_result(
    user_prompt_uuid, user_prompt, sql_query, sql_query_description, result, message
):
    """
    Save video game sales analysis query results to DynamoDB for audit trail and future reference.

    This function stores comprehensive information about each SQL query execution including
    the original user question, the generated SQL query, results, and metadata for
    tracking and auditing purposes.

    Args:
        user_prompt_uuid (str): Unique identifier for the user prompt/analysis session
        user_prompt (str): The original user question about video game sales data
        sql_query (str): The executed SQL query against the video game sales database
        sql_query_description (str): Human-readable description of what the query analyzes
        result (dict): The query results and metadata
        message (str): Additional information about the result (e.g., truncation notices)

    Returns:
        dict: Response with success status and DynamoDB response or error details
    """
    try:
        # Check if the table name is available
        question_answers_table = CONFIG.get("QUESTION_ANSWERS_TABLE")
        if not question_answers_table:
            return {"success": False, "error": "QUESTION_ANSWERS_TABLE not configured"}

        dynamodb_client = boto3.client("dynamodb")

        response = dynamodb_client.put_item(
            TableName=question_answers_table,
            Item={
                "id": {"S": user_prompt_uuid},
                "my_timestamp": {"N": str(int(datetime.now().timestamp()))},
                "datetime": {"S": str(datetime.now())},
                "user_prompt": {"S": user_prompt},
                "sql_query": {"S": sql_query},
                "sql_query_description": {"S": sql_query_description},
                "data": {"S": json.dumps(result)},
                "message_result": {"S": message},
            },
        )

        print("\n" + "=" * 70)
        print("✅ VIDEO GAME SALES ANALYSIS DATA SAVED TO DYNAMODB")
        print("=" * 70)
        print(f"🆔 Session ID: {user_prompt_uuid}")
        print(f"📊 DynamoDB Table: {question_answers_table}")
        print("=" * 70 + "\n")
        return {"success": True, "response": response}

    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ VIDEO GAME SALES ANALYSIS DATA SAVE ERROR")
        print("=" * 70)
        print(f"📊 DynamoDB Table: {question_answers_table}")
        print(f"💥 Error: {str(e)}")
        print("=" * 70 + "\n")
        return {"success": False, "error": str(e)}
