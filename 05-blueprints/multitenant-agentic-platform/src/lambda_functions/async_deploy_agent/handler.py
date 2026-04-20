import json
import os
import boto3

lambda_client = boto3.client("lambda")


def lambda_handler(event, context):
    try:
        # Get tenantId and config from query parameters or body
        query_params = event.get("queryStringParameters") or {}
        tenant_id = query_params.get("tenantId")
        config = {}
        template = {}
        tools = {}

        raw_body = event.get("body")
        if raw_body:
            body = json.loads(raw_body) if isinstance(raw_body, str) else raw_body
            if not tenant_id:
                tenant_id = body.get("tenantId")
            config = body.get("config", {})
            template = body.get("template", {})
            tools = body.get("tools", {})

        if not tenant_id:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps({"error": "tenantId is required"}),
            }

        # Prepare payload with config, template, and tools
        payload = {
            "tenantId": tenant_id,
            "config": config,
            "template": template,
            "tools": tools,
        }

        print(f"Deploying agent for tenant {tenant_id}")
        print(f"Config: {config}")
        print(f"Template: {template}")
        print(f"Tools: {tools}")

        # Invoke the build-deploy lambda asynchronously
        lambda_client.invoke(
            FunctionName=os.environ["BUILD_DEPLOY_FUNCTION_NAME"],
            InvocationType="Event",  # Async invocation
            Payload=json.dumps(payload),
        )

        return {
            "statusCode": 202,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(
                {
                    "message": "Agent deployment started",
                    "tenantId": tenant_id,
                    "config": config,
                    "template": template,
                    "tools": tools,
                    "status": "deploying",
                    "note": "Deployment will take 1-2 minutes. Check token usage table for completion.",
                }
            ),
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"error": str(e)}),
        }
