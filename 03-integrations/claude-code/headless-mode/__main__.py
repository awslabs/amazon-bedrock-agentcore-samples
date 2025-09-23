"""
Module entry point for Claude Code Agent.
This file enables running the agent as a module with python -m claude_code_agent
"""

import os
import sys
import json
from flask import Flask, request, jsonify
from claude_code_agent import handler

# Create Flask app for HTTP server
app = Flask(__name__)

# Get port from environment or default to 8080
PORT = int(os.environ.get("PORT", "8080"))

@app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "claude-code-agent"})

@app.route("/invocations", methods=["POST"])
def invoke():
    """Main invocation endpoint for AgentCore"""
    try:
        # Get request data
        if request.is_json:
            payload = request.get_json()
        else:
            # Try to parse as JSON even if content-type is not set
            payload = json.loads(request.data.decode('utf-8'))
        
        # Call the handler
        result = handler(payload, {})
        
        # Return the result
        return jsonify(result)
    
    except Exception as e:
        error_response = {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }
        return jsonify(error_response), 500

@app.route("/invoke", methods=["POST"])
def invoke_alt():
    """Alternative invocation endpoint"""
    return invoke()

if __name__ == "__main__":
    # Run the Flask app
    print(f"Starting Claude Code Agent on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False)
