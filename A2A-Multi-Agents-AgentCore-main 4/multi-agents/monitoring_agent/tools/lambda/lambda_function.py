import json
import os
import boto3
import logging
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda handler for AgentCore Gateway monitoring tools
    """
    try:
        # Extract tool information from context
        tool_name = context.client_context.custom['bedrockAgentCoreToolName']
        logger.info(f"Original toolName: {tool_name}")
        
        # Handle tool name with delimiter (if present)
        delimiter = "___"
        if delimiter in tool_name:
            tool_name = tool_name[tool_name.index(delimiter) + len(delimiter):]
        logger.info(f"Converted toolName: {tool_name}")
        
        # Route to appropriate monitoring function
        if tool_name == 'list_cloudwatch_dashboards':
            return handle_list_dashboards(event)
        elif tool_name == 'fetch_cloudwatch_logs_for_service':
            return handle_fetch_logs(event)
        elif tool_name == 'get_cloudwatch_alarms_for_service':
            return handle_get_alarms(event)
        elif tool_name == 'setup_cross_account_access':
            return handle_cross_account_setup(event)
        elif tool_name == 'list_log_groups':
            return handle_list_log_groups(event)
        elif tool_name == 'analyze_log_group':
            return handle_analyze_log_group(event)
        elif tool_name == 'get_dashboard_summary':
            return handle_get_dashboard_summary(event)
        elif tool_name == 'create_incident_jira_ticket':
            return handle_create_jira_ticket(event)
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'Unknown tool: {tool_name}'})
            }
            
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Internal server error: {str(e)}'})
        }

def get_cross_account_client(service: str, account_id: Optional[str] = None, role_name: Optional[str] = None):
    """Get AWS client with optional cross-account access"""
    try:
        if account_id and role_name:
            logger.info(f"Setting up cross-account access for account {account_id} with role {role_name}")
            sts = boto3.client('sts')
            role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
            
            assumed_role = sts.assume_role(
                RoleArn=role_arn,
                RoleSessionName='MonitoringAgentLambdaSession'
            )
            credentials = assumed_role['Credentials']
            
            return boto3.client(
                service,
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken']
            )
        
        return boto3.client(service)
        
    except Exception as e:
        logger.error(f"Error creating {service} client: {str(e)}")
        raise

def handle_list_dashboards(event):
    """List all CloudWatch dashboards"""
    account_id = event.get('accountId')
    role_name = event.get('roleName')
    
    try:
        cloudwatch = get_cross_account_client('cloudwatch', account_id, role_name)
        response = cloudwatch.list_dashboards()
        
        dashboards = [
            {
                'name': dashboard['DashboardName'],
                'description': f"Dashboard in account {account_id or 'current'}"
            }
            for dashboard in response.get('DashboardEntries', [])
        ]
        
        logger.info(f"Found {len(dashboards)} dashboards")
        return {
            'statusCode': 200,
            'body': json.dumps({'dashboards': dashboards})
        }
        
    except Exception as e:
        logger.error(f"Error listing dashboards: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def handle_fetch_logs(event):
    """Fetch CloudWatch logs for a specific service"""
    service_name = event.get('serviceName')
    account_id = event.get('accountId')
    role_name = event.get('roleName')
    
    if not service_name:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'serviceName is required'})
        }
    
    try:
        logs_client = get_cross_account_client('logs', account_id, role_name)
        
        # Service to log group mapping
        service_log_groups = {
            'lambda': ['/aws/lambda/'],
            'ec2': ['/aws/ec2/', '/var/log/'],
            'rds': ['/aws/rds/'],
            'eks': ['/aws/eks/'],
            'apigateway': ['/aws/apigateway/'],
            'bedrock': ['/aws/bedrock/'],
            'vpc': ['/aws/vpc/'],
            'iam': ['/aws/iam/'],
            's3': ['/aws/s3/'],
            'cloudtrail': ['/aws/cloudtrail/'],
            'waf': ['/aws/waf/']
        }
        
        log_groups = service_log_groups.get(service_name.lower(), [f'/aws/{service_name}/'])
        
        logs = []
        start_time = int((datetime.now() - timedelta(hours=1)).timestamp() * 1000)
        
        for log_group_prefix in log_groups:
            try:
                # Find matching log groups
                paginator = logs_client.get_paginator('describe_log_groups')
                for page in paginator.paginate(logGroupNamePrefix=log_group_prefix):
                    for log_group in page['logGroups']:
                        try:
                            # Fetch recent logs
                            events = logs_client.filter_log_events(
                                logGroupName=log_group['logGroupName'],
                                startTime=start_time,
                                limit=50
                            )
                            
                            for event in events.get('events', []):
                                logs.append({
                                    'timestamp': datetime.fromtimestamp(event['timestamp']/1000).isoformat(),
                                    'message': event['message']
                                })
                                
                        except Exception as log_error:
                            logger.warning(f"Error fetching logs from {log_group['logGroupName']}: {str(log_error)}")
                            continue
                            
            except Exception as group_error:
                logger.warning(f"Error listing log groups with prefix {log_group_prefix}: {str(group_error)}")
                continue
        
        logger.info(f"Retrieved {len(logs)} log entries for service {service_name}")
        return {
            'statusCode': 200,
            'body': json.dumps({'logs': logs[:100]})  # Limit response size
        }
        
    except Exception as e:
        logger.error(f"Error fetching logs: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def handle_get_alarms(event):
    """Get CloudWatch alarms for a service"""
    service_name = event.get('serviceName')
    account_id = event.get('accountId')
    role_name = event.get('roleName')
    
    if not service_name:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'serviceName is required'})
        }
    
    try:
        cloudwatch = get_cross_account_client('cloudwatch', account_id, role_name)
        
        # Get all alarms and filter by service
        response = cloudwatch.describe_alarms()
        
        service_alarms = []
        for alarm in response.get('MetricAlarms', []):
            # Filter alarms related to the service
            if (service_name.lower() in alarm.get('AlarmName', '').lower() or
                service_name.lower() in alarm.get('Namespace', '').lower()):
                service_alarms.append({
                    'name': alarm['AlarmName'],
                    'state': alarm['StateValue']
                })
        
        logger.info(f"Found {len(service_alarms)} alarms for service {service_name}")
        return {
            'statusCode': 200,
            'body': json.dumps({'alarms': service_alarms})
        }
        
    except Exception as e:
        logger.error(f"Error getting alarms: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def handle_cross_account_setup(event):
    """Setup and verify cross-account access"""
    account_id = event.get('accountId')
    role_name = event.get('roleName')
    
    if not account_id or not role_name:
        return {
            'statusCode': 400,
            'body': json.dumps({
                'success': False,
                'message': 'Both accountId and roleName are required'
            })
        }
    
    try:
        # Test cross-account access
        test_client = get_cross_account_client('sts', account_id, role_name)
        test_client.get_caller_identity()
        
        logger.info(f"Successfully verified cross-account access for account {account_id}")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'message': f'Successfully verified access to account {account_id} with role {role_name}'
            })
        }
        
    except Exception as e:
        logger.error(f"Cross-account setup failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'message': f'Failed to setup cross-account access: {str(e)}'
            })
        }

def handle_list_log_groups(event):
    """List all CloudWatch log groups"""
    account_id = event.get('accountId')
    role_name = event.get('roleName')
    
    try:
        logs_client = get_cross_account_client('logs', account_id, role_name)
        
        log_groups = []
        paginator = logs_client.get_paginator('describe_log_groups')
        
        for page in paginator.paginate():
            for log_group in page['logGroups']:
                log_groups.append({
                    'name': log_group['logGroupName'],
                    'arn': log_group.get('arn', '')
                })
        
        logger.info(f"Found {len(log_groups)} log groups")
        return {
            'statusCode': 200,
            'body': json.dumps({'logGroups': log_groups[:100]})  # Limit response
        }
        
    except Exception as e:
        logger.error(f"Error listing log groups: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def handle_analyze_log_group(event):
    """Analyze a specific log group"""
    log_group_name = event.get('logGroupName')
    account_id = event.get('accountId')
    role_name = event.get('roleName')
    
    if not log_group_name:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'logGroupName is required'})
        }
    
    try:
        logs_client = get_cross_account_client('logs', account_id, role_name)
        
        # Get log events from the past hour
        start_time = int((datetime.now() - timedelta(hours=1)).timestamp() * 1000)
        
        events = logs_client.filter_log_events(
            logGroupName=log_group_name,
            startTime=start_time,
            limit=1000
        )
        
        # Analyze the events
        total_events = len(events.get('events', []))
        error_count = 0
        
        for event in events.get('events', []):
            message = event['message'].lower()
            if any(keyword in message for keyword in ['error', 'fail', 'exception', 'critical']):
                error_count += 1
        
        analysis = {
            'summary': f'Analyzed {total_events} log events from the past hour',
            'errorCount': error_count
        }
        
        logger.info(f"Analyzed log group {log_group_name}: {total_events} events, {error_count} errors")
        return {
            'statusCode': 200,
            'body': json.dumps({'analysis': analysis})
        }
        
    except Exception as e:
        logger.error(f"Error analyzing log group: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def handle_get_dashboard_summary(event):
    """Get summary of a specific dashboard"""
    dashboard_name = event.get('dashboardName')
    account_id = event.get('accountId')
    role_name = event.get('roleName')
    
    if not dashboard_name:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'dashboardName is required'})
        }
    
    try:
        cloudwatch = get_cross_account_client('cloudwatch', account_id, role_name)
        
        # Get dashboard details
        cloudwatch.get_dashboard(DashboardName=dashboard_name)
        
        dashboard = {
            'name': dashboard_name,
            'description': f"Dashboard configuration retrieved from account {account_id or 'current'}"
        }
        
        logger.info(f"Retrieved dashboard summary for {dashboard_name}")
        return {
            'statusCode': 200,
            'body': json.dumps({'dashboard': dashboard})
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

# Get Jira configuration from environment variables
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")
JIRA_USERNAME = os.environ.get("JIRA_USERNAME") 
JIRA_INSTANCE_URL = os.environ.get("JIRA_INSTANCE_URL")
JIRA_CLOUD = os.environ.get("JIRA_CLOUD", "True").lower() == "true"
DEFAULT_PROJECT_KEY = os.environ.get("PROJECT_KEY", "AIRT")

class JiraAPIWrapper:
    def __init__(self, username=None, api_token=None, instance_url=None, is_cloud=True):
        self.username = username or JIRA_USERNAME
        self.api_token = api_token or JIRA_API_TOKEN
        self.instance_url = instance_url or JIRA_INSTANCE_URL
        if self.instance_url:
            self.instance_url = self.instance_url.rstrip('/')
        self.is_cloud = is_cloud if is_cloud is not None else JIRA_CLOUD
        
        logger.info(f"JiraAPIWrapper initialized with:")
        logger.info(f"  - Username: {self.username}")
        logger.info(f"  - Instance URL: {self.instance_url}")
        logger.info(f"  - Cloud: {self.is_cloud}")
        
    def issue_create(self, fields_json):
        """Creates a Jira issue using the Jira REST API."""
        # Validate required attributes
        if not self.username:
            raise ValueError("JIRA_USERNAME is not set")
        if not self.api_token:
            raise ValueError("JIRA_API_TOKEN is not set")
        if not self.instance_url:
            raise ValueError("JIRA_INSTANCE_URL is not set")
        
        # Set up auth and headers
        auth = (self.username, self.api_token)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # API endpoint for issue creation - using API v3 for Cloud
        url = f"{self.instance_url}/rest/api/3/issue"
        
        logger.info(f"Creating issue at: {url}")
        
        # Parse the JSON to extract project key for logging
        fields = json.loads(fields_json)
        if "fields" in fields and "project" in fields["fields"]:
            logger.info(f"Creating issue in project: {fields['fields']['project']['key']}")
            logger.info(f"Issue summary: {fields['fields']['summary']}")
        
        # Make the API request
        response = requests.post(url, auth=auth, headers=headers, data=fields_json)
        
        # Check response status
        if response.status_code == 201:
            return response.json()
        else:
            logger.error(f"Error: {response.status_code} - {response.text}")
            raise Exception(f"Failed to create issue: {response.text}")

def handle_create_jira_ticket(event):
    """
    Creates a new issue in Jira with the specified details.
    """
    summary = event.get("summary")
    description = event.get("description")
    
    if not summary or not description:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'summary and description are required'})
        }
    
    try:
        # Use project key from environment variables
        project_key = DEFAULT_PROJECT_KEY
        logger.info(f"Creating Jira issue for project: {project_key}")
        
        # Create Jira API wrapper
        jira = JiraAPIWrapper()
        
        # Create issue fields - formatted for Jira Cloud API v3
        issue_fields = {
            "fields": {
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": description
                                }
                            ]
                        }
                    ]
                },
                "issuetype": {"name": "Task"},
                "project": {"key": project_key}
            }
        }
        
        # Convert to JSON
        issue_fields_json = json.dumps(issue_fields)
        logger.info(f"Sending JSON: {issue_fields_json}")
        
        # Create the issue
        result = jira.issue_create(issue_fields_json)
        logger.info(f"CREATED THE JIRA TICKET! Check your JIRA dashboard.")
        
        # Return success result
        return {
            "statusCode": 200,
            "body": json.dumps({
                "success": True,
                "message": "Jira issue created successfully",
                "issue_key": result.get("key"),
                "issue_id": result.get("id"),
                "issue_url": f"{jira.instance_url}/browse/{result.get('key')}",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        }
        
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        return {
            "statusCode": 500, 
            "body": json.dumps({
                "error": f"Error creating Jira issue: {str(e)}"
            })
        }