# Plant care Lambda code - uses Nova Lite to provide care recommendations

import json, boto3
def lambda_handler(event, context):
    try:
        plant_name = event.get('plant_name', 'unknown')
        health_status = event.get('health_status', 'healthy')
        
        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
        prompt = f"Provide care advice for {plant_name} with status: {health_status}"
        
        response = bedrock.converse(
            modelId="us.amazon.nova-lite-v1:0",
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"temperature": 0.1, "maxTokens": 1000}
        )
        
        return {'statusCode': 200, 'body': json.dumps({
            'expert_advice': response['output']['message']['content'][0]['text']
        })}
    except Exception as e:
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
