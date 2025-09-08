# Lambda function code (Web search - bedrock model as fallback)
import json
import requests
import boto3
import os

model_id="us.amazon.nova-pro-v1:0"
region = 'us-east-1'
bedrock = boto3.client('bedrock-runtime', region_name=region)

def fallback_to_bedrock(query):
    """Fallback to Bedrock when Tavily is unavailable"""
    try:
        system_prompt = """You are a web search assistant. Provide comprehensive information based on your knowledge.
                    
            Focus on:
            - Accurate, up-to-date information
            - Multiple perspectives when relevant
            - Practical, actionable advice
            - Clear, well-structured responses
            
            Query: Provide detailed information about the user's query."""
    
        payload = {
            "schemaVersion": "messages-v1",
            "inferenceConfig": {
                "max_new_tokens": 2000
            },
            "system": [{"text": system_prompt}],
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": query}]
                }
            ]
        }
        
        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps(payload)
        )
        
        response_body = json.loads(response['body'].read())
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'source': 'bedrock',
                'results': {
                    'answer': response_body['output']['message']['content'][0]['text'],
                    'model': model_id
                }
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'Bedrock fallback error: {str(e)}'
            })
        }

def lambda_handler(event, context):
    """Lambda function for web search with Tavily/Bedrock fallback"""
    
    # Get query from event
    query = event.get('query', '')
    if not query:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Query parameter required'})
        }
    
    # Get Tavily API key from environment
    tavily_api_key = os.environ.get('TAVILY_API_KEY')
    
    if tavily_api_key:
        # Use Tavily API
        try:
            response = requests.post(
                'https://api.tavily.com/search',
                headers={'Content-Type': 'application/json'},
                json={
                    'api_key': tavily_api_key,
                    'query': query,
                    'search_depth': 'advanced',
                    'include_answer': True,
                    'max_results': 5
                },
                timeout=30
            )
            
            if response.status_code == 200:
                search_results = response.json()
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'source': 'tavily',
                        'results': search_results
                    })
                }
            else:
                # Fallback to Bedrock if Tavily fails
                return fallback_to_bedrock(query)
                
        except Exception as e:
            # Fallback to Bedrock if Tavily errors
            return fallback_to_bedrock(query)
    
    else:
        # No Tavily API key - use Bedrock directly
        return fallback_to_bedrock(query)
