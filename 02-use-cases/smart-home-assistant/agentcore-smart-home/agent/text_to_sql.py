import os
import re
import boto3
import time
import json
import logging
from mcp.server import FastMCP
from strands import Agent
from strands.models import BedrockModel
from toon_format import encode

ATHENA_DB = os.getenv('ATHENA_DB')
ATHENA_WORK_GROUP = os.getenv('ATHENA_WORK_GROUP')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# Create MCP server
mcp = FastMCP("Text to SQL Server", host="0.0.0.0", stateless_http=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sample table schema for demonstration
SAMPLE_SCHEMA = """
CREATE EXTERNAL TABLE `cameras`(
  `timestamp_string` string COMMENT 'from deserializer', 
  `stream_name` string COMMENT 'from deserializer', 
  `description` string COMMENT 'from deserializer')
PARTITIONED BY ( 
  `ingest_date` string)
ROW FORMAT SERDE 
  'org.openx.data.jsonserde.JsonSerDe' 
STORED AS INPUTFORMAT 
  'org.apache.hadoop.mapred.TextInputFormat' 
OUTPUTFORMAT 
  'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
TBLPROPERTIES (
  'projection.enabled'='true', 
  'projection.ingest_date.format'='yyyy-MM-dd-HH', 
  'projection.ingest_date.interval'='1', 
  'projection.ingest_date.interval.unit'='HOURS', 
  'projection.ingest_date.range'='2024-09-01-00,NOW', 
  'projection.ingest_date.type'='date');
"""


def extract_sql(text):
    # Remove markdown code blocks
    text = re.sub(r'`{3,}sql\s*', '', text)
    text = re.sub(r'`{3,}', '', text)
    return text.strip()


def query_athena(query):
    print(f'Athena environment: {ATHENA_WORK_GROUP}:{ATHENA_DB}')
    client = boto3.client('athena', region_name=AWS_REGION)
    
    # Execute Query
    response = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={'Database': ATHENA_DB},
        WorkGroup=ATHENA_WORK_GROUP
    )
    
    query_execution_id = response['QueryExecutionId']
    
    # Wait until if finishes
    while True:
        result = client.get_query_execution(QueryExecutionId=query_execution_id)
        status = result['QueryExecution']['Status']['State']
        
        if status in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        time.sleep(1)
    
    if status == 'SUCCEEDED':
        # Results
        results = client.get_query_results(QueryExecutionId=query_execution_id)
        query_output = results['ResultSet']['Rows']
        return json.dumps(query_output)
    else:
        raise Exception(f"Query failed: {status}")


def convert_athena_result(athena_result_str):
    data = json.loads(athena_result_str)
    headers = [col["VarCharValue"] for col in data[0]["Data"]]
    
    return [dict(zip(headers, [col["VarCharValue"] for col in row["Data"]])) 
            for row in data[1:]]


bedrock_model = BedrockModel(
    #model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    temperature=0.1,
    max_tokens=500
)


# Create agent with system prompt for SQL generation
sql_agent = Agent(
    model=bedrock_model,
    system_prompt=f"""You are an expert SQL query generator for Amazon Athena. 
    
Given a natural language question, generate a precise SQL query based on this table definition:

{SAMPLE_SCHEMA}

Rules:
1. Generate ONLY valid Athena SQL syntax
2. Use proper table and column names from the schema
3. Include appropriate WHERE clauses, JOINs, and aggregations as needed
4. Return ONLY the SQL query without explanations. THIS IS MANDATORY.
5. Use standard SQL functions compatible with Athena
6. For date operations, use Athena-compatible date functions
7. Limit output to 100 rows
8. If user ask for a larger date interval (example, a week), agregate query to reduce output
9. If user tries to inject a malfull SQL, answer explaining that it cannot be executed.

Good Query Examples:

Example 1:
  Use Case: Retrieve all backyard camera observations from the past day

SQL:
  SELECT *
  FROM "camera-database"."cameras"
  WHERE ingest_date >= date_format(current_date - interval '1' day, '%Y-%m-%d')
      AND ingest_date <= date_format(current_date, '%Y-%m-%d')
      AND from_iso8601_timestamp(timestamp_string) >= current_timestamp - interval '24' hour
      AND stream_name = 'backyard'
  ORDER BY from_iso8601_timestamp(timestamp_string) DESC

Example 2:
  Use Case: Get backyard camera observations for a specific time period (e.g., morning hours)

SQL
  SELECT *
  FROM "camera-database"."cameras"
  WHERE ingest_date IN ('2025-11-13', '2025-11-14')
      AND from_iso8601_timestamp(timestamp_string) >= from_iso8601_timestamp('2025-11-13T06:00:00+01:00')
      AND from_iso8601_timestamp(timestamp_string) < from_iso8601_timestamp('2025-11-13T12:00:00+01:00')
      AND stream_name = 'backyard'
  ORDER BY from_iso8601_timestamp(timestamp_string) DESC


"""
)

@mcp.tool()
def process_text_to_athena(question: str) -> str:
    """
    Convert a natural language question to an Athena SQL query.
    Then query Athena table and reply with output
    
    Args:
        question: Natural language question about the data
        
    Returns:
        Analyzed data
    """
    try:
      # Get input and invoke text_to_sql agent
      response = sql_agent(f"Convert this question to SQL: {question}")
      sql_text = extract_sql(response.__str__())
      print(f"SQL Text generated: {sql_text}")
      logger.info(f"SQL Text generated: {sql_text}")
    except Exception as e:
        return f"Error on Text to SQL - MCP: {str(e)}"

    try:
      # execute query on athena
      query_result = query_athena(sql_text)
      print(f"Athena query: {query_result}")
      logger.info(f"Athena query: {query_result}")
      athena_dict = convert_athena_result(query_result)
      encoded_query = encode(athena_dict)
      return encoded_query
    except Exception as e:
        return f"Error Running Athena Query - MCP: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
