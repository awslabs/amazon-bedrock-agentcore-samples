import boto3
import logging
from typing import Dict, List, Any, Optional
from decimal import Decimal
from strands.tools import tool
from botocore.exceptions import ClientError, BotoCoreError


logger = logging.getLogger(__name__)


class DynamoDBQueryError(Exception):
    """Custom exception for DynamoDB query errors."""
    pass


def _convert_decimal(obj):
    """Convert DynamoDB Decimal types to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_decimal(v) for v in obj]
    return obj


def _get_dynamodb_client():
    """Get DynamoDB client with error handling."""
    try:
        return boto3.client('dynamodb')
    except Exception as e:
        logger.error(f"Failed to create DynamoDB client: {e}")
        raise DynamoDBQueryError(f"DynamoDB client initialization failed: {e}")


def _get_dynamodb_resource():
    """Get DynamoDB resource with error handling."""
    try:
        return boto3.resource('dynamodb')
    except Exception as e:
        logger.error(f"Failed to create DynamoDB resource: {e}")
        raise DynamoDBQueryError(f"DynamoDB resource initialization failed: {e}")


@tool
def dynamodb_query_tool(
    table_name: str,
    query_type: str,
    filters: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = 100
) -> Dict[str, Any]:
    """
    Query DynamoDB for customer data - pure database access only.
    
    Args:
        table_name: Name of the DynamoDB table to query
        query_type: Type of query - 'scan', 'query', 'query_by_gsi'
        filters: Optional filters to apply (e.g., {'age': {'gte': 25}, 'gender': 'F'})
        limit: Maximum number of items to return (default: 100)
    
    Returns:
        Dictionary containing raw query results from DynamoDB
    """
    try:
        dynamodb = _get_dynamodb_resource()
        table = dynamodb.Table(table_name)
        
        logger.info(f"Executing DynamoDB {query_type} on table {table_name}")
        
        if query_type == "scan":
            return _perform_scan(table, filters, limit)
        elif query_type == "query":
            return _perform_query(table, filters, limit)
        elif query_type == "query_by_gsi":
            return _perform_gsi_query(table, filters, limit)
        else:
            raise DynamoDBQueryError(f"Unsupported query type: {query_type}")
            
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"DynamoDB ClientError: {error_code} - {error_message}")
        return {
            "error": f"DynamoDB error: {error_code}",
            "message": error_message,
            "query_type": query_type
        }
    except BotoCoreError as e:
        logger.error(f"BotoCore error: {e}")
        return {
            "error": "AWS connection error",
            "message": str(e),
            "query_type": query_type
        }
    except Exception as e:
        logger.error(f"Unexpected error in DynamoDB query: {e}")
        return {
            "error": "Query execution failed",
            "message": str(e),
            "query_type": query_type
        }


def _perform_scan(table, filters: Optional[Dict], limit: int) -> Dict[str, Any]:
    """Perform a scan operation on the DynamoDB table."""
    try:
        scan_kwargs = {"Limit": limit}
        
        # Add filter expressions if provided
        if filters:
            filter_expression = _build_filter_expression(filters)
            if filter_expression:
                scan_kwargs["FilterExpression"] = filter_expression
        
        response = table.scan(**scan_kwargs)
        items = [_convert_decimal(item) for item in response.get('Items', [])]
        
        return {
            "query_type": "scan",
            "items": items,
            "count": len(items),
            "scanned_count": response.get('ScannedCount', 0),
            "filters_applied": filters or {},
            "success": True
        }
        
    except Exception as e:
        raise DynamoDBQueryError(f"Scan operation failed: {e}")


def _perform_query(table, filters: Optional[Dict], limit: int) -> Dict[str, Any]:
    """Perform a query operation on the DynamoDB table."""
    try:
        if not filters or 'customer_id' not in filters:
            raise DynamoDBQueryError("Query operation requires customer_id in filters")
        
        query_kwargs = {
            "KeyConditionExpression": "customer_id = :customer_id",
            "ExpressionAttributeValues": {":customer_id": filters['customer_id']},
            "Limit": limit
        }
        
        # Add additional filters if provided
        additional_filters = {k: v for k, v in filters.items() if k != 'customer_id'}
        if additional_filters:
            filter_expression = _build_filter_expression(additional_filters)
            if filter_expression:
                query_kwargs["FilterExpression"] = filter_expression
        
        response = table.query(**query_kwargs)
        items = [_convert_decimal(item) for item in response.get('Items', [])]
        
        return {
            "query_type": "query",
            "items": items,
            "count": len(items),
            "customer_id": filters['customer_id'],
            "additional_filters": additional_filters,
            "success": True
        }
        
    except Exception as e:
        raise DynamoDBQueryError(f"Query operation failed: {e}")


def _perform_gsi_query(table, filters: Optional[Dict], limit: int) -> Dict[str, Any]:
    """Perform a query operation using Global Secondary Index."""
    try:
        if not filters:
            raise DynamoDBQueryError("GSI query requires filters to specify index and key")
        
        index_name = filters.get('index_name')
        if not index_name:
            raise DynamoDBQueryError("GSI query requires 'index_name' in filters")
        
        # Build key condition for GSI
        key_conditions = {}
        expression_values = {}
        
        if 'marketing_channel' in filters:
            key_conditions['marketing_channel'] = ':channel'
            expression_values[':channel'] = filters['marketing_channel']
        elif 'customer_segment' in filters:
            key_conditions['customer_segment'] = ':segment'
            expression_values[':segment'] = filters['customer_segment']
        else:
            raise DynamoDBQueryError("GSI query requires either 'marketing_channel' or 'customer_segment'")
        
        # Build key condition expression
        key_condition = ' = '.join(list(key_conditions.items())[0])
        
        query_kwargs = {
            "IndexName": index_name,
            "KeyConditionExpression": key_condition,
            "ExpressionAttributeValues": expression_values,
            "Limit": limit
        }
        
        # Add additional filters if provided
        additional_filters = {k: v for k, v in filters.items() 
                            if k not in ['index_name', 'marketing_channel', 'customer_segment']}
        if additional_filters:
            filter_expression = _build_filter_expression(additional_filters)
            if filter_expression:
                query_kwargs["FilterExpression"] = filter_expression
        
        response = table.query(**query_kwargs)
        items = [_convert_decimal(item) for item in response.get('Items', [])]
        
        return {
            "query_type": "query_by_gsi",
            "items": items,
            "count": len(items),
            "index_name": index_name,
            "filters_applied": filters,
            "success": True
        }
        
    except Exception as e:
        raise DynamoDBQueryError(f"GSI query operation failed: {e}")


def _build_filter_expression(filters: Dict[str, Any]):
    """Build DynamoDB filter expression from filters dictionary."""
    from boto3.dynamodb.conditions import Attr
    
    try:
        conditions = []
        
        for field, condition in filters.items():
            if isinstance(condition, dict):
                # Handle range conditions like {'gte': 25, 'lte': 65}
                for op, value in condition.items():
                    if op == 'gte':
                        conditions.append(Attr(field).gte(value))
                    elif op == 'lte':
                        conditions.append(Attr(field).lte(value))
                    elif op == 'gt':
                        conditions.append(Attr(field).gt(value))
                    elif op == 'lt':
                        conditions.append(Attr(field).lt(value))
                    elif op == 'eq':
                        conditions.append(Attr(field).eq(value))
                    elif op == 'ne':
                        conditions.append(Attr(field).ne(value))
            else:
                # Handle simple equality conditions
                conditions.append(Attr(field).eq(condition))
        
        # Combine conditions with AND
        if conditions:
            result = conditions[0]
            for condition in conditions[1:]:
                result = result & condition
            return result
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to build filter expression: {e}")
        return None


