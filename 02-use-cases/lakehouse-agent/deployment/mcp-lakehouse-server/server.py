"""
MCP Server for Health Lakehouse Data - Production Security with Lake Formation

This MCP server provides tools for querying and managing health lakehouse data
with enterprise-grade row-level security enforced by AWS Lake Formation.

Security Architecture:
- OAuth authentication (Cognito JWT tokens)
- User identity extraction from Gateway interceptor
- Lake Formation session tag-based row-level security
- No SQL string interpolation (eliminates SQL injection risk)

IMPORTANT: This server ONLY supports Lake Formation security mode.
Application-level SQL filtering has been removed for security reasons.

Configuration:
- Reads from SSM Parameter Store
- Auto-detects region from boto3 session
- Requires SECURITY_MODE=lakeformation
- Optional RLS_ROLE_ARN to be set
"""

import sys
import os
from typing import Any, Dict, Optional
import boto3
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP(host="0.0.0.0", stateless_http=True)

# PRODUCTION ONLY: Use Lake Formation row-level security
from athena_tools_secure import SecureAthenaClaimsTools as AthenaTools

print("🔒 Using Lake Formation row-level security (production mode)")

# Global Athena tools instance
athena_tools = None

# Configuration cache
_config_cache = None


def get_config() -> Dict[str, Optional[str]]:
    """
    Load configuration from environment variables and SSM Parameter Store.
    """
    global _config_cache
    
    if _config_cache is not None:
        return _config_cache
    
    config = {}
    
    # Get region from boto3 session with proper fallback
    try:
        session = boto3.Session()
        config['region'] = (
            session.region_name or
            os.environ.get('AWS_REGION') or
            os.environ.get('AWS_DEFAULT_REGION') or
            'us-east-1'
        )
        if not session.region_name:
            print("⚠️  No region in AWS config, using fallback")
        print(f"✅ Region: {config['region']}")
    except Exception as e:
        print(f"⚠️  Could not detect region: {e}")
        config['region'] = 'us-east-1'
    
    # Get account ID
    try:
        sts = boto3.client('sts', region_name=config['region'])
        config['account_id'] = sts.get_caller_identity()['Account']
    except Exception as e:
        print(f"⚠️  Could not get account ID: {e}")
        config['account_id'] = None
    
    ssm = boto3.client('ssm', region_name=config['region'])
    
    def get_param(name: str, env_var: str = None, default: str = None) -> Optional[str]:
        if env_var and env_var in os.environ:
            value = os.environ[env_var]
            print(f"✅ {name} from environment: {value}")
            return value
        
        try:
            response = ssm.get_parameter(Name=f'/app/lakehouse-agent/{name}')
            value = response['Parameter']['Value']
            print(f"✅ {name} from SSM: {value}")
            return value
        except ssm.exceptions.ParameterNotFound:
            if default:
                print(f"ℹ️  {name} using default: {default}")
                return default
            print(f"⚠️  {name} not found")
            return None
        except Exception as e:
            print(f"❌ Error getting {name}: {e}")
            return default
    
    config['s3_bucket_name'] = get_param('s3-bucket-name', 'S3_BUCKET_NAME')
    config['database_name'] = get_param('database-name', 'ATHENA_DATABASE_NAME')
    config['rls_role_arn'] = get_param('rls-role-arn', None)
    config['security_mode'] = get_param('security-mode', 'SECURITY_MODE', 'lakeformation')
    config['log_level'] = os.environ.get('LOG_LEVEL', 'INFO')
    
    if config['s3_bucket_name']:
        config['s3_output_location'] = f"s3://{config['s3_bucket_name']}/athena-results/"
    else:
        config['s3_output_location'] = None
    
    config['test_user'] = os.environ.get('TEST_USER_1', 'user001@example.com')
    config['local_development'] = os.environ.get('LOCAL_DEVELOPMENT', 'false').lower() == 'true'
    
    _config_cache = config
    return config


def validate_config(config: Dict[str, Optional[str]]) -> bool:
    required_params = [
        ('region', 'AWS Region'),
        ('s3_bucket_name', 'S3 Bucket Name'),
        ('database_name', 'Athena Database Name'),
        ('security_mode', 'Security Mode')
    ]
    
    missing = []
    for param, display_name in required_params:
        if not config.get(param):
            missing.append(display_name)
    
    if missing:
        print(f"❌ Missing required configuration: {', '.join(missing)}")
        return False
    
    if config['security_mode'] != 'lakeformation':
        print(f"❌ Invalid security mode: {config['security_mode']}")
        print("   Only 'lakeformation' is supported")
        return False
    
    return True


def get_athena_tools():
    global athena_tools
    if athena_tools is None:
        config = get_config()
        
        print("Initializing Athena tools with Lake Formation RLS...")
        print(f"  Region: {config['region']}")
        print(f"  Database: {config['database_name']}")
        print(f"  S3 Output: {config['s3_output_location']}")
        print(f"  RLS Role: {config['rls_role_arn']}")

        athena_tools = AthenaTools(
            region=config['region'],
            database_name=config['database_name'],
            s3_output_location=config['s3_output_location'],
            rls_role_arn=config['rls_role_arn']
        )

        print("✅ Athena tools initialized with Lake Formation RLS")

    return athena_tools


def get_user_id_with_fallback(context_arg: Dict[str, Any] = None) -> str:
    """Get user ID from context argument or fallback to test user."""
    config = get_config()
    user_id = None
    
    if context_arg:
        print(f"📋 Context argument received: {context_arg}")
        user_id = context_arg.get('user_id')
        if user_id:
            print(f"   Got user_id from context argument: {user_id}")
            return user_id
    
    if config['local_development']:
        user_id = config['test_user']
        print(f"⚠️  Using test user for local development: {user_id}")
        return user_id
    
    print("❌ User identity not found in request")
    return None


@mcp.tool(
    name="query_claims",
    description="Query health lakehouse data for the authenticated user with optional filters"
)
def query_claims(
    claim_status: str = None,
    claim_type: str = None,
    start_date: str = None,
    end_date: str = None,
    context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Query lakehouse data for the authenticated user."""
    print("=" * 60)
    print("🔧 TOOL INVOKED: query_claims")
    print("=" * 60)
    
    print("📥 INPUT PARAMETERS:")
    print(f"   claim_status: {claim_status}")
    print(f"   claim_type: {claim_type}")
    print(f"   start_date: {start_date}")
    print(f"   end_date: {end_date}")
    print(f"   context: {context}")
    
    try:
        user_id = get_user_id_with_fallback(context)
        print(f"👤 USER ID: {user_id}")
        
        if not user_id:
            return {"success": False, "error": "User identity not found in request"}
        
        filters = {k: v for k, v in {
            'claim_status': claim_status,
            'claim_type': claim_type,
            'start_date': start_date,
            'end_date': end_date
        }.items() if v is not None}
        
        print(f"🔍 FILTERS: {filters}")

        tools = get_athena_tools()
        result = tools.query_claims(user_id, filters if filters else None)
        
        print("📤 OUTPUT:")
        print(f"   success: {result.get('success', 'N/A')}")
        if result.get('success'):
            claims_count = len(result.get('claims', []))
            print(f"   claims_count: {claims_count}")
        else:
            print(f"   error: {result.get('error', 'N/A')}")
        
        print("=" * 60)
        return result

    except Exception as e:
        print(f"❌ ERROR in query_claims: {str(e)}")
        import traceback
        print(f"   Stack trace: {traceback.format_exc()}")
        print("=" * 60)
        return {"success": False, "error": str(e)}


@mcp.tool(
    name="get_claim_details",
    description="Get detailed information about a specific claim by ID"
)
def get_claim_details(claim_id: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Get details of a specific claim."""
    print("=" * 60)
    print("🔧 TOOL INVOKED: get_claim_details")
    print("=" * 60)
    
    print("📥 INPUT PARAMETERS:")
    print(f"   claim_id: {claim_id}")
    print(f"   context: {context}")
    
    try:
        user_id = get_user_id_with_fallback(context)
        print(f"👤 USER ID: {user_id}")
        
        if not user_id:
            return {"success": False, "error": "User identity not found in request"}
        
        tools = get_athena_tools()
        result = tools.get_claim_details(user_id, claim_id)
        
        print("📤 OUTPUT:")
        print(f"   success: {result.get('success', 'N/A')}")
        if result.get('success'):
            claim_data = result.get('claim', {})
            print(f"   claim_id: {claim_data.get('claim_id', 'N/A')}")
            print(f"   claim_status: {claim_data.get('claim_status', 'N/A')}")
        else:
            print(f"   error: {result.get('error', 'N/A')}")
        
        print("=" * 60)
        return result

    except Exception as e:
        print(f"❌ ERROR in get_claim_details: {str(e)}")
        import traceback
        print(f"   Stack trace: {traceback.format_exc()}")
        print("=" * 60)
        return {"success": False, "error": str(e)}


@mcp.tool(
    name="get_claims_summary",
    description="Get summary statistics of all claims for the authenticated user"
)
def get_claims_summary(context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Get claims summary for the user."""
    print("=" * 60)
    print("🔧 TOOL INVOKED: get_claims_summary")
    print("=" * 60)
    
    print("📥 INPUT PARAMETERS:")
    print(f"   context: {context}")
    
    try:
        user_id = get_user_id_with_fallback(context)
        print(f"👤 USER ID: {user_id}")
        
        if not user_id:
            return {"success": False, "error": "User identity not found in request"}
        
        tools = get_athena_tools()
        result = tools.get_claims_summary(user_id)
        
        print("📤 OUTPUT:")
        print(f"   success: {result.get('success', 'N/A')}")
        if result.get('success'):
            summary = result.get('summary', {})
            print(f"   total_claims: {summary.get('total_claims', 'N/A')}")
            print(f"   total_amount: {summary.get('total_amount', 'N/A')}")
            print(f"   by_status: {summary.get('by_status', 'N/A')}")
        else:
            print(f"   error: {result.get('error', 'N/A')}")
        
        print("=" * 60)
        return result

    except Exception as e:
        print(f"❌ ERROR in get_claims_summary: {str(e)}")
        import traceback
        print(f"   Stack trace: {traceback.format_exc()}")
        print("=" * 60)
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    print("\n🔍 Validating configuration...")
    
    config = get_config()
    
    if config['security_mode'] != 'lakeformation':
        print("\n❌ Error: Only Lake Formation security mode is supported!")
        print(f"   Current SECURITY_MODE: {config['security_mode']}")
        sys.exit(1)

    if not validate_config(config):
        print("\n❌ Configuration is invalid!")
        sys.exit(1)

    print("✅ Configuration validated")
    print("🔒 Lake Formation row-level security enabled")

    print(f"Starting MCP Server with Lake Formation RLS:")
    print(f"  Region: {config['region']}")
    print(f"  Database: {config['database_name']}")
    print(f"  S3 Output: {config['s3_output_location']}")
    print(f"  RLS Role: {config['rls_role_arn']}")

    mcp.run(transport="streamable-http")
