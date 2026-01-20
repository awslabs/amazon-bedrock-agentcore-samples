import json
import boto3
from boto3.dynamodb.conditions import Attr, Key
from decimal import Decimal

def lambda_handler(event, context):
    # ---------------------------------------------------------
    # 1. Parse Tool Name (Bedrock Agent Standard)
    # ---------------------------------------------------------
    toolName = context.client_context.custom['bedrockAgentCoreToolName']
    print(f"Original toolName: {toolName}")
    print(f"Event: {event}")
    
    # Handle delimiter if present (e.g., "AgentName___toolName")
    delimiter = "___"
    if delimiter in toolName:
        toolName = toolName[toolName.index(delimiter) + len(delimiter):]
    
    print(f"Converted toolName: {toolName}")
    
    # ---------------------------------------------------------
    # 2. Initialize DynamoDB
    # ---------------------------------------------------------
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('agentcore-demo-projects-budget') # UPDATED TABLE NAME
    
    try:
        # -----------------------------------------------------
        # Tool: Get Specific Project
        # Input: projectId (e.g., "PROJ-001")
        # -----------------------------------------------------
        if toolName == 'get_project':
            project_id = event.get('projectId')
            if not project_id:
                return {'statusCode': 400, 'body': json.dumps({'error': 'projectId required'})}
            
            response = table.get_item(Key={'projectId': project_id})
            
            if 'Item' not in response:
                return {'statusCode': 404, 'body': json.dumps({'error': f'Project {project_id} not found'})}
            
            return {'statusCode': 200, 'body': json.dumps(response['Item'], default=str)}
        
        # -----------------------------------------------------
        # Tool: List Projects by Department
        # Input: department (e.g., "Engineering", "Marketing")
        # -----------------------------------------------------
        elif toolName == 'list_department_projects':
            department = event.get('department')
            if not department:
                return {'statusCode': 400, 'body': json.dumps({'error': 'department required'})}
            
            # Scan with Filter
            response = table.scan(FilterExpression=Attr('department').eq(department))
            
            result = {
                'department': department,
                'count': len(response['Items']),
                'projects': response['Items']
            }
            return {'statusCode': 200, 'body': json.dumps(result, default=str)}
        
        # -----------------------------------------------------
        # Tool: Filter by Budget Range
        # Input: min_budget, max_budget (optional)
        # -----------------------------------------------------
        elif toolName == 'filter_by_budget':
            min_budget = event.get('min_budget')
            max_budget = event.get('max_budget')
            
            # Build Filter Expression
            filter_expression = None
            
            if min_budget and max_budget:
                filter_expression = Attr('totalBudget').between(int(min_budget), int(max_budget))
            elif min_budget:
                filter_expression = Attr('totalBudget').gte(int(min_budget))
            elif max_budget:
                filter_expression = Attr('totalBudget').lte(int(max_budget))
            
            # Execute Scan
            if filter_expression:
                response = table.scan(FilterExpression=filter_expression)
            else:
                # If no parameters, return all (or you could return an error)
                response = table.scan()

            result = {
                'criteria': {'min': min_budget, 'max': max_budget},
                'count': len(response['Items']),
                'projects': response['Items']
            }
            return {'statusCode': 200, 'body': json.dumps(result, default=str)}

        # -----------------------------------------------------
        # Tool: Check Status (e.g., "At Risk", "Over Budget")
        # Input: status
        # -----------------------------------------------------
        elif toolName == 'list_by_status':
            status = event.get('status') # e.g., "At Risk", "Active"
            if not status:
                return {'statusCode': 400, 'body': json.dumps({'error': 'status required'})}

            response = table.scan(FilterExpression=Attr('status').eq(status))
            
            result = {
                'status': status,
                'count': len(response['Items']),
                'projects': response['Items']
            }
            return {'statusCode': 200, 'body': json.dumps(result, default=str)}

        # -----------------------------------------------------
        # Tool: List All Projects
        # -----------------------------------------------------
        elif toolName == 'list_all_projects':
            response = table.scan()
            result = {
                'count': len(response['Items']),
                'projects': response['Items']
            }
            return {'statusCode': 200, 'body': json.dumps(result, default=str)}
        
        else:
            return {'statusCode': 400, 'body': json.dumps({'error': f'Unknown tool: {toolName}'})}
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}