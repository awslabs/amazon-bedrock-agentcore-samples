# Web search Lambda code - uses Tavily search + Nova Pro with LLM fallback

import json
import boto3
import urllib3

def lambda_handler(event, context):
    try:
        print(f"Received event: {json.dumps(event, default=str)}")
        
        plant_name = event.get('plant_name', 'unknown plant')
        health_status = event.get('health_status', '')
        
        # Try Tavily search first
        try:
            # Get Tavily API key from environment
            api_key = os.environ.get('TAVILY_API_KEY')
            
            
            if health_status:
                query = f"{plant_name} plant disease {health_status} treatment care"
            else:
                query = f"{plant_name} plant care fertilizer growing tips"
            
            print(f"🔍 Searching Tavily for: {query}")
            
            # Use urllib3 for Tavily API
            http = urllib3.PoolManager()
            
            search_data = {
                'api_key': api_key,
                'query': query,
                'max_results': 3
            }
            
            response = http.request(
                'POST',
                'https://api.tavily.com/search',
                body=json.dumps(search_data),
                headers={'Content-Type': 'application/json'},
                timeout=15
            )
            
            if response.status == 200:
                search_result = json.loads(response.data.decode('utf-8'))
                raw_results = search_result.get('results', [])
                
                if raw_results:
                    search_text = "\\n\\n".join([f"**{r.get('title', 'No title')}**\\n{r.get('content', 'No content')}" for r in raw_results])
                    
                    prompt = f"""Based on web search results about {plant_name} plant care:

{search_text}

Plant: {plant_name}
Health Issues: {health_status or 'No specific issues'}

Provide comprehensive advice including:
1) Disease treatment (if applicable)
2) Fertilizer recommendations 
3) Care tips and best practices
4) Prevention strategies
5) Recovery timeline (if diseased)"""
                    
                    print("✅ Using Tavily search results")
                    use_tavily = True
                else:
                    raise Exception("No search results from Tavily")
            else:
                raise Exception(f"Tavily API returned status {response.status}")
                
        except Exception as e:
            print(f"⚠️ Tavily failed: {e}, falling back to Nova")
            use_tavily = False
            
            if health_status:
                prompt = f"""Provide comprehensive plant care advice for {plant_name} with health issues: {health_status}

Include detailed information on:
1) Specific treatment for {health_status}
2) Recommended fertilizers and nutrients
3) Watering and care schedule
4) Prevention strategies
5) Expected recovery timeline
6) Signs of improvement to watch for"""
            else:
                prompt = f"""Provide comprehensive care guide for {plant_name}:

1) Optimal growing conditions (light, temperature, humidity)
2) Fertilizer schedule and nutrient requirements
3) Watering frequency and techniques
4) Common problems and solutions
5) Seasonal care variations
6) Harvesting tips (if applicable)
7) Companion planting suggestions"""

        # Use Nova to process the prompt
        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
        
        response = bedrock.converse(
            modelId="us.amazon.nova-pro-v1:0",
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"temperature": 0.1, "maxTokens": 1500}
        )
        
        web_advice = response['output']['message']['content'][0]['text']
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'web_search_results': web_advice,
                'plant_name': plant_name,
                'health_status': health_status,
                'search_source': 'tavily+nova' if use_tavily else 'nova_only'
            })
        }
        
    except Exception as e:
        print(f"Lambda error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'web_search_results': f"Search failed: {str(e)}"
            })
        }
