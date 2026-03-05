import json
import os
import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])


def lambda_handler(event, context):
    print(f"Received {len(event['Records'])} messages")

    for record in event["Records"]:
        try:
            message = json.loads(record["body"])
            table.put_item(Item=message)
            print(f"Recorded usage: {message['id']} - {message['total_tokens']} tokens")
        except Exception as e:
            print(f"Error processing message: {str(e)}")
            raise

    return {"statusCode": 200, "body": "Success"}
