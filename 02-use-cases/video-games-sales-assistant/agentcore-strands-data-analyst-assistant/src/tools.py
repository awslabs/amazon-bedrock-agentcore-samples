"""
Tools for Data Analyst Assistant

This module provides utility tools for the Data Analyst Assistant, including:
1. File content loading utility
2. Database tables information tool

These tools are used by the agent to access information about the database schema
and load content from files.
"""

from strands import tool

def load_file_content(file_path: str, default_content: str = None) -> str:
    """
    Read and return the content of a file at the specified path.
    
    Args:
        file_path: Path to the file to be read
        default_content: Optional content to return if the file is not found
        
    Returns:
        str: The content of the file as a string
        
    Raises:
        FileNotFoundError: If the file doesn't exist and no default_content is provided
        Exception: If there are other errors during file reading
    """
    try:
        with open(file_path, "r") as file:
            return file.read()
    except FileNotFoundError:
        if default_content is not None:
            print("\n" + "="*70)
            print("⚠️  FILE NOT FOUND - USING FALLBACK")
            print("="*70)
            print(f"📁 File: {file_path}")
            print("🔄 Using fallback content")
            print("="*70 + "\n")
            return default_content
        raise
    except Exception as e:
        raise Exception(f"Error reading file {file_path}: {str(e)}")

@tool
def get_tables_information() -> dict:
    """
    Provides information related to the data tables available to generate the SQL queries to answer the users questions

    Returns:
        dict: A dictionary containing the information about the tables
              with keys 'toolUsed' and 'information'
              
    Note:
        Expects a file named 'tables_information.txt' in the current directory.
        Returns an error message in the dictionary if the file is not found.
    """
    try:
        return {
            "toolUsed": "get_tables_information",
            "information": load_file_content("tables_information.txt")
        }
    except FileNotFoundError:
        return {
            "toolUsed": "get_tables_information",
            "information": "Error: tables_info.txt file not found. Please create this file with your tables information."
        }
    except Exception as e:
        return {
            "toolUsed": "get_tables_information",
            "information": f"Error reading tables information: {str(e)}"
        }