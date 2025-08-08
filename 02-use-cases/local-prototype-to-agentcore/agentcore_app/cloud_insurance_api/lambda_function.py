"""
AWS Lambda handler for the Insurance API
"""
import os
import sys

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Import the FastAPI app (now a local import)
from local_insurance_api.app import app

# Import Mangum for AWS Lambda integration
from mangum import Mangum

# Create the handler
handler = Mangum(app)