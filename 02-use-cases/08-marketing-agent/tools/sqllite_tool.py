"""
SQLite Query Tool for executing SQL queries against local SQLite database.
"""
from strands import tool
import sqlite3
import logging
import os
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

@tool
def run_sqlite_query(query: str) -> Dict[str, Any]:
    """
    Execute a SQL query on SQLite database.
    
    Uses sqlite3 to execute the query on local SQLite database and returns the results.
    
    Args:
        query: SQL query string to execute
    
    Returns:
        Dict containing either query results or error information
    """
    try:
        # Get database path from config
        from config import get_config
        config = get_config()
        
        database_path = config.get('sqlite_database_path', './data/customers.db')
        
        # Validate database exists
        db_path = Path(database_path)
        if not db_path.exists():
            logger.error(f"SQLite database not found at {database_path}")
            return {
                "success": False,
                "error": f"Database file not found: {database_path}",
                "query": query
            }
        
        # Execute query
        logger.info(f"Executing SQLite query: {query}")
        
        with sqlite3.connect(database_path) as conn:
            # Enable row factory for dictionary-like access
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Execute the query
            cursor.execute(query)
            
            # Handle different query types
            query_upper = query.strip().upper()
            if query_upper.startswith(('SELECT', 'WITH')):
                # For SELECT queries, fetch results
                rows = cursor.fetchall()
                
                # Get column names
                columns = [description[0] for description in cursor.description] if cursor.description else []
                
                # Convert rows to list of dictionaries
                data = []
                for row in rows:
                    item = {}
                    for column in columns:
                        value = row[column]
                        # Handle None values consistently with Athena tool
                        item[column] = value if value is not None else None
                    data.append(item)
                
                logger.info(f"Query succeeded! Returned {len(data)} rows")
                
                return {
                    "success": True,
                    "data": data,
                    "query": query
                }
            else:
                # For INSERT, UPDATE, DELETE queries
                affected_rows = cursor.rowcount
                conn.commit()
                
                logger.info(f"Query succeeded! {affected_rows} rows affected")
                
                return {
                    "success": True,
                    "data": [],
                    "affected_rows": affected_rows,
                    "message": f"Query executed successfully. {affected_rows} rows affected.",
                    "query": query
                }
    
    except sqlite3.Error as e:
        # Handle SQLite-specific errors
        error_message = _format_sqlite_error(str(e))
        logger.error(f"SQLite query failed: {error_message}")
        
        return {
            "success": False,
            "error": error_message,
            "sqlite_error_details": str(e),
            "query": query
        }
    
    except Exception as e:
        logger.exception("Error executing SQLite query")
        return {
            "success": False,
            "error": str(e),
            "query": query
        }

def _format_sqlite_error(error_message: str) -> str:
    """
    Format SQLite error messages for better readability.
    Similar to how Athena tool handles error formatting.
    
    Args:
        error_message: Raw SQLite error message
        
    Returns:
        Formatted error message
    """
    error_lower = error_message.lower()
    
    # Common SQLite error patterns and their user-friendly explanations
    if 'no such table' in error_lower:
        return f"Table does not exist: {error_message}"
    elif 'no such column' in error_lower:
        return f"Column does not exist: {error_message}"
    elif 'syntax error' in error_lower:
        return f"SQL syntax error: {error_message}"
    elif 'ambiguous column name' in error_lower:
        return f"Ambiguous column name (specify table): {error_message}"
    elif 'foreign key constraint failed' in error_lower:
        return f"Foreign key constraint violation: {error_message}"
    elif 'unique constraint failed' in error_lower:
        return f"Unique constraint violation: {error_message}"
    elif 'not null constraint failed' in error_lower:
        return f"NOT NULL constraint violation: {error_message}"
    else:
        return error_message