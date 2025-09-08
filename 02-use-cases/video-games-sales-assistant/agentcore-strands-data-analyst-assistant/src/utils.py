"""
Utility Functions for Data Analyst Assistant

This module provides utility functions for storing and retrieving data from DynamoDB,
including query results and conversation history. It handles the formatting and
processing of data for storage and retrieval.

The module uses the following SSM parameters:
- QUESTION_ANSWERS_TABLE: DynamoDB table for storing query results
- AGENT_INTERACTIONS_TABLE_NAME: DynamoDB table for storing agent interactions
"""

import boto3
import json
from boto3.dynamodb.conditions import Key
from typing import List, Dict, Any
from datetime import datetime
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

def save_raw_query_result(user_prompt_uuid, user_prompt, sql_query, sql_query_description, result, message):
    """
    Save SQL query execution results to DynamoDB for future reference.
    
    Args:
        user_prompt_uuid: Unique identifier for the user prompt
        user_prompt: The original user question
        sql_query: The executed SQL query
        sql_query_description: A description of the SQL query that was executed
        result: The query results
        message: Additional information about the result (e.g., truncation notice)
        
    Returns:
        dict: Response with success status and DynamoDB response or error details
    """
    try:
        # Check if the table name is available
        question_answers_table = CONFIG.get("QUESTION_ANSWERS_TABLE")
        if not question_answers_table:
            return {"success": False, "error": "QUESTION_ANSWERS_TABLE not configured"}
            
        dynamodb_client = boto3.client('dynamodb', region_name=CONFIG["AWS_REGION"])
        
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
                "message_result": {"S": message}
            },
        )
        
        print("\n" + "="*70)
        print("✅ DATA SAVED TO DYNAMODB")
        print("="*70)
        print(f"🆔 ID: {user_prompt_uuid}")
        print(f"📊 Table: {question_answers_table}")
        print(f"🗄️  Region: {CONFIG['AWS_REGION']}")
        print("="*70 + "\n")
        return {"success": True, "response": response}
        
    except Exception as e:
        print("\n" + "="*70)
        print("❌ DYNAMODB SAVE ERROR")
        print("="*70)
        print(f"📊 Table: {question_answers_table}")
        print(f"💥 Error: {str(e)}")
        print("="*70 + "\n")
        return {"success": False, "error": str(e)}


def read_interactions_by_session(
    session_id: str
) -> List[Dict[str, Any]]:
    """
    Read conversation history interactions from DynamoDB by session_id with pagination.
    
    Args:
        session_id: The session ID to query for
        
    Returns:
        List of interaction objects containing only message attribute
        
    Note:
        Uses AGENT_INTERACTIONS_TABLE_NAME parameter from SSM for data retrieval.
    """
    # Check if the table name is available
    conversation_table = CONFIG.get("AGENT_INTERACTIONS_TABLE_NAME")
    if not conversation_table:
        print("\n" + "="*70)
        print("⚠️  AGENT INTERACTIONS TABLE NOT CONFIGURED")
        print("="*70)
        print("📊 Parameter: AGENT_INTERACTIONS_TABLE_NAME")
        print("🔄 Returning empty list")
        print("="*70 + "\n")
        return []
        
    dynamodb_resource = boto3.resource('dynamodb', region_name=CONFIG["AWS_REGION"])
    table = dynamodb_resource.Table(conversation_table)
    
    messages = []
    last_evaluated_key = None
    
    while True:
        query_params = {
            'KeyConditionExpression': Key('session_id').eq(session_id),
            'ProjectionExpression': 'message',
            'Limit': 100
        }
        
        # Add pagination token if this isn't the first page
        if last_evaluated_key:
            query_params['ExclusiveStartKey'] = last_evaluated_key
        
        response = table.query(**query_params)
        
        # Add the items to our result list
        for item in response.get('Items', []):
            messages.append(json.loads(item.get('message')))
        
        # Update the pagination token
        last_evaluated_key = response.get('LastEvaluatedKey')
        
        # If there's no pagination token, we've reached the end
        if not last_evaluated_key:
            break
    
    return messages


def messages_objects_to_strings(obj_array):
    """
    Convert message objects to a filtered list focusing on user/assistant interactions.
    
    Filters and converts message objects to include only text content and specific
    tool interactions like SQL query execution. This helps maintain a clean conversation
    history focused on the most relevant interactions.
    
    Args:
        obj_array (List): Array of message objects to process
        
    Returns:
        List[str]: List of filtered message objects converted to JSON strings
    """
    filtered_objs = []
    
    for i, obj in enumerate(obj_array):
        # Simple text messages from user or assistant
        if obj["role"] in ["user", "assistant"] and "content" in obj:
            # Check if content contains only text items (no toolUse or toolResult)
            has_only_text = True
            for item in obj["content"]:
                if "text" not in item:
                    has_only_text = False
                    break            
            if has_only_text:
                filtered_objs.append(obj)
        
        # Messages where assistant is using a tool
        if obj["role"] == "assistant" and "content" in obj:
            for item in obj["content"]:
                if "toolUse" in item and "name" in item['toolUse'] and item['toolUse']['name']=="execute_sql_query":
                    data = f"{item['toolUse']['input']["description"]}: {item['toolUse']['input']["sql_query"]}"
                    filtered_objs.append({ 'role': 'assistant', 'content': [{ 'text' : data }] })
                    break

        if obj["role"] == "user" and "content" in obj:
            for item in obj["content"]:
                if "toolResult" in item and "content" in item['toolResult'] and len(item['toolResult']['content'])>0:
                    for content_item in item['toolResult']['content']:
                        if "text" in content_item:
                            if "'toolUsed': 'get_tables_information'" in content_item["text"]:
                                filtered_objs.append({ 'role': 'user', 'content': [{ 'text' : content_item["text"]}] })
                                break

    return [json.dumps(obj) for obj in filtered_objs]


def save_agent_interactions(session_id: str, prompt_uuid: str, starting_message_id: int, 
                         messages: List[str]) -> bool:
    """
    Write multiple messages to a DynamoDB table for conversation history.
    
    This function processes the messages to extract the most relevant parts of the
    conversation and saves them to DynamoDB for future reference.
    
    Args:
        session_id (str): The UUID of the session
        prompt_uuid (str): The UUID of the prompt
        starting_message_id (int): The message_id to start with
        messages (List[str]): List of message objects to write
        
    Returns:
        bool: True if successful, False otherwise
        
    Note:
        Uses AGENT_INTERACTIONS_TABLE_NAME parameter from SSM for data storage.
    """
    
    messages_to_save = messages_objects_to_strings(messages)

    print("\n" + "="*70)
    print("📊 AGENT INTERACTIONS PROCESSING")
    print("="*70)
    print(f"📝 Final messages length: {len(messages_to_save)}")
    print("="*70)

    # Check if the table name is available
    conversation_table = CONFIG.get("AGENT_INTERACTIONS_TABLE_NAME")
    if not conversation_table:
        print("\n" + "="*70)
        print("⚠️  AGENT INTERACTIONS TABLE NOT CONFIGURED")
        print("="*70)
        print("📊 Parameter: AGENT_INTERACTIONS_TABLE_NAME")
        print("🔄 Returning False")
        print("="*70 + "\n")
        return False
        
    dynamodb = boto3.resource('dynamodb', region_name=CONFIG["AWS_REGION"])
    table = dynamodb.Table(conversation_table)
    try:
        with table.batch_writer() as batch:
            for i, message_text in enumerate(messages_to_save):
                if i < starting_message_id:
                    continue
                message_id = starting_message_id
                batch.put_item(
                    Item={
                        'session_id': session_id,
                        'message_id': message_id,
                        'prompt_uuid': prompt_uuid,
                        'message': message_text
                    }
                )
                starting_message_id += 1
        return True
    except Exception as e:
        print("\n" + "="*70)
        print("❌ BATCH WRITE ERROR")
        print("="*70)
        print(f"📊 Table: {conversation_table}")
        print(f"💥 Error: {e}")
        print("="*70 + "\n")
        return False