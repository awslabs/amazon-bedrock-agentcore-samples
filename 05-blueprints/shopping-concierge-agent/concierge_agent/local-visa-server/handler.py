"""
Lambda handler for Visa Proxy Server

Wraps the Flask application using Mangum adapter to make it compatible with AWS Lambda.
"""

import json
import traceback

# Initialize variables at module level
_handler = None
_init_error = None

# Try to import and initialize Flask app
try:
    from mangum import Mangum
    from asgiref.wsgi import WsgiToAsgi
    from server import app

    # Convert Flask WSGI app to ASGI for Mangum compatibility
    asgi_app = WsgiToAsgi(app)

    # Create Lambda handler by wrapping ASGI app with Mangum
    _handler = Mangum(asgi_app, lifespan="off")
    print("✅ Lambda handler initialized successfully")

except Exception as e:
    _init_error = str(e)
    print(f"❌ FATAL ERROR loading handler: {_init_error}")
    print(traceback.format_exc())


def handler(event, context):
    """
    Lambda handler with error catching and CORS support
    Must be defined at module level for Lambda to find it
    """
    # Check if initialization failed
    if _handler is None:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
            },
            "body": json.dumps(
                {
                    "error": "Lambda initialization failed",
                    "message": _init_error or "Unknown initialization error",
                }
            ),
        }

    # Normal request handling
    try:
        print(f"Lambda invoked with event: {json.dumps(event)}")
        response = _handler(event, context)

        # Ensure CORS headers are present in response
        if "headers" not in response:
            response["headers"] = {}

        # Add CORS headers if not already present (Flask-CORS should add them)
        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
        for header, value in cors_headers.items():
            if header not in response["headers"]:
                response["headers"][header] = value

        print(f"Lambda response: {json.dumps(response)}")
        return response

    except Exception as e:
        print(f"ERROR in Lambda handler: {str(e)}")
        print(traceback.format_exc())

        # Return error response with CORS headers
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
            },
            "body": json.dumps({"error": "Internal server error", "message": str(e)}),
        }
