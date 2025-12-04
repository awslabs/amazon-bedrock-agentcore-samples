#!/usr/bin/env python3
import asyncio
import websockets
import sys
import json
import argparse
import pdb
import logging
import os

# Import from root-level websocket_helpers
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from websocket_helpers import prepare_connection

logging.basicConfig(level=logging.DEBUG)
websockets_logger = logging.getLogger('websockets')
websockets_logger.setLevel(logging.DEBUG)

async def test_websocket(runtime_arn, session_id, auth_type='headers', invalid_signature=False):
    uri, headers = prepare_connection(runtime_arn, auth_type, session_id, invalid_signature)

    try:
        async with websockets.connect(uri, additional_headers=headers, open_timeout=130, ping_interval=20, ping_timeout=10) as websocket:
            print("WebSocket connected")

            test_message = {"msg": "Hello, World! Echo Test"}
            await websocket.send(json.dumps(test_message))
            print(f"Sent: {test_message}")

            response = await websocket.recv()
            print(f"Received: {response}")

            if json.loads(response) == test_message:
                print("Echo test PASSED")
                return True
            else:
                print("Echo test FAILED")
                return False

    except websockets.exceptions.InvalidStatus as e:
        # https://websockets.readthedocs.io/en/stable/reference/exceptions.html#websockets.exceptions.InvalidStatus
        print(f"WebSocket handshake failed with status code: {e.response.status_code}")
        print(f"Response headers: {e.response.headers}")
        print(f"Response body: {e.response.body.decode()}")
        return False
    except Exception as e:
        print("Error: " + str(e))
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='WebSocket echo client')
    parser.add_argument('--runtime-arn', required=True, help='Runtime ARN for the WebSocket connection')
    parser.add_argument('--session-id', help='Session ID (auto-generated if not provided)')
    parser.add_argument('--auth-type', choices=['headers', 'query', 'oauth'], default='headers', 
                       help='Authentication type: headers (SigV4 headers), query (SigV4 query parameters), or oauth (Bearer token)')
    parser.add_argument('--invalid-signature', action='store_true', 
                       help='Send invalid signature (only works with query auth type)')
    args = parser.parse_args()
    
    success = asyncio.run(test_websocket(args.runtime_arn, args.session_id, args.auth_type, args.invalid_signature))
    sys.exit(0 if success else 1)
