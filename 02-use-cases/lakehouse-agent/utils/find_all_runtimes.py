#!/usr/bin/env python3
"""
Find All AgentCore Runtimes

This script lists all AgentCore runtimes in your account and their CloudWatch logs.
"""

import boto3
from datetime import datetime

def main():
    print("=" * 80)
    print("Find All AgentCore Runtimes")
    print("=" * 80)
    
    session = boto3.Session()
    region = session.region_name
    
    print(f"\n📍 Region: {region}")
    
    # List all agent runtimes
    print(f"\n🔍 Searching for AgentCore Runtimes...")
    try:
        client = boto3.client('bedrock-agentcore-control', region_name=region)
        
        response = client.list_agent_runtimes()
        runtimes = response.get('agentRuntimeSummaries', [])
        
        if not runtimes:
            print(f"   ❌ No AgentCore runtimes found in {region}")
            print(f"\n💡 To deploy the lakehouse agent:")
            print(f"   python lakehouse-agent/deploy_lakehouse_agent.py")
            return
        
        print(f"   ✅ Found {len(runtimes)} runtime(s):")
        
        for i, runtime_summary in enumerate(runtimes, 1):
            name = runtime_summary.get('agentRuntimeName', 'unknown')
            arn = runtime_summary.get('agentRuntimeArn', 'unknown')
            status = runtime_summary.get('status', 'unknown')
            updated = runtime_summary.get('updatedAt', 'unknown')
            
            print(f"\n   {i}. {name}")
            print(f"      ARN: {arn}")
            print(f"      Status: {status}")
            print(f"      Updated: {updated}")
            
            # Get detailed runtime info
            try:
                detail_response = client.get_agent_runtime(agentRuntimeArn=arn)
                runtime = detail_response['agentRuntime']
                
                # Check auth configuration
                if 'authorizerConfiguration' in runtime:
                    auth_config = runtime['authorizerConfiguration']
                    if 'customJWTAuthorizer' in auth_config:
                        jwt_config = auth_config['customJWTAuthorizer']
                        print(f"      Auth: JWT")
                        print(f"         Discovery URL: {jwt_config.get('discoveryUrl')}")
                        print(f"         Allowed Clients: {jwt_config.get('allowedClients')}")
                    else:
                        print(f"      Auth: IAM SigV4")
                else:
                    print(f"      Auth: IAM SigV4 (default)")
                
                # Extract runtime ID for log search
                runtime_id = arn.split('/')[-1]
                
                # Search for CloudWatch logs
                print(f"\n      🔍 Searching for CloudWatch logs...")
                logs = boto3.client('logs', region_name=region)
                
                # Try different log group patterns
                log_patterns = [
                    f"/aws/bedrock-agentcore/runtime/{runtime_id}",
                    f"/aws/bedrock-agentcore/runtime/{name}",
                    f"/aws/bedrock-agentcore/{runtime_id}",
                    f"/aws/agentcore/runtime/{runtime_id}",
                ]
                
                found_logs = False
                for pattern in log_patterns:
                    try:
                        log_response = logs.describe_log_groups(
                            logGroupNamePrefix=pattern,
                            limit=1
                        )
                        
                        if log_response.get('logGroups'):
                            log_group = log_response['logGroups'][0]
                            log_group_name = log_group['logGroupName']
                            size_mb = log_group.get('storedBytes', 0) / (1024 * 1024)
                            
                            print(f"      ✅ Log Group: {log_group_name}")
                            print(f"         Size: {size_mb:.2f} MB")
                            
                            # Check for recent log streams
                            streams_response = logs.describe_log_streams(
                                logGroupName=log_group_name,
                                orderBy='LastEventTime',
                                descending=True,
                                limit=3
                            )
                            
                            streams = streams_response.get('logStreams', [])
                            if streams:
                                print(f"         Recent streams:")
                                for stream in streams:
                                    stream_name = stream['logStreamName']
                                    last_event = stream.get('lastEventTimestamp')
                                    if last_event:
                                        last_event_date = datetime.fromtimestamp(last_event / 1000).strftime('%Y-%m-%d %H:%M:%S')
                                        print(f"            - {stream_name} (last: {last_event_date})")
                            else:
                                print(f"         ⚠️  No log streams (not invoked yet)")
                            
                            found_logs = True
                            break
                    except Exception:
                        continue
                
                if not found_logs:
                    print(f"      ⚠️  No CloudWatch logs found")
                    print(f"         Logs are created on first invocation")
                    print(f"         Expected log group: /aws/bedrock-agentcore/runtime/{runtime_id}")
                
            except Exception as e:
                print(f"      ⚠️  Error getting runtime details: {e}")
        
        # Provide next steps
        print(f"\n" + "=" * 80)
        print(f"Next Steps")
        print(f"=" * 80)
        
        print(f"\n📋 To view logs for a runtime:")
        print(f"   1. Note the runtime ARN from above")
        print(f"   2. Go to CloudWatch Console > Log groups")
        print(f"   3. Search for the log group name")
        print(f"   4. Or use AWS CLI:")
        print(f"      aws logs tail '/aws/bedrock-agentcore/runtime/<runtime-id>' --follow")
        
        print(f"\n📋 To invoke a runtime and generate logs:")
        print(f"   1. Use the Streamlit UI: streamlit run streamlit-ui/streamlit_app.py")
        print(f"   2. Or use boto3/requests to invoke the runtime")
        
        print(f"\n📋 To store runtime ARN in SSM (for scripts to use):")
        print(f"   aws ssm put-parameter \\")
        print(f"       --name '/app/lakehouse-agent/agent-runtime-arn' \\")
        print(f"       --value '<runtime-arn>' \\")
        print(f"       --type String \\")
        print(f"       --overwrite")
        
    except Exception as e:
        print(f"   ❌ Error listing runtimes: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
