"""
Financial Analyzer Agent using AWS Bedrock AgentCore and Strands.

This agent demonstrates integration of:
- AWS Bedrock AgentCore Gateway (for DynamoDB queries via Lambda)
- AWS Bedrock Code Interpreter (for financial data analysis)
- Amazon Cognito (for JWT authentication)
- Amazon S3 (for data storage)

Prerequisites:
    - Run infrastructure_setup.ipynb to provision AWS resources
    - Ensure AWS credentials are configured
    - Install required packages: strands, boto3, mcp, bedrock-agentcore-tools
"""

import base64
import sys
from pathlib import Path
from typing import Dict, Tuple

# Add src directory to path to support direct imports
src_dir = Path(__file__).parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import boto3
from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter
from strands import Agent, tool
from strands.models import BedrockModel

from utils import (
    authenticate_and_connect_to_gateway,
    load_config_from_ssm,
)


# ============================================================================
# Helper Functions
# ============================================================================

def parse_s3_uri(s3_uri: str) -> Tuple[str, str]:
    """
    Parse S3 URI into bucket name and object key.

    Args:
        s3_uri: Full S3 URI (e.g., s3://my-bucket/path/to/file.csv)

    Returns:
        Tuple of (bucket_name, object_key)

    Example:
        >>> parse_s3_uri("s3://my-bucket/data/file.csv")
        ('my-bucket', 'data/file.csv')
    """
    path = s3_uri.removeprefix("s3://")
    bucket, key = path.split("/", 1)
    return bucket, key


def get_analysis_code(read_code: str, analysis_query: str, filename: str) -> str:
    """Generate pandas analysis code for the given file and query."""
    return f'''
import pandas as pd
import numpy as np
{read_code}

# Query: {analysis_query}

print("Data Analysis Results")
print("=" * 60)
print(f"Dataset: {filename}")
print(f"Records: {{len(df):,}}")
print(f"Columns: {{', '.join(df.columns.tolist())}}")
print()

revenue_cols = [c for c in df.columns if any(x in c.lower() for x in ['revenue', 'sales', 'income'])]
expense_cols = [c for c in df.columns if any(x in c.lower() for x in ['expense', 'cost', 'spending'])]
year_col = next((c for c in df.columns if 'year' in c.lower()), None)
quarter_col = next((c for c in df.columns if 'quarter' in c.lower()), None)
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

print("Key Metrics:")
print("-" * 60)
for col in revenue_cols + expense_cols:
    if col in numeric_cols:
        print(f"{{col}}: Total=${{df[col].sum():,.2f}}, Avg=${{df[col].mean():,.2f}}, Max=${{df[col].max():,.2f}}")
print()

if year_col and revenue_cols:
    print("Year-over-Year:")
    print("-" * 60)
    for rev_col in revenue_cols:
        if rev_col in numeric_cols:
            yearly = df.groupby(year_col)[rev_col].sum()
            print(f"\\n{{rev_col}} by Year:")
            print(yearly.to_string())
    print()

if quarter_col and year_col and revenue_cols:
    print("Quarterly Breakdown:")
    print("-" * 60)
    for rev_col in revenue_cols:
        if rev_col in numeric_cols:
            quarterly = df.groupby([year_col, quarter_col])[rev_col].sum().reset_index()
            quarterly = quarterly.sort_values(rev_col, ascending=False)
            print(f"\\nTop Quarters by {{rev_col}}:")
            print(quarterly.head(10).to_string(index=False))
    print()

if revenue_cols and len(df) > 0:
    print("Top Performers:")
    print("-" * 60)
    for rev_col in revenue_cols:
        if rev_col in numeric_cols:
            best_idx = df[rev_col].idxmax()
            best_row = df.loc[best_idx]
            print(f"Best {{rev_col}}: ", end="")
            if year_col: print(f"Year={{best_row[year_col]}}, ", end="")
            if quarter_col: print(f"Quarter={{best_row[quarter_col]}}, ", end="")
            print(f"Value=${{best_row[rev_col]:,.2f}}")
    print()

print("Sample Data:")
print("-" * 60)
print(df.head().to_string())
'''


def get_system_prompt(gateway_available: bool, s3_data_path: str) -> str:
    """Build system prompt based on available features."""
    financial_instructions = f"""
    For FINANCIAL DATA (quarterly results, revenue, expenses):
    - The quarterly financial data is located at: {s3_data_path}quarterly_results.xlsx
    - Step 1: Use load_s3_file_to_code_interpreter with the S3 URI: {s3_data_path}quarterly_results.xlsx
    - Step 2: Use analyze_data_in_code_interpreter with the filename and analysis query
    - Examples: "What was Q4 2023 revenue?", "Show expense trends", "Which quarter had highest revenue?"

    Workflow:
    1. Call load_s3_file_to_code_interpreter("{s3_data_path}quarterly_results.xlsx") → get filename
    2. Call analyze_data_in_code_interpreter(filename, "your query") → get results"""

    if gateway_available:
        return f"""You are a helpful assistant that can answer questions about:

                1. PROJECT BUDGET DATA (projects, costs, allocations):
                   - Use Gateway tools to query DynamoDB
                   - Examples: "Show project PROJ-001", "List Marketing projects", "Find budgets over 100k"

                2. FINANCIAL DATA (quarterly results, revenue, expenses):
                   {financial_instructions}

                Always route:
                - Project Budget questions → Gateway tools
                - Financial questions → load_s3_file + analyze_data (2 steps)"""

    return f"""You are a helpful assistant that can answer questions about FINANCIAL DATA only.

            Project Budget data is currently unavailable (Gateway not connected).

            {financial_instructions}"""


# ============================================================================
# Agent Tools
# ============================================================================

@tool
def load_s3_file_to_code_interpreter(s3_uri: str) -> Dict:
    """
    Load a file from Amazon S3 into Code Interpreter for analysis.

    This tool:
    1. Downloads the file from S3
    2. Base64 encodes the content
    3. Transfers it to the Code Interpreter session
    4. Makes it available for subsequent analysis

    Args:
        s3_uri: Full S3 URI (e.g., s3://my-bucket/data/quarterly_results.csv)

    Returns:
        Dict containing:
            - status: 'success' or 'error'
            - filename: Name of the loaded file (if successful)
            - message: Success message (if successful)
            - error: Error message (if failed)

    Example:
        >>> load_s3_file_to_code_interpreter("s3://my-bucket/data/q4_results.csv")
        {'status': 'success', 'filename': 'q4_results.csv', 'message': 'File q4_results.csv loaded and ready'}
    """
    try:
        bucket, key = parse_s3_uri(s3_uri)
        filename = key.split("/")[-1]

        # Download file from S3 using configured region
        region = config.get("region")
        s3 = boto3.client("s3", region_name=region) if region else boto3.client("s3")
        file_content = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        b64_content = base64.b64encode(file_content).decode("utf-8")

        # Upload to Code Interpreter
        upload_code = f"""
import base64
with open('{filename}', 'wb') as f:
    f.write(base64.b64decode('{b64_content}'))
print('Ready')
"""

        result = code_interpreter.invoke(
            "executeCode", {"code": upload_code, "language": "python"}
        )

        # Check for errors
        for event in result["stream"]:
            if event.get("result", {}).get("isError"):
                raise Exception("File transfer to Code Interpreter failed")

        return {
            "status": "success",
            "filename": filename,
            "message": f"File {filename} loaded and ready for analysis",
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


@tool
def analyze_data_in_code_interpreter(filename: str, analysis_query: str) -> Dict:
    """
    Analyze data file in Code Interpreter using pandas.

    This tool:
    1. Loads the file into a pandas DataFrame
    2. Executes comprehensive analysis based on the query
    3. Returns formatted analysis results including metrics, trends, and insights

    Args:
        filename: Name of file previously loaded via load_s3_file_to_code_interpreter
        analysis_query: Natural language description of desired analysis
                       (e.g., "Which quarter had highest revenue in 2023?")

    Returns:
        Dict containing:
            - status: 'success' or 'error'
            - output: Analysis results as formatted text (if successful)
            - error: Error message (if failed)

    Example:
        >>> analyze_data_in_code_interpreter("q4_results.csv", "Show revenue by quarter")
        {'status': 'success', 'output': '...formatted analysis results...'}
    """
    try:
        # Determine file type and read accordingly
        if filename.endswith((".xlsx", ".xls")):
            read_code = f"df = pd.read_excel('{filename}', engine='openpyxl')"
        else:
            # Fallback to CSV if not Excel
            read_code = f"df = pd.read_csv('{filename}')"

        # Generate and execute analysis code
        analysis_code = get_analysis_code(read_code, analysis_query, filename)
        response = code_interpreter.invoke(
            "executeCode", {"code": analysis_code, "language": "python"}
        )

        # Extract results
        for event in response["stream"]:
            result = event.get("result", {})
            if "structuredContent" in result:
                stdout = result["structuredContent"].get("stdout", "")
                if stdout:
                    return {"status": "success", "output": stdout}
            return {"status": "success", "result": result}

        return {"status": "success", "result": "Analysis completed with no output"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


# ============================================================================
# Agent Setup
# ============================================================================

def create_agent(
    config: Dict, gateway_available: bool, gateway_tools: list
) -> Agent:
    """
    Create and configure the Strands agent with available tools.

    Args:
        config: Configuration dict
        gateway_available: Whether Gateway connection is available
        gateway_tools: List of tools from AgentCore Gateway

    Returns:
        Configured Strands Agent instance
    """
    tools = [load_s3_file_to_code_interpreter, analyze_data_in_code_interpreter]

    # Add Gateway tools if available (for DynamoDB queries)
    if gateway_available:
        tools.insert(0, gateway_tools)

    # Get S3 data path from config
    s3_data_path = config.get('s3_quarterly_data_path', 's3://finance-analyzer-data/quarterly-data/')

    return Agent(
        model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0"),
        tools=tools,
        system_prompt=get_system_prompt(gateway_available, s3_data_path),
    )


def print_startup_banner(gateway_available: bool, config: Dict) -> None:
    """
    Print startup banner with configuration and available features.

    Args:
        gateway_available: Whether Gateway connection is available
        config: Configuration dict
    """
    print("\n" + "=" * 70)
    print("Financial Analyzer Agent")
    print("=" * 70)

    print("\nConfiguration:")
    print(f"  Region:        {config.get('region', 'N/A')}")
    print(f"  S3 Data Path:  {config.get('s3_quarterly_data_path', 'N/A')}")
    print(f"  Gateway:       {'✓ Connected' if gateway_available else '✗ Not available'}")

    print("\nCapabilities:")
    if gateway_available:
        print("  ✓ Project Budget queries (DynamoDB via Gateway)")
    else:
        print("  ✗ Project Budget queries (Gateway unavailable)")
    print("  ✓ Financial data analysis (S3 + Code Interpreter)")
    print("  ✓ Custom file analysis (CSV, Excel)")

    print("\nExample Queries:")
    if gateway_available:
        print("  • 'Show me project PROJ-001'")
        print("  • 'List all Marketing projects with budget over 100k'")
    print("  • 'What was our Q4 2023 revenue?'")
    print("  • 'Analyze quarterly expense trends'")
    print("  • 'Which quarter had the highest revenue?'")

    print("\nCommands:")
    print("  • Type 'quit' or 'exit' to end the session")
    print("  • Press Ctrl+C to interrupt")
    print("=" * 70 + "\n")


def run_chat_loop(agent: Agent) -> None:
    """
    Run the interactive chat loop for the agent.

    Args:
        agent: Configured Strands Agent instance
    """
    while True:
        try:
            user_input = input("You: ").strip()

            if user_input.lower() in ("quit", "exit"):
                print("\nGoodbye!")
                break

            if not user_input:
                continue

            # Execute agent with user input
            agent(user_input)
            print("-" * 70 + "\n")

        except KeyboardInterrupt:
            print("\n\nSession interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n⚠ Error: {e}\n")


def main():
    """Main entry point for the Financial Analyzer Agent."""

    # Load configuration from AWS Systems Manager Parameter Store
    print("[1/4] Loading configuration from SSM Parameter Store...")
    global config
    config, config_loaded = load_config_from_ssm()

    if not config_loaded:
        print("\n✗ ERROR: Failed to load configuration from SSM Parameter Store")
        print("\nPlease ensure:")
        print("  1. Infrastructure is provisioned using infrastructure_setup.ipynb")
        print("  2. AWS credentials are configured correctly")
        print("  3. You have permissions to access SSM Parameter Store")
        sys.exit(1)

    # Authenticate and connect to Gateway
    print("[2/4] Authenticating with AgentCore Gateway...")
    gateway_tools = []
    gateway_available = False

    mcp_client, gateway_available = authenticate_and_connect_to_gateway(config)
    if gateway_available:
        gateway_tools = mcp_client.list_tools_sync()
        print(f"      ✓ Gateway connected - {len(gateway_tools)} tools available")
    else:
        print("      ⚠ Gateway unavailable - project budget queries will not work")

    # Initialize Code Interpreter
    print("[3/4] Starting Code Interpreter session...")
    global code_interpreter
    code_interpreter = CodeInterpreter(region=config["region"])
    session_id = code_interpreter.start()
    print(f"      ✓ Session started: {session_id}")

    # Create agent
    print("[4/4] Creating agent...")
    agent = create_agent(config, gateway_available, gateway_tools)
    print("      ✓ Agent ready\n")

    # Run interactive session
    try:
        print_startup_banner(gateway_available, config)
        run_chat_loop(agent)
    finally:
        # Cleanup
        print("\n[Cleanup] Stopping Code Interpreter session...")
        code_interpreter.stop()
        print("[Cleanup] Done")


if __name__ == "__main__":
    main()
