"""
Knowledge Base Tool for retrieving schema information.
"""
from strands import tool
import boto3
import logging
import os
import json
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Store the schema information for fallback
CUSTOMER_SCHEMA = [
    {
        "database_name": "customer-db",
        "table_name": "customer",
        "table_description": "Contains core customer information and recent purchases",
        "relationships": {
            "primary_key": [
                {
                    "column_name": "customer_id",
                    "constraint": "not null"
                }
            ]
        },
        "columns": [
            {
                "Name": "customer_id",
                "Type": "integer",
                "Comment": "Unique identifier for customer"
            },
            {
                "Name": "first_name",
                "Type": "string",
                "Comment": "Customer's first name"
            },
            {
                "Name": "last_name",
                "Type": "string",
                "Comment": "Customer's last name"
            },
            {
                "Name": "age",
                "Type": "integer",
                "Comment": "Customer's age"
            },
            {
                "Name": "gender",
                "Type": "string",
                "Comment": "Customer's gender"
            }
        ]
    },
    {
        "database_name": "customer-db",
        "table_name": "recent_purchases",
        "table_description": "Contains purchase details for each customer",
        "relationships": {
            "primary_key": [
                {
                    "column_name": "purchase_id",
                    "constraint": "not null"
                }
            ],
            "foreign_keys": [
                {
                    "database_name": "customer-db",
                    "table_name": "customer",
                    "join_on_column": "customer_id"
                }
            ]
        },
        "columns": [
            {
                "Name": "purchase_id",
                "Type": "integer",
                "Comment": "Unique identifier for the purchase"
            },
            {
                "Name": "customer_id",
                "Type": "integer",
                "Comment": "Reference to customer"
            },
            {
                "Name": "item",
                "Type": "string",
                "Comment": "Type of item purchased"
            },
            {
                "Name": "price",
                "Type": "double",
                "Comment": "Cost of the purchase"
            },
            {
                "Name": "date_purchased",
                "Type": "double",
                "Comment": "Date the item was purchased"
            }
        ]
    }
]

@tool
def get_schema(flag: bool = False, table_name: str = None) -> str:
    """
    Retrieve schema information from a knowledge base.
    
    Uses AWS Knowledge Base to retrieve schema information.
    Falls back to mock data if AWS connection fails.
    
    Args:
        table_name: Optional name of a specific table to retrieve schema for.
                   If None, returns all tables in the knowledge base.
    
    Returns:
        str: Schema information formatted for the LLM context.
    """
    try:
        # For testing purposes, check if we should use mock data
        if flag == True:
            logger.info("get_schema called with flag=True")
            return _format_schema_from_data(CUSTOMER_SCHEMA, table_name)
        
        # Get knowledge base ID from environment
        from config import get_config
        config = get_config()
        knowledge_base_id = config['knowledge_base_id']
        
        if not knowledge_base_id or knowledge_base_id == "default-kb-id":
            # logger.warning("No knowledge base ID provided, using mock schema data")
            return _format_schema_from_data(CUSTOMER_SCHEMA, table_name)
        
        # Create Bedrock client
        logger.debug(f"Connecting to knowledge base: {knowledge_base_id}")
        bedrock_client = boto3.client('bedrock-agent-runtime', region_name=config['aws_region'])
        
        # Prepare the query
        query = f"Describe the schema for {table_name} table" if table_name else "Describe all tables and their schemas"
        logger.debug(f"Querying knowledge base with: {query}")
        
        # Query the knowledge base
        response = bedrock_client.retrieve(
            knowledgeBaseId=knowledge_base_id,
            retrievalQuery={
                'text': query
            },
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': 5
                }
            }
        )
        
        # Process and format the response
        schema_info = ""
        for result in response.get('retrievalResults', []):
            if 'content' in result and 'text' in result['content']:
                schema_info += result['content']['text'] + "\n\n"

        if not schema_info:
            logger.warning("No schema information retrieved from knowledge base, using mock data")
            return _format_schema_from_data(CUSTOMER_SCHEMA, table_name)
        
        logger.info("Successfully retrieved schema from knowledge base")
        return schema_info
        
    except Exception as e:
        logger.exception(f"Error retrieving schema from knowledge base: {e}")
        # Fall back to the provided schema
        return _format_schema_from_data(CUSTOMER_SCHEMA, table_name)


def _format_schema_from_data(schema_data: List[Dict[str, Any]], table_name: str = None) -> str:
    """
    Format schema information from the provided data.
    
    Args:
        schema_data: List of table schema definitions
        table_name: Optional name of a specific table
    
    Returns:
        str: Formatted schema information
    """
    if table_name:
        # Filter for the specific table
        table_info = next((table for table in schema_data if table["table_name"].lower() == table_name.lower()), None)
        if not table_info:
            return f"No schema information found for table: {table_name}"
        
        return _format_table_schema(table_info)
    else:
        # Return all tables
        result = "Database: customer-db\n\n"
        for table in schema_data:
            result += _format_table_schema(table) + "\n\n"
        return result


def _format_table_schema(table_info: Dict[str, Any]) -> str:
    """
    Format a single table's schema information.
    
    Args:
        table_info: Dictionary containing table schema
    
    Returns:
        str: Formatted table schema
    """
    result = f"Table: {table_info['table_name']}\n"
    result += f"Description: {table_info['table_description']}\n"
    result += "Columns:\n"
    
    for column in table_info["columns"]:
        result += f"- {column['Name']} ({column['Type']}): {column['Comment']}\n"
    
    # Add relationship information
    if "relationships" in table_info:
        result += "Relationships:\n"
        
        if "primary_key" in table_info["relationships"]:
            pk_cols = [pk["column_name"] for pk in table_info["relationships"]["primary_key"]]
            result += f"- Primary Key: {', '.join(pk_cols)}\n"
        
        if "foreign_keys" in table_info["relationships"]:
            for fk in table_info["relationships"]["foreign_keys"]:
                result += f"- Foreign Key: {fk['join_on_column']} references {fk['table_name']}\n"
    
    return result
