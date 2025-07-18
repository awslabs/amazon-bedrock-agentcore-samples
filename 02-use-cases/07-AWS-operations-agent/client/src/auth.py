"""
Simple AWS authentication - just SigV4 signing
"""
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

class AWSAuth:
    """Simple AWS authenticator"""
    
    def __init__(self, region: str, profile: str):
        self.region = region
        self.session = boto3.Session(profile_name=profile)
        self.credentials = self.session.get_credentials()
        
        if not self.credentials:
            raise ValueError(f"No AWS credentials found for profile: {profile}")
    
    def sign_request(self, method: str, url: str, body: str = None):
        """Sign request and return headers"""
        headers = {"Content-Type": "application/json"} if body else {}
        
        request = AWSRequest(method=method, url=url, data=body, headers=headers)
        SigV4Auth(self.credentials, "lambda", self.region).add_auth(request)
        
        return dict(request.headers)
