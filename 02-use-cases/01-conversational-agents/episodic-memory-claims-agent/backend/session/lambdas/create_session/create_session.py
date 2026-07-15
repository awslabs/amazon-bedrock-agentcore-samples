import json
import boto3
import os
import uuid
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])


def handler(event, context):
    try:
        # Extract user info from Cognito authorizer
        claims = event['requestContext']['authorizer']['claims']
        user_id = claims.get('sub')  # Cognito UUID
        email = claims.get('email', '')
        actor_id = claims.get('custom:actor_id', '')  # PH-* policyholder ID

        # Parse request body
        body = json.loads(event['body']) if event.get('body') else {}

        # Generate session ID (timestamp-based for sort order)
        timestamp = datetime.utcnow()
        session_id = f"{timestamp.strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}"

        session_title = body.get('session_title', 'New conversation')

        session_item = {
            'user_id': user_id,
            'session_id': session_id,
            'actor_id': actor_id,  # PH-* ID for AgentCore Memory namespacing
            'user_email': email,
            'session_title': session_title,
            'created_at': timestamp.isoformat(),
            'updated_at': timestamp.isoformat(),
        }

        table.put_item(Item=session_item)

        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': True,
            },
            'body': json.dumps({'message': 'Session created', 'session': session_item}),
        }

    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Internal server error'}),
        }
