import json
import boto3
import os

TABLE_NAME = os.environ['TABLE_NAME']

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)


def handler(event, context):
    try:
        actor_id = (event.get('queryStringParameters') or {}).get('actorId', '')

        items = table.scan().get('Items', [])

        rows = [
            {
                'session_id': i.get('session_id'),
                'title': i.get('session_title'),
                'created_at': i.get('created_at'),
                'actor_id': i.get('actor_id'),
            }
            for i in items
            if not actor_id or i.get('actor_id') == actor_id
        ]
        rows.sort(key=lambda r: r.get('created_at') or '', reverse=True)

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'sessions': rows, 'count': len(rows)}),
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': str(e)}),
        }
