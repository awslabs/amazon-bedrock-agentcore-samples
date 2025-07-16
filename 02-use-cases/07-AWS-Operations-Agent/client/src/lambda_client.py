"""
Simple Lambda client - just HTTP requests to Lambda
"""
import json
import requests
from typing import Iterator, Dict, Any
from auth import AWSAuth
import config

class LambdaClient:
    """Simple client for Lambda communication"""
    
    def __init__(self, auth: AWSAuth, function_url: str):
        self.auth = auth
        self.function_url = function_url
    
    def send_message_streaming(self, payload: Dict[str, Any]) -> Iterator[str]:
        """Send message and stream response"""
        try:
            body = json.dumps(payload)
            headers = self.auth.sign_request('POST', self.function_url, body)
            
            with requests.post(
                self.function_url,
                data=body,
                headers=headers,
                stream=True,
                timeout=config.REQUEST_TIMEOUT
            ) as response:
                
                if response.status_code != 200:
                    yield f"Error: HTTP {response.status_code}: {response.text}"
                    return
                
                for chunk in response.iter_content(chunk_size=None):
                    if chunk:
                        chunk_text = chunk.decode('utf-8')
                        
                        # Parse Strands streaming format
                        try:
                            # Try to parse as JSON (Strands streaming object)
                            if chunk_text.startswith('{') and 'delta' in chunk_text:
                                chunk_data = json.loads(chunk_text)
                                
                                # Extract text from delta
                                if 'delta' in chunk_data and 'text' in chunk_data['delta']:
                                    text_content = chunk_data['delta']['text']
                                    if text_content:
                                        yield text_content
                                # Extract text from data field
                                elif 'data' in chunk_data:
                                    text_content = chunk_data['data']
                                    if text_content:
                                        yield text_content
                            else:
                                # Plain text chunk
                                yield chunk_text
                                
                        except json.JSONDecodeError:
                            # Not JSON, treat as plain text
                            yield chunk_text
                        
        except Exception as e:
            yield f"Error: {str(e)}"
    
    def call_api(self, endpoint_url: str, method: str = 'GET', data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call Lambda API endpoint"""
        try:
            body = json.dumps(data) if data else None
            headers = self.auth.sign_request(method, endpoint_url, body)
            
            if method == 'GET':
                response = requests.get(endpoint_url, headers=headers, timeout=config.TOOLS_TIMEOUT)
            elif method == 'POST':
                response = requests.post(endpoint_url, data=body, headers=headers, timeout=config.TOOLS_TIMEOUT)
            elif method == 'DELETE':
                response = requests.delete(endpoint_url, headers=headers, timeout=config.TOOLS_TIMEOUT)
            else:
                return {"error": f"Unsupported method: {method}"}
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            return {"error": str(e)}
