import json
import boto3
import os
from boto3.dynamodb.conditions import Key
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def handler(event, context):
    try:
        claims = event['requestContext']['authorizer']['claims']
        user_id = claims.get('sub')

        response = table.query(
            KeyConditionExpression=Key('user_id').eq(user_id),
            ScanIndexForward=False,  # Newest first
        )

        sessions = response.get('Items', [])

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': os.environ.get('ALLOWED_ORIGIN', '*'),
                'Access-Control-Allow-Credentials': True,
            },
            'body': json.dumps({'sessions': sessions, 'count': len(sessions)}, cls=DecimalEncoder),
        }

    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': os.environ.get('ALLOWED_ORIGIN', '*')},
            'body': json.dumps({'error': 'Internal server error'}),
        }
